param([switch]$Confirm)

$ErrorActionPreference = "Stop"
if (-not $Confirm) { throw "Operação administrativa: execute novamente com -Confirm." }
$projectRoot = Split-Path -Parent $PSScriptRoot
$docker = "C:\Users\MSPA\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe"
Push-Location $projectRoot
try {
    & "$PSScriptRoot\backup_postgres.ps1"
    if ($LASTEXITCODE -ne 0) { throw "Backup PostgreSQL falhou." }
    $backup = Get-ChildItem "instance\backups\mega_sena-postgres-*.dump" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $backup -or $backup.Length -eq 0) { throw "Backup válido não encontrado." }
    & $docker compose --env-file .env.docker cp $backup.FullName "postgres:/tmp/baseline-adoption.dump"
    & $docker compose --env-file .env.docker exec -T postgres pg_restore -l /tmp/baseline-adoption.dump
    & $docker compose --env-file .env.docker exec -T postgres rm -f /tmp/baseline-adoption.dump
    if ($LASTEXITCODE -ne 0) { throw "Validação do backup por pg_restore falhou." }
    # Imagem imutável recém-construída: não depende de bind mount nem reinicia
    # o serviço em execução antes de o banco já estar marcado no baseline.
    & $docker compose -f compose.yaml --env-file .env.docker build app
    if ($LASTEXITCODE -ne 0) { throw "Build da imagem administrativa falhou." }
    & $docker compose -f compose.yaml --env-file .env.docker run --rm --no-deps --entrypoint python app -m scripts.verify_baseline_schema
    if ($LASTEXITCODE -ne 0) { throw "Schema incompatível; stamp recusado." }
    # stamp altera apenas alembic_version; não executa DDL nem toca registros.
    & $docker compose -f compose.yaml --env-file .env.docker run --rm --no-deps --entrypoint flask app --app run.py db stamp --purge 20260803_baseline
    if ($LASTEXITCODE -ne 0) { throw "Não foi possível registrar o baseline." }
    & $docker compose -f compose.yaml --env-file .env.docker run --rm --no-deps --entrypoint python app -m scripts.verify_baseline_schema
    if ($LASTEXITCODE -ne 0) { throw "Verificação posterior ao stamp falhou." }
    Write-Output "Baseline adotado sem alteração de schema ou dados. Backup: $($backup.FullName)"
} finally { Pop-Location }
