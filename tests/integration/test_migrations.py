from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect, text

from app import create_app, db


def _config(database_path: Path, *, initialize: bool) -> dict[str, object]:
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}",
        "AUTO_INITIALIZE_DATABASE": initialize,
    }


def test_fresh_database_is_created_from_migrations(tmp_path: Path) -> None:
    """Contrato independente de dialeto: ensure_database_schema() precisa
    criar o schema completo e deixar o banco na revisão mais recente do
    Alembic, seja em SQLite (usado aqui por não exigir infraestrutura) ou em
    PostgreSQL (validado à parte pelo job postgres-smoke do CI, que roda
    `flask db upgrade` contra um Postgres real)."""
    database_path = tmp_path / "fresh.db"

    app = create_app(_config(database_path, initialize=True))

    with app.app_context():
        tables = set(inspect(db.engine).get_table_names())
        revision = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert {"alembic_version", "config", "draws", "generated_bets"} <= tables
        assert revision == "0003_expand_money"
    check = app.test_cli_runner().invoke(args=["db", "check"])
    assert check.exit_code == 0, check.output
