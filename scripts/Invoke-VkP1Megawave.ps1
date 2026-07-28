[CmdletBinding()]
param(
    [switch]$Execute,
    [string]$SourceApplyBundle,
    [switch]$NoOpen,
    [string]$Account = "legendary-poet",
    [int]$Community = 235216998,
    [ValidateRange(1, 5)]
    [int]$ReadRetryAttempts = 3,
    [ValidateRange(1, 120)]
    [int]$ReadRetryDelaySeconds = 15
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $false

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ExpectedCount = 42
$ExpectedDecisionSet = "p1-all-remaining-megawave-20260728"
$Repo = Split-Path -Parent $PSScriptRoot
$Handoffs = Join-Path $Repo "data\handoffs"
$Reports = Join-Path $Repo "data\reports"
$Policy = Join-Path $Repo "content\policies\vk-p1-megawave-policy-20260728.json"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BundleName = "vk-reviewed-correction-p1-megawave-apply-$Stamp"
$BundleDir = Join-Path $Handoffs $BundleName
$ZipPath = Join-Path $Handoffs "$BundleName.zip"
$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) "video-channel-manager\$BundleName"

$Snapshot = Join-Path $TempDir "source-vk-snapshot.json"
$ReviewBundle = Join-Path $TempDir "source-review-bundle.zip"
$SourceApplyVerification = Join-Path $TempDir "source-apply-verification.json"
$Decisions = Join-Path $TempDir "decisions.json"
$Plan = Join-Path $TempDir "plan.json"
$PlanReport = Join-Path $TempDir "plan-review.md"
$PlanHtml = Join-Path $TempDir "plan-review.html"
$PlanVerification = Join-Path $TempDir "plan-verification.json"
$FinalVerification = Join-Path $TempDir "final-verification.json"

$PreflightLog = Join-Path $BundleDir "06-preflight.txt"
$ApplyLog = Join-Path $BundleDir "07-apply.txt"
$ResultPath = Join-Path $BundleDir "08-result.json"
$FinalSnapshot = Join-Path $BundleDir "09-final-vk-snapshot.json"
$ManifestPath = Join-Path $BundleDir "manifest.json"
$ReadmePath = Join-Path $BundleDir "README.txt"

$RunStatus = "started"
$RunError = $null
$Ready = $null
$AlreadyApplied = $null
$Conflicts = $null
$RemoteWrites = 0
$PlanJson = $null
$DecisionsJson = $null
$ResolvedSourceApply = $null
$HandoffVerified = $false

function Get-LatestFile {
    param([string]$Filter, [string]$ErrorText)
    $File = Get-ChildItem -LiteralPath $Handoffs -File -Filter $Filter |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $File) {
        throw $ErrorText
    }
    return $File.FullName
}

function Expand-BundleEntry {
    param(
        [Parameter(Mandatory)]
        [string]$Bundle,
        [Parameter(Mandatory)]
        [string]$Name,
        [Parameter(Mandatory)]
        [string]$Destination
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $Archive = [System.IO.Compression.ZipFile]::OpenRead($Bundle)
    try {
        $Entries = @(
            $Archive.Entries |
            Where-Object { [System.IO.Path]::GetFileName($_.FullName) -ceq $Name }
        )
        if ($Entries.Count -ne 1) {
            throw "В source apply ZIP должен быть ровно один файл '$Name'."
        }
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile(
            $Entries[0],
            $Destination,
            $true
        )
    }
    finally {
        $Archive.Dispose()
    }
}

function Copy-Artifact {
    param([string]$Path, [string]$Name)
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        Copy-Item -LiteralPath $Path -Destination (Join-Path $BundleDir $Name) -Force
    }
}

function Read-Count {
    param([string]$Text, [string]$Label)
    $Pattern = "(?m)^\s*" + [regex]::Escape($Label) + ":\s*(\d+)\s*$"
    $Match = [regex]::Match($Text, $Pattern)
    if (-not $Match.Success) {
        throw "Не удалось прочитать '$Label' из live megawave preflight."
    }
    return [int]$Match.Groups[1].Value
}

