from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping


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
class GenerationParams:
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
    ) -> "GenerationParams":
        source = values or {}
        quantity = _bounded(_optional_int(source.get("quantity")), "quantity", default_quantity) or 6
        amount = _bounded(_optional_int(source.get("amount")), "amount", default_amount) or 1
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
        return values if include_empty else {key: value for key, value in values.items() if value is not None}

    def query_values(self, *, include_empty: bool = False) -> dict[str, int | str]:
        values: dict[str, int | str] = {"quantity": self.quantity, "amount": self.amount}
        for key, value in self.filters(include_empty=True).items():
            if value is not None:
                values[key] = value
            elif include_empty:
                values[key] = ""
        return values
