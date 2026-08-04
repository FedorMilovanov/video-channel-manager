[CmdletBinding()]
param(
    [string]$ApplyBundle,
    [string]$ReviewBundle,
    [switch]$NoOpen,
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
$Handoffs = Join-Path $Repo "data\handoffs"
$Reports = Join-Path $Repo "data\reports"
$Decisions = Join-Path $Repo "content\policies\vk-reviewed-corrections-p1-fet-whisper-20260727.json"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BundleName = "vk-reviewed-correction-p1-fet-dry-run-$Stamp"
$BundleDir = Join-Path $Handoffs $BundleName
$ZipPath = Join-Path $Handoffs "$BundleName.zip"
$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) "video-channel-manager\$BundleName"
$Snapshot = Join-Path $TempDir "source-vk-snapshot.json"
$SourceApplyVerification = Join-Path $TempDir "source-apply-verification.json"
$Plan = Join-Path $Reports "vk-reviewed-correction-p1-fet-$Stamp.json"
$Report = Join-Path $Reports "vk-reviewed-correction-p1-fet-$Stamp.md"
$HtmlReport = Join-Path $Reports "vk-reviewed-correction-p1-fet-$Stamp.html"
$BuildLog = Join-Path $BundleDir "00-build.txt"
$Preflight = Join-Path $BundleDir "01-preflight.txt"
$ManifestPath = Join-Path $BundleDir "manifest.json"
$ReadmePath = Join-Path $BundleDir "README.txt"

$RunStatus = "started"
$RunError = $null
$Ready = $null
$AlreadyApplied = $null
$Conflicts = $null
$PlanJson = $null

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
        $Entry = $Archive.Entries |
            Where-Object { [System.IO.Path]::GetFileName($_.FullName) -ceq $Name } |
            Select-Object -First 1
        if ($null -eq $Entry) {
            throw "В ZIP не найден обязательный файл: $Name"
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

function Read-Count {
    param([string]$Text, [string]$Label)

    $Match = [regex]::Match(
        $Text,
        "(?m)^\s*" + [regex]::Escape($Label) + ":\s*(\d+)\s*$"
    )
    if (-not $Match.Success) {
        throw "Не удалось прочитать '$Label' из preflight."
    }
    return [int]$Match.Groups[1].Value
}

function Copy-File {
    param([string]$Path, [string]$Name)

    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        Copy-Item -LiteralPath $Path -Destination (Join-Path $BundleDir $Name) -Force
    }
}

function Start-Safely {
    param([scriptblock]$Action)

    try {
        & $Action
    }
    catch {
        Write-Warning "Не удалось открыть артефакт автоматически: $($_.Exception.Message)"
    }
}

