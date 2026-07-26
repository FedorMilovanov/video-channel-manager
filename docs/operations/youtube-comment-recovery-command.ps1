$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Repo = "C:\Users\Fedor\Projects\video-channel-manager"
$Channel = "UC-78ys2S3cQ3lpqgXfo-SvQ"
$Plan = "C:\path\to\original-signed-plan.json"
$Journal = "C:\path\to\original-apply-journal.json"

Set-Location -LiteralPath $Repo
$env:VCM_DATA_DIR = Join-Path $Repo "data"
$env:VCM_YOUTUBE_CLIENT_SECRET_FILE = Join-Path $Repo "secrets\client_secret.json"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

& py -3.11 -X utf8 .\scripts\recover_youtube_comment_wave.py `
    $Plan `
    --journal $Journal `
    --account legendary-poet `
    --channel $Channel `
    --max-operations 200

if ($LASTEXITCODE -ne 0) {
    throw "YouTube recovery did not produce a valid coverage certificate. No create/update mode was used."
}
