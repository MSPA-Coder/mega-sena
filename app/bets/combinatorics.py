from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from functools import lru_cache
from itertools import combinations

from ..core.formatting import format_int
from ..core.numbers import (
    count_occupied_range_bands,
    max_range_band_count,
    parse_int,
)
from ..models import Draw
from .criteria import (
    MAX_BET_NUMBERS,
    MIN_BET_NUMBERS,
    GenerationCriteria,
    coerce_generation_filters,
)

TOTAL_DRAW_COMBINATIONS = math.comb(60, 6)
# A união é calculada apenas quando o conjunto cabe confortavelmente na memória.
# Acima desse limite, a interface apresenta somente o limite superior teórico.
MAX_EXACT_COVERAGE_COMBINATIONS = 250_000
FILTER_SCAN_BATCH_SIZE = 1_000


@lru_cache(maxsize=1)
def _combination_distribution() -> dict[tuple[int, int, int, int, int], int]:
    states: dict[tuple[int, int, int, int, int, int, int, int], int] = {
        (0, 0, 0, 0, 0, 0, 0, 0): 1
    }
    for number in range(1, 61):
        if number in {11, 21, 31, 41, 51}:
            reset_states: dict[tuple[int, int, int, int, int, int, int, int], int] = {}
            for (
                quantity,
                total_sum,
                even_count,
                current_run,
                longest_run,
                occupied_bands,
                _current_band_count,
                max_band_count,
            ), count in states.items():
                key = (
                    quantity,
                    total_sum,
                    even_count,
                    current_run,
                    longest_run,
                    occupied_bands,
                    0,
                    max_band_count,
                )
                reset_states[key] = reset_states.get(key, 0) + count
            states = reset_states

        next_states: dict[tuple[int, int, int, int, int, int, int, int], int] = {}
        for (
            quantity,
            total_sum,
            even_count,
            current_run,
            longest_run,
            occupied_bands,
            current_band_count,
            max_band_count,
        ), count in states.items():
            skip_key = (
                quantity,
                total_sum,
                even_count,
                0,
                longest_run,
                occupied_bands,
                current_band_count,
                max_band_count,
            )
            next_states[skip_key] = next_states.get(skip_key, 0) + count

            if quantity < 6:
                new_current_run = current_run + 1 if current_run else 1
                new_longest_run = max(
                    longest_run, new_current_run if new_current_run >= 2 else 0
                )
                new_current_band_count = current_band_count + 1
                new_occupied_bands = occupied_bands + (
                    1 if current_band_count == 0 else 0
                )
                new_max_band_count = max(max_band_count, new_current_band_count)
                take_key = (
                    quantity + 1,
                    total_sum + number,
                    even_count + (1 if number % 2 == 0 else 0),
                    new_current_run,
                    new_longest_run,
                    new_occupied_bands,
                    new_current_band_count,
                    new_max_band_count,
                )
                next_states[take_key] = next_states.get(take_key, 0) + count
        states = next_states

    distribution: dict[tuple[int, int, int, int, int], int] = {}
    for (
        quantity,
        total_sum,
        even_count,
        _current_run,
        longest_run,
        occupied_bands,
        _current_band_count,
        max_band_count,
    ), count in states.items():
        if quantity == 6:
            key = (longest_run, even_count, total_sum, occupied_bands, max_band_count)
            distribution[key] = distribution.get(key, 0) + count
    return distribution


def count_possible_draw_combinations(
    consecutive_count: int | None = None,
    even_min: int | None = None,
    even_max: int | None = None,
    sum_min: int | None = None,
    sum_max: int | None = None,
    range_min_occupied: int | None = None,
    range_max_per_band: int | None = None,
) -> int:
    criteria = GenerationCriteria(
        consecutive_count=consecutive_count,
        even_min=even_min,
        even_max=even_max,
        sum_min=sum_min,
        sum_max=sum_max,
        range_min_occupied=range_min_occupied,
        range_max_per_band=range_max_per_band,
    )
    total = 0
    for (
        longest_run,
        even_numbers,
        total_sum,
        occupied_bands,
        max_band_count,
    ), count in _combination_distribution().items():
        if not criteria.matches_distribution(
            longest_run=longest_run,
            even_count_min=even_numbers,
            total_sum_min=total_sum,
            occupied_bands=occupied_bands,
            max_band_count=max_band_count,
        ):
            continue
        total += count
    return total


def count_distinct_internal_combinations(bets: Iterable[Iterable[int]]) -> int | None:
    """Conta a união exata das combinações de seis dezenas cobertas pelas apostas.

    ``None`` significa que calcular a união custaria mais do que a prévia
    aceita; é deliberadamente uma recusa, não uma estimativa.
    """
    normalized_bets = [tuple(sorted(set(bet))) for bet in bets]
    upper_bound = sum(math.comb(len(bet), 6) for bet in normalized_bets if len(bet) >= 6)
    if upper_bound > MAX_EXACT_COVERAGE_COMBINATIONS:
        return None

    return len(
        {
            combination
            for bet in normalized_bets
            if len(bet) >= 6
            for combination in combinations(bet, 6)
        }
    )


