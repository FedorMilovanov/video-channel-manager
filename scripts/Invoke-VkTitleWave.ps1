[CmdletBinding()]
param(
    [switch]$Execute,
    [switch]$NoOpen,
    [string]$Plan,
    [string]$Account = "legendary-poet",
    [int]$Community = 235216998
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
$Reports = Join-Path $Repo "data\reports"
$Exports = Join-Path $Repo "data\exports"
$Handoffs = Join-Path $Repo "data\handoffs"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Mode = if ($Execute) { "apply" } else { "dry-run" }
$BundleName = "vk-title-wave-$Mode-$Stamp"
$BundleDir = Join-Path $Handoffs $BundleName
$ZipPath = Join-Path $Handoffs "$BundleName.zip"

New-Item -ItemType Directory -Path $BundleDir -Force | Out-Null

$PreflightLog = Join-Path $BundleDir "01-preflight.txt"
$ApplyLog = Join-Path $BundleDir "02-apply.txt"
$ResultPath = Join-Path $BundleDir "03-result.json"
$FinalSnapshot = Join-Path $BundleDir "04-final-vk-snapshot.json"
$ReadmePath = Join-Path $BundleDir "README.txt"
$ManifestPath = Join-Path $BundleDir "manifest.json"

$RunStatus = "started"
$RunError = $null
$Ready = $null
$AlreadyApplied = $null
$Conflicts = $null
$PlanJson = $null
$ResolvedPlan = $null

function Copy-Artifact {
    param(
        [Parameter(Mandatory)]
        [string]$Path,
        [string]$Name
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }

    $TargetName = if ($Name) { $Name } else { Split-Path -Leaf $Path }
    Copy-Item -LiteralPath $Path -Destination (Join-Path $BundleDir $TargetName) -Force
}

function Read-PreflightCount {
    param(
        [Parameter(Mandatory)]
        [string]$Text,
        [Parameter(Mandatory)]
        [string]$Label
    )

    $Pattern = "(?m)^\s*" + [regex]::Escape($Label) + ":\s*(\d+)\s*$"
    $Match = [regex]::Match($Text, $Pattern)
    if (-not $Match.Success) {
        throw "Не удалось прочитать '$Label' из live preflight."
    }
    return [int]$Match.Groups[1].Value
}

function Write-Bundle {
    $Readme = @"
VK TITLE WAVE HANDOFF

Статус: $RunStatus
Режим: $Mode
Community: $Community
Ready перед запуском: $Ready
Already applied перед запуском: $AlreadyApplied
Conflicts: $Conflicts
Ошибка: $RunError

ОТПРАВЛЯТЬ НУЖНО ТОЛЬКО ОДИН ФАЙЛ:
$ZipPath

Внутри архива автоматически собраны:
- подписанный JSON-план;
- читаемый Markdown-отчёт;
- редакционная политика;
- свежий live preflight;
- лог применения, если запускался execute;
- result journal, если был создан;
- финальный VK snapshot, если применение завершилось успешно;
- manifest.json с SHA-256 каждого файла.
"@
    Set-Content -LiteralPath $ReadmePath -Value $Readme -Encoding UTF8

    $Files = @(
        Get-ChildItem -LiteralPath $BundleDir -File |
        Where-Object { $_.Name -ne "manifest.json" } |
        Sort-Object Name |
        ForEach-Object {
            $Hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
            [ordered]@{
                name = $_.Name
                size_bytes = $_.Length
                sha256 = "sha256:$($Hash.Hash.ToLowerInvariant())"
            }
        }
    )

    $Manifest = [ordered]@{
        schema_name = "video-manager.vk-handoff-bundle"
        schema_version = 1
        created_at = (Get-Date).ToUniversalTime().ToString("o")
        status = $RunStatus
        mode = $Mode
        community_id = $Community
        ready = $Ready
        already_applied = $AlreadyApplied
        conflicts = $Conflicts
        error = $RunError
        plan_sha256 = if ($null -ne $PlanJson) { [string]$PlanJson.plan_sha256 } else { $null }
        files = $Files
    }
    $Manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8

    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }
    Compress-Archive -Path (Join-Path $BundleDir "*") -DestinationPath $ZipPath -CompressionLevel Optimal

    Write-Host ""
    Write-Host "ГОТОВ ОДИН ФАЙЛ ДЛЯ ОТПРАВКИ:" -ForegroundColor Green
    Write-Host $ZipPath -ForegroundColor Cyan

    if (-not $NoOpen -and $IsWindows) {
        Start-Process explorer.exe -ArgumentList "/select,`"$ZipPath`""
    }
}

try {
    Set-Location -LiteralPath $Repo

    if ([string]::IsNullOrWhiteSpace($Plan)) {
        $ResolvedPlan = Get-ChildItem -LiteralPath $Reports -File -Filter "vk-editorial-title-wave-*.json" |
            Where-Object { $_.Name -notlike "*-apply-*" } |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($null -eq $ResolvedPlan) {
            throw "Не найден ни один vk-editorial-title-wave-*.json в $Reports"
        }
        $Plan = $ResolvedPlan.FullName
    }
    else {
        $Plan = (Resolve-Path -LiteralPath $Plan).Path
        $ResolvedPlan = Get-Item -LiteralPath $Plan
    }

    $PlanJson = Get-Content -LiteralPath $Plan -Raw -Encoding UTF8 | ConvertFrom-Json

    if ([string]$PlanJson.operation_scope -ne "editorial_only") {
        throw "План не является editorial_only."
    }
    if ([string]$PlanJson.component_scope -ne "titles_only") {
        throw "План не является titles_only."
    }
    if ([int]$PlanJson.target_community_id -ne $Community) {
        throw "План относится к другому VK-сообществу."
    }
    if ([int]$PlanJson.summary.descriptions_to_update -ne 0) {
        throw "План содержит изменения описаний."
    }
    if ([int]$PlanJson.summary.albums_to_rename -ne 0) {
        throw "План содержит переименование альбомов."
    }
    if ([int]$PlanJson.summary.placements_to_add -ne 0 -or
        [int]$PlanJson.summary.placements_to_remove -ne 0 -or
        [int]$PlanJson.summary.videos_to_delete -ne 0) {
        throw "План содержит каталожные изменения или удаления."
    }

    $BadDescriptions = @(
        $PlanJson.video_text_operations |
        Where-Object {
            [string]$_.before_description -cne [string]$_.after_description -or
            [string]$_.before_description_sha256 -cne [string]$_.after_description_sha256 -or
            [bool]$_.description_changed
        }
    )
    if ($BadDescriptions.Count -gt 0) {
        throw "План содержит скрытые изменения описаний."
    }

    Copy-Artifact -Path $Plan -Name "plan.json"

    $ReportPath = [System.IO.Path]::ChangeExtension($Plan, ".md")
    Copy-Artifact -Path $ReportPath -Name "plan-review.md"

    $PolicyPath = Join-Path $Repo "content\policies\vk-editorial-policy-20260727.json"
    Copy-Artifact -Path $PolicyPath -Name "editorial-policy.json"

    $PreviousDryRun = Get-ChildItem -LiteralPath $Reports -File -Filter "vk-editorial-title-wave-dry-run-*.txt" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -ne $PreviousDryRun) {
        Copy-Artifact -Path $PreviousDryRun.FullName -Name "previous-reviewed-dry-run.txt"
    }

    Write-Host "План: $Plan" -ForegroundColor Cyan
    Write-Host "Запускается свежий live preflight..." -ForegroundColor Yellow

    & py -3.11 -X utf8 .\scripts\apply_vk_editorial_cleanup_plan.py `
        "$Plan" `
        --account "$Account" `
        --community $Community `
        --max-operations ([int]$PlanJson.summary.total_operations) 2>&1 |
        Tee-Object -FilePath $PreflightLog

    $PreflightExit = $LASTEXITCODE
    if ($PreflightExit -ne 0) {
        throw "Live preflight завершился с кодом $PreflightExit."
    }

    $PreflightText = Get-Content -LiteralPath $PreflightLog -Raw -Encoding UTF8
    $Ready = Read-PreflightCount -Text $PreflightText -Label "ready"
    $AlreadyApplied = Read-PreflightCount -Text $PreflightText -Label "already applied"
    $Conflicts = Read-PreflightCount -Text $PreflightText -Label "conflicts"

    if ($Conflicts -ne 0) {
        throw "Live preflight обнаружил $Conflicts конфликтов."
    }

    if (-not $Execute) {
        $RunStatus = "dry_run_completed"
        Write-Host ""
        Write-Host "Dry-run завершён. Записей в VK не было." -ForegroundColor Green
        return
    }

    Write-Host ""
    Write-Host "Выполняется безопасное продолжение:" -ForegroundColor Yellow
    Write-Host "  ready:           $Ready"
    Write-Host "  already applied: $AlreadyApplied"
    Write-Host "  total plan ops:  $($PlanJson.summary.total_operations)"

    & py -3.11 -X utf8 .\scripts\apply_vk_editorial_cleanup_plan.py `
        "$Plan" `
        --account "$Account" `
        --community $Community `
        --execute `
        --confirm-community $Community `
        --confirm-ready $Ready `
        --confirm-plan-sha256 "$($PlanJson.plan_sha256)" `
        --confirm-video-coverage "$($PlanJson.target_video_ids_sha256)" `
        --confirm-memberships "$($PlanJson.initial_memberships_sha256)" `
        --max-operations ([int]$PlanJson.summary.total_operations) `
        --write-delay 2.0 `
        --result-output "$ResultPath" 2>&1 |
        Tee-Object -FilePath $ApplyLog

    $ApplyExit = $LASTEXITCODE
    if ($ApplyExit -ne 0) {
        throw "Применение завершилось с кодом $ApplyExit."
    }

    if (-not (Test-Path -LiteralPath $ResultPath -PathType Leaf)) {
        throw "Не создан result journal."
    }

    $ResultJson = Get-Content -LiteralPath $ResultPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$ResultJson.status -ne "completed") {
        throw "Result journal не получил status=completed."
    }
    if ([string]$ResultJson.plan_sha256 -ne [string]$PlanJson.plan_sha256) {
        throw "Result journal относится к другому плану."
    }

    video-manager vk scan `
        --account "$Account" `
        --community "$Community" `
        --output "$FinalSnapshot"

    if ($LASTEXITCODE -ne 0) {
        throw "Финальный read-only VK scan завершился ошибкой."
    }

    $RunStatus = "completed"
    Write-Host ""
    Write-Host "VK title wave завершена и postflight-подтверждена." -ForegroundColor Green
}
catch {
    $RunStatus = "failed"
    $RunError = $_.Exception.Message
    Write-Host ""
    Write-Host "ОШИБКА: $RunError" -ForegroundColor Red
    throw
}
finally {
    Write-Bundle
}
