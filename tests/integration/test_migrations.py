from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy import inspect, text

from app import create_app, db
from app.schema import ensure_database_schema
from tests.support import get_test_database_url


def test_fresh_database_is_created_from_migrations() -> None:
    """`ensure_database_schema()` cria o schema completo e deixa o banco na
    revisão mais recente do Alembic.

    Validado em PostgreSQL real e descartável (criado e destruído só para
    este teste), não em SQLite: migrações, constraints e tipos de coluna são
    um contrato específico de dialeto e SQLite não é usado para simular
    PostgreSQL (ver AGENTS.md).
    """
    base_url = sa.make_url(get_test_database_url())
    server_url = base_url.set(database="postgres")
    temp_db_name = f"mega_sena_migration_test_{uuid.uuid4().hex[:12]}"

    _run_as_admin(server_url, f'CREATE DATABASE "{temp_db_name}"')

    temp_url = base_url.set(database=temp_db_name)
    try:
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "SQLALCHEMY_DATABASE_URI": temp_url.render_as_string(
                    hide_password=False
                ),
            }
        )
        with app.app_context():
            ensure_database_schema(app)

            tables = set(inspect(db.engine).get_table_names())
            revision = db.session.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            assert {"alembic_version", "config", "draws", "generated_bets"} <= tables
            assert revision == "20260803_baseline"
            assert (
                db.session.execute(
                    text("SELECT to_regclass('generated_bets_generation_id_seq')")
                ).scalar_one()
                == "generated_bets_generation_id_seq"
            )
            assert (
                db.session.execute(
                    text("SELECT nextval('generated_bets_generation_id_seq')")
                ).scalar_one()
                == 1
            )
            checks = {
                check["name"] for check in inspect(db.engine).get_check_constraints("draws")
            }
            assert {
                "ck_draws_contest_positive",
                "ck_draws_numbers_ordered_and_bounded",
                "ck_draws_total_sum_matches_numbers",
                "ck_draws_even_count_matches_numbers",
                "ck_draws_consecutive_count_matches_numbers",
                "ck_draws_winners_nonnegative",
                "ck_draws_money_nonnegative",
            } <= checks
            generated_bet_checks = {
                check["name"]
                for check in inspect(db.engine).get_check_constraints("generated_bets")
            }
            assert {
                "ck_generated_bets_quantity_range",
                "ck_generated_bets_score_range",
                "ck_generated_bets_generation_id_positive",
            } <= generated_bet_checks

            with pytest.raises(sa.exc.IntegrityError):
                db.session.execute(
                    text(
                        "INSERT INTO draws "
                        "(contest, n1, n2, n3, n4, n5, n6, total_sum, even_count, "
                        "consecutive_count, winners_6, winners_5, winners_4, prize_cents, "
                        "accumulated_cents, quina_rateio_cents, quadra_rateio_cents, created_at) "
                        "VALUES (0, 1, 2, 3, 4, 5, 6, 21, 3, 6, 0, 0, 0, 0, 0, 0, 0, NOW())"
                    )
                )
                db.session.commit()
            db.session.rollback()

            with pytest.raises(sa.exc.IntegrityError):
                db.session.execute(
                    text(
                        "INSERT INTO draws "
                        "(contest, n1, n2, n3, n4, n5, n6, total_sum, even_count, "
                        "consecutive_count, winners_6, winners_5, winners_4, prize_cents, "
                        "accumulated_cents, quina_rateio_cents, quadra_rateio_cents, created_at) "
                        "VALUES (2, 1, 2, 10, 20, 30, 40, 103, 5, 0, 0, 0, 0, 0, 0, 0, 0, NOW())"
                    )
                )
                db.session.commit()
            db.session.rollback()

            db.session.execute(
                text(
                    "INSERT INTO draws "
                    "(contest, n1, n2, n3, n4, n5, n6, total_sum, even_count, "
                    "consecutive_count, winners_6, winners_5, winners_4, prize_cents, "
                    "accumulated_cents, quina_rateio_cents, quadra_rateio_cents, created_at) "
                    "VALUES (3, 1, 2, 10, 20, 30, 40, 103, 5, 2, 0, 0, 0, 0, 0, 0, 0, NOW())"
                )
            )
            db.session.rollback()

            db.session.execute(
                text(
                    "INSERT INTO draws "
                    "(contest, n1, n2, n3, n4, n5, n6, total_sum, even_count, "
                    "consecutive_count, winners_6, winners_5, winners_4, prize_cents, "
                    "accumulated_cents, quina_rateio_cents, quadra_rateio_cents, created_at) "
                    "VALUES "
                    "(4, 1, 3, 5, 7, 9, 11, 36, 0, 0, 0, 0, 0, 0, 0, 0, 0, NOW()), "
                    "(5, 1, 2, 3, 4, 5, 6, 21, 3, 6, 0, 0, 0, 0, 0, 0, 0, NOW())"
                )
            )
            db.session.rollback()

            with pytest.raises(sa.exc.IntegrityError):
                db.session.execute(
                    text(
                        "INSERT INTO generated_bets "
                        "(numbers_csv, quantity, score, created_at) "
                        "VALUES ('1,2,3,4,5,6', 5, 0, NOW())"
                    )
                )
                db.session.commit()
            db.session.rollback()

            check = app.test_cli_runner().invoke(args=["db", "check"])
            assert check.exit_code == 0, check.output

            db.session.remove()
            db.engine.dispose()
    finally:
        _run_as_admin(
            server_url,
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{temp_db_name}' AND pid <> pg_backend_pid()",
        )
        _run_as_admin(server_url, f'DROP DATABASE IF EXISTS "{temp_db_name}"')


def _run_as_admin(server_url: sa.engine.URL, statement: str) -> None:
    """Executa uma instrução administrativa (CREATE/DROP DATABASE) fora de
    transação, conectando-se ao banco de manutenção `postgres` do mesmo
    servidor usado pela suíte de testes."""
    engine = sa.create_engine(server_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(text(statement))
    finally:
        engine.dispose()
