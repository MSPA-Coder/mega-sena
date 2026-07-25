"""Smoke test transacional do backend PostgreSQL."""

from __future__ import annotations

from sqlalchemy import insert, select

from app import create_app
from app.extensions import db
from app.models import Config, Draw, GeneratedBet


def main() -> int:
    app = create_app()
    with app.app_context():
        if db.engine.url.get_backend_name() != "postgresql":
            raise RuntimeError("A aplicação não está conectada ao PostgreSQL.")
        counts = {
            "config": db.session.scalar(select(db.func.count()).select_from(Config)),
            "draws": db.session.scalar(select(db.func.count()).select_from(Draw)),
            "generated_bets": db.session.scalar(
                select(db.func.count()).select_from(GeneratedBet)
            ),
        }
        if not counts["config"] or not counts["draws"]:
            raise RuntimeError("Os dados essenciais migrados não foram encontrados.")

        connection = db.engine.connect()
        transaction = connection.begin()
        try:
            connection.execute(
                insert(Config).values(
                    key="__postgres_smoke_rollback__", value="temporary"
                )
            )
            transaction.rollback()
        finally:
            connection.close()
        if Config.query.filter_by(key="__postgres_smoke_rollback__").count():
            raise RuntimeError("O rollback transacional não foi respeitado.")

        print(
            "PostgreSQL OK:",
            " ".join(f"{name}={count}" for name, count in counts.items()),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
