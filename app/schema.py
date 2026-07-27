from __future__ import annotations

from pathlib import Path

from flask import Flask
from flask_migrate import upgrade


def _migration_directory(app: Flask) -> Path:
    return Path(app.root_path).resolve().parent / "migrations"


def ensure_database_schema(app: Flask) -> None:
    """Cria ou atualiza o schema do banco até a revisão mais recente do Alembic.

    PostgreSQL é o único backend suportado. Esta função nunca é chamada
    automaticamente por `create_app()`: aplicar migrações é uma etapa
    controlada e separada da inicialização da aplicação (entrypoint do
    container, comando manual `flask db upgrade`, ou a suíte de testes, que
    aplica o schema uma única vez por sessão contra um PostgreSQL
    descartável). Backups de dados ficam a cargo de
    `pg_dump`/`scripts/backup_postgres.ps1`.
    """
    directory = _migration_directory(app)
    if not directory.is_dir():
        raise RuntimeError(f"Diretório de migrações ausente: {directory}")
    upgrade(directory=str(directory))
