# Shellwash remote bootstrap (Windows).
# irm https://raw.githubusercontent.com/tonykorycki/shellwash/main/install-remote.ps1 | iex

$ErrorActionPreference = 'Stop'

$repo = if ($env:SHELLWASH_REPO) { $env:SHELLWASH_REPO } else { 'https://github.com/tonykorycki/shellwash.git' }
$dir  = if ($env:SHELLWASH_DIR)  { $env:SHELLWASH_DIR }  else { Join-Path $env:LOCALAPPDATA 'shellwash' }
$ref  = if ($env:SHELLWASH_REF)  { $env:SHELLWASH_REF }  else { 'main' }

Write-Host 'Shellwash bootstrap' -ForegroundColor Cyan
Write-Host "  repo: $repo"
Write-Host "  dir:  $dir"
Write-Host "  ref:  $ref"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host '  git not found — install Git for Windows first' -ForegroundColor Red
    exit 1
}

if (Test-Path (Join-Path $dir '.git')) {
    Write-Host '  updating existing install…'
    git -C $dir fetch --depth 1 origin $ref 2>$null
    if ($LASTEXITCODE -ne 0) { git -C $dir fetch origin }
    git -C $dir checkout -q $ref 2>$null
    if ($LASTEXITCODE -ne 0) { git -C $dir pull --ff-only }
} else {
    Write-Host '  cloning…'
    New-Item -ItemType Directory -Force -Path (Split-Path $dir -Parent) | Out-Null
    git clone --depth 1 --branch $ref $repo $dir 2>$null
    if ($LASTEXITCODE -ne 0) {
        git clone $repo $dir
        git -C $dir checkout -q $ref
    }
}

& (Join-Path $dir 'install.ps1')
