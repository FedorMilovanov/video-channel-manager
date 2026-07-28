[CmdletBinding()]
param(
    [string]$Account = "legendary-poet",
    [int]$Community = 235216998
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $false

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Repo = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Repo

Write-Host "Читается стена VK: опубликованные и отложенные записи. Запись в VK не выполняется." -ForegroundColor Cyan

& py -3.11 -X utf8 .\scripts\build_vk_wall_content_audit.py `
    --account "$Account" `
    --community $Community

if ($LASTEXITCODE -ne 0) {
    throw "Read-only аудит стены VK завершился с ошибкой. Никаких публикаций или изменений в VK не выполнено."
}
