[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Plan,

    [Parameter(Mandatory = $true)]
    [string]$Journal,

    [string]$Account = "legendary-poet",
    [string]$Channel = "UC-78ys2S3cQ3lpqgXfo-SvQ",
    [int]$ExpectedOwnedPresent = 127,
    [string]$Repo = (Split-Path -Parent $PSScriptRoot)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,

        [Parameter(Mandatory = $true)]
        [string]$Stage
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Stage завершился с кодом $LASTEXITCODE."
    }
}

function Read-RequiredCount {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Counts,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $Property = $Counts.PSObject.Properties[$Name]
    if ($null -eq $Property -or $null -eq $Property.Value) {
        throw "В финальном аудите отсутствует обязательный счётчик '$Name'."
    }

    $Parsed = 0
    if (-not [int]::TryParse([string]$Property.Value, [ref]$Parsed)) {
        throw "Счётчик '$Name' в финальном аудите не является целым числом."
    }
    return $Parsed
}

try {
    $Repo = (Resolve-Path -LiteralPath $Repo).Path
    Set-Location -LiteralPath $Repo

    $Plan = (Resolve-Path -LiteralPath $Plan).Path
    $Journal = (Resolve-Path -LiteralPath $Journal).Path

    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    $env:VCM_DATA_DIR = Join-Path $Repo "data"
    $env:VCM_YOUTUBE_CLIENT_SECRET_FILE = Join-Path $Repo "secrets\client_secret.json"

    if (-not (Test-Path -LiteralPath $env:VCM_YOUTUBE_CLIENT_SECRET_FILE -PathType Leaf)) {
        throw "Не найден OAuth-файл: $env:VCM_YOUTUBE_CLIENT_SECRET_FILE"
    }

    Write-Host "1/6 Проверяю импорт модулей в чистом Python-процессе..." -ForegroundColor Cyan
    Invoke-NativeChecked -Stage "Проверка импортов" -Command {
        & py -3.11 -X utf8 -c "from video_channel_manager.platforms.youtube.comments import YouTubeCommentWriter; from video_channel_manager.editorial import preview_payload; print('imports OK')"
    }

    $PlanData = Get-Content -LiteralPath $Plan -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$PlanData.channel_id -ne $Channel) {
        throw "Канал в плане не совпадает с ожидаемым каналом $Channel."
    }
    if ($null -eq $PlanData.source_snapshot -or $null -eq $PlanData.plan_sha256) {
        throw "В подписанном плане отсутствует source_snapshot или plan_sha256."
    }

    $SourceSnapshot = [string]$PlanData.source_snapshot
    $PlanSha256 = [string]$PlanData.plan_sha256

    Write-Host "`n2/6 Выполняю verify-only по исходному плану и журналу..." -ForegroundColor Cyan
    Write-Host "Ни один метод создания или обновления комментариев вызываться не будет." -ForegroundColor Yellow
    Invoke-NativeChecked -Stage "Verify-only" -Command {
        & py -3.11 -X utf8 .\scripts\apply_youtube_comment_plan.py `
            $Plan `
            --account $Account `
            --journal $Journal `
            --verify-only `
            --confirm-channel $Channel `
            --confirm-source-snapshot $SourceSnapshot `
            --confirm-plan-sha256 $PlanSha256
    }

    Write-Host "`n3/6 Проверяю, что исходный журнал закрыт как completed..." -ForegroundColor Cyan
    $JournalData = Get-Content -LiteralPath $Journal -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$JournalData.status -ne "completed") {
        throw "Verify-only не закрыл журнал: status=$($JournalData.status)"
    }

    Write-Host "`n4/6 Делаю новый read-only снимок YouTube..." -ForegroundColor Cyan
    $VideoManager = (Get-Command video-manager -ErrorAction Stop).Source
    $ScanStarted = Get-Date
    Invoke-NativeChecked -Stage "YouTube scan" -Command {
        & $VideoManager youtube scan `
            --account $Account `
            --channel $Channel
    }

    $Snapshot = Get-ChildItem `
        -LiteralPath (Join-Path $Repo "data\exports") `
        -Filter "youtube-$Account-$Channel-*.json" |
        Where-Object { $_.LastWriteTime -ge $ScanStarted.AddSeconds(-2) } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($null -eq $Snapshot) {
        throw "После scan не найден новый YouTube snapshot."
    }

    Write-Host "`n5/6 Выполняю полный read-only аудит публичных роликов..." -ForegroundColor Cyan
    $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $FinalAudit = Join-Path $Repo "data\reports\youtube-comment-audit-final-$Stamp.json"
    Invoke-NativeChecked -Stage "Финальный аудит" -Command {
        & py -3.11 -X utf8 .\scripts\audit_youtube_comments.py `
            $Snapshot.FullName `
            --account $Account `
            --channel $Channel `
            --output $FinalAudit
    }

    if (-not (Test-Path -LiteralPath $FinalAudit -PathType Leaf)) {
        throw "Финальный аудит не создал JSON: $FinalAudit"
    }
    if ((Get-Item -LiteralPath $FinalAudit).Length -le 0) {
        throw "Финальный JSON-аудит пуст: $FinalAudit"
    }

    Write-Host "`n6/6 Проверяю обязательные счётчики и нулевой хвост..." -ForegroundColor Cyan
    $AuditData = Get-Content -LiteralPath $FinalAudit -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -eq $AuditData.counts) {
        throw "В финальном JSON отсутствует объект counts."
    }

    $OwnedPresent = Read-RequiredCount -Counts $AuditData.counts -Name "owned_present"
    $ForeignOnly = Read-RequiredCount -Counts $AuditData.counts -Name "foreign_only"
    $Missing = Read-RequiredCount -Counts $AuditData.counts -Name "missing"
    $CommentsDisabled = Read-RequiredCount -Counts $AuditData.counts -Name "comments_disabled"
    $ApiErrors = Read-RequiredCount -Counts $AuditData.counts -Name "error"

    Write-Host ""
    Write-Host "ФИНАЛЬНЫЙ РЕЗУЛЬТАТ" -ForegroundColor Cyan
    Write-Host "owned_present:     $OwnedPresent"
    Write-Host "foreign_only:      $ForeignOnly"
    Write-Host "missing:           $Missing"
    Write-Host "comments_disabled: $CommentsDisabled"
    Write-Host "error:             $ApiErrors"
    Write-Host "audit:             $FinalAudit"

    if ($OwnedPresent -ne $ExpectedOwnedPresent) {
        throw "Ожидалось owned_present=$ExpectedOwnedPresent, получено $OwnedPresent."
    }
    if ($Missing -ne 0 -or $ForeignOnly -ne 0 -or $CommentsDisabled -ne 0 -or $ApiErrors -ne 0) {
        throw "Канал ещё не закрыт полностью. Точный остаток сохранён в $FinalAudit"
    }

    Write-Host ""
    Write-Host "ГОТОВО: все $OwnedPresent публичных роликов подтверждены авторским комментарием." -ForegroundColor Green
    exit 0
}
catch {
    Write-Error $_
    Write-Host "ОШИБКА: успешный результат не подтверждён. Скрипт не создавал и не обновлял комментарии." -ForegroundColor Red
    exit 1
}
