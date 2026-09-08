from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from flask import current_app

config = context.config
if config.config_file_name:
    # `disable_existing_loggers=False` não é detalhe: o padrão do `fileConfig`
    # é True, e ele DESLIGA todo logger que já exista no processo -- inclusive
    # o da aplicação.
    #
    # No contêiner isso nunca apareceu, porque o `docker-entrypoint.sh` roda
    # `flask db upgrade` como processo separado, que morre em seguida. Aparece
    # quando a migração é aplicada no mesmo processo: foi assim que a fixture
    # `app_com_banco` da suíte fez `app/__init__.py` parar de registrar o
    # WARNING de `SECRET_KEY` para todos os testes seguintes.
    #
    # Manter os loggers existentes é a recomendação da própria documentação do
    # Alembic para este caso, e não deixa de configurar nada: os loggers
    # declarados no `alembic.ini` continuam sendo aplicados.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = current_app.extensions["migrate"].db.metadata


def _engine():
    return current_app.extensions["migrate"].db.engine


def run_migrations_offline() -> None:
    context.configure(
        url=str(_engine().url).replace("%", "%%"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configure_args = current_app.extensions["migrate"].configure_args
    with _engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, **configure_args)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
