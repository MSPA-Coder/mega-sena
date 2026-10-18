#!/usr/bin/env bash
set -euo pipefail
: "${DELIVERY_APP_ID:?}" "${DELIVERY_POSTGRES_ID:?}"
app_id=$DELIVERY_APP_ID
compose=(docker compose -p mega-sena-runtime-ci -f compose.yaml -f compose.ci.yaml)
trap '"${compose[@]}" down --remove-orphans' EXIT
docker run --rm --read-only --tmpfs /tmp --entrypoint sh "$app_id" -ec '
  test "$(id -u)" != 0
  for path in /app /app/app /app/migrations; do test ! -w "$path"; done
  for path in /app/.secrets /app/.certs /app/.env /app/tests; do test ! -e "$path"; done
  for tool in gcc make wget ruff pytest mypy pip pip-audit; do ! command -v "$tool"; done
'
"${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 180 app
"${compose[@]}" exec -T app python -c 'import json, urllib.request; assert json.load(urllib.request.urlopen("http://127.0.0.1:5001/health"))["status"] == "ok"'
role=$("${compose[@]}" exec -T postgres psql -U mega_sena -d mega_sena -tAc \
    "select string_agg(distinct a.usename || ':' || r.rolsuper, ',') from pg_stat_activity a join pg_roles r on r.rolname=a.usename where a.datname=current_database() and a.application_name <> 'psql'")
test "$role" = "mega_sena_app:false"
