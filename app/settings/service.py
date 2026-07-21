from __future__ import annotations

from ..core.numbers import _clamp_int, _to_int
from ..extensions import db
from ..generation_params import GENERATION_LIMITS
from ..models import Config

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


def _clean_config_value(key: str, value: object) -> str:
    parsed = _to_int(value)
    default_value = DEFAULT_CONFIG[key]
    if parsed is None:
        return default_value if key in {"bet_quantity", "generation_amount"} else ""
    min_value, max_value = CONFIG_LIMITS[key]
    return str(_clamp_int(parsed, min_value, max_value))


def _normalize_config_values(values: dict[str, object]) -> dict[str, str]:
    normalized = {key: _clean_config_value(key, values.get(key, DEFAULT_CONFIG[key])) for key in DEFAULT_CONFIG}
    for key in ("consecutive_count", "even_min", "even_max"):
        if normalized[key]:
            normalized[key] = str(_clamp_int(int(normalized[key]), 0, 6))
    for key in ("range_min_occupied", "range_max_per_band"):
        if normalized[key]:
            normalized[key] = str(_clamp_int(int(normalized[key]), 1, 6))
    if normalized["even_min"] and normalized["even_max"] and int(normalized["even_min"]) > int(normalized["even_max"]):
        normalized["even_max"] = normalized["even_min"]
    if normalized["sum_min"] and normalized["sum_max"] and int(normalized["sum_min"]) > int(normalized["sum_max"]):
        normalized["sum_min"], normalized["sum_max"] = normalized["sum_max"], normalized["sum_min"]
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
