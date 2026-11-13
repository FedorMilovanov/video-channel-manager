# Canonical Milovi Cake sole daily writer; for Nov 14 only, use the verified URL transport.
# Next dates retain their original scoped publisher until independently authorized.
[CmdletBinding()]
param(
    [switch]$Execute,
    [switch]$DryRun
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root = 'C:\Users\Fedor\Projects\video-channel-manager\operator-output\milovi-cake-instagram\2026-11-05'
$IndexPath = Join-Path $Root 'meta-verified\milovi-ig-original-audio-handoff-v5-daily-20261110-28.json'
$ExpectedIndexHash = '19a211320f32e3c0f16c0aad1ed23db4b2bd89f100bbd22b8d1b801734aba5a4'
if ((Get-FileHash -LiteralPath $IndexPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ExpectedIndexHash) {
    throw 'Frozen Milovi Cake daily index differs from approved v5'
}
$Index = Get-Content -LiteralPath $IndexPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Index.project_key -cne 'milovi-cake' -or
    $Index.target_instagram_id -cne '17841407843933779' -or
    $Index.meta_app_id -cne '989716813600695' -or
    @($Index.rows).Count -ne 20) {
    throw 'Project/target/source count mismatch'
}
$Rows = @($Index.rows)
$DueDays = @(
    '2026-11-06','2026-11-10','2026-11-11','2026-11-12','2026-11-13',
    '2026-11-14','2026-11-15','2026-11-16','2026-11-17','2026-11-18',
    '2026-11-19','2026-11-20','2026-11-21','2026-11-22','2026-11-23',
    '2026-11-24','2026-11-25','2026-11-26','2026-11-27','2026-11-28'
)
if (@($Rows | Where-Object {
    ([datetime]$_.proposed_moscow_slot).ToString('yyyy-MM-dd') -notin $DueDays
}).Count -gt 0) {
    throw 'Unexpected proposed slot date'
}
$Msk = [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId(
    [datetimeoffset]::UtcNow, 'Russian Standard Time'
).DateTime
$NowClock = $Msk.ToString('yyyy-MM-ddTHH:mm:ss')
if ($DryRun -and $Execute) { throw 'Cannot mix dry-run and execution' }

if ($DryRun) {
    # Preview the next due slot, never a historical row.
    $match = @($Rows | Where-Object {
        [datetime]$_.proposed_moscow_slot -ge $Msk
    } | Sort-Object proposed_moscow_slot | Select-Object -First 1)
} else {
    $match = @($Rows | Where-Object {
        $slot = [datetime]$_.proposed_moscow_slot
        $Msk -ge $slot -and $Msk -lt $slot.AddMinutes(18)
    })
}
if ($match.Count -eq 0) {
    Write-Output ('NO_DUE_SLOT_FOR_MOSCOW_TIME=' + $NowClock)
    exit 0
}
if ($match.Count -ne 1) { throw 'Multiple rows due; refuse batch writes' }
$row = $match[0]
$id = [string]$row.youtube_id
if ($id -in @('IpoJiH5hPxo','L6XG2_zzrPU')) {
    throw 'Confirmed duplicate excluded'
}
$folder = [string]$row.folder
$ack = Join-Path $folder 'OWNER_DIRECTED_RISK_ACCEPTED.json'
$manifest = Join-Path $folder 'exact-local-publish-manifest.json'
if (!(Test-Path -LiteralPath $ack) -or !(Test-Path -LiteralPath $manifest)) {
    throw 'Frozen release documents missing'
}
$approval = Get-Content -LiteralPath $ack -Raw -Encoding UTF8 | ConvertFrom-Json
if ($approval.schema -cne 'milovi-owner-directed-repost-risk-ack-v1' -or
    $approval.publication_key -cne $row.publication_key -or
    $approval.project_key -cne 'milovi-cake' -or
    $approval.app_id -cne '989716813600695' -or
    $approval.instagram_id -cne '17841407843933779' -or
    $approval.media_sha256 -cne ('sha256:' + [string]$row.media_sha256) -or
    $approval.owner_directed_repost -cne $true -or
    $approval.accepts_unverified_crossplatform_audio_risk -cne $true -or
    $approval.source_owned_youtube_channel_verified -cne $true -or
    $approval.caption_editorially_reviewed -cne $true) {
    throw 'Exact owner-directed risk acceptance mismatch'
}

$UrlOnly = ($id -ceq 'fbGZYKS7byM' -and
    $row.proposed_moscow_slot -ceq '2026-11-14T19:00:00' -and
    $row.publication_key -ceq 'milovi-cake.2026-11-14.yt-fbGZYKS7byM.original-audio-v1')
if ($UrlOnly) {
    $target = Join-Path $Root 'milovi_cake_https_single_slot_20261114.ps1'
} else {
    $target = Join-Path $Root 'milovi_original_audio_owner_risk_release.ps1'
}
if (!(Test-Path -LiteralPath $target)) {
    # No silent fallback to rupload for the approved URL canary.
    throw 'Exact release target missing; refuse provider dispatch'
}

if ($DryRun) {
    Write-Output ('DRY_RUN_PROPOSED_ID=' + $id)
    Write-Output ('DRY_RUN_PROPOSED_SLOT=' + [string]$row.proposed_moscow_slot)
    Write-Output ('DRY_RUN_TRANSPORT=' + $(if ($UrlOnly) { 'verified-public-https' } else { 'original-audio-local' }))
    if ($UrlOnly) {
        & $target -YoutubeId $id -OwnerApprovalFile $ack -DryRun
    } else {
        & $target -YoutubeId $id -OwnerApprovalFile $ack
    }
    if ($LASTEXITCODE -ne 0) { throw 'Canonical preflight failed' }
    exit 0
}
if (!$Execute) {
    Write-Output ('DUE_BUT_EXECUTE_NOT_ENABLED=' + $id)
    exit 0
}

$LockPath = Join-Path $Root 'milovi-reels-single-writer.lock'
$Lock = [System.IO.File]::Open(
    $LockPath, [System.IO.FileMode]::OpenOrCreate,
    [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None
)
try {
    # One writer, one slot. No catch-up after the 18-minute window.
    Write-Output ('ATTEMPTING_EXACT_MILOVI_REEL=' + $id +
        ' SLOT=' + [string]$row.proposed_moscow_slot +
        ' TRANSPORT=' + $(if ($UrlOnly) { 'verified-public-https' } else { 'original-audio-local' }))
    & $target -YoutubeId $id -OwnerApprovalFile $ack -Execute
    if ($LASTEXITCODE -ne 0) {
        throw 'Canonical publisher failed: inspect durable ledger, never blindly retry'
    }
    Write-Output ('MILESTONE_CANONICAL_PUBLISH_INVOCATION_RETURNED_SUCCESS=' + $id)
} finally {
    $Lock.Dispose()
}
