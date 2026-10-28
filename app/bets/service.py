from __future__ import annotations

import logging
import math
import secrets
import threading
import time
from collections.abc import Iterable
from hashlib import sha256
from itertools import combinations, islice

from sqlalchemy import func, text

from ..core.numbers import (
    clamp_int,
    parse_int,
)
from ..draws.statistics import all_draw_numbers
from ..extensions import db
from ..models import Draw, GeneratedBet
from .contracts import ConfirmationResult
from .criteria import (
    MAX_BET_NUMBERS,
    MIN_BET_NUMBERS,
    GenerationCriteria,
)

_log = logging.getLogger(__name__)
MAX_SAVED_BETS = math.comb(MAX_BET_NUMBERS, MIN_BET_NUMBERS)
MAX_RECENT_GENERATIONS = 20
MAX_RECENT_BETS_PER_GENERATION = 200
_RNG = secrets.SystemRandom()
_GENERATION_ID_SEQUENCE = "generated_bets_generation_id_seq"
# A geração é CPU pura e segura o worker inteiro: filtros severos com apostas de
# 20 dezenas custam vários segundos, e três pedidos simultâneos passavam do
# timeout de 60 s do gunicorn. O orçamento de tempo limita cada pedido e as
# vagas limitam quantos rodam ao mesmo tempo em cada processo, deixando threads
# livres para o resto do sistema.
GENERATION_TIME_BUDGET_SECONDS = 3.0
MAX_CONCURRENT_GENERATIONS = 2
_GENERATION_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_GENERATIONS)


def _passes_generation_filters(numbers: list[int], filters: dict | None) -> bool:
    if not filters:
        return True
    return GenerationCriteria.from_mapping(filters, default_amount=1).matches_candidate(numbers)


def _diversity_score(numbers: list[int], existing_candidates: list[list[int]]) -> float:
    if not existing_candidates:
        return 1.0
    max_overlap = max(len(set(numbers) & set(candidate)) for candidate in existing_candidates)
    return max(0.0, 1.0 - (max_overlap / max(len(numbers), 1)))


def _passes_diversity_control(numbers: list[int], created_numbers: list[list[int]]) -> bool:
    if not created_numbers:
        return True
    # Evita apostas praticamente iguais dentro da mesma geração.
    # Para apostas de 6 dezenas, no máximo 4 números podem se repetir entre duas apostas.
    max_allowed_overlap = max(0, len(numbers) - 2)
    current = set(numbers)
    return all(
        len(current & set(candidate)) <= max_allowed_overlap for candidate in created_numbers
    )


def _secure_random_candidate(quantity: int) -> list[int]:
    return sorted(_RNG.sample(range(1, 61), quantity))


def _batch_fingerprint(quantity: int, numbers_csv: Iterable[str], contest: int | None = None) -> str:
    """Deriva a identidade estável da confirmação já normalizada.

    O schema legado não possui uma coluna de token de idempotência. A própria
    confirmação normalizada é, portanto, a identidade do lote: repetir o POST
    da mesma confirmação devolve o lote já persistido, inclusive depois de um
    retry que atravesse outro worker do Gunicorn. Uma chave explícita pode ser
    acrescentada apenas com um contrato persistido próprio, se houver consumidor.
    """
    payload = "\x1f".join([str(quantity), str(contest), *sorted(set(numbers_csv))])
    return sha256(payload.encode("utf-8")).hexdigest()


def _lock_batch_fingerprint(fingerprint: str) -> None:
    """Serializa confirmações iguais enquanto a transação atual estiver aberta."""
    get_bind = getattr(db.session, "get_bind", None)
    bind = get_bind() if get_bind is not None else None
    if bind is not None and bind.dialect.name == "postgresql":
        db.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:fingerprint, 0))"),
            {"fingerprint": fingerprint},
        )


def _find_existing_batch(quantity: int, numbers_csv: list[str], contest: int | None = None) -> int | None:
    """Encontra exatamente o lote confirmado, sem materializar o histórico."""
    if not numbers_csv or not hasattr(db.session, "query"):
        return None
    expected_count = len(numbers_csv)
    candidates = (
        db.session.query(GeneratedBet.generation_id)
        .filter(
            GeneratedBet.generation_id.isnot(None),
            GeneratedBet.quantity == quantity,
            GeneratedBet.contest == contest,
            GeneratedBet.numbers_csv.in_(numbers_csv),
        )
        .group_by(GeneratedBet.generation_id)
        .having(func.count(GeneratedBet.id) == expected_count)
        .having(func.count(func.distinct(GeneratedBet.numbers_csv)) == expected_count)
        .all()
    )
    for (generation_id,) in candidates:
        total = (
            db.session.query(func.count(GeneratedBet.id))
            .filter(
                GeneratedBet.generation_id == generation_id,
                GeneratedBet.quantity == quantity,
            )
            .scalar()
        )
        if total == expected_count:
            return int(generation_id)
    return None


