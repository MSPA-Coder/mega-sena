from __future__ import annotations

import logging
import math
import secrets
from itertools import combinations
from threading import Lock
from typing import Iterable

from sqlalchemy import func

from ..core.numbers import (
    _clamp_int,
    _to_int,
)
from ..draws.statistics import all_draw_numbers
from ..extensions import db
from ..models import GeneratedBet
from .criteria import GenerationCriteria, coerce_generation_filters

_log = logging.getLogger(__name__)
MAX_SAVED_BETS = math.comb(15, 6)
_GENERATION_SAVE_LOCK = Lock()
_RNG = secrets.SystemRandom()


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
    return all(len(current & set(candidate)) <= max_allowed_overlap for candidate in created_numbers)


def _secure_random_candidate(quantity: int) -> list[int]:
    return sorted(_RNG.sample(range(1, 61), quantity))


def _persist_bet_batch(bets: list[GeneratedBet]) -> int | None:
    """Persiste um lote com ID unico entre as threads do servidor local."""
    if not bets:
        return None
    with _GENERATION_SAVE_LOCK:
        try:
            last_generation_id = db.session.query(func.max(GeneratedBet.generation_id)).scalar() or 0
            generation_id = last_generation_id + 1
            for bet in bets:
                bet.generation_id = generation_id
            db.session.add_all(bets)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
    return generation_id


def generate_bets(
    quantity: int,
    amount: int,
    persist: bool = True,
    filters: dict | None = None,
) -> list[GeneratedBet]:
    quantity = _clamp_int(_to_int(quantity) or 6, 6, 15)
    amount = _clamp_int(_to_int(amount) or 1, 1, 100)
    filters = coerce_generation_filters(filters)
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
            len(created), amount, attempts, filters,
        )
    if persist:
        _persist_bet_batch(created)
    return created


def generate_closure_bets(numbers: Iterable[int]) -> list[GeneratedBet]:
    base_numbers = sorted(set(numbers))
    if len(base_numbers) < 6:
        raise RuntimeError("Informe pelo menos 6 dezenas distintas para gerar um fechamento matemático.")
    if len(base_numbers) > 15:
        raise RuntimeError("Use no máximo 15 dezenas no fechamento matemático.")
    if any(number < 1 or number > 60 for number in base_numbers):
        raise RuntimeError("As dezenas do fechamento devem estar entre 1 e 60.")

    return [
        GeneratedBet(
            quantity=6,
            numbers_csv=",".join(map(str, combination)),
            score=0,
        )
        for combination in combinations(base_numbers, 6)
    ]


def list_recent_generations(limit: int = 12) -> list[dict]:
    limit = _clamp_int(_to_int(limit) or 12, 1, 100)
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


def get_generation_bets(generation_id: int) -> list[GeneratedBet]:
    """Lista as apostas de uma geracao em ordem de criacao."""
    return (
        GeneratedBet.query.filter(GeneratedBet.generation_id == generation_id)
        .order_by(GeneratedBet.id)
        .all()
    )


def save_generated_bets(quantity: int, bets: Iterable[str]) -> tuple[int, int | None]:
    quantity = _clamp_int(_to_int(quantity) or 6, 6, 15)
    valid_bets = []
    seen_bets: set[str] = set()
    for index, numbers_csv in enumerate(bets, start=1):
        if index > MAX_SAVED_BETS:
            raise RuntimeError(f"Uma geração pode conter no máximo {MAX_SAVED_BETS} apostas.")
        nums = [_to_int(n) for n in numbers_csv.split(",")]
        if len(nums) != quantity or any(n is None or n < 1 or n > 60 for n in nums) or len(set(nums)) != quantity:
            continue
        nums = sorted(nums)  # type: ignore[arg-type]
        normalized_bet = ",".join(map(str, nums))
        if normalized_bet not in seen_bets:
            seen_bets.add(normalized_bet)
            valid_bets.append(normalized_bet)

    if not valid_bets:
        return 0, None

    # O servidor local do Flask pode atender requisicoes em threads diferentes;
    # a persistencia compartilhada serializa a alocacao do ID do lote.
    models = [GeneratedBet(quantity=quantity, numbers_csv=numbers_csv, score=0) for numbers_csv in valid_bets]
    generation_id = _persist_bet_batch(models)
    if generation_id is None:  # protegido pelo teste de valid_bets acima
        return 0, None
    _log.info("Apostas salvas: %d na geração #%d.", len(valid_bets), generation_id)
    return len(valid_bets), generation_id
