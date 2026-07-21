from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import inspect, text

from app import create_app, db
from app.models import Config, Draw, GeneratedBet
from app.core.numbers import draw_parameters


def _config(database_path: Path, backup_dir: Path, *, initialize: bool) -> dict[str, object]:
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}",
        "DATABASE_BACKUP_DIR": str(backup_dir),
        "AUTO_INITIALIZE_DATABASE": initialize,
    }


def test_fresh_database_is_created_from_migrations(tmp_path: Path) -> None:
    database_path = tmp_path / "fresh.db"
    backup_dir = tmp_path / "backups"

    app = create_app(_config(database_path, backup_dir, initialize=True))

    with app.app_context():
        tables = set(inspect(db.engine).get_table_names())
        revision = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert {"alembic_version", "config", "draws", "generated_bets"} <= tables
        assert revision == "0002_repair_indexes"
    check = app.test_cli_runner().invoke(args=["db", "check"])
    assert check.exit_code == 0, check.output
    assert not backup_dir.exists()


def test_legacy_database_is_backed_up_stamped_and_preserved(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.db"
    backup_dir = tmp_path / "backups"
    legacy_app = create_app(_config(database_path, backup_dir, initialize=False))
    with legacy_app.app_context():
        db.create_all()
        db.session.add(Config(key="bet_quantity", value="8"))
        db.session.add(
            Draw(
                contest=123,
                n1=1,
                n2=2,
                n3=3,
                n4=4,
                n5=5,
                n6=6,
                **draw_parameters([1, 2, 3, 4, 5, 6]),
            )
        )
        db.session.add(GeneratedBet(generation_id=1, numbers_csv="1,2,3,4,5,6", quantity=6, score=0))
        db.session.commit()
        db.session.execute(text("DROP INDEX ix_generated_bets_generation_id"))
        db.session.commit()
        db.session.remove()
        db.engine.dispose()

    upgraded_app = create_app(_config(database_path, backup_dir, initialize=True))
    with upgraded_app.app_context():
        assert Draw.query.filter_by(contest=123).count() == 1
        assert GeneratedBet.query.filter_by(generation_id=1).count() == 1
        assert Config.query.filter_by(key="bet_quantity").one().value == "8"
        assert db.session.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0002_repair_indexes"
        indexes = {index["name"] for index in inspect(db.engine).get_indexes("generated_bets")}
        assert "ix_generated_bets_generation_id" in indexes

    backups = list(backup_dir.glob("legacy-*-baseline.db"))
    assert len(backups) == 1
    assert backups[0].stat().st_size > 0
    with sqlite3.connect(backups[0]) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("SELECT COUNT(*) FROM draws").fetchone() == (1,)

    create_app(_config(database_path, backup_dir, initialize=True))
    assert list(backup_dir.glob("*.db")) == backups
