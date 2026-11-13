# One authorized Milovi Cake HTTPS canary, dispatched only by the existing 19:00 writer.
# No historical key replay and no generic publication authority for future sources.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_-]{11}$')][string]$YoutubeId,
    [Parameter(Mandatory=$true)][string]$OwnerApprovalFile,
    [switch]$Execute,
    [switch]$DryRun
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Execute -and $DryRun) { throw 'Execute and DryRun are mutually exclusive' }
$Repo = 'C:\Users\Fedor\Projects\video-channel-manager'
$Root = Join-Path $Repo 'operator-output\milovi-cake-instagram\2026-11-05'
$IndexPath = Join-Path $Root 'meta-verified\milovi-ig-original-audio-handoff-v5-daily-20261110-28.json'
$ManifestPath = Join-Path $Root 'meta-verified\milovi-ig-20261114-public-https-v1-candidate.json'
$DbPath = Join-Path $Repo 'data\video_manager.db'
$Account = '17841407843933779'
$AppId = '989716813600695'
$OriginalKey = 'milovi-cake.2026-11-14.yt-fbGZYKS7byM.original-audio-v1'
$UrlKey = 'milovi-cake.2026-11-14.yt-fbGZYKS7byM.public-https-v1'
$MediaDigest = '54b6731ca166a25405fb1ff135eb9bf5c0905a9bd5d03241ef432a80b692d2d3'
$FrozenIndexHash = '19a211320f32e3c0f16c0aad1ed23db4b2bd89f100bbd22b8d1b801734aba5a4'
$FrozenManifestHash = '52c40517d3fa32ab4c4912f09a5ca47b5de7f9ba3bd346817468ba44f353bdde'
$Url = 'https://fedormilovanov.github.io/media/instagram/milovi-cake/' + $MediaDigest + '.mp4'
$Slot = [datetime]'2026-11-14T19:00:00'
$Msk = [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId(
    [datetimeoffset]::UtcNow, 'Russian Standard Time'
).DateTime

if ($YoutubeId -cne 'fbGZYKS7byM') { throw 'This approval covers only the exact 14 November source' }
if ($Execute -and ($Msk -lt $Slot -or $Msk -ge $Slot.AddMinutes(18))) {
    throw 'Refuse provider write outside the approved 14 November 19:00-19:18 Moscow slot'
}
if (!(Test-Path -LiteralPath $IndexPath) -or !(Test-Path -LiteralPath $ManifestPath)) {
    throw 'Frozen index or verified hosted manifest missing'
}
if ((Get-FileHash -LiteralPath $IndexPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $FrozenIndexHash) {
    throw 'Frozen index SHA-256 changed'
}
if ((Get-FileHash -LiteralPath $ManifestPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $FrozenManifestHash) {
    throw 'Reviewed hosted manifest SHA-256 changed'
}
$Index = Get-Content -LiteralPath $IndexPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Index.project_key -cne 'milovi-cake' -or $Index.meta_app_id -cne $AppId -or
    $Index.target_instagram_id -cne $Account -or @($Index.rows).Count -ne 20) {
    throw 'Frozen index identity or cardinality changed'
}
$Rows = @($Index.rows | Where-Object {
    $_.publication_key -ceq $OriginalKey -and
    $_.youtube_id -ceq $YoutubeId -and
    $_.proposed_moscow_slot -ceq '2026-11-14T19:00:00'
})
if ($Rows.Count -ne 1) { throw 'Missing or ambiguous exact Nov 14 source' }
$SourcePath = Join-Path ([string]$Rows[0].folder) 'ORIGINAL-MUSIC-REEL.mp4'
$SourceManifestPath = Join-Path ([string]$Rows[0].folder) 'exact-local-publish-manifest.json'
if (!(Test-Path -LiteralPath $OwnerApprovalFile) -or
    !(Test-Path -LiteralPath $SourcePath) -or
    !(Test-Path -LiteralPath $SourceManifestPath)) {
    throw 'Original MP4, source manifest or owner risk acceptance missing'
}
$ExpectedApproval = Join-Path ([string]$Rows[0].folder) 'OWNER_DIRECTED_RISK_ACCEPTED.json'
if ([System.IO.Path]::GetFullPath($OwnerApprovalFile) -cne [System.IO.Path]::GetFullPath($ExpectedApproval)) {
    throw 'External owner approval file path not bound to the selected source'
}
$Owner = Get-Content -LiteralPath $OwnerApprovalFile -Raw -Encoding UTF8 | ConvertFrom-Json
$Original = Get-Content -LiteralPath $SourceManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Owner.schema -cne 'milovi-owner-directed-repost-risk-ack-v1' -or
    $Owner.project_key -cne 'milovi-cake' -or
    $Owner.app_id -cne $AppId -or
    $Owner.instagram_id -cne $Account -or
    $Owner.publication_key -cne $OriginalKey -or
    $Owner.media_sha256 -cne ('sha256:' + $MediaDigest) -or
    $Owner.owner_directed_repost -cne $true -or
    $Owner.accepts_unverified_crossplatform_audio_risk -cne $true -or
    $Owner.source_owned_youtube_channel_verified -cne $true -or
    $Owner.caption_editorially_reviewed -cne $true) {
    throw 'Exact owner approval or original-audio risk binding mismatch'
}
if ($Original.publication_key -cne $OriginalKey -or
    $Original.account_id -cne $Account -or
    $Original.media_sha256 -cne ('sha256:' + $MediaDigest) -or
    $Original.media_size_bytes -ne 11400270 -or
    $Manifest.publication_key -cne $UrlKey -or
    $Manifest.account_id -cne $Account -or
    $Manifest.video_url -cne $Url -or
    $Manifest.media_sha256 -cne ('sha256:' + $MediaDigest) -or
    $Manifest.media_size_bytes -ne 11400270 -or
    $Manifest.media_content_type -cne 'video/mp4' -or
    $Manifest.caption -cne $Original.caption -or
    $Manifest.share_to_feed -cne $Original.share_to_feed -or
    $Manifest.thumb_offset_ms -ne $Original.thumb_offset_ms -or
    $null -ne $Manifest.cover_url) {
    throw 'Original and hosted immutable media/caption identity mismatch'
}
if ((Get-Item -LiteralPath $SourcePath).Length -ne 11400270 -or
    (Get-FileHash -LiteralPath $SourcePath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $MediaDigest) {
    throw 'Original MP4 was changed after review'
}

$Python = Join-Path $Repo '.venv\Scripts\python.exe'
$Cli = Join-Path $Repo '.venv\Scripts\video-manager.exe'
if (!(Test-Path $Python) -or !(Test-Path $Cli)) { throw 'Installed production publisher not found' }

# Ledger read only, source-key-based guard across BOTH transports.
$Guard = @'
import os
import sqlite3
from pathlib import Path
p = Path(os.environ["MILOVI_LEDGER_DB"])
uri = "file:" + p.resolve().as_posix() + "?mode=ro"
db = sqlite3.connect(uri, uri=True)
try:
    rows = db.execute(
        "SELECT publication_key, status FROM instagram_publications "
        "WHERE account_id=? AND publication_key LIKE 'milovi-cake.%' "
        "AND instr(publication_key, ?) > 0",
        ("17841407843933779", ".yt-fbGZYKS7byM."),
    ).fetchall()
finally:
    db.close()
if rows:
    print("SOURCE_ALREADY_ATTEMPTED_COUNT=" + str(len(rows)))
    raise SystemExit(3)
print("EXACT_SOURCE_UNATTEMPTED")
'@
try {
    $env:MILOVI_LEDGER_DB = $DbPath
    & $Python -c $Guard
    if ($LASTEXITCODE -ne 0) { throw 'Any previous durable attempt blocks re-dispatch of this source' }
} finally {
    Remove-Item Env:MILOVI_LEDGER_DB -ErrorAction SilentlyContinue
}

$Token = $null
try {
    # All provider-bound preflights are safe GET. Never print the credential.
    $EnvFile = Join-Path $Repo '.env'
    $Lines = @(Get-Content -LiteralPath $EnvFile -Encoding UTF8 | Where-Object {
        $_ -match '^VCM_INSTAGRAM_ACCESS_TOKEN_MILOVI_CAKE_SYSTEM\s*='
    })
    if ($Lines.Count -ne 1) { throw 'Dedicated Milovi system credential missing or ambiguous' }
    $Token = ($Lines[0] -split '=', 2)[1].Trim().Trim('"').Trim("'")
    if ($Token.Length -lt 30) { throw 'Dedicated credential invalid' }
    $env:VCM_INSTAGRAM_LOGIN_MODE = 'facebook'
    $env:VCM_INSTAGRAM_GRAPH_HOST = 'https://graph.facebook.com'
    $env:VCM_INSTAGRAM_GRAPH_API_VERSION = 'v26.0'
    $env:VCM_INSTAGRAM_ACCOUNT_ID = $Account
    $env:VCM_INSTAGRAM_ACCOUNT_USERNAME = 'milovi_cake'
    $env:VCM_INSTAGRAM_ACCESS_TOKEN = $Token
    $env:VCM_INSTAGRAM_MEDIA_ALLOWED_HOSTS = '["fedormilovanov.github.io"]'
    $env:VCM_INSTAGRAM_WRITES_ENABLED = 'false'

    $App = Invoke-RestMethod -Method GET -Uri 'https://graph.facebook.com/v26.0/app?fields=id' -Headers @{
        Authorization = ('Bearer ' + $Token)
    } -TimeoutSec 30
    if ([string]$App.id -cne $AppId) { throw 'Meta token bound to wrong app' }

    & $Cli instagram production validate-local $SourcePath
    if ($LASTEXITCODE -ne 0) { throw 'Original local MP4 validation failed' }
    & $Cli instagram production validate-public $ManifestPath
    if ($LASTEXITCODE -ne 0) { throw 'Public HTTPS exact-byte validation failed' }
    & $Cli instagram production preflight
    if ($LASTEXITCODE -ne 0) { throw 'Exact target/permission/quota preflight failed' }

    # Fresh read-only account inventory, not just yesterday's SQLite/caption audit.
    # Build each paginated URL ourselves: never trust/print opaque paging.next URLs.
    $Cursor = ''
    $PageHasNext = $false
    $Inspected = 0
    for ($Page = 1; $Page -le 10; $Page++) {
        $MediaUrl = 'https://graph.facebook.com/v26.0/' + $Account +
            '/media?fields=id,caption&limit=100'
        if ($Cursor) { $MediaUrl += '&after=' + [uri]::EscapeDataString($Cursor) }
        $Inventory = Invoke-RestMethod -Method GET -Uri $MediaUrl -Headers @{
            Authorization = ('Bearer ' + $Token)
        } -TimeoutSec 35
        foreach ($Post in @($Inventory.data)) {
            $Inspected++
            # A real Instagram media item may omit caption entirely.
            $PostCaption = ''
            if ($Post.PSObject.Properties.Name -contains 'caption') {
                $PostCaption = [string]$Post.caption
            }
            if ($PostCaption -ceq [string]$Manifest.caption) {
                throw 'Exact reviewed caption is already present on the target Instagram account'
            }
        }
        # StrictMode also requires us to test optional paging members.
        $PageHasNext = $false
        if ($Inventory.PSObject.Properties.Name -contains 'paging' -and
            $null -ne $Inventory.paging -and
            $Inventory.paging.PSObject.Properties.Name -contains 'next') {
            $PageHasNext = -not [string]::IsNullOrEmpty([string]$Inventory.paging.next)
        }
        if (!$PageHasNext) { break }
        if ($Inventory.paging.PSObject.Properties.Name -notcontains 'cursors' -or
            $null -eq $Inventory.paging.cursors -or
            $Inventory.paging.cursors.PSObject.Properties.Name -notcontains 'after') {
            throw 'Provider paging lacked a safe after-cursor'
        }
        $Cursor = [string]$Inventory.paging.cursors.after
        if (!$Cursor) { throw 'Provider paging lacked a safe after-cursor' }
    }
    if ($PageHasNext) { throw 'Instagram media inventory exceeded safe pagination cap' }
    Write-Output ('FRESH_INSTAGRAM_DUPLICATE_PREFLIGHT_PASS POSTS_SCANNED=' + $Inspected)

    if (!$Execute) {
        Write-Output ('MILOVI_HTTPS_SINGLE_SLOT_PREFLIGHT_PASS NO_POST NO_PUBLISH '+ $UrlKey)
        return
    }

    # The outer due-slot wrapper owns the one-writer OS file lock.
    # This is one provider attempt under a new exact key; no provider retries.
    $env:VCM_INSTAGRAM_WRITES_ENABLED = 'true'
    try {
        & $Cli instagram production publish $ManifestPath --execute
        if ($LASTEXITCODE -ne 0) {
            throw 'Provider write failed or ambiguous: inspect ledger, NEVER retry blindly'
        }
    } finally {
        $env:VCM_INSTAGRAM_WRITES_ENABLED = 'false'
    }
    Write-Output ('MILOVI_HTTPS_CANARY_PUBLISH_COMMAND_SUCCESS '+$UrlKey)
} finally {
    $env:VCM_INSTAGRAM_WRITES_ENABLED = 'false'
    $env:VCM_INSTAGRAM_ACCESS_TOKEN = $null
    $Token = $null
}
