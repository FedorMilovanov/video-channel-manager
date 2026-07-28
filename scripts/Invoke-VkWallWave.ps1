[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SourceAuditBundle,

    [switch]$Execute,

    [string]$Account = "legendary-poet",
    [int]$Community = 235216998,
    [string]$Policy = ".\content\policies\vk-wall-wave-202608.json",
    [double]$WriteDelay = 1.0
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $false

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Repo = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Repo

$ModeLabel = if ($Execute) { "APPLY" } else { "DRY-RUN" }
Write-Host "VK wall wave: 12 редакционных отложенных постов. Режим: $ModeLabel." -ForegroundColor Cyan
if (-not $Execute) {
    Write-Host "VK не изменяется. Для постановки записей в очередь нужен явный флаг -Execute." -ForegroundColor Yellow
}

$Arguments = @(
    "-3.11",
    "-X", "utf8",
    ".\scripts\run_vk_wall_wave.py",
    "--source-audit-bundle", $SourceAuditBundle,
    "--policy", $Policy,
    "--account", $Account,
    "--community", "$Community",
    "--write-delay", "$WriteDelay"
)
if ($Execute) {
    $Arguments += "--execute"
}

& py @Arguments
if ($LASTEXITCODE -ne 0) {
    throw "VK wall wave завершилась с ошибкой. Проверьте диагностический ZIP; неподтверждённые операции не продолжаются."
}
