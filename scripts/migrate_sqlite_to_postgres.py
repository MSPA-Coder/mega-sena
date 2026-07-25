"""Migra o SQLite legado para PostgreSQL e confere a carga tabela a tabela."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

import sqlalchemy as sa


TABLES = ("config", "draws", "generated_bets")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--confirm-reset-postgres", action="store_true")
    return parser.parse_args()


def _convert(value: object, column: sa.Column[object]) -> object:
    if value is None or not isinstance(value, str):
        return value
    if isinstance(column.type, sa.DateTime):
        return datetime.fromisoformat(value)
    if isinstance(column.type, sa.Date):
        return date.fromisoformat(value)
    return value


def _source_rows(
    connection: sqlite3.Connection, table: sa.Table
) -> list[dict[str, object]]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(f'SELECT * FROM "{table.name}" ORDER BY id').fetchall()
    return [
        {
            column.name: _convert(row[column.name], column)
            for column in table.columns
        }
        for row in rows
    ]


def main() -> int:
    args = _parse_args()
    if not args.confirm_reset_postgres:
        raise SystemExit("Use --confirm-reset-postgres para autorizar a substituição da carga.")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise SystemExit("DATABASE_URL deve apontar para PostgreSQL.")
    if not args.sqlite.is_file():
        raise SystemExit(f"SQLite não encontrado: {args.sqlite}")

    target_engine = sa.create_engine(database_url, pool_pre_ping=True)
    metadata = sa.MetaData()
    metadata.reflect(bind=target_engine, only=list(TABLES))
    missing = set(TABLES) - set(metadata.tables)
    if missing:
        raise SystemExit("Tabelas ausentes no PostgreSQL: " + ", ".join(sorted(missing)))

    sqlite_uri = f"file:{args.sqlite.as_posix()}?mode=ro&immutable=1"
    report: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(args.sqlite),
        "target": target_engine.url.render_as_string(hide_password=True),
        "tables": {},
    }
    with sqlite3.connect(sqlite_uri, uri=True) as source, target_engine.begin() as target:
        for table_name in reversed(TABLES):
            target.execute(metadata.tables[table_name].delete())

        for table_name in TABLES:
            table = metadata.tables[table_name]
            rows = _source_rows(source, table)
            if rows:
                for start in range(0, len(rows), 500):
                    target.execute(table.insert(), rows[start : start + 500])
            source_count = len(rows)
            target_count = target.scalar(sa.select(sa.func.count()).select_from(table))
            source_ids = [int(row["id"]) for row in rows]
            target_min, target_max = target.execute(
                sa.select(sa.func.min(table.c.id), sa.func.max(table.c.id))
            ).one()
            expected_min = min(source_ids) if source_ids else None
            expected_max = max(source_ids) if source_ids else None
            if (target_count, target_min, target_max) != (
                source_count,
                expected_min,
                expected_max,
            ):
                raise RuntimeError(f"Conferência divergente na tabela {table_name}.")
            report["tables"][table_name] = {
                "source_count": source_count,
                "target_count": target_count,
                "source_min_id": expected_min,
                "target_min_id": target_min,
                "source_max_id": expected_max,
                "target_max_id": target_max,
            }
            target.execute(
                sa.text(
                    "SELECT setval("
                    f"pg_get_serial_sequence('{table_name}', 'id'), "
                    f"COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {table_name}"
                )
            )

    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
