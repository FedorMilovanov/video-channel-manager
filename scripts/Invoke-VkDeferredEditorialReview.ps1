[CmdletBinding()]
param(
    [string]$ApplyBundle,
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $false

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Repo = Split-Path -Parent $PSScriptRoot
$Handoffs = Join-Path $Repo "data\handoffs"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Output = Join-Path $Handoffs "vk-deferred-editorial-review-$Stamp.zip"
$Verification = Join-Path $Handoffs "vk-description-apply-verification-$Stamp.json"

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

Write-Host "Проверяется итоговый apply-ZIP..." -ForegroundColor Yellow
& py -3.11 -X utf8 .\scripts\verify_vk_description_apply_bundle.py `
    "$ResolvedBundle" `
    --json-output "$Verification"
if ($LASTEXITCODE -ne 0) {
    throw "Apply-ZIP не прошёл независимую проверку."
}

Write-Host "Создаётся review-only очередь без VK-записей..." -ForegroundColor Yellow
& py -3.11 -X utf8 .\scripts\build_vk_deferred_review_bundle.py `
    "$ResolvedBundle" `
    --output "$Output"
if ($LASTEXITCODE -ne 0) {
    throw "Не удалось создать deferred review bundle."
}

Write-Host ""
Write-Host "ГОТОВ REVIEW-ONLY ZIP:" -ForegroundColor Green
Write-Host $Output
Write-Host "Удалённых или изменённых данных VK: 0"

if (-not $NoOpen -and $IsWindows) {
    Start-Process explorer.exe -ArgumentList "/select,`"$Output`""
}
