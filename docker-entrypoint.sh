#!/bin/sh
# Etapa controlada, separada da aplicação: aplica as migrações pendentes ANTES
# de iniciar o processo do servidor (gunicorn em produção, `python run.py` em
# desenvolvimento). A aplicação (`app/__init__.py::create_app`) nunca faz isso
# por conta própria — ver docs/architecture.md e AGENTS.md.
#
# No Compose quem migra é o serviço `migrate`, com o papel administrativo; o
# `app` conecta com o papel restrito, que não tem DDL, e por isso sobe com
# MEGA_SENA_MIGRAR_NA_SUBIDA=0. Fora do Compose o padrão continua migrando.
set -e

if [ "${MEGA_SENA_MIGRAR_NA_SUBIDA:-1}" = "1" ]; then
    echo "[entrypoint] Aplicando migracoes pendentes (flask db upgrade)..."
    flask --app run.py db upgrade
fi

echo "[entrypoint] Iniciando: $*"
exec "$@"
