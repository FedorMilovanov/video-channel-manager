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

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Repo = Split-Path -Parent $PSScriptRoot
$Handoffs = Join-Path $Repo "data\handoffs"
$Reports = Join-Path $Repo "data\reports"
$Decisions = Join-Path $Repo "content\policies\vk-reviewed-corrections-p1-esenin-confession-20260727.json"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BundleName = "vk-reviewed-correction-p1-dry-run-$Stamp"
$BundleDir = Join-Path $Handoffs $BundleName
$ZipPath = Join-Path $Handoffs "$BundleName.zip"
$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) "video-channel-manager\$BundleName"
$Snapshot = Join-Path $TempDir "source-vk-snapshot.json"
$Plan = Join-Path $Reports "vk-reviewed-correction-p1-$Stamp.json"
$Report = Join-Path $Reports "vk-reviewed-correction-p1-$Stamp.md"
$HtmlReport = Join-Path $Reports "vk-reviewed-correction-p1-$Stamp.html"
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
    if ($null -eq $File) { throw $ErrorText }
    return $File.FullName
}

function Expand-FinalSnapshot {
    param([string]$Bundle, [string]$Destination)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $Archive = [System.IO.Compression.ZipFile]::OpenRead($Bundle)
    try {
        $Entry = $Archive.Entries |
            Where-Object { [System.IO.Path]::GetFileName($_.FullName) -eq "04-final-vk-snapshot.json" } |
            Select-Object -First 1
        if ($null -eq $Entry) { throw "В apply-ZIP нет 04-final-vk-snapshot.json: $Bundle" }
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($Entry, $Destination, $true)
    }
    finally { $Archive.Dispose() }
}

function Read-Count {
    param([string]$Text, [string]$Label)
    $Match = [regex]::Match($Text, "(?m)^\s*" + [regex]::Escape($Label) + ":\s*(\d+)\s*$")
    if (-not $Match.Success) { throw "Не удалось прочитать '$Label' из preflight." }
    return [int]$Match.Groups[1].Value
}

function Copy-File {
    param([string]$Path, [string]$Name)
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        Copy-Item -LiteralPath $Path -Destination (Join-Path $BundleDir $Name) -Force
    }
}

