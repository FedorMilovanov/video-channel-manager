# MILOVI CAKE — exact-source Instagram Reel HTTPS recovery (provider-inert)

**Scope:** only Instagram Professional `17841407843933779`, Meta app
`989716813600695`, original v5 release index with SHA-256
`19a211320f32e3c0f16c0aad1ed23db4b2bd89f100bbd22b8d1b801734aba5a4`.
Issue [#790](https://github.com/FedorMilovanov/video-channel-manager/issues/790).
This document is **not** public-hosting authority or permission to publish.

## Evidence, 13 November 2026 (Europe/Moscow)

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

MILOVI CAKE currently has no independently verified, approved
publicly hosted original MP4 to point Meta at. Its existing original-audio
risk approval permits the identified Instagram repost; it **does not**
by itself authorize an additional permanent public hosting location.
Avoid silently hosting unverified third-party music on a separate site.

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
   production media verifier. It refuses any source that already has an
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
  --index $index --database $db --day '2026-11-14' `
  --video-url 'https://fedormilovanov.github.io/media/instagram/milovi-cake/<exact-sha256>.mp4' `
  --allowed-host 'fedormilovanov.github.io' `
  --output 'E:\MiloviRecovery\approved-new-key-candidate.json' `
  --public-hosting-authorized
```

The URL above is deliberately a **placeholder**, not a claim that the video is
hosted. The example fails closed until the exact content-addressed object
actually exists and the external-hosting authorization was granted. It
produces a candidate JSON, not a publication or any scheduler changes.
`video-manager instagram production validate-public <candidate.json>` may
provide an additional independent provider-inert check with
`VCM_INSTAGRAM_MEDIA_ALLOWED_HOSTS` set to the exact approved hostname.

### Non-negotiable guards

- Do **not** repeat the 10, 12 or 13 Nov `original-audio-v1` keys.
- Do **not** call `-Execute`, post to Meta, upload another public copy,
  update scheduled tasks or change any other Instagram identity during
  diagnostics or source code reviews.
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
