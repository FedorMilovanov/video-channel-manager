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
$SourceContract = Join-Path $Repo "content\policies\lord-god-article-wave-v3-source-contract.json"
$LegacyDeliveryContract = Join-Path $Repo "content\policies\lord-god-article-wave-v3-link-card-delivery-contract.json"
$DeliveryContract = Join-Path $Repo "content\policies\lord-god-article-wave-v3-link-card-delivery-contract-v3.json"
$LegacyHardenedCore = Join-Path $Package "link_cards_hardened.py"
$LegacyHardenedEntrypoint = Join-Path $Package "link_cards_hardened_entry.py"
$ParsedEntrypoint = Join-Path $Package "link_cards_parsed.py"
$ParsedContract = Join-Path $Package "parsed_link_contract.py"
$ParsedPreview = Join-Path $Package "parsed_link_preview.py"
$ParsedState = Join-Path $Package "parsed_link_state.py"
$ParsedMutations = Join-Path $Package "parsed_link_mutations.py"

if (-not (Test-Path -LiteralPath $Script)) {
    throw "Не найден исполнитель: $Script"
}
if (-not (Test-Path -LiteralPath $Package)) {
    throw "Не найден пакет исполнителя: $Package"
}
if (-not (Test-Path -LiteralPath $Policy)) {
    throw "Не найдена политика: $Policy"
}
if (-not (Test-Path -LiteralPath $SourceContract)) {
    throw "Не найден контракт источников: $SourceContract"
}
if (-not (Test-Path -LiteralPath $LegacyDeliveryContract)) {
    throw "Не найден исторический link-card delivery-contract v2: $LegacyDeliveryContract"
}
if (-not (Test-Path -LiteralPath $DeliveryContract)) {
    throw "Не найден parsed link-card delivery-contract v3: $DeliveryContract"
}
foreach ($RequiredModule in @(
    $LegacyHardenedCore,
    $LegacyHardenedEntrypoint,
    $ParsedEntrypoint,
    $ParsedContract,
    $ParsedPreview,
    $ParsedState,
    $ParsedMutations
)) {
    if (-not (Test-Path -LiteralPath $RequiredModule)) {
        throw "Не найден модуль parsed link-card исполнителя: $RequiredModule"
    }
}

& $Python -m compileall -q $Package $Script
if ($LASTEXITCODE -ne 0) {
    throw "Python-исполнитель не прошёл проверку синтаксиса."
}

if ($Mode -eq "Plan") {
    Write-Host "Господь Бог — Сила Моя: read-only аудит 40 ресурсов и 10 VK-превью через wall.parseAttachedLink; без загрузки фото и без wall.post." -ForegroundColor Cyan
    & $Python $Script --repo $Repo
    if ($LASTEXITCODE -ne 0) {
        throw "Parsed link-card Plan завершился ошибкой. wall.post не выполнялся."
    }
    exit 0
}

if (-not $Execute) {
    throw "Для записи укажи -Mode $Mode -Execute."
}

$env:VCM_ALLOW_WALL_POSTS = "1"
try {
    if ($Mode -eq "Canary") {
        Write-Host "Господь Бог — Сила Моя: одна parsed link-карточка; wall.parseAttachedLink перед wall.post, без отдельной фотографии." -ForegroundColor Yellow
        & $Python $Script --repo $Repo --canary
    }
    elseif ($Mode -eq "Apply") {
        Write-Host "Господь Бог — Сила Моя: остальные девять parsed link-карточек; без загрузки отдельных фотографий." -ForegroundColor Cyan
        & $Python $Script --repo $Repo --execute
    }
    else {
        throw "Неподдерживаемый режим: $Mode"
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Постановка parsed link-карточек остановилась. Повторный запуск разрешён только после проверки journal v3."
    }
}
finally {
    Remove-Item Env:VCM_ALLOW_WALL_POSTS -ErrorAction SilentlyContinue
}
