$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$Python = ".\.venv\Scripts\python.exe"

& $Python -m ruff check .
& $Python -m ruff format --check .
& $Python -m mypy src
& $Python -m pytest
