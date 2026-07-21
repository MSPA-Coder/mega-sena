from __future__ import annotations

from ..bets.criteria import GENERATION_FILTER_KEYS, GENERATION_LIMITS, GenerationCriteria
from ..core.numbers import _to_int
from ..extensions import db
from ..models import Config, Draw, GeneratedBet

DEFAULT_CONFIG = {
    "bet_quantity": "6",
    "generation_amount": "5",
    "consecutive_count": "",
    "even_min": "",
    "even_max": "",
    "sum_min": "",
    "sum_max": "",
    "range_min_occupied": "",
    "range_max_per_band": "",
}
CONFIG_LIMITS = {
    "bet_quantity": GENERATION_LIMITS["quantity"],
    "generation_amount": GENERATION_LIMITS["amount"],
    **{key: GENERATION_LIMITS[key] for key in GENERATION_LIMITS if key not in {"quantity", "amount"}},
}


def _normalize_config_values(values: dict[str, object]) -> dict[str, str]:
    criteria = GenerationCriteria.from_mapping(
        {
            "quantity": values.get("bet_quantity", DEFAULT_CONFIG["bet_quantity"]),
            "amount": values.get("generation_amount", DEFAULT_CONFIG["generation_amount"]),
            **{key: values.get(key, DEFAULT_CONFIG[key]) for key in GENERATION_FILTER_KEYS},
        },
        default_quantity=int(DEFAULT_CONFIG["bet_quantity"]),
        default_amount=int(DEFAULT_CONFIG["generation_amount"]),
    )
    normalized = {
        "bet_quantity": str(criteria.quantity),
        "generation_amount": str(criteria.amount),
    }
    normalized.update(
        {
            key: "" if value is None else str(value)
            for key, value in criteria.filters(include_empty=True).items()
        }
    )
    return normalized


def ensure_default_config() -> dict[str, str]:
    existing = {row.key: row for row in Config.query.all()}
    changed = False
    for key, value in DEFAULT_CONFIG.items():
        if key not in existing:
            db.session.add(Config(key=key, value=value))
            changed = True
    if changed:
        db.session.commit()
    return get_config_values()


def get_config_values() -> dict[str, str]:
    rows = {row.key: row.value for row in Config.query.all()}
    missing = [key for key in DEFAULT_CONFIG if key not in rows]
    if missing:
        for key in missing:
            db.session.add(Config(key=key, value=DEFAULT_CONFIG[key]))
        db.session.commit()
        rows = {row.key: row.value for row in Config.query.all()}
    return _normalize_config_values({key: rows.get(key, DEFAULT_CONFIG[key]) for key in DEFAULT_CONFIG})


def update_config_values(values: dict[str, object]) -> dict[str, str]:
    normalized = _normalize_config_values(values)
    rows = {row.key: row for row in Config.query.all()}
    for key, value in normalized.items():
        if key in rows:
            rows[key].value = value
        else:
            db.session.add(Config(key=key, value=value))
    db.session.commit()
    return normalized


def get_generation_defaults() -> dict[str, int | None]:
    values = get_config_values()
    return {
        "bet_quantity": int(values["bet_quantity"]),
        "generation_amount": int(values["generation_amount"]),
        "consecutive_count": _to_int(values["consecutive_count"]),
        "even_min": _to_int(values["even_min"]),
        "even_max": _to_int(values["even_max"]),
        "sum_min": _to_int(values["sum_min"]),
        "sum_max": _to_int(values["sum_max"]),
        "range_min_occupied": _to_int(values["range_min_occupied"]),
        "range_max_per_band": _to_int(values["range_max_per_band"]),
    }


def reset_all_data() -> tuple[int, int]:
    """Remove concursos e apostas, devolvendo suas quantidades anteriores."""
    bet_count = GeneratedBet.query.count()
    draw_count = Draw.query.count()
    GeneratedBet.query.delete()
    Draw.query.delete()
    db.session.commit()
    return draw_count, bet_count
