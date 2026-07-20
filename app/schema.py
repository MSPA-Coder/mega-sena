from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from flask import Flask
from flask_migrate import stamp, upgrade
from sqlalchemy import inspect, text

from . import db


_log = logging.getLogger(__name__)
_DOMAIN_TABLES = frozenset({"config", "draws", "generated_bets"})
_LEGACY_BASELINE_REVISION = "0001_initial"


def _migration_directory(app: Flask) -> Path:
    return Path(app.root_path).resolve().parent / "migrations"


def _migration_head(directory: Path) -> str:
    config = AlembicConfig(str(directory / "alembic.ini"))
    config.set_main_option("script_location", str(directory))
    head = ScriptDirectory.from_config(config).get_current_head()
    if not head:
        raise RuntimeError("O repositório de migrações não possui uma revisão principal.")
    return head


def _sqlite_database_path() -> Path | None:
    url = db.engine.url
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return None
    return Path(url.database).resolve()


def backup_sqlite_database(app: Flask, reason: str) -> Path | None:
    """Cria um snapshot consistente do SQLite usando a API nativa de backup."""
    source_path = _sqlite_database_path()
    if source_path is None or not source_path.exists() or source_path.stat().st_size == 0:
        return None

    configured_dir = app.config.get("DATABASE_BACKUP_DIR")
    backup_dir = Path(str(configured_dir)).resolve() if configured_dir else source_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe_reason = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in reason)
    backup_path = backup_dir / f"{source_path.stem}-{timestamp}-{safe_reason}.db"

    source = sqlite3.connect(source_path)
    target = sqlite3.connect(backup_path)
    try:
        source.backup(target)
        integrity = target.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise RuntimeError("O backup do banco não passou na verificação de integridade.")
    finally:
        target.close()
        source.close()

    _log.info("Backup do banco criado em %s antes de %s.", backup_path, reason)
    return backup_path


def _validate_legacy_schema() -> None:
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    missing_tables = _DOMAIN_TABLES - tables
    if missing_tables:
        raise RuntimeError(
            "Banco legado incompatível: tabelas ausentes: " + ", ".join(sorted(missing_tables))
        )
    for table_name in _DOMAIN_TABLES:
        expected = {column.name for column in db.metadata.tables[table_name].columns}
        actual = {column["name"] for column in inspector.get_columns(table_name)}
        if actual != expected:
            missing = expected - actual
            extra = actual - expected
            details = []
            if missing:
                details.append("ausentes=" + ",".join(sorted(missing)))
            if extra:
                details.append("extras=" + ",".join(sorted(extra)))
            raise RuntimeError(f"Banco legado incompatível na tabela {table_name}: {'; '.join(details)}")


def ensure_database_schema(app: Flask) -> dict[str, str | None]:
    """Cria, reconhece ou atualiza o schema antes do uso da aplicação."""
    directory = _migration_directory(app)
    if not directory.is_dir():
        raise RuntimeError(f"Diretório de migrações ausente: {directory}")

    if _sqlite_database_path() is None:
        db.create_all()
        return {"action": "create_all", "backup": None}

    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    if not tables:
        upgrade(directory=str(directory))
        return {"action": "created", "backup": None}

    head = _migration_head(directory)
    if "alembic_version" not in tables:
        _validate_legacy_schema()
        backup = backup_sqlite_database(app, "baseline")
        stamp(directory=str(directory), revision=_LEGACY_BASELINE_REVISION)
        upgrade(directory=str(directory), revision="head")
        return {"action": "adopted", "backup": str(backup) if backup else None}

    current = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    if current == head:
        return {"action": "current", "backup": None}

    backup = backup_sqlite_database(app, f"upgrade-{current or 'unknown'}-to-{head}")
    upgrade(directory=str(directory), revision="head")
    return {"action": "upgraded", "backup": str(backup) if backup else None}