function Write-Handoff {
    New-Item -ItemType Directory -Path $Handoffs, $BundleDir -Force | Out-Null

    $Readme = @"
VK REVIEWED CORRECTION P1 — ЕДИНАЯ МЕГАВОЛНА — APPLY

Статус: $RunStatus
Community: $Community
Decision set: $ExpectedDecisionSet
Операций: $ExpectedCount
Ready перед execute: $Ready
Already applied перед execute: $AlreadyApplied
Conflicts: $Conflicts
Подтверждённых VK-записей: $RemoteWrites
Ошибка: $RunError

Это один локальный запуск для всех оставшихся активных P1:
- 42 видео;
- 37 уникальных описаний;
- один детерминированный correction plan;
- один preflight;
- один guarded execute;
- один финальный VK scan;
- одна независимая postflight-проверка.

Заморожено:
- все 111 названий;
- 69 нетаргетных описаний;
- 17 коллекций и их названия;
- 294 membership-пары и позиции;
- состав из 111 видео;
- URL, хэштеги, плейлисты, сохранённые стихотворные блоки и footer.

Мегаволна удаляет неподтверждённые биографические, психологические,
медицинские, пророческие и богословские утверждения, не превращая
литературную интерпретацию в документированный факт.
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

    $SourceApplySha = if ($null -ne $ResolvedSourceApply -and (Test-Path -LiteralPath $ResolvedSourceApply)) {
        "sha256:$((Get-FileHash -LiteralPath $ResolvedSourceApply -Algorithm SHA256).Hash.ToLowerInvariant())"
    }
    else {
        $null
    }

    $ReviewSha = if (Test-Path -LiteralPath $ReviewBundle) {
        "sha256:$((Get-FileHash -LiteralPath $ReviewBundle -Algorithm SHA256).Hash.ToLowerInvariant())"
    }
    else {
        $null
    }

    $Manifest = [ordered]@{
        schema_name = "video-manager.vk-p1-megawave-apply-handoff"
        schema_version = 1
        created_at = (Get-Date).ToUniversalTime().ToString("o")
        status = $RunStatus
        mode = "apply"
        component_scope = "descriptions_only"
        correction_scope = "reviewed_factual_and_sensitive"
        decision_set_id = $ExpectedDecisionSet
        community_id = $Community
        operations = $ExpectedCount
        ready = $Ready
        already_applied = $AlreadyApplied
        conflicts = $Conflicts
        remote_writes = $RemoteWrites
        error = $RunError
        plan_sha256 = if ($null -ne $PlanJson) { [string]$PlanJson.plan_sha256 } else { $null }
        decisions_sha256 = if ($null -ne $PlanJson) { [string]$PlanJson.decisions_sha256 } else { $null }
        source_apply_bundle_sha256 = $SourceApplySha
        source_review_bundle_sha256 = $ReviewSha
        files = $Files
    }
    $Manifest |
        ConvertTo-Json -Depth 12 |
        Set-Content -LiteralPath $ManifestPath -Encoding UTF8

    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }
    Compress-Archive `
        -Path (Join-Path $BundleDir "*") `
        -DestinationPath $ZipPath `
        -CompressionLevel Optimal
}

try {
    Set-Location -LiteralPath $Repo
    New-Item -ItemType Directory -Path $Handoffs, $Reports, $BundleDir, $TempDir -Force | Out-Null

    if (-not $Execute) {
        throw "Мегаволна выполняется одним guarded запуском. Добавьте явный флаг -Execute."
    }
    if (-not (Test-Path -LiteralPath $Policy -PathType Leaf)) {
        throw "Не найден megawave policy: $Policy"
    }

    if ([string]::IsNullOrWhiteSpace($SourceApplyBundle)) {
        $SourceApplyBundle = Get-LatestFile `
            "vk-reviewed-correction-p1-pushkin-cloud-apply-*.zip" `
            "Не найден завершённый Pushkin Cloud apply ZIP."
    }
    $ResolvedSourceApply = (Resolve-Path -LiteralPath $SourceApplyBundle).Path

    Write-Host "Проверяется завершённый Pushkin Cloud apply ZIP..." -ForegroundColor Yellow
    & py -3.11 -X utf8 .\scripts\verify_vk_reviewed_correction_pushkin_cloud_apply_bundle.py `
        "$ResolvedSourceApply" `
        --json-output "$SourceApplyVerification"
    if ($LASTEXITCODE -ne 0) {
        throw "Source Pushkin Cloud apply ZIP не прошёл независимую проверку."
    }

    Expand-BundleEntry $ResolvedSourceApply "04-final-vk-snapshot.json" $Snapshot
    Expand-BundleEntry $ResolvedSourceApply "source-review-bundle.zip" $ReviewBundle

    Write-Host "Строятся детерминированные решения для всех 42 P1..." -ForegroundColor Yellow
    & py -3.11 -X utf8 .\scripts\build_vk_p1_megawave_decisions.py `
        "$Snapshot" `
        --policy "$Policy" `
        --review-bundle "$ReviewBundle" `
        --output "$Decisions"
    if ($LASTEXITCODE -ne 0) {
        throw "Не удалось построить megawave decisions."
    }

    & py -3.11 -X utf8 .\scripts\build_vk_reviewed_correction_wave.py `
        "$Snapshot" `
        --decisions-json "$Decisions" `
        --review-bundle "$ReviewBundle" `
        --output "$Plan" `
        --report "$PlanReport" `
        --html-report "$PlanHtml"
    if ($LASTEXITCODE -ne 0) {
        throw "Не удалось построить единый megawave plan."
    }

    & py -3.11 -X utf8 .\scripts\verify_vk_p1_megawave_plan.py `
        "$Snapshot" `
        --policy "$Policy" `
        --review-bundle "$ReviewBundle" `
        --decisions "$Decisions" `
        --plan "$Plan" `
        --json-output "$PlanVerification"
    if ($LASTEXITCODE -ne 0) {
        throw "Единый megawave plan не прошёл независимую проверку."
    }

    $PlanJson = Get-Content -LiteralPath $Plan -Raw -Encoding UTF8 | ConvertFrom-Json
    $DecisionsJson = Get-Content -LiteralPath $Decisions -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$PlanJson.decision_set_id -cne $ExpectedDecisionSet) {
        throw "Megawave plan принадлежит другому decision set."
    }
    if ([int]$PlanJson.summary.descriptions_to_update -ne $ExpectedCount -or
        [int]$PlanJson.summary.total_operations -ne $ExpectedCount -or
        [int]$PlanJson.summary.titles_to_update -ne 0 -or
        [int]$PlanJson.summary.albums_to_rename -ne 0 -or
        [int]$PlanJson.summary.placements_to_add -ne 0 -or
        [int]$PlanJson.summary.placements_to_remove -ne 0 -or
        [int]$PlanJson.summary.videos_to_delete -ne 0) {
        throw "Megawave plan имеет неожиданный scope."
    }
    if ([int]$DecisionsJson.target_count -ne $ExpectedCount -or
        [int]$DecisionsJson.unique_description_count -ne 37) {
        throw "Megawave decisions имеют неожиданное покрытие."
    }

    Copy-Artifact $Snapshot "00-source-vk-snapshot.json"
    Copy-Artifact $Decisions "01-decisions.json"
    Copy-Artifact $Plan "02-plan.json"
    Copy-Artifact $PlanReport "03-plan-review.md"
    Copy-Artifact $PlanHtml "04-plan-review.html"
    Copy-Artifact $PlanVerification "05-plan-verification.json"
    Copy-Artifact $Policy "megawave-policy.json"
    Copy-Artifact $ResolvedSourceApply "source-pushkin-cloud-apply.zip"
    Copy-Artifact $ReviewBundle "source-review-bundle.zip"

    $PreflightSucceeded = $false
    for ($Attempt = 1; $Attempt -le $ReadRetryAttempts; $Attempt++) {
        $Output = & py -3.11 -X utf8 .\scripts\apply_vk_editorial_cleanup_plan.py `
            "$Plan" `
            --account "$Account" `
            --community $Community `
            --max-operations $ExpectedCount 2>&1
        $ExitCode = $LASTEXITCODE
        $Text = ($Output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
        Set-Content -LiteralPath $PreflightLog -Value $Text -Encoding UTF8
        Write-Host $Text
        if ($ExitCode -eq 0) {
            $PreflightSucceeded = $true
            break
        }
        if ($Text -notmatch "VK API 204 in video\.get: Access denied") {
            throw "Live megawave preflight завершился с кодом $ExitCode."
        }
        if ($Attempt -lt $ReadRetryAttempts) {
            $Delay = $ReadRetryDelaySeconds * $Attempt
            Write-Host "Read-only video.get временно недоступен; повтор через $Delay секунд." -ForegroundColor Yellow
            Start-Sleep -Seconds $Delay
        }
    }
    if (-not $PreflightSucceeded) {
        throw "Live megawave preflight не завершился после $ReadRetryAttempts попыток."
    }

    $PreflightText = Get-Content -LiteralPath $PreflightLog -Raw -Encoding UTF8
    $Ready = Read-Count $PreflightText "ready"
    $AlreadyApplied = Read-Count $PreflightText "already applied"
    $Conflicts = Read-Count $PreflightText "conflicts"
    if ($Ready + $AlreadyApplied -ne $ExpectedCount -or $Conflicts -ne 0) {
        throw "Unexpected megawave preflight: ready=$Ready already=$AlreadyApplied conflicts=$Conflicts"
    }

    Write-Host ""
    Write-Host "ЕДИНАЯ P1-МЕГАВОЛНА ДОПУЩЕНА К EXECUTE" -ForegroundColor Green
    Write-Host "  plan SHA-256:    $($PlanJson.plan_sha256)"
    Write-Host "  video coverage:  $($PlanJson.target_video_ids_sha256)"
    Write-Host "  memberships:     $($PlanJson.initial_memberships_sha256)"
    Write-Host "  ready:           $Ready"
    Write-Host "  already applied: $AlreadyApplied"

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
        --max-operations $ExpectedCount `
        --write-delay 2.0 `
        --result-output "$ResultPath" 2>&1 |
        Tee-Object -FilePath $ApplyLog
    if ($LASTEXITCODE -ne 0) {
        throw "Megawave execute завершился с ошибкой."
    }
    if (-not (Test-Path -LiteralPath $ResultPath -PathType Leaf)) {
        throw "Megawave execute не создал result journal."
    }

    $ResultJson = Get-Content -LiteralPath $ResultPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$ResultJson.status -ne "completed" -or
        [string]$ResultJson.plan_sha256 -cne [string]$PlanJson.plan_sha256) {
        throw "Result journal не подтверждает завершение точного megawave plan."
    }
    $ResultOperations = @($ResultJson.operations)
    if ($ResultOperations.Count -ne $ExpectedCount) {
        throw "Megawave result journal содержит неожиданное число операций."
    }
    $BadStatuses = @(
        $ResultOperations |
        Where-Object { [string]$_.status -notin @("updated_and_verified", "already_applied") }
    )
    if ($BadStatuses.Count -gt 0) {
        throw "Megawave result journal содержит неподтверждённый статус операции."
    }
    $RemoteWrites = @(
        $ResultOperations |
        Where-Object { [string]$_.status -eq "updated_and_verified" }
    ).Count

    video-manager vk scan `
        --account "$Account" `
        --community "$Community" `
        --output "$FinalSnapshot"
    if ($LASTEXITCODE -ne 0) {
        throw "Финальный read-only VK scan после megawave завершился ошибкой."
    }

    $RunStatus = "completed"
    Write-Handoff

    & py -3.11 -X utf8 .\scripts\verify_vk_p1_megawave_apply_bundle.py `
        "$ZipPath" `
        --json-output "$FinalVerification"
    if ($LASTEXITCODE -ne 0) {
        throw "Megawave apply ZIP не прошёл независимую postflight-проверку."
    }
    Copy-Artifact $FinalVerification "10-independent-verification.json"
    Write-Handoff

    & py -3.11 -X utf8 .\scripts\verify_vk_p1_megawave_apply_bundle.py "$ZipPath"
    if ($LASTEXITCODE -ne 0) {
        throw "Финальный megawave ZIP с embedded verification не прошёл повторную проверку."
    }
    $HandoffVerified = $true

    Write-Host ""
    Write-Host "ЕДИНАЯ VK P1-МЕГАВОЛНА ЗАВЕРШЕНА И POSTFLIGHT-ПОДТВЕРЖДЕНА" -ForegroundColor Green
    Write-Host $ZipPath -ForegroundColor Cyan
}
catch {
    $RunStatus = "failed"
    $RunError = $_.Exception.Message
    Write-Host ""
    Write-Host "ОШИБКА: $RunError" -ForegroundColor Red
}
finally {
    try {
        if (-not $HandoffVerified) {
            Write-Handoff
            Write-Host ""
            Write-Host "Создан диагностический megawave ZIP:" -ForegroundColor Yellow
            Write-Host $ZipPath -ForegroundColor Cyan
        }
        if (-not $NoOpen -and $IsWindows -and (Test-Path -LiteralPath $ZipPath)) {
            Start-Process explorer.exe -ArgumentList "/select,`"$ZipPath`""
        }
    }
    finally {
        if (Test-Path -LiteralPath $TempDir) {
            Remove-Item -LiteralPath $TempDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $BundleDir) {
            Remove-Item -LiteralPath $BundleDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

if ($RunStatus -ne "completed" -or -not $HandoffVerified) {
    throw $RunError
}
