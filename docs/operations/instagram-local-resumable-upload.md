# Instagram local resumable upload runbook

This runbook extends the production Instagram publisher with a reviewed local-file transport. The existing `docs/operations/instagram-production-publishing.md` runbook remains authoritative for the public-HTTPS-URL `publish` command; the rules below apply only to `publish-local`.

Owning implementation issue: #584. Resumable incident hardening: #600. Strict local Reel media proof: #614. Rupload diagnostics/fallback decision: #613.

## Supported provider mode

The production boundary is deliberately narrow:

- `VCM_INSTAGRAM_LOGIN_MODE=facebook`
- `VCM_INSTAGRAM_GRAPH_HOST=https://graph.facebook.com`
- an explicit reviewed Graph API version
- an exact Instagram Professional account ID
- an optional exact expected username
- a valid access token with the permissions needed by the existing preflight and content-publishing flow

`publish-local` fails closed for the Instagram Login / `graph.instagram.com` mode until that resumable protocol is separately reviewed.

## Resumable wire-framing decision

The reviewed Instagram sample intentionally sends the complete local file body with `Authorization: OAuth ...`, `offset: 0`, and `file_size`. This implementation keeps that shape: the body is materialized as bytes, HTTPX derives `Content-Length`, and the application does **not** add a manual `Content-Length`.

The current reviewed implementation deliberately sends `Content-Type: application/octet-stream` on the binary POST to `rupload.facebook.com`, alongside `Authorization: OAuth ...`, `offset: 0`, and `file_size`. This is the actual request contract in `src/video_channel_manager/instagram/local_resumable.py::_dispatch_binary_upload`, asserted by `tests/test_instagram_local_resumable.py` together with the HTTPX-derived `Content-Length` and exact binary body. The header was introduced as an incident-specific transport correction; it is **not** a claim that Meta publicly documents this header as mandatory, nor proof that the real upload succeeds. The 11 November provider failure (`ProcessingFailedError`, nested `1363008 FILE_NOT_FOUND`, zero bytes accepted) remains terminal and must never be retried with the same publication key. Do not remove or change the current header as an incidental cleanup: any future protocol change requires separate review, an immutable test update and an explicitly authorized live canary.

A successful HTTP 200 binary response is accepted only when Meta explicitly returns JSON `{"success": true}`. Missing, non-boolean, or malformed success acknowledgement is treated as **ambiguous** and requires read-only reconciliation; it must not advance the durable child upload ledger. The **public-HTTPS `video_url` route must instead poll only `GET /{container_id}?fields=status_code,status`**. A real 15 November 2026 Meta Graph v26.0 request returned **HTTP 400, code 100 / subcode 2207065** when the generic status request included `video_status`: that nested field is not valid for a `video_url` media container. The local **resumable `rupload`** client retains a separate container-status override with `video_status` to capture nested `1363008`. For public HTTPS, `FINISHED` means processing complete but **not published**; `IN_PROGRESS` remains a bounded pending state, and `ERROR`/`EXPIRED` must block publishing. Neither transport error should be silently retried.

On upload failure, diagnostics record only a non-secret wire fingerprint: method, host, actual body length, HTTP `Content-Length`, `file_size`, `offset`, and request `Content-Type` presence/value. The one-time rupload path, authorization value, and access token are never recorded. Available Meta correlation headers include `x-fb-request-id`, `x-fb-trace-id`, and `Proxy-Status`.

## Public-HTTPS fallback

If `rupload.facebook.com` continues to fail at the provider/OIL boundary, the preferred transport fallback is the already-reviewed public-URL publisher documented in `instagram-production-publishing.md`. This is a different transport and therefore requires a new reviewed publication key and fresh operation-specific authority.

The fallback must be a stable HTTPS object URL on an explicitly allowed host. Before Graph container creation, the production publisher follows at most three redirects, requiring HTTPS and an exactly allowlisted hostname at every hop, then proves the exact content type, byte size and SHA-256. GitHub Release MP4 delivery may use `github.com` -> `release-assets.githubusercontent.com` with `application/octet-stream` only at the latter host; never bypass byte integrity. Use the same reviewed CLEAN bytes; do not silently re-encode or substitute another file merely to change transport.

Provisioning a public object URL is an external deployment step and is not implied by this runbook. An HTML share page, unallowlisted redirector, expiring browser-only link, or URL whose bytes cannot be re-fetched and hashed exactly is not an acceptable `video_url`.

