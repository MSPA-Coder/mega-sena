param(
    [string]$OutputPath = "dist\MegaSena-clean.zip",
    [switch]$IncludeData,
    [switch]$ListOnly
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ProjectName = Split-Path $ProjectRoot -Leaf
$FixedTimestamp = Get-Date "2000-01-01T00:00:00"

function Get-RelativePath {
    param(
        [string]$BasePath,
        [string]$TargetPath
    )

    $baseFullPath = [System.IO.Path]::GetFullPath($BasePath)
    $targetFullPath = [System.IO.Path]::GetFullPath($TargetPath)

    if (-not $baseFullPath.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $baseFullPath += [System.IO.Path]::DirectorySeparatorChar
    }

    $baseUri = New-Object System.Uri($baseFullPath)
    $targetUri = New-Object System.Uri($targetFullPath)
    $relativeUri = $baseUri.MakeRelativeUri($targetUri)

    return [System.Uri]::UnescapeDataString($relativeUri.ToString()).Replace("/", [System.IO.Path]::DirectorySeparatorChar)
}

$ExcludedDirectoryNames = @(
    ".git",
    ".idea",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "instance",
    "dist",
    "build",
    "htmlcov",
    ".coverage"
)

if (-not $IncludeData) {
    $ExcludedDirectoryNames += "data"
}

$ExcludedFilePatterns = @(
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.log",
    "*.tmp",
    "*.temp",
    "*.bak",
    "*.swp",
    "*.swo",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.db-journal",
    "*.sqlite-journal",
    "*.xls",
    "*.xlsx",
    ".coverage",
    "coverage.xml",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini"
)

function Test-ExcludedPath {
    param([System.IO.FileSystemInfo]$Item)

    $relativePath = Get-RelativePath -BasePath $ProjectRoot -TargetPath $Item.FullName
    $parts = $relativePath -split '[\\/]'

    foreach ($part in $parts) {
        if ($ExcludedDirectoryNames -contains $part) {
            return $true
        }
    }

    if (-not $Item.PSIsContainer) {
        foreach ($pattern in $ExcludedFilePatterns) {
            if ($Item.Name -like $pattern) {
                return $true
            }
        }
    }

    return $false
}

$items = Get-ChildItem -LiteralPath $ProjectRoot -Recurse -Force |
    Where-Object { -not (Test-ExcludedPath $_) } |
    Sort-Object FullName

if ($ListOnly) {
    $items |
        Where-Object { -not $_.PSIsContainer } |
        ForEach-Object { Get-RelativePath -BasePath $ProjectRoot -TargetPath $_.FullName }
    exit 0
}

$resolvedOutputPath = if ([System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath
} else {
    Join-Path $ProjectRoot $OutputPath
}

$outputDirectory = Split-Path $resolvedOutputPath -Parent
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

if (Test-Path -LiteralPath $resolvedOutputPath) {
    Remove-Item -LiteralPath $resolvedOutputPath -Force
}

$stagingRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("{0}-cleanzip-{1}" -f $ProjectName, [guid]::NewGuid())
$stagingProject = Join-Path $stagingRoot $ProjectName
New-Item -ItemType Directory -Force -Path $stagingProject | Out-Null

try {
    foreach ($item in $items) {
        $relativePath = Get-RelativePath -BasePath $ProjectRoot -TargetPath $item.FullName
        $targetPath = Join-Path $stagingProject $relativePath

        if ($item.PSIsContainer) {
            New-Item -ItemType Directory -Force -Path $targetPath | Out-Null
        } else {
            $targetDirectory = Split-Path $targetPath -Parent
            New-Item -ItemType Directory -Force -Path $targetDirectory | Out-Null
            Copy-Item -LiteralPath $item.FullName -Destination $targetPath -Force
        }
    }

    Get-ChildItem -LiteralPath $stagingProject -Recurse -Force | ForEach-Object {
        $_.CreationTime = $FixedTimestamp
        $_.LastWriteTime = $FixedTimestamp
        $_.LastAccessTime = $FixedTimestamp

        if (-not $_.PSIsContainer) {
            $_.Attributes = [System.IO.FileAttributes]::Archive
        }
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $stagingProject,
        $resolvedOutputPath,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $true
    )

    Write-Host "ZIP limpo gerado em: $resolvedOutputPath"
} finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}
