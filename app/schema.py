from __future__ import annotations

from pathlib import Path

from flask import Flask
from flask_migrate import upgrade


def _migration_directory(app: Flask) -> Path:
    return Path(app.root_path).resolve().parent / "migrations"


def ensure_database_schema(app: Flask) -> None:
    """Cria ou atualiza o schema do banco até a revisão mais recente do Alembic.

    O PostgreSQL é o único backend de execução suportado (Docker Compose); o
    SQLite continua disponível como banco efêmero da suíte de testes isolada.
    Backups de dados ficam a cargo de `pg_dump`/`scripts/backup_postgres.ps1`,
    fora do processo de inicialização da aplicação.
    """
    directory = _migration_directory(app)
    if not directory.is_dir():
        raise RuntimeError(f"Diretório de migrações ausente: {directory}")
    upgrade(directory=str(directory))