function Write-Handoff {
    $Readme = @"
VK REVIEWED CORRECTION P1 — DRY-RUN

Статус: $RunStatus
Community: $Community
Ready: $Ready
Already applied: $AlreadyApplied
Conflicts: $Conflicts
Ошибка: $RunError

Этот пакет содержит только три точных reviewed correction для роликов «Исповедь Самоубийцы»:
- академическая датировка 1913–1915 вместо 1912;
- духовный вывод, согласованный с PROJECT_CHARTER, богословскими стандартами The Legendary Poet и Research.

Названия, альбомы, memberships, состав видеотеки, остальные описания, ссылки, хэштеги и текст стихотворения заморожены.
DRY-RUN НЕ ВЫЗЫВАЕТ VK MUTATION API.

ОТПРАВИТЬ НУЖНО ТОЛЬКО:
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
        schema_version = 1
        created_at = (Get-Date).ToUniversalTime().ToString("o")
        status = $RunStatus
        mode = "dry-run"
        component_scope = "descriptions_only"
        correction_scope = "reviewed_factual_and_sensitive"
        community_id = $Community
        ready = $Ready
        already_applied = $AlreadyApplied
        conflicts = $Conflicts
        remote_writes = 0
        error = $RunError
        plan_sha256 = if ($null -ne $PlanJson) { [string]$PlanJson.plan_sha256 } else { $null }
        source_apply_bundle = $ApplyBundle
        source_review_bundle = $ReviewBundle
        files = $Files
    }
    $Manifest | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8
    if (Test-Path -LiteralPath $ZipPath) { Remove-Item -LiteralPath $ZipPath -Force }
    Compress-Archive -Path (Join-Path $BundleDir "*") -DestinationPath $ZipPath -CompressionLevel Optimal

    Write-Host ""
    Write-Host "ГОТОВ REVIEWED CORRECTION DRY-RUN ZIP:" -ForegroundColor Green
    Write-Host $ZipPath -ForegroundColor Cyan
    Write-Host "VK-записей: 0"
    if (-not $NoOpen -and $IsWindows) {
        Start-Process (Join-Path $BundleDir "plan-review.html")
        Start-Process explorer.exe -ArgumentList "/select,`"$ZipPath`""
    }
}

try {
    Set-Location -LiteralPath $Repo
    New-Item -ItemType Directory -Path $Handoffs, $Reports, $BundleDir, $TempDir -Force | Out-Null
    if ([string]::IsNullOrWhiteSpace($ApplyBundle)) {
        $ApplyBundle = Get-LatestFile "vk-description-wave-apply-*.zip" "Не найден verified description apply-ZIP."
    }
    if ([string]::IsNullOrWhiteSpace($ReviewBundle)) {
        $ReviewBundle = Get-LatestFile "vk-deferred-editorial-review-*.zip" "Не найден deferred editorial review-ZIP."
    }
    $ApplyBundle = (Resolve-Path -LiteralPath $ApplyBundle).Path
    $ReviewBundle = (Resolve-Path -LiteralPath $ReviewBundle).Path
    if (-not (Test-Path -LiteralPath $Decisions -PathType Leaf)) { throw "Не найден reviewed decisions JSON: $Decisions" }

    Expand-FinalSnapshot -Bundle $ApplyBundle -Destination $Snapshot

    & py -3.11 -X utf8 .\scripts\build_vk_reviewed_correction_wave.py `
        "$Snapshot" `
        --decisions-json "$Decisions" `
        --review-bundle "$ReviewBundle" `
        --output "$Plan" `
        --report "$Report" `
        --html-report "$HtmlReport"
    if ($LASTEXITCODE -ne 0) { throw "Не удалось построить reviewed correction plan." }

    $PlanJson = Get-Content -LiteralPath $Plan -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$PlanJson.component_scope -ne "descriptions_only") { throw "Correction plan is not descriptions_only." }
    if ([string]$PlanJson.correction_scope -ne "reviewed_factual_and_sensitive") { throw "Unexpected correction scope." }
    if ([int]$PlanJson.summary.descriptions_to_update -ne 3) { throw "Expected exactly 3 correction operations." }
    if ([int]$PlanJson.summary.titles_to_update -ne 0 -or [int]$PlanJson.summary.albums_to_rename -ne 0) {
        throw "Correction plan attempts non-description changes."
    }

    Copy-File $Snapshot "00-source-vk-snapshot.json"
    Copy-File $Decisions "reviewed-decisions.json"
    Copy-File $ReviewBundle "source-review-bundle.zip"
    Copy-File $Plan "plan.json"
    Copy-File $Report "plan-review.md"
    Copy-File $HtmlReport "plan-review.html"

    $Output = & py -3.11 -X utf8 .\scripts\apply_vk_editorial_cleanup_plan.py `
        "$Plan" `
        --account "$Account" `
        --community $Community `
        --max-operations 3 2>&1
    $ExitCode = $LASTEXITCODE
    $Text = ($Output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    Set-Content -LiteralPath $Preflight -Value $Text -Encoding UTF8
    Write-Host $Text
    if ($ExitCode -ne 0) { throw "Live correction preflight завершился с кодом $ExitCode." }

    $Ready = Read-Count $Text "ready"
    $AlreadyApplied = Read-Count $Text "already applied"
    $Conflicts = Read-Count $Text "conflicts"
    if ($Ready + $AlreadyApplied -ne 3 -or $Conflicts -ne 0) {
        throw "Unexpected correction preflight: ready=$Ready already=$AlreadyApplied conflicts=$Conflicts"
    }
    $RunStatus = "completed"
}
catch {
    $RunStatus = "failed"
    $RunError = $_.Exception.Message
    Write-Host $RunError -ForegroundColor Red
}
finally {
    try { Write-Handoff }
    finally {
        if (Test-Path -LiteralPath $TempDir) { Remove-Item -LiteralPath $TempDir -Recurse -Force }
        if (Test-Path -LiteralPath $BundleDir) { Remove-Item -LiteralPath $BundleDir -Recurse -Force }
    }
}

if ($RunStatus -ne "completed") { throw $RunError }
