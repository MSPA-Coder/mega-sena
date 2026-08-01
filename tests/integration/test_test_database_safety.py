from __future__ import annotations

import sqlalchemy as sa

from app import db
from tests.support import _reset_test_database, get_test_database_url, make_app


def test_database_reset_preserves_tables_outside_the_application() -> None:
    database_url = get_test_database_url()
    app = make_app(database_url)

    with app.app_context():
        db.session.execute(
            sa.text(
                "CREATE TABLE IF NOT EXISTS external_audit "
                "(id integer PRIMARY KEY, note text NOT NULL)"
            )
        )
        db.session.execute(sa.text("DELETE FROM external_audit"))
        db.session.execute(
            sa.text("INSERT INTO external_audit (id, note) VALUES (1, 'preserve')")
        )
        db.session.commit()
        db.session.remove()

    try:
        _reset_test_database(database_url)
        engine = sa.create_engine(database_url)
        try:
            with engine.connect() as connection:
                assert connection.scalar(
                    sa.text("SELECT count(*) FROM external_audit")
                ) == 1
        finally:
            engine.dispose()
    finally:
        cleanup_engine = sa.create_engine(database_url)
        try:
            with cleanup_engine.begin() as connection:
                connection.execute(sa.text("DROP TABLE IF EXISTS external_audit"))
        finally:
            cleanup_engine.dispose()