function Write-Handoff {
    New-Item -ItemType Directory -Path $Handoffs, $BundleDir -Force | Out-Null

    $ArtifactKind = if ($RunStatus -eq "completed") {
        "verified dry-run"
    }
    else {
        "failed diagnostic"
    }
    $Readme = @"
VK REVIEWED CORRECTION P1 — ФЕТ

Тип пакета: $ArtifactKind
Статус: $RunStatus
Community: $Community
Ready: $Ready
Already applied: $AlreadyApplied
Conflicts: $Conflicts
Ошибка: $RunError

Разрешённый scope:
- ровно два описания «Шёпот, робкое дыханье…»;
- академическая датировка и точная атрибуция критики Чернышевского;
- различение установленного факта, биографического фона и гипотезы;
- исправление утверждений о Марии Лазич, поздней любовной лирике и последних часах Фета;
- удаление одного оборванного дубликата footer.

Заморожено:
- оба названия;
- остальные 109 описаний;
- 17 альбомов и 294 membership-пары;
- состав из 111 видео;
- ссылки, хэштеги, текст стихотворения и музыкальная рамка.

DRY-RUN НЕ ВЫЗЫВАЕТ VK MUTATION API.

При status=completed этот ZIP можно передавать на независимую проверку.
При status=failed это только диагностический пакет; execute по нему запрещён.

Файл:
$ZipPath
"@
    Set-Content -LiteralPath $ReadmePath -Value $Readme -Encoding UTF8

    $Files = Get-ChildItem -LiteralPath $BundleDir -File |
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

    $Manifest = [ordered]@{
        schema_name = "video-manager.vk-reviewed-correction-handoff"
        schema_version = 2
        created_at = (Get-Date).ToUniversalTime().ToString("o")
        status = $RunStatus
        artifact_kind = $ArtifactKind
        mode = "dry-run"
        component_scope = "descriptions_only"
        correction_scope = "reviewed_factual_and_sensitive"
        decision_set_id = "p1-fet-whisper-20260727"
        community_id = $Community
        ready = $Ready
        already_applied = $AlreadyApplied
        conflicts = $Conflicts
        remote_writes = 0
        error = $RunError
        plan_sha256 = if ($null -ne $PlanJson) { [string]$PlanJson.plan_sha256 } else { $null }
        source_apply_bundle = $ApplyBundle
        source_apply_bundle_sha256 = if ($ApplyBundle) {
            "sha256:$((Get-FileHash -LiteralPath $ApplyBundle -Algorithm SHA256).Hash.ToLowerInvariant())"
        }
        else { $null }
        source_review_bundle = $ReviewBundle
        source_review_bundle_sha256 = if ($ReviewBundle) {
            "sha256:$((Get-FileHash -LiteralPath $ReviewBundle -Algorithm SHA256).Hash.ToLowerInvariant())"
        }
        else { $null }
        files = $Files
    }
    $Manifest | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8

    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }
    Compress-Archive -Path (Join-Path $BundleDir "*") -DestinationPath $ZipPath -CompressionLevel Optimal

    Write-Host ""
    if ($RunStatus -eq "completed") {
        Write-Host "ГОТОВ VERIFIED REVIEWED CORRECTION P1 FET DRY-RUN ZIP:" -ForegroundColor Green
    }
    else {
        Write-Host "СОЗДАН ДИАГНОСТИЧЕСКИЙ ZIP; DRY-RUN НЕ ПОСТРОЕН:" -ForegroundColor Yellow
    }
    Write-Host $ZipPath -ForegroundColor Cyan
    Write-Host "VK-записей: 0"

    if (-not $NoOpen -and $IsWindows) {
        $PlanHtmlInBundle = Join-Path $BundleDir "plan-review.html"
        if ($RunStatus -eq "completed" -and (Test-Path -LiteralPath $PlanHtmlInBundle -PathType Leaf)) {
            Start-Safely { Start-Process $PlanHtmlInBundle }
        }
        if (Test-Path -LiteralPath $ZipPath -PathType Leaf) {
            Start-Safely { Start-Process explorer.exe -ArgumentList "/select,`"$ZipPath`"" }
        }
    }
}

try {
    Set-Location -LiteralPath $Repo
    New-Item -ItemType Directory -Path $Handoffs, $Reports, $BundleDir, $TempDir -Force | Out-Null

    if ([string]::IsNullOrWhiteSpace($ApplyBundle)) {
        $ApplyBundle = Get-LatestFile `
            "vk-reviewed-correction-p1-apply-*.zip" `
            "Не найден apply-ZIP предыдущей independently verified correction-wave."
    }
    if ([string]::IsNullOrWhiteSpace($ReviewBundle)) {
        $ReviewBundle = Get-LatestFile `
            "vk-deferred-editorial-review-*.zip" `
            "Не найден deferred editorial review-ZIP."
    }
    $ApplyBundle = (Resolve-Path -LiteralPath $ApplyBundle).Path
    $ReviewBundle = (Resolve-Path -LiteralPath $ReviewBundle).Path

    if (-not (Test-Path -LiteralPath $Decisions -PathType Leaf)) {
        throw "Не найден reviewed decisions JSON: $Decisions"
    }

    Write-Host "Независимо проверяется source apply-ZIP предыдущей correction-wave..." -ForegroundColor Yellow
    & py -3.11 -X utf8 .\scripts\verify_vk_reviewed_correction_apply_bundle.py `
        "$ApplyBundle" `
        --json-output "$SourceApplyVerification"
    if ($LASTEXITCODE -ne 0) {
        throw "Source correction apply-ZIP не прошёл независимую проверку."
    }
    $SourceApplyReport = Get-Content -LiteralPath $SourceApplyVerification -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$SourceApplyReport.status -ne "verified_completed" -or
        [int]$SourceApplyReport.operations -ne 3 -or
        [int]$SourceApplyReport.non_target_videos_verified_unchanged -ne 108) {
        throw "Source apply verification имеет неожиданный статус или scope."
    }

    Expand-BundleEntry -Bundle $ApplyBundle -Name "04-final-vk-snapshot.json" -Destination $Snapshot

    Copy-File $Snapshot "00-source-vk-snapshot.json"
    Copy-File $SourceApplyVerification "source-apply-verification.json"
    Copy-File $Decisions "reviewed-decisions.json"
    Copy-File $ReviewBundle "source-review-bundle.zip"

    $BuildOutput = & py -3.11 -X utf8 .\scripts\build_vk_reviewed_correction_wave.py `
        "$Snapshot" `
        --decisions-json "$Decisions" `
        --review-bundle "$ReviewBundle" `
        --output "$Plan" `
        --report "$Report" `
        --html-report "$HtmlReport" 2>&1
    $BuildExitCode = $LASTEXITCODE
    $BuildText = ($BuildOutput | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    Set-Content -LiteralPath $BuildLog -Value $BuildText -Encoding UTF8
    Write-Host $BuildText
    if ($BuildExitCode -ne 0) {
        throw "Не удалось построить Fet reviewed correction plan. Подробности сохранены в 00-build.txt.`n$BuildText"
    }

    $PlanJson = Get-Content -LiteralPath $Plan -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$PlanJson.component_scope -ne "descriptions_only" -or
        [string]$PlanJson.correction_scope -ne "reviewed_factual_and_sensitive" -or
        [string]$PlanJson.decision_set_id -ne "p1-fet-whisper-20260727") {
        throw "Fet correction plan имеет неожиданный scope."
    }
    if ([int]$PlanJson.summary.descriptions_to_update -ne 2 -or
        [int]$PlanJson.summary.total_operations -ne 2 -or
        [int]$PlanJson.summary.titles_to_update -ne 0 -or
        [int]$PlanJson.summary.albums_to_rename -ne 0 -or
        [int]$PlanJson.summary.placements_to_add -ne 0 -or
        [int]$PlanJson.summary.placements_to_remove -ne 0 -or
        [int]$PlanJson.summary.videos_to_delete -ne 0) {
        throw "Ожидалось ровно два descriptions-only исправления Фета."
    }
    $Operations = @($PlanJson.video_text_operations)
    $ActualIds = @($Operations | ForEach-Object { [string]$_.target_video_id } | Sort-Object)
    $ExpectedIds = @("-235216998_456239127", "-235216998_456239143")
    if (($ActualIds -join "|") -cne ($ExpectedIds -join "|")) {
        throw "Fet correction plan содержит неожиданные video IDs."
    }
    $TooLong = @($Operations | Where-Object { ([string]$_.after_description).Length -gt 5000 })
    if ($TooLong.Count -gt 0) {
        throw "Fet correction plan содержит описание длиннее 5000 символов."
    }

    Copy-File $Plan "plan.json"
    Copy-File $Report "plan-review.md"
    Copy-File $HtmlReport "plan-review.html"

    $Output = & py -3.11 -X utf8 .\scripts\apply_vk_editorial_cleanup_plan.py `
        "$Plan" `
        --account "$Account" `
        --community $Community `
        --max-operations 2 2>&1
    $ExitCode = $LASTEXITCODE
    $Text = ($Output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    Set-Content -LiteralPath $Preflight -Value $Text -Encoding UTF8
    Write-Host $Text
    if ($ExitCode -ne 0) {
        throw "Live Fet correction preflight завершился с кодом $ExitCode."
    }

    $Ready = Read-Count $Text "ready"
    $AlreadyApplied = Read-Count $Text "already applied"
    $Conflicts = Read-Count $Text "conflicts"
    if ($Ready + $AlreadyApplied -ne 2 -or $Conflicts -ne 0) {
        throw "Unexpected Fet correction preflight: ready=$Ready already=$AlreadyApplied conflicts=$Conflicts"
    }
    $RunStatus = "completed"
}
catch {
    $RunStatus = "failed"
    $RunError = $_.Exception.Message
    Write-Host $RunError -ForegroundColor Red
}
finally {
    try {
        Write-Handoff
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

if ($RunStatus -ne "completed") {
    throw $RunError
}
