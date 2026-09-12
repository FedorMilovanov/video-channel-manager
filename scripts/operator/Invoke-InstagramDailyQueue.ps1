[CmdletBinding()]
param(
    [string]$QueuePath,
    [string]$SourceId,
    [switch]$Prepare,
    [switch]$Stage,
    [switch]$Plan,
    [string]$OutputRoot,
    [string]$ReleaseRepository = "FedorMilovanov/FedorMilovanov.github.io",
    [string]$ReleaseTag = "instagram-staging"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$RepositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
if (-not $QueuePath) {
    $QueuePath = Join-Path $RepositoryRoot "content\instagram\legendary-poet-daily-reels-queue-20260913.json"
}
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $RepositoryRoot "data\instagram\daily-prep"
}
$QueuePath = [IO.Path]::GetFullPath($QueuePath)
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)

$env:VCM_INSTAGRAM_WRITES_ENABLED = "false"
$env:VCM_INSTAGRAM_MEDIA_ALLOWED_HOSTS = '["github.com","release-assets.githubusercontent.com"]'

$RuntimeRoot = $RepositoryRoot
$VideoManager = Join-Path $RuntimeRoot ".venv\Scripts\video-manager.exe"
$PythonExe = Join-Path $RuntimeRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VideoManager)) {
    $GitCommonDir = (& git.exe -C $RepositoryRoot rev-parse --git-common-dir).Trim()
    if (-not [IO.Path]::IsPathRooted($GitCommonDir)) {
        $GitCommonDir = [IO.Path]::GetFullPath((Join-Path $RepositoryRoot $GitCommonDir))
    }
    if ([IO.Path]::GetFileName($GitCommonDir) -eq ".git") {
        $RuntimeRoot = [IO.Path]::GetDirectoryName($GitCommonDir)
        $VideoManager = Join-Path $RuntimeRoot ".venv\Scripts\video-manager.exe"
        $PythonExe = Join-Path $RuntimeRoot ".venv\Scripts\python.exe"
    }
}
if (-not (Test-Path -LiteralPath $VideoManager) -or -not (Test-Path -LiteralPath $PythonExe)) {
    throw "video-manager runtime not found in worktree or common repository."
}
$env:PYTHONPATH = Join-Path $RepositoryRoot "src"

$DatabasePath = Join-Path $RuntimeRoot "data\video_manager.db"
$LedgerStatuses = @{}
if (Test-Path -LiteralPath $DatabasePath) {
    $StatusJson = & $PythonExe -c 'import json,sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(json.dumps(dict(c.execute("select publication_key,status from instagram_publications").fetchall())))' $DatabasePath
    if ($LASTEXITCODE -ne 0) { throw "Failed to read Instagram durable ledger." }
    if ($StatusJson) {
        $StatusObject = $StatusJson | ConvertFrom-Json
        foreach ($Property in $StatusObject.PSObject.Properties) {
            $LedgerStatuses[$Property.Name] = [string]$Property.Value
        }
    }
}

$Queue = Get-Content -Raw -LiteralPath $QueuePath | ConvertFrom-Json
$Ready = @(
    $Queue.items |
        Where-Object { $_.status -eq "ready" } |
        Sort-Object { [DateTimeOffset]$_.scheduled_at }
)
if ($Ready.Count -eq 0) {
    throw "Queue has no ready Instagram Reels."
}

if ($SourceId) {
    $Selected = $Ready | Where-Object { $_.source_id -eq $SourceId } | Select-Object -First 1
    if (-not $Selected) { throw "SourceId '$SourceId' is not a ready queue item." }
    $ExplicitStatus = $LedgerStatuses[[string]$Selected.publication_key]
    if ($ExplicitStatus -eq "published") {
        throw "SourceId '$SourceId' is already published according to the durable ledger."
    }
}
else {
    $Selected = $null
    foreach ($Candidate in $Ready) {
        $LedgerStatus = $LedgerStatuses[[string]$Candidate.publication_key]
        if ($LedgerStatus -eq "published") { continue }
        if ($LedgerStatus -and $LedgerStatus -ne "planned") {
            throw ("Instagram daily queue is fail-closed on {0}: durable ledger status is {1}; reconcile before advancing." -f
                $Candidate.publication_key, $LedgerStatus)
        }
        $Selected = $Candidate
        break
    }
    if (-not $Selected) {
        Write-Host "All ready Instagram Reel publication keys are already published."
        exit 0
    }
}

