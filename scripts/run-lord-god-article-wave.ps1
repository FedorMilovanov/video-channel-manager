[CmdletBinding()]
param(
    [ValidateSet("Plan", "Canary", "Apply")]
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
    Write-Host "Господь Бог — Сила Моя: полный read-only аудит 10 статей и VK-карточек." -ForegroundColor Cyan
    & $Python $Script --repo $Repo
    if ($LASTEXITCODE -ne 0) {
        throw "Проверка очереди статей завершилась ошибкой. Запись в VK не выполнялась."
    }
    exit 0
}

if (-not $Execute) {
    throw "Для Canary или Apply укажи -Execute."
}

$env:VCM_ALLOW_WALL_POSTS = "1"
try {
    if ($Mode -eq "Canary") {
        Write-Host "Господь Бог — Сила Моя: постановка только первой проверочной статьи." -ForegroundColor Yellow
        & $Python $Script --repo $Repo --canary
    }
    else {
        Write-Host "Господь Бог — Сила Моя: постановка оставшихся девяти статей после проверенного canary." -ForegroundColor Cyan
        & $Python $Script --repo $Repo --execute
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Операция $Mode завершилась ошибкой. Повторять можно только этим же исполнителем после чтения результата."
    }
}
finally {
    Remove-Item Env:VCM_ALLOW_WALL_POSTS -ErrorAction SilentlyContinue
}
