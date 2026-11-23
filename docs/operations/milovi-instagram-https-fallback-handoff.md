# MILOVI CAKE — exact-source Instagram Reel HTTPS recovery (provider-inert)

**Scope:** only Instagram Professional `17841407843933779`, Meta app
`989716813600695`, original v5 release index with SHA-256
`19a211320f32e3c0f16c0aad1ed23db4b2bd89f100bbd22b8d1b801734aba5a4`.
Issue [#790](https://github.com/FedorMilovanov/video-channel-manager/issues/790).
This document is **not** public-hosting authority or permission to publish.

## Later incident checkpoint — 23 November 2026 Moscow time

The 14 November window below is historical and has expired. The owner's
[read-only SQLite reconciliation](https://github.com/FedorMilovanov/video-channel-manager/issues/790#issuecomment-7085944239)
found the separate 14 November `public-https-v1` key in `container_created`,
container `18341870875261465`, with **no provider media ID**. A created
container or earlier dry-run is not a published Reel, and a missing media ID
is not proof that a provider effect is absent. Do not retry that key or source
or claim a successful HTTPS canary without exact reconciliation and separately
scoped authority. The reported attempt to GET eight historical containers was
blocked by the execution security layer; do not bypass it with another token.

The owner's later [route and single-writer checkpoint](https://github.com/FedorMilovanov/video-channel-manager/issues/790#issuecomment-7086329857)
supersedes the earlier installed wrapper SHA. Routed root-URL GETs and local
media checks do not establish Meta upload acceptance or independently cleared
soundtrack rights. The existing owner task was still enabled at that checkpoint;
confirm its current state rather than creating another writer. Future slots do
not inherit permission to auto-switch to HTTPS or to host new files.

The repository proxy-routing change [#1093](https://github.com/FedorMilovanov/video-channel-manager/pull/1093)
merged on 22 November 23:32 UTC as `a78bf4e6c46bba5f3831bf9cdf514c6d940e3168`;
the exact PR head `9946067ca830d0cd7684d4b8d84d78e7299117a6` passed CI and its
tree matches the merge tree. This is repository evidence, **not proof of
owner-local deployment**, Meta ingestion, a Reel receipt or fresh execution
authority. The old unknown/failed effects and no-replay boundary still apply.

## Historical evidence, 13 November 2026 (Europe/Moscow)

The Windows daily 19:00 writer runs. Local SQL and independent authenticated **GET**
to the exact Media container IDs showed:

| Slot | Local state | Independent Meta `video_status` | Result |
| --- | --- | --- | --- |
| 6 Nov | `published` | Previous verified receipt | Real Reel `18237604546322268` |
| 10 Nov | `container_created/upload_unknown` | `EXPIRED`, uploading `in_progress`, bytes=0 | Do not replay |
| 11 Nov | `published` | Previous verified receipt | Real Reel `18098828018130613` |
| 12 Nov | `terminal_failure/provider_failed` | `EXPIRED`, uploading/processing `error`, bytes=0, code `1363008` | Do not replay |
| 13 Nov | `terminal_failure/provider_failed` | Outer `IN_PROGRESS`, nested uploading/processing `error`, bytes=0, code `1363008` | Do not replay |

12 Nov POST carried 59,761,648 bytes and 13 Nov POST 19,512,151 bytes.
For both, Content-Length = `file_size` = actual request bytes; offset=0,
Content-Type=`application/octet-stream`, and rupload rejected HTTP 400
`ProcessingFailedError`, `retriable=false`. Zero bytes were acknowledged at
Meta's media-ingest stage. The nested error is `OIL FILE_NOT_FOUND`, not
proof that a local MP4 path was missing. This narrows the failing boundary;
it does **not** uniquely prove whether Meta's backend or an account/
protocol-level condition caused it.

[PR #915](https://github.com/FedorMilovanov/video-channel-manager/pull/915)
enforces nested-phase error and exact JSON upload acknowledgement.
[PR #917](https://github.com/FedorMilovanov/video-channel-manager/pull/917)
rechecks exact binary bytes before dispatch. Both are merged/deployed to the
working Windows source, but neither makes Meta accept a rejected body.
All **15/15** future MP4s, 14–28 Nov, passed the actual local `validate-local`,
manifest SHA/size and exact owner-risk-ack checks. This is not a guarantee of
remote delivery.

## Existing proven alternative: public HTTPS `video_url`

The common publisher already supports the official `video_url` transport.
Legendary Poet successfully published verified Reel
`18135337036649890` through an exact SHA-256-addressed GitHub Pages object,
with a matching published Media ID and independent provider GET. This is
**technical precedent only**; that prior media/approval cannot be reused for
MILOVI CAKE.

## Scoped 14 November live HTTPS source — verified 13 November

Under the owner's fresh authorization in the 13 November 2026 ChatGPT conversation
(one new MILOVI CAKE `video_url` publication; the original soundtrack's independent
license remains unverified), the exact **14 November** reviewed original source
was staged through the protected GitHub Pages PR
[#5](https://github.com/FedorMilovanov/FedorMilovanov.github.io/pull/5),
squashed as `c98d1c907aa2e1a802131af175e45869f81af528`.
This is public hosting, not a claim of licensed music.

- Source: `yt-fbGZYKS7byM`, 11,400,270 bytes,
  SHA-256 `54b6731ca166a25405fb1ff135eb9bf5c0905a9bd5d03241ef432a80b692d2d3`.
- Direct HTTPS object:
  `https://fedormilovanov.github.io/media/instagram/milovi-cake/54b6731ca166a25405fb1ff135eb9bf5c0905a9bd5d03241ef432a80b692d2d3.mp4`.
- Pages build `built`; independent full GET (curl, 0 redirects) gave
  `200 OK`, `Content-Type: video/mp4`, `Content-Length: 11400270` and exact
  downloaded SHA-256. The production `video-manager instagram production
  validate-public` then passed with **zero Meta provider writes**.
- Separate `prepare_milovi_instagram_https_fallback.py` produced an exact
  `public-https-v1` manifest after reviewing the local video, original
  owner-risk approval, immutable v5 index, read-only SQLite, remote bytes and
  content type. Frozen candidate:
  `operator-output/milovi-cake-instagram/2026-11-05/meta-verified/milovi-ig-20261114-public-https-v1-candidate.json`;
  SHA-256 `52c40517d3fa32ab4c4912f09a5ca47b5de7f9ba3bd346817468ba44f353bdde`.
- The historical one-time release was limited to **14 November 19:00 MSK**
  and the existing 18-minute due window through the single Task Scheduler
  writer, never a second writer. That window is over and the later local
  ledger contains a container without a media ID; see the checkpoint above.
  Canonical historical script sources were
  `scripts/instagram/milovi_cake_due_slot_single_writer.ps1` and
  `scripts/instagram/milovi_cake_https_single_slot_20261114.ps1`.
  This old approval is not permission for an immediate run or retry.
- Full end-to-end PowerShell **dry-run** against the real 14 Nov source,
  Graph `/app`, Instagram identity/quota, local and public media validators
  ended `MILOVI_HTTPS_SINGLE_SLOT_PREFLIGHT_PASS NO_POST NO_PUBLISH`.
  This is not the live Reel result.
- No other MILOVI MP4 was staged here. The 15–28 November future schedule
  is **not** authorized to auto-switch transport. Future dates need fresh
  media/rights/provenance/delivery decisions after this canary.

## Safe handoff when public hosting is separately authorized

Keep the existing Windows Task Scheduler writer and all previous SQLite rows
unchanged. For one **not-yet-attempted future slot**, with separate explicit
authorization to stage these exact video bytes on a direct public HTTPS origin:

1. Stage the **same immutable MP4 bytes** in an approved origin under a
   filename `<sha256>.mp4` (for example an approved owner's
   `fedormilovanov.github.io/media/instagram/milovi-cake/` path).
   Only claim success after public GET returns the exact original file and
   the correct `video/mp4` MIME type. This document does not perform upload.
2. Run the provider-inert script shown below, with the frozen v5 index,
   the existing local read-only SQLite ledger, the exact intended date,
   exact allowlisted hostname, the direct content-addressed HTTPS URL and
   a new output filename. The tool checks old owner/caption review,
   original bytes, full production local MP4/GOP validation,
   existing durable state, full hosted bytes and HTTP MIME with the common
   production media verifier. Its owner-risk acknowledgment must match the
   original release's **exact schema, Meta App ID, Instagram account ID,
   publication key, SHA-256, explicit repost approval, unverified-audio-risk
   acceptance, source-channel ownership evidence and reviewed caption**.
   A plausible file with only a few matching fields is insufficient. It refuses any source that already has an
   Instagram publication attempt on that account.
3. Review the resulting **new** `public-https-v1` publication key, the
   caption, rights, current Instagram inventory, the scheduler's competing
   local due slot, the exact owner-approved publication operation, and the
   approved hosting retention/cost policy. Never auto-switch the daily
   writer or post the same source twice.
4. Only after a separate operation-specific permission may the existing
   production URL publisher be invoked under its normal two-factor write
   gate. The script here has no Meta credential, POST or execution path.

```powershell
$root = 'C:\Users\Fedor\Projects\video-channel-manager'
$index = Join-Path $root 'operator-output\milovi-cake-instagram\2026-11-05\meta-verified\milovi-ig-original-audio-handoff-v5-daily-20261110-28.json'
$db = Join-Path $root 'data\video_manager.db'

& (Join-Path $root '.venv\Scripts\python.exe') `
  (Join-Path $root 'scripts\prepare_milovi_instagram_https_fallback.py') `
  --index $index --database $db --day '<approved-future-date-YYYY-MM-DD>' `
  --video-url 'https://fedormilovanov.github.io/media/instagram/milovi-cake/<exact-sha256>.mp4' `
  --allowed-host 'fedormilovanov.github.io' `
  --output 'E:\MiloviRecovery\approved-new-key-candidate.json' `
  --public-hosting-authorized
```

The **generic future-source example** above contains non-executable date and
`<exact-sha256>` placeholders; it does not represent another hosted video or
permission to use a particular date. Only a separately approved, not-yet-attempted
future source and date may be considered. The historically approved 14 November
file was hosted at the exact URL recorded earlier; hosting did not prove
publication. Future source URLs still fail closed without fresh public-hosting
authority and complete byte verification. The command produces a candidate
JSON, not a publication or any scheduler changes.
`video-manager instagram production validate-public <candidate.json>` may
provide an additional independent provider-inert check with
`VCM_INSTAGRAM_MEDIA_ALLOWED_HOSTS` set to the exact approved hostname.

### Non-negotiable guards

- Do **not** repeat the 10, 12 or 13 Nov `original-audio-v1` keys.
- Do **not** call `-Execute` or Meta POST during diagnostics, CI, read-only
  audits or preview. The historical 14 Nov 19:00 MSK `public-https-v1`
  approval was limited to that expired window; the key now has an unresolved
  local container. It does not cover a retry, immediate manual run, other
  dates, a second task or another Instagram identity.
- Do **not** automatically create a new key for a failed source. Provider
  reconciliation and operation-specific authorization come first.
- Do **not** treat Windows `LastTaskResult=0`, accepted container response,
  local validation, CI or public hosting alone as evidence of a published Reel.
  Closure requires a durable `published` row and matching official Media ID,
  permalink, `REELS` type, date/account/caption through independent GET.
- If new reviewed attempts still return zero-byte `1363008`, escalate to
  Meta support with bounded, redacted request IDs, timestamps, original
  HTTP 400 and nested `video_status` evidence. Do not expose tokens/one-time
  rupload URLs in public tickets.
