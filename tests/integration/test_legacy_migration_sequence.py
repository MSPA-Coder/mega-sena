from __future__ import annotations

import sys
from datetime import datetime, timezone

import sqlalchemy as sa
import pytest

from app import db
from app.models import Config, Draw, GeneratedBet
from scripts import migrate_sqlite_to_postgres
from tests.support import get_test_database_url, make_app


def _create_legacy_database(path, generation_ids: list[int | None]) -> None:
    """Cria uma fonte SQLite mínima com o formato legado esperado pelo migrador."""
    engine = sa.create_engine(f"sqlite:///{path}")

    def register_sqlite_functions(dbapi_connection, _connection_record) -> None:
        # O schema operacional espelha CHECKs PostgreSQL. A fonte SQLite é
        # criada apenas para testar a importação legada explícita.
        dbapi_connection.create_function("GREATEST", -1, max)

    sa.event.listen(engine, "connect", register_sqlite_functions)
    try:
        Config.__table__.create(engine)
        Draw.__table__.create(engine)
        GeneratedBet.__table__.create(engine)
        rows = [
            {
                "id": index,
                "generation_id": generation_id,
                "numbers_csv": "1,2,3,4,5,6",
                "quantity": 6,
                "score": 0,
                "created_at": datetime.now(timezone.utc),
            }
            for index, generation_id in enumerate(generation_ids, start=1)
        ]
        if not rows:
            return
        with engine.begin() as connection:
            connection.execute(
                GeneratedBet.__table__.insert(),
                rows,
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("generation_ids", "expected_next_generation_id"),
    [([1, 7], 8), ([], 1), ([None], 1)],
)
def test_legacy_migration_advances_generation_id_sequence(
    tmp_path, monkeypatch, generation_ids: list[int | None], expected_next_generation_id: int
) -> None:
    """O próximo lote não pode reutilizar um identificador importado do SQLite."""
    app = make_app()
    sqlite_path = tmp_path / "legacy.db"
    report_path = tmp_path / "migration-report.json"
    _create_legacy_database(sqlite_path, generation_ids)
    monkeypatch.setenv("DATABASE_URL", get_test_database_url())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "migrate_sqlite_to_postgres.py",
            "--sqlite",
            str(sqlite_path),
            "--report",
            str(report_path),
            "--confirm-reset-postgres",
        ],
    )

    with app.app_context():
        assert migrate_sqlite_to_postgres.main() == 0
        next_generation_id = db.session.scalar(
            sa.text("SELECT nextval('generated_bets_generation_id_seq')")
        )

    assert next_generation_id == expected_next_generation_id
    assert report_path.is_file()