def build_combination_report(quantity: int = 6, filters: dict | None = None) -> dict:
    filters = coerce_generation_filters(filters)
    quantity = max(
        MIN_BET_NUMBERS,
        min(parse_int(quantity) or MIN_BET_NUMBERS, MAX_BET_NUMBERS),
    )
    total = TOTAL_DRAW_COMBINATIONS
    remaining = total
    steps = []

    filter_steps = [
        (
            "even",
            "Quantidade de números pares",
            (filters.get("even_min"), filters.get("even_max")),
        ),
        ("sum", "Soma dos números", (filters.get("sum_min"), filters.get("sum_max"))),
        (
            "range",
            "Distribuição por faixas",
            (filters.get("range_min_occupied"), filters.get("range_max_per_band")),
        ),
        (
            "consecutive_count",
            "Maior sequência de números consecutivos",
            filters.get("consecutive_count"),
        ),
    ]

    active_filters: dict[str, int] = {}
    for key, label, value in filter_steps:
        step_number = len(steps) + 1
        if key == "sum":
            value_min, value_max = value
            if value_min is None and value_max is None:
                continue
            lower_bound = value_min if value_min is not None else 21
            upper_bound = value_max if value_max is not None else 345
            if value_min is not None:
                active_filters["sum_min"] = value_min
            if value_max is not None:
                active_filters["sum_max"] = value_max
            display_value = f"{lower_bound} a {upper_bound}"
            formula = f"S{step_number} = {{ jogo em S{step_number - 1} | {lower_bound} <= soma(jogo) <= {upper_bound} }}"
            explanation = "A soma de cada jogo é comparada com o intervalo informado. Jogos abaixo da soma inicial ou acima da soma final saem do universo restante."
        elif key == "even":
            value_min, value_max = value
            if value_min is None and value_max is None:
                continue
            lower_bound = value_min if value_min is not None else 0
            upper_bound = value_max if value_max is not None else 6
            if value_min is not None:
                active_filters["even_min"] = value_min
            if value_max is not None:
                active_filters["even_max"] = value_max
            display_value = f"{lower_bound} a {upper_bound}"
            formula = f"S{step_number} = {{ jogo em S{step_number - 1} | {lower_bound} <= quantidade_de_pares(jogo) <= {upper_bound} }}"
            explanation = "Conta os números divisíveis por 2 dentro de cada jogo. O filtro mantém todos os jogos cuja quantidade de pares fique dentro da faixa informada."
        elif key == "range":
            min_occupied, max_per_band = value
            if min_occupied is None and max_per_band is None:
                continue
            if min_occupied is not None:
                active_filters["range_min_occupied"] = min_occupied
            if max_per_band is not None:
                active_filters["range_max_per_band"] = max_per_band
            parts = []
            formula_parts = []
            if min_occupied is not None:
                parts.append(f"mín. {min_occupied} faixas")
                formula_parts.append(f"faixas_ocupadas(jogo) >= {min_occupied}")
            if max_per_band is not None:
                parts.append(f"máx. {max_per_band} por faixa")
                formula_parts.append(f"max_por_faixa(jogo) <= {max_per_band}")
            display_value = ", ".join(parts)
            formula = f"S{step_number} = {{ jogo em S{step_number - 1} | {' e '.join(formula_parts)} }}"
            explanation = "Divide as dezenas nos blocos 01-10, 11-20, 21-30, 31-40, 41-50 e 51-60. O filtro controla quantas faixas precisam aparecer e quantas dezenas podem ficar concentradas na mesma faixa."
        else:
            if value is None:
                continue
            active_filters[key] = value
            display_value = f"até {value}"
            formula = f"S{step_number} = {{ jogo em S{step_number - 1} | maior_sequencia_consecutiva(jogo) <= {value} }}"
            explanation = "Ordena os 6 números do jogo e mede o maior bloco em que cada número vem logo depois do anterior. O filtro mantém jogos com sequência máxima menor ou igual ao limite informado."

        new_remaining = count_possible_draw_combinations(**active_filters)
        eliminated = remaining - new_remaining
        steps.append(
            {
                "label": label,
                "value": display_value,
                "formula": formula,
                "explanation": explanation,
                "previous_remaining": remaining,
                "previous_remaining_formatted": format_int(remaining),
                "eliminated": eliminated,
                "remaining": new_remaining,
                "eliminated_formatted": format_int(eliminated),
                "remaining_formatted": format_int(new_remaining),
            }
        )
        remaining = new_remaining

    covered_combinations = math.comb(quantity, 6)
    return {
        "total": total,
        "total_formatted": format_int(total),
        "remaining": remaining,
        "remaining_formatted": format_int(remaining),
        "eliminated_formatted": format_int(total - remaining),
        # `covered_combinations` alimenta o limite superior teórico calculado
        # pela camada HTTP; o restante do relatório é apresentação.
        "covered_combinations": covered_combinations,
        "covered_combinations_formatted": format_int(covered_combinations),
        "steps": steps,
    }