**Controlled 15 November transport A/B (owned, unpublished synthetic test):** The same 95.067-second MP4 (SHA-256 `b39dd1d9e29c7ee201720d3959c6f466ec726e00e9a50fe672d235e4575d9ad4`, 1,725,609 bytes, AAC 48 kHz) produced `ProcessingFailedError`, nested Meta `1363008`, zero bytes and approximately **33,759 ms** for one direct resumable `rupload` request; the same bytes passed to Meta through a temporary owned GitHub Release HTTPS source produced a private container with **`status_code=FINISHED`**. The corresponding 44.1-kHz 95-second variant also failed via `rupload` at approximately **33,903 ms**. These are **direct provider observations**, not the official specification of a 34-second timeout, and **no `media_publish` was sent**. The temporary QA host and pre-publication container are not authorization to publicly host or publish the twelve frozen third-party-derived videos. For real releases use a separately reviewed and authorized stable HTTPS object with the repository's complete SHA/size/MIME/allowlisted-redirect gate and a separately approved publication slot. Successful transport does not establish third-party source or translation rights.

## Provider-inert local validation

Before any provider preflight or write, validate the exact local file with the same media boundary used by `publish-local`:

```powershell
video-manager instagram production validate-local "D:\Videos\output-instagram-clean.mp4"
```

`validate-local` needs no Instagram credential, publication key, database state, network access or write gate. It performs no provider request and creates no durable publication intent. A successful result reports the exact SHA-256 and byte size, MP4 layout/edit-list verdict, codec/dimensions, pixel format, field order, frame rate, audio parameters, active Reel ruleset, and closed-GOP intra/IDR evidence.

A non-zero result is blocking. Do not substitute ad-hoc ffprobe checks for a failed `validate-local`: `publish-local` calls the same verifier and will fail for the same media incompatibility.

## What the command does

`publish-local` does not stage media on an external CDN. It:

1. reads the local `.mp4` and freezes exact SHA-256, byte size, caption, account, feed-sharing choice and thumbnail offset into immutable publication identity;
2. requires the existing double write gate (`--execute` plus `VCM_INSTAGRAM_WRITES_ENABLED=true`);
3. runs the existing read-only exact-account and publishing-limit preflight;
4. verifies the local MP4 structure before durable intent: `ftyp`, `moov` before `mdat`, and no `edts/elst` edit list;
5. verifies the canonical Reel media contract, including H.264/HEVC, progressive scan, 4:2:0 chroma, a closed-GOP proof from local AVC/HEVC access units, AAC, audio sample rate at most 48 kHz, mono/stereo, frame rate, dimensions, bitrate, duration and file size;
6. persists the publication plan before a provider mutation;
7. creates one Reel container with `media_type=REELS` and `upload_type=resumable`;
8. validates that the returned upload URI is HTTPS on exactly `rupload.facebook.com`, persists the exact container response in a child ledger, and only then advances the parent container state;
9. opens and re-verifies the same local bytes, persists `upload_requested`, and sends the binary body to the returned URI with the Meta resumable headers;
10. uses a dedicated long resumable-upload timeout (`connect=30s`, `write=900s`, `read=300s`) rather than the short Graph request timeout;
11. treats any ambiguous binary-upload result as blocking evidence and refuses blind replay;
12. polls the existing container with `id,status,status_code,video_status`; upload/processing phase `error` is terminal even if Meta leaves top-level `status_code=IN_PROGRESS`;
13. persists the final publish intent before `media_publish`, then records the exact returned media ID.

The filesystem path is attempt metadata only. It is intentionally excluded from immutable publication identity, so identical reviewed bytes may be moved without changing the publication key binding.

## MP4 requirements that must be proved locally

Meta's local Reel path requires a compatible MP4. For this repository, `publish-local` fails closed unless the local structure proves:

- an `ftyp` box is present;
- `moov` exists and precedes `mdat` (`faststart` layout);
- no MP4 edit list (`edts` / `elst`) is present;
- the video stream reports progressive scan;
- the pixel format proves 4:2:0 chroma subsampling;
- every ffprobe-observed I picture can be mapped back to its MP4 packet and contains an AVC/H.264 IDR NAL (type 5) or HEVC IDR NAL (type 19/20); non-IDR I pictures fail closed as an open-GOP risk;
- the remaining canonical Reel codec/rate/size contract passes.

AAC at 44.1 kHz is valid because the Meta contract is **48 kHz maximum**, not exactly 48 kHz. Do not transcode an otherwise-valid file solely to turn 44.1 kHz into 48 kHz.

If an MP4 contains edit lists, a byte-preserving stream-copy remux is the preferred first repair when the streams themselves are already compatible:

