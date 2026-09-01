from __future__ import annotations

import logging
import math
import secrets
from collections.abc import Iterable
from itertools import combinations, islice

from sqlalchemy import func, text

from ..core.numbers import (
    clamp_int,
    parse_int,
)
from ..draws.statistics import all_draw_numbers
from ..extensions import db
from ..models import GeneratedBet
from .criteria import (
    MAX_BET_NUMBERS,
    MIN_BET_NUMBERS,
    GenerationCriteria,
)

_log = logging.getLogger(__name__)
MAX_SAVED_BETS = math.comb(MAX_BET_NUMBERS, MIN_BET_NUMBERS)
_RNG = secrets.SystemRandom()
_GENERATION_ID_SEQUENCE = "generated_bets_generation_id_seq"


def _passes_generation_filters(numbers: list[int], filters: dict | None) -> bool:
    if not filters:
        return True
    return GenerationCriteria.from_mapping(filters, default_amount=1).matches_candidate(
        numbers
    )


def _diversity_score(numbers: list[int], existing_candidates: list[list[int]]) -> float:
    if not existing_candidates:
        return 1.0
    max_overlap = max(
        len(set(numbers) & set(candidate)) for candidate in existing_candidates
    )
    return max(0.0, 1.0 - (max_overlap / max(len(numbers), 1)))


def _passes_diversity_control(
    numbers: list[int], created_numbers: list[list[int]]
) -> bool:
    if not created_numbers:
        return True
    # Evita apostas praticamente iguais dentro da mesma geração.
    # Para apostas de 6 dezenas, no máximo 4 números podem se repetir entre duas apostas.
    max_allowed_overlap = max(0, len(numbers) - 2)
    current = set(numbers)
    return all(
        len(current & set(candidate)) <= max_allowed_overlap
        for candidate in created_numbers
    )


def _secure_random_candidate(quantity: int) -> list[int]:
    return sorted(_RNG.sample(range(1, 61), quantity))


def _persist_bet_batch(bets: list[GeneratedBet]) -> int | None:
    """Persiste um lote com identificador único fornecido pelo PostgreSQL."""
    if not bets:
        return None
    try:
        # Interpolação deliberada: `nextval` recebe o nome da sequência como
        # identificador, que não pode ser parametrizado. O valor é constante do
        # módulo, nunca entrada do usuário — não há caminho de injeção.
        generation_id = db.session.execute(
            text(f"SELECT nextval('{_GENERATION_ID_SEQUENCE}')")  # noqa: S608
        ).scalar_one()
        for bet in bets:
            bet.generation_id = generation_id
        db.session.add_all(bets)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return int(generation_id)


def generate_bets(
    quantity: int,
    amount: int,
    filters: dict | None = None,
) -> list[GeneratedBet]:
    """Gera candidatas em memória; gravar é uma decisão posterior do usuário.

    Nada aqui persiste: as apostas só chegam ao banco por `save_generated_bets`
    ou `save_closure_bets`, depois da confirmação na tela.
    """
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
    draws = all_draw_numbers()
    existing_draws = {tuple(d) for d in draws}
    created: list[GeneratedBet] = []
    created_numbers: list[list[int]] = []
    attempts = 0
    # Limite razoável: evita loop infinito com filtros muito restritivos.
    # 2000 tentativas por aposta é suficiente para qualquer configuração prática.
    max_attempts = amount * 2000
    while len(created) < amount and attempts < max_attempts:
        attempts += 1
        nums = _secure_random_candidate(quantity)
        if quantity == 6 and tuple(nums) in existing_draws:
            continue
        if not _passes_generation_filters(nums, filters):
            continue
        if not _passes_diversity_control(nums, created_numbers):
            continue
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
        raise RuntimeError(
            f"Use no máximo {MAX_BET_NUMBERS} dezenas no fechamento matemático."
        )
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
    limit = clamp_int(parse_int(limit) or 12, 1, 100)
    rows = (
        db.session.query(
            GeneratedBet.generation_id,
            func.count(GeneratedBet.id),
            func.min(GeneratedBet.quantity),
            func.max(GeneratedBet.created_at),
        )
        .filter(GeneratedBet.generation_id.isnot(None))
        .group_by(GeneratedBet.generation_id)
        .order_by(
            func.max(GeneratedBet.created_at).desc(), GeneratedBet.generation_id.desc()
        )
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

    bets = (
        GeneratedBet.query.filter(GeneratedBet.generation_id.in_(generation_ids))
        .order_by(GeneratedBet.generation_id.desc(), GeneratedBet.id)
        .all()
    )
    bets_by_generation: dict[int, list[GeneratedBet]] = {}
    for bet in bets:
        bets_by_generation.setdefault(bet.generation_id, []).append(bet)

    for generation in generations:
        generation["bets"] = bets_by_generation.get(generation["generation_id"], [])
    return generations


def save_generated_bets(quantity: int, bets: Iterable[str]) -> tuple[int, int | None]:
    quantity = clamp_int(
        parse_int(quantity) or MIN_BET_NUMBERS,
        MIN_BET_NUMBERS,
        MAX_BET_NUMBERS,
    )
    valid_bets: list[GeneratedBet] = []
    seen_bets: set[str] = set()
    for index, numbers_csv in enumerate(bets, start=1):
        if index > MAX_SAVED_BETS:
            raise RuntimeError(
                f"Uma geração pode conter no máximo {MAX_SAVED_BETS} apostas."
            )
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

    if not valid_bets:
        return 0, None

    # O servidor local do Flask pode atender requisicoes em threads diferentes;
    # a persistencia compartilhada serializa a alocacao do ID do lote.
    generation_id = _persist_bet_batch(valid_bets)
    if generation_id is None:  # protegido pelo teste de valid_bets acima
        return 0, None
    _log.info("Apostas salvas: %d na geração #%d.", len(valid_bets), generation_id)
    return len(valid_bets), generation_id


def save_closure_bets(numbers: Iterable[int]) -> tuple[int, int | None]:
    base_numbers = _normalize_closure_numbers(numbers)
    serialized_bets = (
        ",".join(map(str, combination))
        for combination in combinations(base_numbers, MIN_BET_NUMBERS)
    )
    return save_generated_bets(MIN_BET_NUMBERS, serialized_bets)
