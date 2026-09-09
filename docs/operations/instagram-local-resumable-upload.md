# Instagram local resumable upload runbook

This runbook extends the production Instagram publisher with a reviewed local-file transport. The existing `docs/operations/instagram-production-publishing.md` runbook remains authoritative for the public-HTTPS-URL `publish` command; the rules below apply only to `publish-local`.

Owning issue: #584.

## Supported provider mode

The initial production boundary is deliberately narrow:

- `VCM_INSTAGRAM_LOGIN_MODE=facebook`
- `VCM_INSTAGRAM_GRAPH_HOST=https://graph.facebook.com`
- an explicit reviewed Graph API version
- an exact Instagram Professional account ID
- an optional exact expected username
- a valid access token with the permissions needed by the existing preflight and content-publishing flow

`publish-local` fails closed for the Instagram Login / `graph.instagram.com` mode until that resumable protocol is separately reviewed.

## What the command does

`publish-local` does not stage media on an external CDN. It:

1. reads the local `.mp4` and freezes exact SHA-256, byte size, caption, account, feed-sharing choice and thumbnail offset into immutable publication identity;
2. requires the existing double write gate (`--execute` plus `VCM_INSTAGRAM_WRITES_ENABLED=true`);
3. runs the existing read-only exact-account and publishing-limit preflight;
4. persists the publication plan before a provider mutation;
5. creates one Reel container with `media_type=REELS` and `upload_type=resumable`;
6. validates that the returned upload URI is HTTPS on exactly `rupload.facebook.com`, persists the exact container response in a child ledger, and only then advances the parent container state;
7. opens and re-verifies the same local bytes, persists `upload_requested`, and sends the binary body to the returned URI with the Meta resumable headers;
8. treats any ambiguous binary-upload result as blocking evidence and refuses blind replay;
9. polls the existing container status until provider-visible processing is `FINISHED` (or returns a non-ready durable state);
10. persists the final publish intent before `media_publish`, then records the exact returned media ID.

The filesystem path is attempt metadata only. It is intentionally excluded from immutable publication identity, so identical reviewed bytes may be moved without changing the publication key binding.

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

- Before container creation: local byte mismatch or an invalid target causes zero provider writes.
- Ambiguous container creation: no automatic second container is created. Resolve exact provider evidence first.
- Container response received but process crashes before parent-state update: rerunning `publish-local` may recover the exact persisted container ID/upload URI without creating another container.
- Ambiguous binary upload (`upload_requested` / `upload_unknown`): `publish-local` will not resend the bytes. Run the existing read-only reconciliation against the known container first. Provider-visible `IN_PROGRESS`/`FINISHED` is sufficient to continue without replaying the upload; otherwise keep the operation blocked.
- Ambiguous `media_publish`: use the existing publication reconciliation rules and never issue a blind second `media_publish`.
- A completed publication is idempotent under the same `publication_key` and immutable content hash.

## Operator checks

Useful commands:

```powershell
video-manager instagram production --help
video-manager instagram production publish-local --help
video-manager instagram production status legendary-poet-canary-20260910
video-manager instagram production reconcile legendary-poet-canary-20260910
```

If the local file changes, keep the old publication key bound to the old immutable content. Use a new reviewed key only for intentionally changed media/caption/account identity.
