"""Padrões de geração (de cada conta) e configuração do sistema.

Desde 04/11/2026 (ADR 0004) cada conta gera com os próprios padrões, gravados
em `user_config`. Chave que a pessoa ainda não salvou vale o padrão do
sistema (`config`, com os valores que existiam quando os padrões eram de
todos) e, na falta dele, o do código. É assim que cada conta começa com uma
cópia dos valores atuais sem nenhuma linha semeada.

O endereço da planilha de resultados continua sendo do sistema: a importação
de concursos é comum a todos, e só `admin` o altera.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from ..bets.criteria import GENERATION_FILTER_KEYS, GenerationCriteria
from ..core.numbers import parse_int
from ..draws.downloading import DEFAULT_RESULTS_SOURCE_URL, normalize_results_source_url
from ..extensions import db
from ..models import Config, Draw, GeneratedBet, UserConfig

#: Padrões de geração do código, usados quando nem a conta nem o sistema têm valor.
DEFAULT_GENERATION = {
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
GENERATION_KEYS = tuple(DEFAULT_GENERATION)
RESULTS_SOURCE_URL_KEY = "results_source_url"


def _normalize_generation_values(
    values: dict[str, object], *, strict: bool = False
) -> dict[str, str]:
    """Normaliza os padrões de geração.

    `strict=True` vale para o que a pessoa digita em Configurações: valor fora
    dos limites ou contraditório é recusado com mensagem, não corrigido em
    silêncio. A leitura (`strict=False`) continua tolerante para não quebrar a
    tela por causa de um valor gravado por uma versão anterior.
    """
    factory = GenerationCriteria.from_mapping_strict if strict else GenerationCriteria.from_mapping
    criteria = factory(
        {
            "quantity": values.get("bet_quantity", DEFAULT_GENERATION["bet_quantity"]),
            "amount": values.get("generation_amount", DEFAULT_GENERATION["generation_amount"]),
            **{key: values.get(key, DEFAULT_GENERATION[key]) for key in GENERATION_FILTER_KEYS},
        },
        default_quantity=int(DEFAULT_GENERATION["bet_quantity"]),
        default_amount=int(DEFAULT_GENERATION["generation_amount"]),
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


def _system_values(keys: tuple[str, ...]) -> dict[str, str]:
    return {row.key: row.value for row in Config.query.filter(Config.key.in_(keys)).all()}


def get_generation_values(user_id: int) -> dict[str, str]:
    """Padrões de geração da conta: os dela, senão os do sistema, senão os do código.

    Só lê: a primeira gravação em Configurações é que cria as linhas da conta.
    """
    own = {
        row.key: row.value
        for row in UserConfig.query.filter(
            UserConfig.user_id == user_id, UserConfig.key.in_(GENERATION_KEYS)
        ).all()
    }
    system = _system_values(GENERATION_KEYS)
    return _normalize_generation_values(
        {key: own.get(key, system.get(key, DEFAULT_GENERATION[key])) for key in GENERATION_KEYS}
    )


def update_generation_values(
    user_id: int, values: dict[str, object], *, commit: bool = True
) -> dict[str, str]:
    """Grava os padrões de geração da conta, todos de uma vez.

    O `ON CONFLICT` na chave (conta, chave) dispensa lock de tabela: duas
    gravações da mesma pessoa ao mesmo tempo terminam com a última, e as de
    contas diferentes nem se encostam.
    """
    normalized = _normalize_generation_values(values, strict=True)
    try:
        statement = insert(UserConfig).values(
            [{"user_id": user_id, "key": key, "value": value} for key, value in normalized.items()]
        )
        db.session.execute(
            statement.on_conflict_do_update(
                index_elements=[UserConfig.user_id, UserConfig.key],
                set_={"value": statement.excluded.value},
            )
        )
        if commit:
            db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return normalized


def get_generation_defaults(user_id: int) -> dict[str, int | None]:
    values = get_generation_values(user_id)
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
    gravado = _system_values((RESULTS_SOURCE_URL_KEY,)).get(RESULTS_SOURCE_URL_KEY)
    return normalize_results_source_url(gravado or DEFAULT_RESULTS_SOURCE_URL)


def update_results_source_url(value: object, *, commit: bool = True) -> str:
    """Grava o endereço da planilha de resultados, que vale para todos."""
    normalized = normalize_results_source_url(value)
    try:
        # `Config` pode começar vazio. Lockar apenas a linha existente não
        # impediria dois primeiros salvamentos de disputarem o mesmo INSERT; o
        # lock de tabela cobre as duas situações e dura até o commit.
        db.session.execute(text("LOCK TABLE config IN SHARE ROW EXCLUSIVE MODE"))
        row = (
            Config.query.filter(Config.key == RESULTS_SOURCE_URL_KEY).with_for_update().one_or_none()
        )
        if row is None:
            db.session.add(Config(key=RESULTS_SOURCE_URL_KEY, value=normalized))
        else:
            row.value = normalized
        if commit:
            db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return normalized


def reset_all_data(*, commit: bool = True) -> tuple[int, int]:
    """Remove concursos e apostas de TODAS as contas, devolvendo as quantidades.

    É a reinicialização do sistema, só de `admin`: apaga também as apostas das
    outras contas, e a tela diz isso antes de confirmar.
    """
    bet_count = GeneratedBet.query.count()
    draw_count = Draw.query.count()
    try:
        GeneratedBet.query.delete()
        Draw.query.delete()
        if commit:
            db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return draw_count, bet_count
