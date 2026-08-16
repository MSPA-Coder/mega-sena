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
$temporaryFile = "$outputFile.partial"

try {
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo.FileName = $docker
    $process.StartInfo.WorkingDirectory = $projectRoot
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true

    foreach ($argument in @(
        "compose", "--env-file", ".env.docker", "exec", "-T", "postgres",
        "pg_dump", "-U", $user, "-d", $database, "-Fc"
    )) {
        [void] $process.StartInfo.ArgumentList.Add($argument)
    }

    if (-not $process.Start()) {
        throw "Não foi possível iniciar pg_dump no contêiner."
    }

    $errorTask = $process.StandardError.ReadToEndAsync()
    $output = [System.IO.File]::Open(
        $temporaryFile,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
    try {
        $process.StandardOutput.BaseStream.CopyTo($output)
    } finally {
        $output.Dispose()
    }
    $process.WaitForExit()
    [void] $errorTask.GetAwaiter().GetResult()

    if ($process.ExitCode -ne 0) {
        throw "pg_dump falhou."
    }

    $backup = Get-Item -LiteralPath $temporaryFile
    if ($backup.Length -eq 0) {
        throw "O arquivo de backup foi criado vazio."
    }

    Move-Item -LiteralPath $temporaryFile -Destination $outputFile
} finally {
    if (Test-Path -LiteralPath $temporaryFile) {
        Remove-Item -LiteralPath $temporaryFile -Force
    }
}

$backup = Get-Item -LiteralPath $outputFile
Write-Output "Backup PostgreSQL criado em $($backup.FullName)"
Write-Output "Tamanho: $($backup.Length) bytes"
