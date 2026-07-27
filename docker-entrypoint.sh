#!/bin/sh
# Etapa controlada, separada da aplicação: aplica migrações pendentes e
# garante dados de aplicação ANTES de iniciar o processo do servidor
# (gunicorn em produção, `python run.py` em desenvolvimento). A aplicação
# (`app/__init__.py::create_app`) nunca faz isso por conta própria — ver
# docs/architecture.md e AGENTS.md.
set -e

echo "[entrypoint] Aplicando migracoes pendentes (flask db upgrade)..."
flask --app run.py db upgrade

echo "[entrypoint] Garantindo dados de aplicacao (flask seed-defaults)..."
flask --app run.py seed-defaults

echo "[entrypoint] Iniciando: $*"
exec "$@"
