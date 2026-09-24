[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$EnvFile = (Join-Path $PSScriptRoot "..\.env.docker"),
    [string]$SecretsDirectory = (Join-Path $PSScriptRoot "..\.secrets"),
    [switch]$Force,
    [switch]$RemoveLegacyValues
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw "Arquivo de ambiente não encontrado: $EnvFile"
}

$legacyValues = @{}
foreach ($line in Get-Content -LiteralPath $EnvFile) {
    if ($line -match '^\s*(POSTGRES_PASSWORD|SECRET_KEY)=(.*)$') {
        $legacyValues[$Matches[1]] = $Matches[2].Trim()
    }
}

function New-SecretValue {
    $bytes = [byte[]]::new(48)
    # `RandomNumberGenerator::Fill` só existe no PowerShell 7; `Create()` e
    # `GetBytes` funcionam também no Windows PowerShell 5.1.
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Write-SecretFile {
    param(
        [string]$Name,
        [string]$LegacyName
    )

    $target = Join-Path $SecretsDirectory $Name
    if ((Test-Path -LiteralPath $target) -and -not $Force) {
        return [pscustomobject]@{ Name = $Name; Written = $false }
    }

    $value = $legacyValues[$LegacyName]
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = New-SecretValue
    }

    if ($PSCmdlet.ShouldProcess($target, "gravar segredo")) {
        $temporary = Join-Path $SecretsDirectory ".${Name}.$([guid]::NewGuid().ToString('N')).tmp"
        try {
            [System.IO.File]::WriteAllText(
                $temporary,
                $value,
                [System.Text.UTF8Encoding]::new($false)
            )
            Move-Item -LiteralPath $temporary -Destination $target -Force
        }
        finally {
            Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
        }
    }
    return [pscustomobject]@{ Name = $Name; Written = $true }
}

if ($PSCmdlet.ShouldProcess($SecretsDirectory, "criar diretório de segredos")) {
    New-Item -ItemType Directory -Path $SecretsDirectory -Force | Out-Null
}

$postgresResult = Write-SecretFile -Name "postgres_password.txt" -LegacyName "POSTGRES_PASSWORD"
$sessionResult = Write-SecretFile -Name "secret_key.txt" -LegacyName "SECRET_KEY"
# Senha do papel restrito da aplicação: ninguém a escolhe, o `db-provision` a
# aplica ao papel a cada subida.
$appResult = Write-SecretFile -Name "postgres_app_password.txt" -LegacyName "POSTGRES_APP_PASSWORD"
foreach ($result in @($postgresResult, $sessionResult, $appResult)) {
    $status = if ($result.Written) { "Provisionado" } else { "Preservado" }
    Write-Output "${status}: .secrets/$($result.Name)"
}

if ($RemoveLegacyValues) {
    $requiredSecretFiles = @(
        (Join-Path $SecretsDirectory "postgres_password.txt"),
        (Join-Path $SecretsDirectory "secret_key.txt")
    )
    foreach ($secretFile in $requiredSecretFiles) {
        if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf) -or
            (Get-Item -LiteralPath $secretFile).Length -eq 0) {
            throw "Recusei remover valores legados: um arquivo de segredo está ausente ou vazio."
        }
    }
    $remaining = Get-Content -LiteralPath $EnvFile | Where-Object {
        $_ -notmatch '^\s*(POSTGRES_PASSWORD|SECRET_KEY)='
    }
    if ($PSCmdlet.ShouldProcess($EnvFile, "remover valores legados de segredo")) {
        $envDirectory = Split-Path -Parent ([System.IO.Path]::GetFullPath($EnvFile))
        $temporaryEnv = Join-Path $envDirectory ".env.$([guid]::NewGuid().ToString('N')).tmp"
        try {
            [System.IO.File]::WriteAllLines(
                $temporaryEnv,
                $remaining,
                [System.Text.UTF8Encoding]::new($false)
            )
            Move-Item -LiteralPath $temporaryEnv -Destination $EnvFile -Force
        }
        finally {
            Remove-Item -LiteralPath $temporaryEnv -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Output "Valores legados removidos de $([System.IO.Path]::GetFileName($EnvFile))."
}

Write-Output "Concluído. Nenhum valor de segredo foi exibido."