Write-Host ("Instagram daily queue: {0} total / {1} ready / {2} published / {3} rights-review" -f
    $Queue.item_count, $Queue.ready_count, $Queue.published_count, $Queue.rights_review_count)
Write-Host ("Selected: {0} | {1} | scheduled {2}" -f
    $Selected.source_id, $Selected.source_title, $Selected.scheduled_at)
Write-Host ("Publication key: {0}" -f $Selected.publication_key)
Write-Host "Meta provider writes: disabled."

if (-not $Prepare) {
    exit 0
}
$YtDlp = (Get-Command yt-dlp.exe -ErrorAction Stop).Source
$Ffmpeg = (Get-Command ffmpeg.exe -ErrorAction Stop).Source
if ($Stage) { $null = Get-Command gh.exe -ErrorAction Stop }
Set-Location $RuntimeRoot

$WorkDir = Join-Path $OutputRoot $Selected.source_id
[IO.Directory]::CreateDirectory($WorkDir) | Out-Null
$SourceTemplate = Join-Path $WorkDir "youtube-source.%(ext)s"
$SourceMp4 = Join-Path $WorkDir "youtube-source.mp4"
$CleanMp4 = Join-Path $WorkDir "instagram-clean.mp4"

& $YtDlp --no-warnings -f 'bv*[vcodec^=avc1][ext=mp4]+ba[ext=m4a]/137+140' --merge-output-format mp4 -o $SourceTemplate $Selected.source_url
if ($LASTEXITCODE -ne 0) { throw "yt-dlp failed with exit $LASTEXITCODE" }

& $Ffmpeg -hide_banner -y -i $SourceMp4 -map 0:v:0 -map 0:a:0 -c copy -use_editlist 0 -movflags +faststart $CleanMp4
if ($LASTEXITCODE -ne 0) { throw "ffmpeg remux failed with exit $LASTEXITCODE" }

# Establish exact-byte stability before the structural/GOP probe. On Windows,
# faststart rewrites the MP4; a complete SHA read is the deterministic barrier.
$FileBeforeHash = Get-Item -LiteralPath $CleanMp4
$Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $CleanMp4).Hash.ToLowerInvariant()
$File = Get-Item -LiteralPath $CleanMp4
if ($File.Length -ne $FileBeforeHash.Length) {
    throw "Instagram clean MP4 changed size while establishing exact-byte stability."
}

& $VideoManager instagram production validate-local $CleanMp4
if ($LASTEXITCODE -ne 0) { throw "Instagram validate-local failed." }

$AssetName = "$Sha.mp4"
$AssetPath = Join-Path $WorkDir $AssetName
Copy-Item -LiteralPath $CleanMp4 -Destination $AssetPath -Force

if (-not $Stage) {
    Write-Host ("Prepared local Reel: {0} bytes sha256:{1}" -f $File.Length, $Sha)
    Write-Host "Public staging skipped because -Stage was not supplied."
    exit 0
}
& gh.exe release upload $ReleaseTag $AssetPath --repo $ReleaseRepository --clobber
if ($LASTEXITCODE -ne 0) { throw "GitHub Release staging failed." }

$VideoUrl = "https://github.com/$ReleaseRepository/releases/download/$ReleaseTag/$AssetName"
$ManifestPath = Join-Path $WorkDir "manifest.json"
$Manifest = [ordered]@{
    schema_version = "1"
    publication_key = [string]$Selected.publication_key
    account_id = [string]$Queue.account_id
    video_url = $VideoUrl
    media_sha256 = "sha256:$Sha"
    media_size_bytes = [int64]$File.Length
    media_content_type = "video/mp4"
    caption = [string]$Selected.caption
    share_to_feed = $true
    cover_url = $null
    cover_sha256 = $null
    cover_size_bytes = $null
    cover_content_type = $null
    thumb_offset_ms = $null
}
$Json = $Manifest | ConvertTo-Json -Depth 6
[IO.File]::WriteAllText($ManifestPath, $Json, [Text.UTF8Encoding]::new($false))

& $VideoManager instagram production validate-public $ManifestPath
if ($LASTEXITCODE -ne 0) { throw "Instagram validate-public failed." }

if ($Plan) {
    & $VideoManager instagram production plan $ManifestPath
    if ($LASTEXITCODE -ne 0) { throw "Instagram plan failed." }
}

Write-Host ("Prepared exact manifest: {0}" -f $ManifestPath)
Write-Host ("Public URL: {0}" -f $VideoUrl)
Write-Host "Meta provider writes: none."
