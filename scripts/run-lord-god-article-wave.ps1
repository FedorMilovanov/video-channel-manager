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
$PhotoExecutor = Join-Path $Package "photo_wave_v4.py"
$PhotoMutations = Join-Path $Package "mutations.py"
$PhotoSources = Join-Path $Package "sources.py"
$PhotoWall = Join-Path $Package "wall.py"

# Retired parsed-link artifacts are retained in Git history and unit tests only.
$RetiredParsedLinkArtifacts = @(
    "link_cards_hardened.py",
    "link-card-delivery-contract.json",
    "delivery-contract-v3.json"
)
$null = $RetiredParsedLinkArtifacts

foreach ($RequiredPath in @(
    $Script,
    $Package,
    $Policy,
    $SourceContract,
    $PhotoExecutor,
    $PhotoMutations,
    $PhotoSources,
    $PhotoWall
)) {
    if (-not (Test-Path -LiteralPath $RequiredPath)) {
        throw "Не найден обязательный файл фото-волны v4: $RequiredPath"
    }
}

& $Python -m compileall -q $Package $Script
if ($LASTEXITCODE -ne 0) {
    throw "Python-исполнитель не прошёл проверку синтаксиса."
}

if ($Mode -eq "Plan") {
    Remove-Item Env:VCM_ALLOW_WALL_POSTS -ErrorAction SilentlyContinue
    Write-Host "Господь Бог — Сила Моя: read-only подготовка 10 JPEG-обложек и проверка фото-пути VK; без загрузки фото и без wall.post." -ForegroundColor Cyan
    & $Python $Script --repo $Repo
    if ($LASTEXITCODE -ne 0) {
        throw "Photo-wave v4 Plan завершился ошибкой. Ни photos.saveWallPhoto, ни wall.post не выполнялись."
    }
    exit 0
}

if (-not $Execute) {
    throw "Для записи укажи -Mode $Mode -Execute."
}

$env:VCM_ALLOW_WALL_POSTS = "1"
try {
    if ($Mode -eq "Canary") {
        Write-Host "Господь Бог — Сила Моя: один отложенный пост с JPEG-обложкой и ссылкой в тексте." -ForegroundColor Yellow
        & $Python $Script --repo $Repo --canary
    }
    elseif ($Mode -eq "Apply") {
        Write-Host "Господь Бог — Сила Моя: остальные девять отложенных постов с JPEG-обложками и ссылками в тексте." -ForegroundColor Cyan
        & $Python $Script --repo $Repo --execute
    }
    else {
        throw "Неподдерживаемый режим: $Mode"
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Фото-волна v4 остановилась. Не повторяй команду до проверки photo-journal-v4.json."
    }
}
finally {
    Remove-Item Env:VCM_ALLOW_WALL_POSTS -ErrorAction SilentlyContinue
}
