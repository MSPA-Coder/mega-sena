param(
    [string]$OutputDirectory = "instance\backups"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectRoot ".env.docker"
$docker = "C:\Users\MSPA\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe"

if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Arquivo .env.docker não encontrado."
}
if (-not (Test-Path -LiteralPath $docker)) {
    throw "Docker CLI não encontrado em $docker."
}

$settings = @{}
Get-Content -LiteralPath $envFile | ForEach-Object {
    if ($_ -and -not $_.StartsWith("#")) {
        $name, $value = $_ -split "=", 2
        $settings[$name] = $value
    }
}
$database = $settings["POSTGRES_DB"]
$user = $settings["POSTGRES_USER"]
if (-not $database -or -not $user) {
    throw "POSTGRES_DB e POSTGRES_USER devem estar definidos em .env.docker."
}

$resolvedOutput = Join-Path $projectRoot $OutputDirectory
New-Item -ItemType Directory -Path $resolvedOutput -Force | Out-Null
$timestamp = Get-Date -Format "yyyyMMddTHHmmss"
$fileName = "mega_sena-postgres-$timestamp.dump"
$outputFile = Join-Path $resolvedOutput $fileName
$containerFile = "/tmp/$fileName"

Push-Location $projectRoot
try {
    & $docker compose --env-file .env.docker exec -T postgres `
        pg_dump -U $user -d $database -Fc -f $containerFile
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump falhou."
    }
    & $docker compose --env-file .env.docker cp `
        "postgres:$containerFile" $outputFile
    if ($LASTEXITCODE -ne 0) {
        throw "Não foi possível copiar o backup do contêiner."
    }
    & $docker compose --env-file .env.docker exec -T postgres `
        rm -f $containerFile
} finally {
    Pop-Location
}

$backup = Get-Item -LiteralPath $outputFile
if ($backup.Length -eq 0) {
    throw "O arquivo de backup foi criado vazio."
}
Write-Output "Backup PostgreSQL criado em $($backup.FullName)"
Write-Output "Tamanho: $($backup.Length) bytes"
