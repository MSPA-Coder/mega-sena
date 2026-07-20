from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Iterable

from ..generation_params import GenerationParams

_MAX_SQLITE_INTEGER = (1 << 63) - 1


def _to_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        if value is None or value == "":
            return None
        text = str(value).strip()
        if not text or len(text) > 64:
            return None
        parsed = Decimal(text)
        if not parsed.is_finite() or parsed != parsed.to_integral_value():
            return None
        result = int(parsed)
        if not -_MAX_SQLITE_INTEGER <= result <= _MAX_SQLITE_INTEGER:
            return None
        return result
    except (InvalidOperation, OverflowError, TypeError, ValueError):
        return None


def _clamp_int(value: int, min_value: int | None = None, max_value: int | None = None) -> int:
    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    return value


def _coerce_generation_filters(filters: dict | None) -> dict[str, int]:
    params = GenerationParams.from_mapping(filters, default_amount=1)
    return {key: value for key, value in params.filters().items() if value is not None}


def count_even_numbers(numbers: Iterable[int]) -> int:
    return sum(1 for number in numbers if number % 2 == 0)


def range_band_counts(numbers: Iterable[int]) -> list[int]:
    counts = [0, 0, 0, 0, 0, 0]
    for number in numbers:
        if 1 <= number <= 60:
            counts[(number - 1) // 10] += 1
    return counts


def count_occupied_range_bands(numbers: Iterable[int]) -> int:
    return sum(1 for count in range_band_counts(numbers) if count)


def max_range_band_count(numbers: Iterable[int]) -> int:
    return max(range_band_counts(numbers), default=0)


def _format_int(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def format_int(value: int) -> str:
    """Formata inteiro com separador de milhar brasileiro (ponto)."""
    return _format_int(value)


def _format_percent(value: float) -> str:
    return f"{value:.8f}".rstrip("0").rstrip(".").replace(".", ",")


def format_percent(value: float) -> str:
    """Formata percentual com precisão de 8 casas, usando vírgula decimal."""
    return _format_percent(value)


def draw_parameters(numbers: Iterable[int]) -> dict[str, int]:
    values = list(numbers)
    return {
        "total_sum": sum(values),
        "even_count": count_even_numbers(values),
        "consecutive_count": count_consecutive_numbers(values),
    }


def count_consecutive_numbers(numbers: Iterable[int]) -> int:
    ordered = sorted(set(numbers))
    longest = 0
    current = 1
    for previous, current_number in zip(ordered, ordered[1:]):
        if current_number == previous + 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest
