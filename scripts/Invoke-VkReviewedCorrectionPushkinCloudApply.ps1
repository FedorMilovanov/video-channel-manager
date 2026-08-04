[CmdletBinding()]
param(
    [switch]$Execute,
    [string]$ReviewedDryRunBundle,
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
# VCM-WAVE5-RETIRED-GUARD
$VcmOperatorModule = Join-Path $PSScriptRoot "operator\VideoManager.Operator.psm1"
Import-Module -Name $VcmOperatorModule -Force -ErrorAction Stop
Stop-VcmRetiredWrapper -WrapperPath $PSCommandPath -RepositoryRoot (Split-Path -Parent $PSScriptRoot)


[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ExpectedCount = 1
$ExpectedDecisionSet = "p1-pushkin-cloud-20260728"
$ExpectedIds = @("-235216998_456239106")

$Repo = Split-Path -Parent $PSScriptRoot
$Handoffs = Join-Path $Repo "data\handoffs"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BundleName = "vk-reviewed-correction-p1-pushkin-cloud-apply-$Stamp"
$BundleDir = Join-Path $Handoffs $BundleName
$ZipPath = Join-Path $Handoffs "$BundleName.zip"
$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) "video-channel-manager\$BundleName"

$Plan = Join-Path $TempDir "plan.json"
$PlanReport = Join-Path $TempDir "plan-review.md"
$PlanHtml = Join-Path $TempDir "plan-review.html"
$SourceSnapshot = Join-Path $TempDir "00-source-vk-snapshot.json"
$Decisions = Join-Path $TempDir "reviewed-decisions.json"
$SourceReviewBundle = Join-Path $TempDir "source-review-bundle.zip"
$DryRunVerification = Join-Path $TempDir "dry-run-verification.json"
$FinalVerification = Join-Path $TempDir "final-verification.json"

$PreflightLog = Join-Path $BundleDir "01-preflight.txt"
$ApplyLog = Join-Path $BundleDir "02-apply.txt"
$ResultPath = Join-Path $BundleDir "03-result.json"
$FinalSnapshot = Join-Path $BundleDir "04-final-vk-snapshot.json"
$ManifestPath = Join-Path $BundleDir "manifest.json"
$ReadmePath = Join-Path $BundleDir "README.txt"

$RunStatus = "started"
$RunError = $null
$Ready = $null
$AlreadyApplied = $null
$Conflicts = $null
$RemoteWrites = 0
$PlanJson = $null
$ResolvedDryRun = $null
$HandoffVerified = $false

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
        $Entry = $Archive.Entries |
            Where-Object { [System.IO.Path]::GetFileName($_.FullName) -ceq $Name } |
            Select-Object -First 1
        if ($null -eq $Entry) {
            throw "В reviewed Pushkin Cloud dry-run ZIP не найден обязательный файл: $Name"
        }
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile(
            $Entry,
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
        throw "Не удалось прочитать '$Label' из live Pushkin Cloud preflight."
    }
    return [int]$Match.Groups[1].Value
}

