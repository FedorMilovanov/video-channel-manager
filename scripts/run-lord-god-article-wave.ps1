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

$Script = Join-Path $PSScriptRoot "schedule_lord_god_article_wave_v3.py"
$Package = Join-Path $PSScriptRoot "lord_god_article_wave_v3"
$Policy = Join-Path $Repo "content\policies\lord-god-article-wave-v3-202608.json"

if (-not (Test-Path -LiteralPath $Script)) {
    throw "Не найден исполнитель: $Script"
}
if (-not (Test-Path -LiteralPath $Package)) {
    throw "Не найден пакет исполнителя: $Package"
}
if (-not (Test-Path -LiteralPath $Policy)) {
    throw "Не найдена политика: $Policy"
}

& $Python -m compileall -q $Package $Script
if ($LASTEXITCODE -ne 0) {
    throw "Python-исполнитель не прошёл проверку синтаксиса."
}

if ($Mode -eq "Plan") {
    Write-Host "Господь Бог — Сила Моя: read-only аудит 30 URL и 10 отложенных постов." -ForegroundColor Cyan
    & $Python $Script --repo $Repo
    if ($LASTEXITCODE -ne 0) {
        throw "Проверка очереди статей завершилась ошибкой. Запись в VK не выполнялась."
    }
    exit 0
}

if (-not $Execute) {
    throw "Для записи укажи -Mode $Mode -Execute."
}

$env:VCM_ALLOW_WALL_POSTS = "1"
try {
    if ($Mode -eq "Canary") {
        Write-Host "Господь Бог — Сила Моя: один проверочный отложенный пост." -ForegroundColor Yellow
        & $Python $Script --repo $Repo --canary
    }
    elseif ($Mode -eq "Apply") {
        Write-Host "Господь Бог — Сила Моя: остальные девять отложенных постов." -ForegroundColor Cyan
        & $Python $Script --repo $Repo --execute
    }
    else {
        throw "Неподдерживаемый режим: $Mode"
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Постановка очереди остановилась. Повторный запуск разрешён только через этот исполнитель после проверки журнала."
    }
}
finally {
    Remove-Item Env:VCM_ALLOW_WALL_POSTS -ErrorAction SilentlyContinue
}
