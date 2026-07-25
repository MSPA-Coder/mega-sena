from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Iterable

# Maior inteiro de 64 bits com sinal: cabe tanto no SQLite (afinidade INTEGER
# dinâmica) quanto nas colunas BigInteger do PostgreSQL (int8). É o limite
# padrão de parse_int, usado quando o valor não é gravado em uma coluna
# Integer comum.
MAX_INT64 = (1 << 63) - 1

# Maior inteiro de 32 bits com sinal: teto real das colunas db.Integer no
# PostgreSQL (int4). Use este limite ao validar valores que serão gravados em
# uma coluna Integer (não BigInteger) — por exemplo Draw.contest ou
# Draw.winners_6 — para rejeitar o valor antes do INSERT em vez de deixar o
# PostgreSQL derrubar a transação inteira com "integer out of range".
MAX_INT32 = (1 << 31) - 1


def parse_int(value: object, *, max_abs: int = MAX_INT64) -> int | None:
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
        if not -max_abs <= result <= max_abs:
            return None
        return result
    except (InvalidOperation, OverflowError, TypeError, ValueError):
        return None


def clamp_int(
    value: int, min_value: int | None = None, max_value: int | None = None
) -> int:
    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    return value


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
