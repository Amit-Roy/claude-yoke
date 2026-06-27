<#
  Launches Claude TUI using the project virtual environment.
  Creates the venv and installs dependencies on first run.
#>
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$py = Join-Path $root '.venv\Scripts\python.exe'

if (-not (Test-Path $py)) {
    Write-Host 'Creating virtual environment…' -ForegroundColor Cyan
    python -m venv (Join-Path $root '.venv')
    & $py -m pip install --upgrade pip --quiet
    & $py -m pip install -r (Join-Path $root 'requirements.txt') --quiet
}

& $py -m claude_tui @args