```powershell
ffmpeg -y `
  -i "D:\Videos\input.mp4" `
  -map 0:v:0 -map 0:a:0 `
  -c copy `
  -movflags +faststart `
  -use_editlist 0 `
  "D:\Videos\output-instagram-clean.mp4"
```

Verify structure before any provider write:

```powershell
ffprobe -v trace "D:\Videos\output-instagram-clean.mp4" 2>&1 |
  Select-String "type:'ftyp'|type:'moov'|type:'mdat'|type:'edts'|type:'elst'|edit_count"
```

Expected: `ftyp`, then `moov`, then `mdat`; no `edts`, `elst`, or `edit_count` lines.

The trace command above proves container layout only. The production `publish-local` pre-write verifier additionally reads ffprobe `pix_fmt` / `field_order` and performs the closed-GOP packet/NAL proof. A file that cannot supply packet positions/sizes or a supported AVC/HEVC sample description fails closed before container creation.

## Database migration

Before first use after installing the revision containing #584:

```powershell
cd C:\Users\Fedor\Projects\video-channel-manager
alembic upgrade head
```

The migration adds `instagram_resumable_uploads`, a child-operation ledger that stores the exact returned container ID and upload URI plus upload request/outcome state. The access token is never stored in this table.

## Read-only preflight first

Keep writes off:

```dotenv
VCM_INSTAGRAM_WRITES_ENABLED=false
```

Then run:

```powershell
video-manager instagram production preflight
```

Do not proceed to a live canary unless the returned account ID/username are the intended Instagram Professional target and publishing-limit access succeeds.

## One reviewed live canary

Only after the exact target, caption and MP4 have been reviewed, enable the kill switch locally:

```dotenv
VCM_INSTAGRAM_WRITES_ENABLED=true
```

Then run exactly one canary:

```powershell
video-manager instagram production publish-local `
  "D:\Videos\test-reel.mp4" `
  --caption "Тестовая публикация" `
  --publication-key legendary-poet-canary-20260910 `
  --execute
```

Immediately restore:

```dotenv
VCM_INSTAGRAM_WRITES_ENABLED=false
```

Do not commit the real token or the local `.env`.

## Failure and resume rules

- Before container creation: local byte mismatch, invalid MP4 structure, incompatible media, or an invalid target causes zero provider writes.
- Ambiguous container creation: no automatic second container is created. Resolve exact provider evidence first.
- Container response received but process crashes before parent-state update: rerunning `publish-local` may recover the exact persisted container ID/upload URI without creating another container.
- Explicit non-retriable HTTP 4xx upload rejection: if Meta returns `debug_info.retriable=false`, the child is terminalized as `provider_failed` immediately and the parent becomes `terminal_failure`; the same publication key is never replayed.
- On that explicit terminal upload 4xx, the publisher makes **at most one read-only GET** of the same returned container. If the provider reports a nested phase `error`, a bounded, credential-redacted diagnostic (including code, bytes and useful text) is added to both durable SQLite error messages. If that GET is unavailable, or only reports outer `IN_PROGRESS` without phase failure, the original HTTP 4xx still terminates the attempt. The GET never triggers a second upload, a new container or `media_publish`.
- Ambiguous binary upload (`upload_requested` / `upload_unknown`): transport failures, 5xx responses, or 4xx responses without an explicit non-retriable provider decision remain no-replay ambiguous. Run read-only reconciliation against the known container first.
- **Top-level `IN_PROGRESS` is not proof of successful upload.** Read `video_status.uploading_phase` and `video_status.processing_phase`. A phase-level `error` is terminal and blocks publish/replay even when top-level status remains `IN_PROGRESS`.
- Phase diagnostics are preserved in the durable error message, including available `bytes_transferred`, `source_file_size`, provider error code and provider message.
- HTTP failures from `rupload.facebook.com` preserve a bounded secret-redacted response/debug body, a non-secret request fingerprint, and available `x-fb-request-id`, `x-fb-trace-id`, `Proxy-Status`, and response content type; access tokens and the one-time upload URI must never appear in logs or ledger diagnostics.
- Transport failures preserve the underlying exception class/message but still remain ambiguous until provider reconciliation.
- Ambiguous `media_publish`: use the existing publication reconciliation rules and never issue a blind second `media_publish`.
- A completed publication is idempotent under the same `publication_key` and immutable content hash.

A known failure shape observed during the first canary investigation was Meta error `1363008` / `OIL Error[FILE_NOT_FOUND]` with `uploading_phase.status=error`, `bytes_transferred=0` and `source_file_size=0`. That state is a provider-visible terminal upload failure, not a reason to keep polling forever and not permission to replay the same container.

