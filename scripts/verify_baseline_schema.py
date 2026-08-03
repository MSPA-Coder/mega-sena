"""Verifica se um banco existente corresponde ao baseline consolidado."""

from __future__ import annotations

import sys

from sqlalchemy import inspect, text

from app import create_app
from app.extensions import db


BASELINE_REVISION = "20260803_baseline"
LEGACY_REVISIONS = {
    "0001_initial",
    "0002_repair_indexes",
    "0003_expand_money",
    "0004_generation_id_sequence",
    "0005_integrity_constraints",
}
REQUIRED_TABLES = {"alembic_version", "config", "draws", "generated_bets"}
REQUIRED_INDEXES = {
    "config": {"ix_config_key"},
    "draws": {"ix_draws_contest"},
    "generated_bets": {"ix_generated_bets_generation_id"},
}
REQUIRED_CHECKS = {
    "draws": {
        "ck_draws_contest_positive",
        "ck_draws_numbers_ordered_and_bounded",
        "ck_draws_total_sum_matches_numbers",
        "ck_draws_even_count_matches_numbers",
        "ck_draws_consecutive_count_matches_numbers",
        "ck_draws_winners_nonnegative",
        "ck_draws_money_nonnegative",
    },
    "generated_bets": {
        "ck_generated_bets_quantity_range",
        "ck_generated_bets_score_range",
        "ck_generated_bets_generation_id_positive",
    },
}


def verify_schema(*, allow_baseline: bool = False) -> tuple[str, dict[str, int]]:
    app = create_app()
    with app.app_context():
        if db.engine.url.get_backend_name() != "postgresql":
            raise RuntimeError("A adoção do baseline exige PostgreSQL.")
        inspector = inspect(db.engine)
        actual_tables = set(inspector.get_table_names())
        if not REQUIRED_TABLES <= actual_tables:
            raise RuntimeError(f"Tabelas ausentes: {sorted(REQUIRED_TABLES - actual_tables)}")
        for table, expected in REQUIRED_INDEXES.items():
            actual = {item["name"] for item in inspector.get_indexes(table)}
            if not expected <= actual:
                raise RuntimeError(f"Índices ausentes em {table}: {sorted(expected - actual)}")
        for table, expected in REQUIRED_CHECKS.items():
            actual = {item["name"] for item in inspector.get_check_constraints(table)}
            if not expected <= actual:
                raise RuntimeError(f"Constraints ausentes em {table}: {sorted(expected - actual)}")
        if db.session.execute(text("SELECT to_regclass('generated_bets_generation_id_seq')")).scalar_one() != "generated_bets_generation_id_seq":
            raise RuntimeError("Sequence generated_bets_generation_id_seq ausente.")
        revision = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        allowed = LEGACY_REVISIONS | ({BASELINE_REVISION} if allow_baseline else set())
        if revision not in allowed:
            raise RuntimeError(f"Revisão Alembic não é elegível para adoção: {revision!r}.")
        counts = {table: db.session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() for table in ("config", "draws", "generated_bets")}
    return revision, counts


def main() -> int:
    revision, counts = verify_schema(allow_baseline=True)
    print("Schema do baseline confirmado:", f"revision={revision}", *(f"{name}={count}" for name, count in counts.items()))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"ERRO: {error}", file=sys.stderr)
        raise SystemExit(1) from error
