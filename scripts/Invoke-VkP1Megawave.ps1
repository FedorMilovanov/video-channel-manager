[CmdletBinding()]
param(
    [switch]$Execute,
    [string]$SourceApplyBundle,
    [string]$Account = "legendary-poet",
    [int]$Community = 235216998,
    [ValidateRange(0, 10)]
    [double]$WriteDelay = 1.0
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
$Policy = Join-Path $Repo "content\policies\vk-p1-final-megawave-policy-20260728.json"

if (-not $Execute) {
    throw "Финальная мегаволна требует явный флаг -Execute."
}

if ([string]::IsNullOrWhiteSpace($SourceApplyBundle)) {
    $Latest = Get-ChildItem -LiteralPath $Handoffs -File -Filter "vk-reviewed-correction-p1-pushkin-cloud-apply-*.zip" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $Latest) {
        throw "Не найден проверенный Pushkin Cloud apply ZIP."
    }
    $SourceApplyBundle = $Latest.FullName
}

$SourceApplyBundle = (Resolve-Path -LiteralPath $SourceApplyBundle).Path
if (-not (Test-Path -LiteralPath $Policy -PathType Leaf)) {
    throw "Не найдена политика финальной мегаволны: $Policy"
}

Set-Location -LiteralPath $Repo
Write-Host "Запускается финальная VK P1-мегаволна: 42 описания, 3 заголовка, 3 альбома, 32 размещения." -ForegroundColor Yellow

& py -3.11 -X utf8 .\scripts\run_vk_p1_final_megawave_resume.py `
    --source-apply-bundle "$SourceApplyBundle" `
    --policy "$Policy" `
    --account "$Account" `
    --community $Community `
    --write-delay $WriteDelay `
    --execute

if ($LASTEXITCODE -ne 0) {
    throw "Финальная VK P1-мегаволна завершилась с ошибкой. Диагностический ZIP сохранён в data\handoffs."
}
