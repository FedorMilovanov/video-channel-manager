[CmdletBinding()]
param(
    [ValidateSet("Plan", "Apply")]
    [string]$Mode = "Plan",

    [switch]$Execute
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $false

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Repo = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Repo

$env:VCM_DATA_DIR = Join-Path $Repo "data"
$env:PYTHONPATH = Join-Path $Repo "src"

$Python = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

$Script = Join-Path $PSScriptRoot "schedule_lord_god_article_wave.py"
if (-not (Test-Path -LiteralPath $Script)) {
    throw "Не найден исполнитель: $Script"
}

& $Python -m py_compile $Script
if ($LASTEXITCODE -ne 0) {
    throw "Проверка Python-скрипта завершилась ошибкой."
}

if ($Mode -eq "Plan") {
    Write-Host "Господь Бог — Сила Моя: проверка 10 ежедневных карточек статей." -ForegroundColor Cyan
    & $Python $Script --repo $Repo
    if ($LASTEXITCODE -ne 0) {
        throw "Проверка очереди статей завершилась ошибкой."
    }
    exit 0
}

if (-not $Execute) {
    throw "Для постановки статей укажи -Mode Apply -Execute."
}

Write-Host "Господь Бог — Сила Моя: постановка 10 статей в отложенную очередь." -ForegroundColor Cyan
$env:VCM_ALLOW_WALL_POSTS = "1"
try {
    & $Python $Script --repo $Repo --execute
    if ($LASTEXITCODE -ne 0) {
        throw "Постановка статей завершилась ошибкой. Повторять можно только через этот же исполнитель."
    }
}
finally {
    Remove-Item Env:VCM_ALLOW_WALL_POSTS -ErrorAction SilentlyContinue
}
