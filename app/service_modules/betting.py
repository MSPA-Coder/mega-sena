from __future__ import annotations

import logging
import math
import secrets
from itertools import combinations
from threading import Lock
from typing import Iterable

from sqlalchemy import func

from ..extensions import db
from ..models import GeneratedBet
from .common import (
    _clamp_int,
    _coerce_generation_filters,
    _to_int,
    count_consecutive_numbers,
    count_even_numbers,
    range_band_counts,
)
from .statistics import all_draw_numbers

_log = logging.getLogger(__name__)
MAX_SAVED_BETS = math.comb(15, 6)
_GENERATION_SAVE_LOCK = Lock()
_RNG = secrets.SystemRandom()


def _passes_generation_filters(numbers: list[int], filters: dict | None) -> bool:
    if not filters:
        return True
    ordered = sorted(numbers)
    quantity = len(ordered)
    subset_size = min(6, quantity)
    consecutive_count = filters.get("consecutive_count")
    even_min = filters.get("even_min")
    even_max = filters.get("even_max")
    sum_min = filters.get("sum_min")
    sum_max = filters.get("sum_max")
    range_min_occupied = filters.get("range_min_occupied")
    range_max_per_band = filters.get("range_max_per_band")
    even_count = count_even_numbers(ordered)
    odd_count = quantity - even_count
    min_subset_evens = max(0, subset_size - odd_count)
    max_subset_evens = min(subset_size, even_count)
    min_subset_sum = sum(ordered[:subset_size])
    max_subset_sum = sum(ordered[-subset_size:])
    band_counts = sorted(range_band_counts(ordered), reverse=True)
    remaining = subset_size
    min_occupied_bands = 0
    for band_count in band_counts:
        if remaining <= 0:
            break
        if band_count:
            min_occupied_bands += 1
            remaining -= min(band_count, remaining)
    max_subset_band_count = min(subset_size, band_counts[0] if band_counts else 0)
    max_subset_consecutive = min(subset_size, count_consecutive_numbers(ordered))

    # Para apostas de 7 a 15 dezenas, todos os subconjuntos cobertos de 6
    # precisam respeitar os filtros. Assim o racional C(n, 6) permanece correto.
    if even_min is not None and min_subset_evens < even_min:
        return False
    if even_max is not None and max_subset_evens > even_max:
        return False
    if sum_min is not None and min_subset_sum < sum_min:
        return False
    if sum_max is not None and max_subset_sum > sum_max:
        return False
    if consecutive_count is not None and max_subset_consecutive > consecutive_count:
        return False
    if range_min_occupied is not None and min_occupied_bands < range_min_occupied:
        return False
    if range_max_per_band is not None and max_subset_band_count > range_max_per_band:
        return False
    return True


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
    filters = _coerce_generation_filters(filters)
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
