# MILOVI CAKE — owner YouTube ↔ VK source-gap read-only guard

Owning issue: [#792](https://github.com/FedorMilovanov/video-channel-manager/issues/792). Exact source: `milovi-cake`, YouTube `UCMDnxfGZiBqcDzgUV1zjFpw`, VK community `68859909` (owner `-68859909`).

This is **a derived evidence classification, not a new clip uploader, a release, or provider execution authority**. It calls no YouTube or VK API and does not interact with the Windows desktop/browser. Do not wire its historical `HISTORICAL_VK_PRESENCE_PROTECT` status into a claim of fresh owner-visible VK presence.

## What it corrects

The November 7 archival 135-Short source crosswalk alone misclassifies a rights-retired private LEGO video as `VERIFIED_OLDER_60`, retains weak false-collision IDs for real VK Clips and misses previously accepted manual 12-frame adjudications. Without a later proof overlay, these errors can cause duplicate upload proposals and attempted recreation of deleted postponed wall posts.

`video_channel_manager.platforms.vk.milovi_source_gap_guard` derives a **source-ID-based, rights-retirement-aware read-only register** from:

1. A fresh **official owner** YouTube scan of exact channel `UCMDnxfGZiBqcDzgUV1zjFpw`.
2. Historical exact source crosswalk, used as **historical evidence only**.
3. The VK `-68859909` authoritative deletion receipt, including Clip `456239266` / wall `536`.
4. The previously SHA-accepted eight-pair 12-frame manual evidence bundle; only exact accepted high-confidence pairs are adopted.
5. Independently verified six-frame matches for the **six PROBABLE scope sources** (not all 11 entries of that archive).
6. Exact public-wall VK video attachments (present observations only).
7. The independently observed timed `SiluLt5Bz1c` / `456239096` overlay, including the second near-duplicate VK `456239082`.

The tool refuses wrong project or owner identities, missing historical YouTube IDs, mismatched accepted evidence, a missing confirmed public attachment for protected manual pairs, malformed rights-terminal evidence or conflicting staged files.

## Operator command — local-only, with explicit paths

Run from the VIDEO MANAGER repo checkout after the original evidence inputs have been accepted; replace each path only with a separately reviewed exact revision. A successful report says **zero provider writes** and never says "safe to upload".

```powershell
$Repo = "C:\Users\Fedor\Projects\video-channel-manager"
$Out = Join-Path $Repo "operator-output"
$Report = Join-Path $Out "milovi-current-readonly-source-gate.json"
Set-Location $Repo

.\.venv\Scripts\python.exe -m video_channel_manager.platforms.vk.milovi_source_gap_guard `
  --youtube-owner (Join-Path $Out "milovi-youtube-owner-full-audit-live-20261118.json") `
  --crosswalk (Join-Path $Out "milovi_135_youtube_source_all_vk_cross_surface_rights_scoped_closeout_20261107.json") `
  --rights-terminal (Join-Path $Out "milovi_rights_lego_2clips_2posts_terminal_20261107.json") `
  --accepted-manual (Join-Path $Out "milovi-cake-final-review-queue\01-final-review-queue.json") `
  --independent-visual (Join-Path $Out "milovi_11_probable_visual_confirmed_already_on_vk_20261107.json") `
  --public-wall (Join-Path $Out "milovi-vk-wall-video-dedup-live2-20261118.json") `
  --additional-visual (Join-Path $Out "milovi-five-source-verified-dedup-closeout-20261118.json") `
  --output $Report

if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Report)) {
    throw "Read-only source gate did not produce an accepted report"
}
Write-Host "OPEN THIS FILE: $Report"
```

The chosen output file must not already exist; do **not** overwrite earlier evidence. This example uses the previously accepted November 18 snapshot filenames as historical reproducibility inputs, not standing current-day authorization.

## Decision semantics

- `RETIRED_RIGHTS_NEVER_RESTORE`: named source was deleted by the exact verified receipt. No future writer may resurrect it.
- `HISTORICAL_VK_PRESENCE_PROTECT`: earlier accepted matching VK video, sometimes in a historical future wall slot, **not** necessarily a published/currently owner-visible Clip.
- `SIXFRAME_VK_PRESENCE_PROTECT`, `MANUAL_VK_PRESENCE_PROTECT`, `TIMED_VK_PRESENCE_PROTECT`: video content already represented in a VK Clip with exact observed published wall attachment; protect against replay even if edits vary.
- `REVIEW_ONLY_NO_VK_OWNER_ABSENCE`: metadata/published-wall non-observation is **not** proof of absence across all VK surfaces.
- `EXCLUDED_RIGHTS`, `EXCLUDED_OFF_TOPIC`, `PRIVATE_OR_UNLISTED_HOLD`: never select automatically.

Every row has `upload_authorized=false`, `postponed_create_authorized=false`. The report also has `verified_missing_source_ids=[]`, `transfer_queue_created=false`, `provider_writes=0`.

## Remaining decisive gap

Current owner-visible **VK native Clips plus ordinary Videos**, including scheduled/private/draft/processing and a fresh admin postponed wall snapshot, are **not** available from the Milovi community key (VK API errors `5` / `27`). The read-only public wall is not such a snapshot. Before ANY new upload/scheduling flow, obtain legitimate owner-wide proof, inspect exact source media/rights/music, freeze verified hashes and explicit approval, persist a no-replay operation intent and independently verify each VK provider effect under the existing single-writer contract. This module intentionally cannot grant that authority.

The 69-second YouTube `K2bq-GN8onk` longform is **not** in the old 135-Short historical crosswalk. Handle it as a separate unresolved source; do not miscount it as a Short or infer absence from this report.

Historical deletion receipts and prior review bundles remain immutable. Do not republish the old five editorial drafts superseded by the 18 November visual reconciliation.
