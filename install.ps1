# ═══════════════════════════════════════════════════════════════════════
#  bedazzle — installer
#  Clone the repo anywhere, run:  .\install.ps1
#  Sets up the venv and wires bedazzle into your PowerShell profile.
#  Idempotent: safe to run again. Undo: delete the marked block in $PROFILE.
# ═══════════════════════════════════════════════════════════════════════

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

Write-Host "bedazzle installer" -ForegroundColor Cyan
Write-Host "  repo: $root"

# 1. python venv
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { Write-Host "  python not found on PATH — install Python 3.10+ first" -ForegroundColor Red; exit 1 }
if (-not (Test-Path "$root\.venv\Scripts\python.exe")) {
    Write-Host "  creating venv..."
    python -m venv "$root\.venv"
}
Write-Host "  installing requirements..."
& "$root\.venv\Scripts\python.exe" -m pip install --quiet -r "$root\requirements.txt"

# 2. profile block
$prof = $PROFILE
$profDir = Split-Path $prof -Parent
if (-not (Test-Path $profDir)) { New-Item -ItemType Directory -Force $profDir | Out-Null }
if (-not (Test-Path $prof)) { New-Item -ItemType File $prof | Out-Null }

$content = Get-Content $prof -Raw -ErrorAction SilentlyContinue
if ($content -and ($content -match '>>> bedazzle >>>' -or $content -match 'ascii-dreams bedazzle')) {
    Write-Host "  profile block already present — skipped"
} else {
    Copy-Item $prof "$prof.bak-before-bedazzle" -ErrorAction SilentlyContinue
    $block = @"


# >>> bedazzle >>>
if (Test-Path "$root\bedazzle.ps1") {
    . "$root\bedazzle.ps1"
}
# <<< bedazzle <<<
"@
    Add-Content -Path $prof -Value $block -Encoding UTF8
    Write-Host "  profile block appended to $prof (backup: .bak-before-bedazzle)"
}

Write-Host ""
Write-Host "done. open a new tab, then try:" -ForegroundColor Green
Write-Host "  bedazzle      feature toggles"
Write-Host "  buddy         pet roster + gacha"
Write-Host "  fetch         system panel"
Write-Host "  lava          corner metaballs lamp"
Write-Host "  termbg on     living background (evolves per command)"