function Write-Handoff {
    New-Item -ItemType Directory -Path $Handoffs, $BundleDir -Force | Out-Null

    $Readme = @"
VK REVIEWED CORRECTION P1 — ПУШКИН «ТУЧА» — APPLY

Статус: $RunStatus
Community: $Community
Decision set: $ExpectedDecisionSet
Ready перед execute: $Ready
Already applied перед execute: $AlreadyApplied
Conflicts: $Conflicts
Подтверждённых VK-записей: $RemoteWrites
Ошибка: $RunError

Разрешённый scope:
- ровно одно описание «Туча»;
- возраст, семья и служебная хронология Пушкина в 1833–1835 годах;
- первая публикация и авторская правка текста;
- различение дуэли 27 января и смерти 29 января 1837 года;
- отделение документированного факта от поздней литературной интерпретации.

Заморожено:
- все 111 названий;
- остальные 110 описаний;
- 17 коллекций и их названия;
- 294 membership-пары;
- состав из 111 видео;
- ссылки, хэштеги, стихотворные цитаты, footer и музыкальная рамка.

Этот ZIP содержит точный reviewed dry-run, свежий preflight, result journal,
финальный VK snapshot и независимую postflight-проверку, если execute завершён.
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

    $DryRunSha = if ($null -ne $ResolvedDryRun -and (Test-Path -LiteralPath $ResolvedDryRun)) {
        "sha256:$((Get-FileHash -LiteralPath $ResolvedDryRun -Algorithm SHA256).Hash.ToLowerInvariant())"
    }
    else {
        $null
    }

    $Manifest = [ordered]@{
        schema_name = "video-manager.vk-reviewed-correction-apply-handoff"
        schema_version = 2
        created_at = (Get-Date).ToUniversalTime().ToString("o")
        status = $RunStatus
        artifact_kind = if ($RunStatus -eq "completed") { "verified apply candidate" } else { "diagnostic apply handoff" }
        mode = "apply"
        component_scope = "descriptions_only"
        correction_scope = "reviewed_factual_and_sensitive"
        decision_set_id = $ExpectedDecisionSet
        community_id = $Community
        ready = $Ready
        already_applied = $AlreadyApplied
        conflicts = $Conflicts
        remote_writes = $RemoteWrites
        error = $RunError
        plan_sha256 = if ($null -ne $PlanJson) { [string]$PlanJson.plan_sha256 } else { $null }
        source_dry_run_bundle = $ResolvedDryRun
        source_dry_run_bundle_sha256 = $DryRunSha
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
    New-Item -ItemType Directory -Path $Handoffs, $BundleDir, $TempDir -Force | Out-Null

    if (-not $Execute) {
        throw "Этот helper выполняет только точный проверенный Pushkin Cloud ZIP. Добавьте явный флаг -Execute."
    }

    if ([string]::IsNullOrWhiteSpace($ReviewedDryRunBundle)) {
        $Latest = Get-ChildItem `
            -LiteralPath $Handoffs `
            -File `
            -Filter "vk-reviewed-correction-p1-pushkin-cloud-dry-run-*.zip" |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($null -eq $Latest) {
            throw "Не найден reviewed Pushkin Cloud dry-run ZIP."
        }
        $ReviewedDryRunBundle = $Latest.FullName
    }
    $ResolvedDryRun = (Resolve-Path -LiteralPath $ReviewedDryRunBundle).Path

    Write-Host "Независимо проверяется точный Pushkin Cloud dry-run ZIP..." -ForegroundColor Yellow
    & py -3.11 -X utf8 .\scripts\verify_vk_reviewed_correction_pushkin_cloud_dry_run.py `
        "$ResolvedDryRun" `
        --json-output "$DryRunVerification"
    if ($LASTEXITCODE -ne 0) {
        throw "Pushkin Cloud dry-run ZIP не прошёл независимую проверку."
    }
    $DryRunReport = Get-Content -LiteralPath $DryRunVerification -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$DryRunReport.status -ne "verified_dry_run" -or
        [string]$DryRunReport.artifact_review -ne "exact_independently_reviewed_contents" -or
        [int]$DryRunReport.operations -ne $ExpectedCount -or
        [int]$DryRunReport.remote_writes -ne 0 -or
        -not [bool]$DryRunReport.canonical_text_hashes_verified -or
        -not [bool]$DryRunReport.reviewed_replacements_reconstructed -or
        -not [bool]$DryRunReport.urls_and_hashtags_unchanged -or
        -not [bool]$DryRunReport.exact_member_hashes_verified) {
        throw "Pushkin Cloud dry-run verification report имеет неожиданный статус или scope."
    }
    $VerifiedIds = @($DryRunReport.target_video_ids | ForEach-Object { [string]$_ } | Sort-Object)
    if (($VerifiedIds -join "|") -cne ($ExpectedIds -join "|")) {
        throw "Независимый verifier подтвердил другой набор video IDs."
    }

    Expand-BundleEntry $ResolvedDryRun "plan.json" $Plan
    Expand-BundleEntry $ResolvedDryRun "plan-review.md" $PlanReport
    Expand-BundleEntry $ResolvedDryRun "plan-review.html" $PlanHtml
    Expand-BundleEntry $ResolvedDryRun "00-source-vk-snapshot.json" $SourceSnapshot
    Expand-BundleEntry $ResolvedDryRun "reviewed-decisions.json" $Decisions
    Expand-BundleEntry $ResolvedDryRun "source-review-bundle.zip" $SourceReviewBundle

    $PlanJson = Get-Content -LiteralPath $Plan -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$PlanJson.plan_sha256 -cne [string]$DryRunReport.plan_sha256 -or
        [string]$PlanJson.decision_set_id -cne $ExpectedDecisionSet) {
        throw "Извлечённый plan.json отличается от проверенного Pushkin Cloud плана."
    }
    if ([int]$PlanJson.summary.descriptions_to_update -ne $ExpectedCount -or
        [int]$PlanJson.summary.total_operations -ne $ExpectedCount -or
        [int]$PlanJson.summary.titles_to_update -ne 0 -or
        [int]$PlanJson.summary.albums_to_rename -ne 0 -or
        [int]$PlanJson.summary.placements_to_add -ne 0 -or
        [int]$PlanJson.summary.placements_to_remove -ne 0 -or
        [int]$PlanJson.summary.videos_to_delete -ne 0) {
        throw "Извлечённый Pushkin Cloud plan имеет неожиданный scope."
    }
    $PlanIds = @(
        $PlanJson.video_text_operations |
        ForEach-Object { [string]$_.target_video_id } |
        Sort-Object
    )
    if (($PlanIds -join "|") -cne ($ExpectedIds -join "|")) {
        throw "Извлечённый plan.json содержит неожиданные video IDs."
    }

    Copy-Artifact $SourceSnapshot "00-source-vk-snapshot.json"
    Copy-Artifact $Plan "plan.json"
    Copy-Artifact $PlanReport "plan-review.md"
    Copy-Artifact $PlanHtml "plan-review.html"
    Copy-Artifact $Decisions "reviewed-decisions.json"
    Copy-Artifact $SourceReviewBundle "source-review-bundle.zip"
    Copy-Artifact $ResolvedDryRun "previous-reviewed-dry-run.zip"
    Copy-Artifact $DryRunVerification "dry-run-verification.json"

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
            throw "Live Pushkin Cloud preflight завершился с кодом $ExitCode."
        }
        if ($Attempt -lt $ReadRetryAttempts) {
            $Delay = $ReadRetryDelaySeconds * $Attempt
            Write-Host "Read-only video.get временно недоступен; повтор через $Delay секунд." -ForegroundColor Yellow
            Start-Sleep -Seconds $Delay
        }
    }
    if (-not $PreflightSucceeded) {
        throw "Live Pushkin Cloud preflight не завершился после $ReadRetryAttempts попыток."
    }

    $PreflightText = Get-Content -LiteralPath $PreflightLog -Raw -Encoding UTF8
    $Ready = Read-Count $PreflightText "ready"
    $AlreadyApplied = Read-Count $PreflightText "already applied"
    $Conflicts = Read-Count $PreflightText "conflicts"
    if ($Ready + $AlreadyApplied -ne $ExpectedCount -or $Conflicts -ne 0) {
        throw "Unexpected Pushkin Cloud preflight: ready=$Ready already=$AlreadyApplied conflicts=$Conflicts"
    }

    Write-Host ""
    Write-Host "ПРОВЕРЕННЫЙ PUSHKIN CLOUD ПЛАН ДОПУЩЕН К EXECUTE" -ForegroundColor Green
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
        --write-delay 1.0 `
        --result-output "$ResultPath" 2>&1 |
        Tee-Object -FilePath $ApplyLog
    if ($LASTEXITCODE -ne 0) {
        throw "Pushkin Cloud execute завершился с ошибкой."
    }
    if (-not (Test-Path -LiteralPath $ResultPath -PathType Leaf)) {
        throw "Pushkin Cloud execute не создал result journal."
    }

    $ResultJson = Get-Content -LiteralPath $ResultPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$ResultJson.status -ne "completed" -or
        [string]$ResultJson.plan_sha256 -cne [string]$PlanJson.plan_sha256) {
        throw "Result journal не подтверждает точный Pushkin Cloud план."
    }
    $ResultOperations = @($ResultJson.operations)
    if ($ResultOperations.Count -ne $ExpectedCount -or
        [string]$ResultOperations[0].remote_id -cne $ExpectedIds[0] -or
        [string]$ResultOperations[0].status -notin @("updated_and_verified", "already_applied")) {
        throw "Pushkin Cloud result journal имеет неожиданный scope или статус."
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
        throw "Финальный read-only VK scan после Pushkin Cloud correction завершился ошибкой."
    }

    $RunStatus = "completed"
    Write-Handoff

    & py -3.11 -X utf8 .\scripts\verify_vk_reviewed_correction_pushkin_cloud_apply_bundle.py `
        "$ZipPath" `
        --json-output "$FinalVerification"
    if ($LASTEXITCODE -ne 0) {
        throw "Pushkin Cloud apply ZIP не прошёл независимую postflight-проверку."
    }
    Copy-Artifact $FinalVerification "05-independent-verification.json"
    Write-Handoff

    & py -3.11 -X utf8 .\scripts\verify_vk_reviewed_correction_pushkin_cloud_apply_bundle.py "$ZipPath"
    if ($LASTEXITCODE -ne 0) {
        throw "Финальный Pushkin Cloud ZIP с embedded verification не прошёл повторную проверку."
    }
    $HandoffVerified = $true

    Write-Host ""
    Write-Host "PUSHKIN CLOUD ЗАВЕРШЕНА И POSTFLIGHT-ПОДТВЕРЖДЕНА" -ForegroundColor Green
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
            Write-Host "Создан диагностический Pushkin Cloud apply ZIP:" -ForegroundColor Yellow
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
