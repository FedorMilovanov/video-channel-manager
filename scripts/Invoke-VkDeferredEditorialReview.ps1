[CmdletBinding()]
param(
    [string]$ApplyBundle,
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $false
# VCM-WAVE5-RETIRED-GUARD
$VcmOperatorModule = Join-Path $PSScriptRoot "operator\VideoManager.Operator.psm1"
Import-Module -Name $VcmOperatorModule -Force -ErrorAction Stop
Stop-VcmRetiredWrapper -WrapperPath $PSCommandPath -RepositoryRoot (Split-Path -Parent $PSScriptRoot)


[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Repo = Split-Path -Parent $PSScriptRoot
$Handoffs = Join-Path $Repo "data\handoffs"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Output = Join-Path $Handoffs "vk-deferred-editorial-review-$Stamp.zip"

Set-Location -LiteralPath $Repo
New-Item -ItemType Directory -Path $Handoffs -Force | Out-Null

if ([string]::IsNullOrWhiteSpace($ApplyBundle)) {
    $Latest = Get-ChildItem `
        -LiteralPath $Handoffs `
        -File `
        -Filter "vk-description-wave-apply-*.zip" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $Latest) {
        throw "Не найден apply-ZIP волны описаний."
    }
    $ApplyBundle = $Latest.FullName
}

$ResolvedBundle = (Resolve-Path -LiteralPath $ApplyBundle).Path

Write-Host "Проверяется apply-ZIP и строится legacy-safe review-only очередь..." -ForegroundColor Yellow
& py -3.11 -X utf8 .\scripts\build_vk_deferred_review_bundle_v3.py `
    "$ResolvedBundle" `
    --output "$Output"
if ($LASTEXITCODE -ne 0) {
    throw "Не удалось проверить apply-ZIP или создать deferred review bundle."
}

Write-Host ""
Write-Host "ГОТОВ ЛОКАЛИЗОВАННЫЙ REVIEW-ONLY ZIP:" -ForegroundColor Green
Write-Host $Output
Write-Host "Записей, удалений или изменений данных VK: 0"
Write-Host "P1/P2 — активные маркеры финального текста; P3 legacy — старые или технические срабатывания."

if (-not $NoOpen -and $IsWindows) {
    Start-Process explorer.exe -ArgumentList "/select,`"$Output`""
}