def stage_bet_batch(bets: list[GeneratedBet]) -> ConfirmationResult:
    """Prepara a escrita com o lock aberto; só o comando confirma a transação."""
    if not bets:
        return ConfirmationResult(0, None)
    quantity = bets[0].quantity
    numbers_csv = [bet.numbers_csv for bet in bets]
    contest = bets[0].contest
    fingerprint = _batch_fingerprint(quantity, numbers_csv, contest)
    _lock_batch_fingerprint(fingerprint)
    existing_generation_id = _find_existing_batch(quantity, numbers_csv, contest)
    if existing_generation_id is not None:
        return ConfirmationResult(len(bets), existing_generation_id, replayed=True)
    generation_id = int(
        db.session.execute(text(f"SELECT nextval('{_GENERATION_ID_SEQUENCE}')")).scalar_one()
    )
    for bet in bets:
        bet.generation_id = generation_id
    db.session.add_all(bets)
    return ConfirmationResult(len(bets), generation_id)


def generate_bets(
    quantity: int,
    amount: int,
    filters: dict | None = None,
    *,
    exclude_previous: bool = True,
    prioritize_coverage: bool = False,
) -> list[GeneratedBet]:
    """Gera candidatas em memória; gravar é uma decisão posterior do usuário.

    Nada aqui persiste: as apostas só chegam ao banco pelos comandos de
    confirmação, depois da revisão na tela.
    """
    if not _GENERATION_SLOTS.acquire(blocking=False):
        raise RuntimeError(
            "Há outras gerações em andamento. Aguarde alguns segundos e tente de novo."
        )
    try:
        return _generate_bets(quantity, amount, filters, exclude_previous, prioritize_coverage)
    finally:
        _GENERATION_SLOTS.release()


def _generate_bets(
    quantity: int,
    amount: int,
    filters: dict | None,
    exclude_previous: bool,
    prioritize_coverage: bool,
) -> list[GeneratedBet]:
    quantity = clamp_int(
        parse_int(quantity) or MIN_BET_NUMBERS,
        MIN_BET_NUMBERS,
        MAX_BET_NUMBERS,
    )
    amount = clamp_int(parse_int(amount) or 1, 1, 100)
    strict_values = {"quantity": quantity, "amount": amount, **(filters or {})}
    criteria = GenerationCriteria.from_mapping_strict(
        strict_values, default_quantity=quantity, default_amount=amount
    )
    filters = criteria.filters()
    draws = all_draw_numbers() if exclude_previous and quantity == 6 else []
    existing_draws = {tuple(d) for d in draws}
    created: list[GeneratedBet] = []
    created_numbers: list[list[int]] = []
    attempts = 0
    # Limite razoável: evita loop infinito com filtros muito restritivos.
    # 2000 tentativas por aposta é suficiente para qualquer configuração prática.
    max_attempts = amount * 2000
    deadline = time.monotonic() + GENERATION_TIME_BUDGET_SECONDS
    while len(created) < amount and attempts < max_attempts:
        candidates: list[list[int]] = []
        target = 8 if prioritize_coverage and created_numbers else 1
        while len(candidates) < target and attempts < max_attempts:
            if attempts % 256 == 0 and time.monotonic() > deadline:
                break
            attempts += 1
            nums = _secure_random_candidate(quantity)
            if quantity == 6 and tuple(nums) in existing_draws:
                continue
            if not _passes_generation_filters(nums, filters):
                continue
            if not _passes_diversity_control(nums, created_numbers):
                continue
            candidates.append(nums)
        if not candidates:
            break
        # Penaliza subconjuntos de quatro dezenas já cobertos. É uma heurística
        # limitada a oito candidatas, não uma otimização global exata.
        nums = min(
            candidates,
            key=lambda candidate: sum(
                math.comb(len(set(candidate) & set(previous)), 4)
                for previous in created_numbers
                if len(set(candidate) & set(previous)) >= 4
            ),
        )
        score = _diversity_score(nums, created_numbers)
        bet = GeneratedBet(
            quantity=quantity,
            numbers_csv=",".join(map(str, nums)),
            score=round(score, 4),
        )
        created.append(bet)
        created_numbers.append(nums)
    if len(created) < amount:
        _log.warning(
            "generate_bets: geradas %d/%d apostas após %d tentativas (filtros: %s).",
            len(created),
            amount,
            attempts,
            filters,
        )
    return created


def _normalize_closure_numbers(numbers: Iterable[int]) -> list[int]:
    base_numbers = sorted(set(numbers))
    if len(base_numbers) < MIN_BET_NUMBERS:
        raise RuntimeError(
            "Informe pelo menos 6 dezenas distintas para gerar um fechamento matemático."
        )
    if len(base_numbers) > MAX_BET_NUMBERS:
        raise RuntimeError(f"Use no máximo {MAX_BET_NUMBERS} dezenas no fechamento matemático.")
    if any(number < 1 or number > 60 for number in base_numbers):
        raise RuntimeError("As dezenas do fechamento devem estar entre 1 e 60.")
    return base_numbers


def count_closure_bets(numbers: Iterable[int]) -> int:
    base_numbers = _normalize_closure_numbers(numbers)
    return math.comb(len(base_numbers), MIN_BET_NUMBERS)


