[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Plan,

    [Parameter(Mandatory = $true)]
    [string]$Journal,

    [string]$Account = "legendary-poet",
    [string]$Channel = "UC-78ys2S3cQ3lpqgXfo-SvQ",
    [int]$MaxOperations = 200,
    [string]$Certificate = "",
    [string]$Repo = (Split-Path -Parent $PSScriptRoot)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# VCM-WAVE5-RETIRED-GUARD
$VcmOperatorModule = Join-Path $PSScriptRoot "operator\VideoManager.Operator.psm1"
Import-Module -Name $VcmOperatorModule -Force -ErrorAction Stop
Stop-VcmRetiredWrapper -WrapperPath $PSCommandPath -RepositoryRoot (Split-Path -Parent $PSScriptRoot)


try {
    $Repo = (Resolve-Path -LiteralPath $Repo).Path
    $Plan = (Resolve-Path -LiteralPath $Plan).Path
    $Journal = (Resolve-Path -LiteralPath $Journal).Path
    Set-Location -LiteralPath $Repo

    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    $env:VCM_DATA_DIR = Join-Path $Repo "data"
    $env:VCM_YOUTUBE_CLIENT_SECRET_FILE = Join-Path $Repo "secrets\client_secret.json"

    if (-not (Test-Path -LiteralPath $env:VCM_YOUTUBE_CLIENT_SECRET_FILE -PathType Leaf)) {
        throw "Не найден OAuth-файл: $env:VCM_YOUTUBE_CLIENT_SECRET_FILE"
    }

    $RecoveryArgs = @(
        $Plan,
        "--journal", $Journal,
        "--account", $Account,
        "--channel", $Channel,
        "--max-operations", [string]$MaxOperations
    )
    if ($Certificate) {
        $RecoveryArgs += @("--certificate", $Certificate)
    }

    Write-Host "Запускаю единый no-write recovery и динамическую проверку всего публичного inventory..." -ForegroundColor Cyan
    & py -3.11 -X utf8 .\scripts\recover_youtube_comment_wave.py @RecoveryArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Recovery не смог выпустить достоверный coverage certificate."
    }

    Write-Host "ГОТОВО: доказательство покрытия создано Python-валидатором." -ForegroundColor Green
    exit 0
}
catch {
    Write-Error $_
    Write-Host "ОШИБКА: завершение не доказано. Скрипт не создавал и не обновлял комментарии." -ForegroundColor Red
    exit 1
}
