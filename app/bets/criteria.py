from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping

from ..core.numbers import (
    count_consecutive_numbers,
    count_even_numbers,
    range_band_counts,
)

GENERATION_FILTER_KEYS = (
    "consecutive_count",
    "even_min",
    "even_max",
    "sum_min",
    "sum_max",
    "range_min_occupied",
    "range_max_per_band",
)
GENERATION_PARAM_KEYS = ("quantity", "amount", *GENERATION_FILTER_KEYS)
GENERATION_LIMITS = {
    "quantity": (6, 15),
    "amount": (1, 100),
    "consecutive_count": (0, 6),
    "even_min": (0, 6),
    "even_max": (0, 6),
    "sum_min": (0, 345),
    "sum_max": (0, 345),
    "range_min_occupied": (1, 6),
    "range_max_per_band": (1, 6),
}


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        text = str(value).strip()
        if not text or len(text) > 64:
            return None
        parsed = Decimal(text)
        if not parsed.is_finite() or parsed != parsed.to_integral_value():
            return None
        return int(parsed)
    except (InvalidOperation, OverflowError, TypeError, ValueError):
        return None


def _bounded(value: int | None, key: str, fallback: int | None = None) -> int | None:
    if value is None:
        value = fallback
    if value is None:
        return None
    minimum, maximum = GENERATION_LIMITS[key]
    return max(minimum, min(value, maximum))


@dataclass(frozen=True, slots=True)
class GenerationCriteria:
    quantity: int = 6
    amount: int = 5
    consecutive_count: int | None = None
    even_min: int | None = None
    even_max: int | None = None
    sum_min: int | None = None
    sum_max: int | None = None
    range_min_occupied: int | None = None
    range_max_per_band: int | None = None

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, object] | None,
        *,
        default_quantity: int = 6,
        default_amount: int = 5,
    ) -> "GenerationCriteria":
        source = values or {}
        quantity = (
            _bounded(
                _optional_int(source.get("quantity")), "quantity", default_quantity
            )
            or 6
        )
        amount = (
            _bounded(_optional_int(source.get("amount")), "amount", default_amount) or 1
        )
        normalized = {
            key: _bounded(_optional_int(source.get(key)), key)
            for key in GENERATION_FILTER_KEYS
        }
        even_min = normalized["even_min"]
        even_max = normalized["even_max"]
        if even_min is not None and even_max is not None and even_min > even_max:
            even_max = even_min
        sum_min = normalized["sum_min"]
        sum_max = normalized["sum_max"]
        if sum_min is not None and sum_max is not None and sum_min > sum_max:
            sum_min, sum_max = sum_max, sum_min
        return cls(
            quantity=quantity,
            amount=amount,
            consecutive_count=normalized["consecutive_count"],
            even_min=even_min,
            even_max=even_max,
            sum_min=sum_min,
            sum_max=sum_max,
            range_min_occupied=normalized["range_min_occupied"],
            range_max_per_band=normalized["range_max_per_band"],
        )

    def filters(self, *, include_empty: bool = False) -> dict[str, int | None]:
        values = {key: getattr(self, key) for key in GENERATION_FILTER_KEYS}
        return (
            values
            if include_empty
            else {key: value for key, value in values.items() if value is not None}
        )

    def matches_candidate(self, numbers: Iterable[int]) -> bool:
        """Verifica uma aposta, inclusive todos os subconjuntos cobertos de seis dezenas."""
        ordered = sorted(numbers)
        quantity = len(ordered)
        subset_size = min(6, quantity)
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
        return self.matches_distribution(
            longest_run=max_subset_consecutive,
            even_count_min=min_subset_evens,
            even_count_max=max_subset_evens,
            total_sum_min=min_subset_sum,
            total_sum_max=max_subset_sum,
            occupied_bands=min_occupied_bands,
            max_band_count=max_subset_band_count,
        )

    def matches_distribution(
        self,
        *,
        longest_run: int,
        even_count_min: int,
        even_count_max: int | None = None,
        total_sum_min: int,
        total_sum_max: int | None = None,
        occupied_bands: int,
        max_band_count: int,
    ) -> bool:
        """Avalia metricas de uma combinacao ou os limites de uma aposta ampliada."""
        even_count_max = even_count_min if even_count_max is None else even_count_max
        total_sum_max = total_sum_min if total_sum_max is None else total_sum_max
        if self.even_min is not None and even_count_min < self.even_min:
            return False
        if self.even_max is not None and even_count_max > self.even_max:
            return False
        if self.sum_min is not None and total_sum_min < self.sum_min:
            return False
        if self.sum_max is not None and total_sum_max > self.sum_max:
            return False
        if self.consecutive_count is not None and longest_run > self.consecutive_count:
            return False
        if (
            self.range_min_occupied is not None
            and occupied_bands < self.range_min_occupied
        ):
            return False
        if (
            self.range_max_per_band is not None
            and max_band_count > self.range_max_per_band
        ):
            return False
        return True

    def query_values(self, *, include_empty: bool = False) -> dict[str, int | str]:
        values: dict[str, int | str] = {
            "quantity": self.quantity,
            "amount": self.amount,
        }
        for key, value in self.filters(include_empty=True).items():
            if value is not None:
                values[key] = value
            elif include_empty:
                values[key] = ""
        return values


def coerce_generation_filters(filters: Mapping[str, object] | None) -> dict[str, int]:
    criteria = GenerationCriteria.from_mapping(filters, default_amount=1)
    return {
        key: value for key, value in criteria.filters().items() if value is not None
    }
