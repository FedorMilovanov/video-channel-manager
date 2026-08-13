$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"

$Repo = Join-Path $HOME "Projects\video-channel-manager"
$Confirmation = "ISSUE_323_UPLOAD_12_CLIPS_AND_POSTPONE_DAILY"
$Result = Join-Path $Repo "operator-output\milovi-cake-issue-323-token-daily-rollout.json"
$Journal = Join-Path $Repo "data\vk\milovi-cake\issue-323-token-daily-rollout-journal.json"
$Schedule = Join-Path $Repo "data\vk\milovi-cake\issue-323-daily-wall-schedule.json"
$WorkDir = Join-Path $Repo "operator-output\milovi-cake-issue-323-work"

if (-not (Test-Path -LiteralPath $Repo -PathType Container)) {
    throw "Repository not found: $Repo"
}
Set-Location $Repo

$dirty = @(git status --porcelain --untracked-files=no)
if ($LASTEXITCODE -ne 0) { throw "git status failed" }
if ($dirty.Count -gt 0) { throw "Tracked working tree is dirty; live rollout stopped." }

git switch main
if ($LASTEXITCODE -ne 0) { throw "Cannot switch to main" }
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw "Cannot fast-forward main" }
$Head = (git rev-parse HEAD).Trim()
Write-Host "main: $Head" -ForegroundColor Cyan

$Python = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}
$env:PYTHONPATH = (Join-Path $Repo "src")

foreach ($tool in @("yt-dlp", "ffprobe")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "$tool is required on PATH. VK has not been changed."
    }
}

Write-Host ""
Write-Host "MILOVI CAKE #323 — TOKEN ONLY" -ForegroundColor Cyan
Write-Host "No browser. No cookies. No interactive VK login." -ForegroundColor Green
Write-Host "Preflight: all 12 vertical and <=60.0s BEFORE the first VK write." -ForegroundColor Green
Write-Host "Canary: d48QLgOuiTs -> exact type=short_video -> postponed wall post." -ForegroundColor Green
Write-Host "Then remaining 11; one postponed wall post per calendar day." -ForegroundColor Green
Write-Host ""

& $Python -m video_channel_manager.platforms.vk.milovi_token_clip_rollout `
    --execute $Confirmation `
    --output $Result `
    --journal $Journal `
    --schedule $Schedule `
    --work-dir $WorkDir `
    --verify-timeout 1800
$ExitCode = $LASTEXITCODE

if ($ExitCode -ne 0) {
    Write-Host "" 
    Write-Host "ROLLOUT STOPPED. DO NOT BLINDLY RERUN." -ForegroundColor Yellow
    Write-Host "Result: $Result"
    Write-Host "Journal: $Journal"
    if (Test-Path -LiteralPath $Result) {
        try { Start-Process explorer.exe -ArgumentList "/select,`"$Result`"" } catch {}
    }
    exit $ExitCode
}

if (-not (Test-Path -LiteralPath $Result -PathType Leaf)) {
    throw "Rollout returned success without result JSON: $Result"
}
$Payload = Get-Content -LiteralPath $Result -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Payload.status -ne "batch_verified" -or -not $Payload.canary_verified -or $Payload.browser_used) {
    throw "Result is not exact batch_verified token-only completion. Do not rerun blindly: $Result"
}
$Rows = @($Payload.items)
if ($Rows.Count -ne 12 -or @($Rows | Where-Object { $_.status -ne "wall_verified" -or -not $_.clip_remote_id -or -not $_.wall_remote_id }).Count -ne 0) {
    throw "Result does not prove 12/12 Clip + postponed wall mappings: $Result"
}

Write-Host ""
Write-Host "MILOVI CAKE #323 — BATCH VERIFIED" -ForegroundColor Green
Write-Host "12/12 native VK Clips verified; 12/12 postponed wall posts verified; browser=false." -ForegroundColor Green
Write-Host "Result: $Result"
try { Start-Process explorer.exe -ArgumentList "/select,`"$Result`"" } catch {}