def count_draws_matching_filters(
    consecutive_count: int | None = None,
    even_min: int | None = None,
    even_max: int | None = None,
    sum_min: int | None = None,
    sum_max: int | None = None,
    range_min_occupied: int | None = None,
    range_max_per_band: int | None = None,
) -> int:
    query = Draw.query
    if consecutive_count is not None:
        query = query.filter(Draw.consecutive_count <= consecutive_count)
    if even_min is not None:
        query = query.filter(Draw.even_count >= even_min)
    if even_max is not None:
        query = query.filter(Draw.even_count <= even_max)
    if sum_min is not None:
        query = query.filter(Draw.total_sum >= sum_min)
    if sum_max is not None:
        query = query.filter(Draw.total_sum <= sum_max)
    if range_min_occupied is None and range_max_per_band is None:
        return query.count()
    count = 0
    rows = query.with_entities(
        Draw.n1, Draw.n2, Draw.n3, Draw.n4, Draw.n5, Draw.n6
    ).yield_per(FILTER_SCAN_BATCH_SIZE)
    for row in rows:
        numbers = list(row)
        if (
            range_min_occupied is not None
            and count_occupied_range_bands(numbers) < range_min_occupied
        ):
            continue
        if (
            range_max_per_band is not None
            and max_range_band_count(numbers) > range_max_per_band
        ):
            continue
        count += 1
    return count


def calculate_individual_filter_targets(target_percentage: float) -> dict:
    rows = Draw.query.with_entities(
        Draw.consecutive_count,
        Draw.even_count,
        Draw.total_sum,
        Draw.n1,
        Draw.n2,
        Draw.n3,
        Draw.n4,
        Draw.n5,
        Draw.n6,
    ).yield_per(FILTER_SCAN_BATCH_SIZE)
    try:
        target_percentage = float(target_percentage)
    except (TypeError, ValueError):
        target_percentage = 80.0
    if not math.isfinite(target_percentage):
        target_percentage = 80.0
    target_percentage = max(0.0, min(target_percentage, 100.0))
    consecutive_counter: Counter[int] = Counter()
    even_counter: Counter[int] = Counter()
    sum_counter: Counter[int] = Counter()
    occupied_range_counter: Counter[int] = Counter()
    max_range_counter: Counter[int] = Counter()
    total = 0
    for row in rows:
        total += 1
        consecutive_counter[row.consecutive_count] += 1
        even_counter[row.even_count] += 1
        sum_counter[row.total_sum] += 1
        numbers = [row.n1, row.n2, row.n3, row.n4, row.n5, row.n6]
        occupied_range_counter[count_occupied_range_bands(numbers)] += 1
        max_range_counter[max_range_band_count(numbers)] += 1

    target_count = math.ceil((target_percentage / 100) * total) if total else 0

    def metric(value: int | None) -> dict:
        return {"value": value}

    if not total:
        empty_parameters = {
            "consecutive_count": metric(None),
            "even_min": metric(None),
            "even_max": metric(None),
            "sum_min": metric(None),
            "sum_max": metric(None),
            "range_min_occupied": metric(None),
            "range_max_per_band": metric(None),
        }
        return {
            "target_percentage": target_percentage,
            "total": 0,
            "parameters": empty_parameters,
        }

    def first_at_or_above(candidates: Iterable[int], counter: Counter[int], predicate) -> dict:
        for value in candidates:
            if sum(
                count for item, count in counter.items() if predicate(item, value)
            ) >= target_count:
                return metric(value)
        candidates = list(candidates)
        return metric(candidates[-1])

    def last_at_or_above(candidates: Iterable[int], counter: Counter[int], predicate) -> dict:
        selected_value = None
        for value in candidates:
            if sum(
                count for item, count in counter.items() if predicate(item, value)
            ) >= target_count:
                selected_value = value
        return metric(selected_value)

    unique_sums = sorted(sum_counter)
    parameters = {
        "consecutive_count": first_at_or_above(
            range(0, 7),
            consecutive_counter,
            lambda item, value: item <= value,
        ),
        "even_min": last_at_or_above(
            range(0, 7), even_counter, lambda item, value: item >= value
        ),
        "even_max": first_at_or_above(
            range(0, 7), even_counter, lambda item, value: item <= value
        ),
        "sum_min": last_at_or_above(
            unique_sums, sum_counter, lambda item, value: item >= value
        ),
        "sum_max": first_at_or_above(
            unique_sums, sum_counter, lambda item, value: item <= value
        ),
        "range_min_occupied": last_at_or_above(
            range(1, 7),
            occupied_range_counter,
            lambda item, value: item >= value,
        ),
        "range_max_per_band": first_at_or_above(
            range(1, 7),
            max_range_counter,
            lambda item, value: item <= value,
        ),
    }
    return {
        "target_percentage": target_percentage,
        "total": total,
        "parameters": parameters,
    }