**Lord God 11–14 November 2026 production evidence:** four consecutive `rupload` HTTP 400 responses led to one terminal key each. The *actual official container GETs* all exposed `uploading_phase.errors[].code=1363008`, `OIL Error[FILE_NOT_FOUND: 6]: File not found`, and zero transferred bytes; the three older containers became `EXPIRED`, while the 14 November container still showed outer `IN_PROGRESS` despite nested `error`. The message is a **Meta-side ingest/processing symptom**, not proof that an existing local MP4 is missing. File-size, faststart, edit-list and H.264/AAC checks were performed separately. All 12 frozen videos are longer than 90 seconds and have AAC 44.1 kHz, but **neither is by itself outside the documented Instagram Reels media limits**; do not bulk-transcode without a controlled result. The measured pre-instrumentation SQLite intervals 48.5, 51.9, 134.8, and 45.5 seconds are application-ledger windows, **not exact HTTP request durations**; PR #944 adds dedicated `upload_dispatch_elapsed_ms` on future provider failures. Publish success requires exact `media_product_type=REELS`, real media ID, permalink and a matching durable ledger entry.

**Rights and fallback gate:** The public-HTTPS `video_url` route may process a lengthy MP4 asynchronously, but *support in Meta's API does not grant distribution rights*. Never upload YouTube-derived or translated material to a new publicly accessible CDN without source/translation reupload permission. The separately prepared original article pilot also requires actual human listening/editorial approval before a public release. An OIL failure or a new publication key is not authorization to bypass either gate.

### MILOVI CAKE: 18 November 2026 independent provider readback

The owner-controlled `milovi-cake` production account was checked with **GET-only** Graph API v26.0 reads against the exact reviewed Instagram ID; no publish, new container, upload, retry, token disclosure, scheduling change or database mutation occurred. The original SQLite ledger had nine attempted dates (6, 10–17 November). Provider results, not merely local status strings, showed:

- **6 and 11 November:** `status_code=PUBLISHED`, completed binary-upload phases. Both exact media IDs and normalized captions were independently matched in the account's returned Reels feed, with real permalinks.
- **10 and 14 November:** `status_code=EXPIRED`. The 14 November human-readable `status` text misleadingly said *Finished*; **always trust the machine `status_code`**, not free-form status prose. Neither is publishable nor confirmed posted. Importantly, 14 November's persisted `container_created` record belongs to a **distinct exceptional `public-https-v1` publication key**; the frozen daily `resumable_local` 14 November key remains `not_started`. Do not coalesce these different transport keys or infer that the frozen local upload ran.
- **12, 13, 15 and 16 November:** `EXPIRED` with nested `uploading_phase=error`, provider error `1363008`, `bytes_transferred=0` and `source_file_size=0`.
- **17 November:** outer `IN_PROGRESS` but nested uploading and processing phases were already `error` with `1363008` and zero transferred bytes. Do not treat the outer status as permission to poll indefinitely or replay.
- The reviewed feed response included 100 account items and reached back to June 2023. The newest item was from **11 November 2026**. Within the 6–17 November window, only the two known successful captions/IDs matched the nine proposed owner records. This is a scoped Graph readback, not a claim about manually edited or independently uploaded media outside the known records.

An additional **GET-only** identity and quota diagnostic on the same account confirmed the expected Meta app ID and `quota_usage=0` at observation time. An unauthenticated GET to the **root** of `https://rupload.facebook.com/` returned HTTP `429`; this **is not the authenticated container-upload endpoint** and must not be treated as proof that the `1363008` binary failures were caused by a rate limit or solved by switching IPs or credentials.

The separately verified 15 November owned **synthetic** transport A/B above showed public-HTTPS `video_url` can finish Meta processing while `rupload` failed on the same benign source. It does **not** automatically authorize placing the actual third-party-derived MILOVI media on a public host. A recovery must use an individually approved source, new properly reviewed immutable key, registered HTTPS-host allowlist, identical SHA-256 and byte count, rights gate, and independent Meta permalink/live readback. Do not silently bulk-switch or automatically re-key the existing daily Windows publisher. Full operational evidence and outstanding actions are tracked in [Issue #790](https://github.com/FedorMilovanov/video-channel-manager/issues/790).

## Operator checks

Useful commands:

```powershell
video-manager instagram production --help
video-manager instagram production publish-local --help
video-manager instagram production status legendary-poet-canary-20260910
video-manager instagram production reconcile legendary-poet-canary-20260910
```

If the local file changes, keep the old publication key bound to the old immutable content. Use a new reviewed key only for intentionally changed media/caption/account identity. A new key does not itself authorize a new provider write.
