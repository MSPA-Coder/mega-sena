#!/bin/sh
# Etapa controlada, separada da aplicação: aplica as migrações pendentes ANTES
# de iniciar o processo do servidor (gunicorn em produção, `python run.py` em
# desenvolvimento). A aplicação (`app/__init__.py::create_app`) nunca faz isso
# por conta própria — ver docs/architecture.md e AGENTS.md.
set -e

echo "[entrypoint] Aplicando migracoes pendentes (flask db upgrade)..."
flask --app run.py db upgrade

echo "[entrypoint] Iniciando: $*"
exec "$@"
