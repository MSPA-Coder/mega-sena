from __future__ import annotations

from sqlalchemy import text

from ..bets.criteria import GENERATION_FILTER_KEYS, GenerationCriteria
from ..core.numbers import parse_int
from ..draws.downloading import DEFAULT_RESULTS_SOURCE_URL, normalize_results_source_url
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
    "results_source_url": DEFAULT_RESULTS_SOURCE_URL,
}


def _normalize_config_values(values: dict[str, object]) -> dict[str, str]:
    criteria = GenerationCriteria.from_mapping(
        {
            "quantity": values.get("bet_quantity", DEFAULT_CONFIG["bet_quantity"]),
            "amount": values.get(
                "generation_amount", DEFAULT_CONFIG["generation_amount"]
            ),
            **{
                key: values.get(key, DEFAULT_CONFIG[key])
                for key in GENERATION_FILTER_KEYS
            },
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
    normalized["results_source_url"] = normalize_results_source_url(
        values.get("results_source_url", DEFAULT_CONFIG["results_source_url"])
    )
    return normalized


def get_config_values() -> dict[str, str]:
    """Lê a configuração de geração, caindo nos padrões sem gravar nada.

    Uma chave ausente vale exatamente o padrão, então o banco não precisa ser
    semeado: a primeira gravação em Configurações é que cria as linhas.
    """
    rows = {
        row.key: row.value
        for row in Config.query.filter(Config.key.in_(DEFAULT_CONFIG)).all()
    }
    return _normalize_config_values(
        {key: rows.get(key, DEFAULT_CONFIG[key]) for key in DEFAULT_CONFIG}
    )


def update_config_values(values: dict[str, object]) -> dict[str, str]:
    normalized = _normalize_config_values(values)
    try:
        # `Config` começa vazio em uma instalação nova. Lockar apenas as linhas
        # existentes não impediria dois primeiros salvamentos de disputarem o
        # mesmo INSERT; o lock de tabela cobre as duas situações e dura até o
        # commit desta transação.
        db.session.execute(text("LOCK TABLE config IN SHARE ROW EXCLUSIVE MODE"))
        rows = {
            row.key: row
            for row in Config.query.filter(Config.key.in_(DEFAULT_CONFIG))
            .with_for_update()
            .all()
        }
        for key, value in normalized.items():
            if key in rows:
                rows[key].value = value
            else:
                db.session.add(Config(key=key, value=value))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return normalized


def get_generation_defaults() -> dict[str, int | None]:
    values = get_config_values()
    return {
        "bet_quantity": int(values["bet_quantity"]),
        "generation_amount": int(values["generation_amount"]),
        "consecutive_count": parse_int(values["consecutive_count"]),
        "even_min": parse_int(values["even_min"]),
        "even_max": parse_int(values["even_max"]),
        "sum_min": parse_int(values["sum_min"]),
        "sum_max": parse_int(values["sum_max"]),
        "range_min_occupied": parse_int(values["range_min_occupied"]),
        "range_max_per_band": parse_int(values["range_max_per_band"]),
    }


def get_results_source_url() -> str:
    return get_config_values()["results_source_url"]


def reset_all_data() -> tuple[int, int]:
    """Remove concursos e apostas, devolvendo suas quantidades anteriores."""
    bet_count = GeneratedBet.query.count()
    draw_count = Draw.query.count()
    try:
        GeneratedBet.query.delete()
        Draw.query.delete()
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return draw_count, bet_count
