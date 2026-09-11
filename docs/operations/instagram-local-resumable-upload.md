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

Do not add a `Content-Type` merely to imitate an incidental client default. The current Meta sample does not document a required resumable upload content type, while different public examples use different values. Until Meta documents a requirement or a separately authorized controlled test proves otherwise, this repository leaves request `Content-Type` absent. Changing it is a protocol change, not a harmless retry.

On upload failure, diagnostics record only a non-secret wire fingerprint: method, host, actual body length, HTTP `Content-Length`, `file_size`, `offset`, and request `Content-Type` presence/value. The one-time rupload path, authorization value, and access token are never recorded. Available Meta correlation headers include `x-fb-request-id`, `x-fb-trace-id`, and `Proxy-Status`.

## Public-HTTPS fallback

If `rupload.facebook.com` continues to fail at the provider/OIL boundary, the preferred transport fallback is the already-reviewed public-URL publisher documented in `instagram-production-publishing.md`. This is a different transport and therefore requires a new reviewed publication key and fresh operation-specific authority.

The fallback URL must be a stable direct HTTPS object URL on an explicitly allowed host. Before the Graph container POST, the production publisher fetches that object without redirects and proves exact content type, byte size, and SHA-256 against the frozen manifest. Use the same reviewed CLEAN media bytes; do not silently re-encode or substitute another file merely to change transport.

Provisioning a public object URL is an external deployment step and is not implied by this runbook. A share page, redirector, expiring browser-only link, or URL whose bytes cannot be re-fetched and hashed exactly is not an acceptable `video_url`.

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
- Ambiguous binary upload (`upload_requested` / `upload_unknown`): transport failures, 5xx responses, or 4xx responses without an explicit non-retriable provider decision remain no-replay ambiguous. Run read-only reconciliation against the known container first.
- **Top-level `IN_PROGRESS` is not proof of successful upload.** Read `video_status.uploading_phase` and `video_status.processing_phase`. A phase-level `error` is terminal and blocks publish/replay even when top-level status remains `IN_PROGRESS`.
- Phase diagnostics are preserved in the durable error message, including available `bytes_transferred`, `source_file_size`, provider error code and provider message.
- HTTP failures from `rupload.facebook.com` preserve a bounded secret-redacted response/debug body, a non-secret request fingerprint, and available `x-fb-request-id`, `x-fb-trace-id`, `Proxy-Status`, and response content type; access tokens and the one-time upload URI must never appear in logs or ledger diagnostics.
- Transport failures preserve the underlying exception class/message but still remain ambiguous until provider reconciliation.
- Ambiguous `media_publish`: use the existing publication reconciliation rules and never issue a blind second `media_publish`.
- A completed publication is idempotent under the same `publication_key` and immutable content hash.

A known failure shape observed during the first canary investigation was Meta error `1363008` / `OIL Error[FILE_NOT_FOUND]` with `uploading_phase.status=error`, `bytes_transferred=0` and `source_file_size=0`. That state is a provider-visible terminal upload failure, not a reason to keep polling forever and not permission to replay the same container.

## Operator checks

Useful commands:

```powershell
video-manager instagram production --help
video-manager instagram production publish-local --help
video-manager instagram production status legendary-poet-canary-20260910
video-manager instagram production reconcile legendary-poet-canary-20260910
```

If the local file changes, keep the old publication key bound to the old immutable content. Use a new reviewed key only for intentionally changed media/caption/account identity. A new key does not itself authorize a new provider write.