def generate_closure_bets(
    numbers: Iterable[int], *, limit: int | None = None
) -> list[GeneratedBet]:
    base_numbers = _normalize_closure_numbers(numbers)
    generated_combinations = combinations(base_numbers, MIN_BET_NUMBERS)
    if limit is not None:
        generated_combinations = islice(generated_combinations, max(0, limit))
    return [
        GeneratedBet(
            quantity=MIN_BET_NUMBERS,
            numbers_csv=",".join(map(str, combination)),
            score=0,
        )
        for combination in generated_combinations
    ]


def list_recent_generations(limit: int = 12) -> list[dict]:
    limit = clamp_int(parse_int(limit) or 12, 1, MAX_RECENT_GENERATIONS)
    rows = (
        db.session.query(
            GeneratedBet.generation_id,
            func.count(GeneratedBet.id),
            func.min(GeneratedBet.quantity),
            func.max(GeneratedBet.created_at),
        )
        .filter(GeneratedBet.generation_id.isnot(None))
        .group_by(GeneratedBet.generation_id)
        .order_by(func.max(GeneratedBet.created_at).desc(), GeneratedBet.generation_id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "generation_id": generation_id,
            "bet_count": bet_count,
            "quantity": quantity,
            "created_at": created_at,
        }
        for generation_id, bet_count, quantity, created_at in rows
    ]


def list_recent_generations_with_bets(limit: int = 12) -> list[dict]:
    generations = list_recent_generations(limit=limit)
    generation_ids = [generation["generation_id"] for generation in generations]
    if not generation_ids:
        return generations

    # Uma consulta para todos os lotes, e não uma por lote: o ROW_NUMBER corta
    # cada lote no limite de exibição dentro do próprio banco.
    ranked = (
        db.session.query(
            GeneratedBet.id.label("id"),
            func.row_number()
            .over(partition_by=GeneratedBet.generation_id, order_by=GeneratedBet.id)
            .label("position"),
        )
        .filter(GeneratedBet.generation_id.in_(generation_ids))
        .subquery()
    )
    bets = (
        db.session.query(GeneratedBet, Draw).join(ranked, GeneratedBet.id == ranked.c.id)
        .outerjoin(Draw, Draw.contest == GeneratedBet.contest)
        .filter(ranked.c.position <= MAX_RECENT_BETS_PER_GENERATION)
        .order_by(GeneratedBet.generation_id, GeneratedBet.id)
        .all()
    )
    bets_by_generation: dict[int, list[GeneratedBet]] = {}
    for bet, draw in bets:
        hits = set(bet.numbers) & set(draw.numbers) if draw else set()
        bet.winning_numbers = hits if len(hits) >= 4 else set()
        bet.hit_count = len(hits) if draw else None
        bets_by_generation.setdefault(bet.generation_id, []).append(bet)

    for generation in generations:
        generation["bets"] = bets_by_generation.get(generation["generation_id"], [])
        generation["contest"] = generation["bets"][0].contest if generation["bets"] else None
        generation["bets_truncated"] = generation["bet_count"] > MAX_RECENT_BETS_PER_GENERATION
    return generations


def stage_delete_bet(bet_id: int) -> GeneratedBet:
    """Exclui uma aposta salva, sem tocar nos concursos importados.

    O id é conferido no servidor; assim o botão da interface não é a única
    barreira e uma tentativa de remover algo inexistente recebe erro explícito.
    """
    bet = db.session.get(GeneratedBet, bet_id, with_for_update=True)
    if bet is None:
        raise RuntimeError("A aposta salva não foi encontrada.")
    db.session.delete(bet)
    return bet


def prepare_generated_bets(quantity: int, bets: Iterable[str]) -> list[GeneratedBet]:
    quantity = clamp_int(
        parse_int(quantity) or MIN_BET_NUMBERS,
        MIN_BET_NUMBERS,
        MAX_BET_NUMBERS,
    )
    valid_bets: list[GeneratedBet] = []
    seen_bets: set[str] = set()
    for index, numbers_csv in enumerate(bets, start=1):
        if index > MAX_SAVED_BETS:
            raise RuntimeError(f"Uma geração pode conter no máximo {MAX_SAVED_BETS} apostas.")
        nums = [parse_int(n) for n in numbers_csv.split(",")]
        if (
            len(nums) != quantity
            or any(n is None or n < 1 or n > 60 for n in nums)
            or len(set(nums)) != quantity
        ):
            continue
        nums = sorted(nums)  # type: ignore[arg-type]
        normalized_bet = ",".join(map(str, nums))
        if normalized_bet not in seen_bets:
            seen_bets.add(normalized_bet)
            valid_bets.append(
                GeneratedBet(
                    quantity=quantity,
                    numbers_csv=normalized_bet,
                    score=0,
                )
            )

    return valid_bets


def prepare_closure_bets(numbers: Iterable[int]) -> list[GeneratedBet]:
    base_numbers = _normalize_closure_numbers(numbers)
    serialized_bets = (
        ",".join(map(str, combination))
        for combination in combinations(base_numbers, MIN_BET_NUMBERS)
    )
    return prepare_generated_bets(
        MIN_BET_NUMBERS,
        serialized_bets,
    )
