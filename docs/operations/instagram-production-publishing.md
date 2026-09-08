# Instagram production publishing runbook

Updated: 2026-09-08
Owner: issue #568 / PR #569

This runbook describes the repository-side Instagram production publishing capability. It does **not** authorize a provider mutation. A live Reel requires a fresh exact Instagram Professional account identity, external credentials/permissions, a reviewed immutable publish manifest, current durable ledger state, and explicit operation-specific execution authority.

## Provider contract

The preferred integration is **Instagram API with Instagram Login**:

- host: `https://graph.instagram.com`;
- no linked Facebook Page is required;
- token: Instagram User access token;
- required publishing permissions: `instagram_business_basic` and `instagram_business_content_publish`;
- media used for publishing must be available to Meta at a public URL;
- Reel publishing uses container creation, container-status polling, then `media_publish`.

The repository also permits an explicitly selected Facebook Login compatibility mode using `https://graph.facebook.com`; there is no automatic fallback between login modes.

Do not hard-code an API version from this runbook. Set the currently reviewed Meta Graph API version explicitly for each runtime environment.

Current Meta reference collection: https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api

## Safety invariants

1. Provider writes are disabled by default.
2. A write requires both `--execute` on that invocation and `VCM_INSTAGRAM_WRITES_ENABLED=true` in runtime configuration.
3. `VCM_INSTAGRAM_ACCOUNT_ID` is an exact provider target, never a guessed username-derived identity.
4. `VCM_INSTAGRAM_ACCOUNT_USERNAME`, when configured, is an additional identity assertion and must match read-only provider preflight.
5. `VCM_INSTAGRAM_ACCESS_TOKEN` is secret material. Never commit it, print it, place it in a manifest, issue, PR, log bundle or receipt.
6. `VCM_INSTAGRAM_GRAPH_API_VERSION` is mandatory. The runtime does not guess or silently upgrade API versions.
7. A stable `publication_key` is bound permanently to one account and one canonical manifest content hash.
8. Every provider-bound video/cover URL must use an exact hostname allowlisted by `VCM_INSTAGRAM_MEDIA_ALLOWED_HOSTS`.
9. Before the first Meta provider POST for a logical publication, the runtime downloads the exact public media through an isolated unauthenticated client, refuses redirects, streams the bytes and verifies exact SHA-256, size and content type against the immutable manifest.
10. The Meta Bearer token is sent only to the configured Graph host; it is never attached to public-media verification requests.
11. Before `POST /media`, the durable ledger atomically claims `container_requested`; only one process can own container creation for that logical publication.
12. Before `POST /media_publish`, the durable ledger atomically claims `publish_requested` for the exact known container; only one process can own final publication.
13. `container_requested`, `container_unknown`, `publish_requested`, `publish_unknown` and `published_unresolved` are fail-closed states. They prohibit blind mutation replay.
14. A network failure or 5xx around container creation is treated as an ambiguous creation effect (`container_unknown`), not as permission to create another container.
15. A network failure or 5xx around `media_publish` is treated as an ambiguous publication effect (`publish_unknown`), not as permission to retry.
16. A provider-confirmed `PUBLISHED` container without an exact media ID is recorded as `published_unresolved`; never infer or fabricate the media ID.
17. Default container-status polling follows Meta's current recommendation: once per minute for no more than five minutes. A more aggressive override requires a separately reviewed operational reason.
18. Provider writes never occur in CI tests.

## Runtime configuration

All application settings use the repository `VCM_` prefix.

Required for provider preflight:

```text
VCM_INSTAGRAM_LOGIN_MODE=instagram
VCM_INSTAGRAM_GRAPH_HOST=https://graph.instagram.com
VCM_INSTAGRAM_GRAPH_API_VERSION=<reviewed-current-version>
VCM_INSTAGRAM_ACCOUNT_ID=<exact-professional-account-id>
VCM_INSTAGRAM_ACCOUNT_USERNAME=<optional-exact-username-assertion>
VCM_INSTAGRAM_ACCESS_TOKEN=<secret>
```

Required before the first provider write, using the JSON list representation expected by `pydantic-settings` and exact bare public hostnames only:

```text
VCM_INSTAGRAM_MEDIA_ALLOWED_HOSTS=["media.example.net"]
```

Multiple trusted hosts are represented explicitly, never with wildcards:

```text
VCM_INSTAGRAM_MEDIA_ALLOWED_HOSTS=["media.example.net","cdn.example.com"]
```

PowerShell example:

```powershell
$env:VCM_INSTAGRAM_MEDIA_ALLOWED_HOSTS = '["media.example.net"]'
```

Do not allowlist `localhost`, private IP literals, URL schemes or paths.

Production kill switch, default false:

```text
VCM_INSTAGRAM_WRITES_ENABLED=false
```

Operational defaults:

```text
VCM_INSTAGRAM_REQUEST_TIMEOUT_SECONDS=30
VCM_INSTAGRAM_POLL_INTERVAL_SECONDS=60
VCM_INSTAGRAM_POLL_ATTEMPTS=5
```

The 60-second / five-attempt polling defaults intentionally match Meta's current recommendation to query a container status once per minute for no more than five minutes. Do not lower the interval merely to make a live run appear faster; an explicit override should be reviewed against current provider guidance and rate-limit pressure.

For Facebook Login compatibility mode, set both:

```text
VCM_INSTAGRAM_LOGIN_MODE=facebook
VCM_INSTAGRAM_GRAPH_HOST=https://graph.facebook.com
```

A mode/host mismatch is rejected instead of silently changing providers.

## Database migration

Production/deployed environments must migrate the database before using the publication ledger:

```powershell
alembic upgrade head
```

Migration `0002` creates `instagram_publications`. `video-manager db init` remains a development/bootstrap helper; do not substitute it for migration discipline in deployed environments.

## Publish manifest

A live publish accepts one immutable JSON manifest. Example:

```json
{
  "schema_version": "1",
  "publication_key": "legendary-poet.2026-09-08.reel-001",
  "account_id": "<exact-professional-account-id>",
  "video_url": "https://media.example.net/immutable/reel-001.mp4",
  "media_sha256": "sha256:<64-lowercase-hex>",
  "media_size_bytes": 12345678,
  "media_content_type": "video/mp4",
  "caption": "Reviewed caption",
  "share_to_feed": true,
  "cover_url": null,
  "cover_sha256": null,
  "cover_size_bytes": null,
  "cover_content_type": null,
  "thumb_offset_ms": null
}
```

The URL must be HTTPS and publicly reachable by Meta; localhost and non-global IP targets are rejected. Its hostname must also match the explicit media-host allowlist. The publication key is an idempotency boundary, not a display label. Never reuse it for changed caption/media/account content.

Before the first Graph POST, the publisher itself fetches the public object using a separate client with no Meta Authorization header. Redirects are refused. A non-2xx response, unexpected content type, wrong byte count or wrong SHA-256 fails closed before container creation. If `cover_url` is supplied, its SHA-256, byte size and content type are mandatory and receive the same verification.

The public URL must therefore expose the **same immutable bytes** that were reviewed. Do not use an editor preview, mutable local tunnel, temporary authenticated URL that may expire during Meta ingestion, URL that redirects to another object, or an unreviewed source master.

Meta's current Reels documentation should be re-read before a live rollout. At the time of this runbook sync the official Meta Postman collection documents MOV/MP4, H.264 or HEVC video, AAC audio, 23-60 FPS, maximum 1920 horizontal pixels, recommended 9:16, 3 seconds to 15 minutes duration, and a public server URL. Provider specifications can change; repository code deliberately does not freeze a speculative API version.

## Read-only preflight

Preflight does not mutate Instagram:

```powershell
video-manager instagram production preflight
```

It must prove:

- the token resolves the configured exact `account_id`;
- the optional exact username assertion matches;
- the publishing-limit endpoint is readable with the active token/permissions.

Meta currently documents a limit of 100 API-published posts in a moving 24-hour period and recommends that applications also enforce the publishing rate limit. Before an authorized canary, inspect the returned publishing-limit evidence and treat quota exhaustion or ambiguous quota evidence as blocking rather than relying on `media_publish` to reject the operation.

Failure is blocking. Do not bypass identity mismatch by editing a manifest to whichever account the token happened to return.

## Provider-inert plan

After the `0002` migration, bind a reviewed manifest into the durable ledger without any provider request:

```powershell
video-manager instagram production plan .\operator-output\instagram-reel-001.json
video-manager instagram production status legendary-poet.2026-09-08.reel-001
```

Expected initial state: `planned`.

Re-running the same manifest is idempotent. Concurrent planners are also idempotent: a primary-key race is re-read and accepted only if the account/content binding is byte-for-byte the same canonical manifest. Reusing the same publication key with different canonical content is rejected.

## Canary execution

A live canary is a separate operational act from implementation completion.

Before enabling writes, independently verify:

- exact current `main` and deployed revision;
- exact issue/release/operation identity authorized for the canary;
- exact Instagram account ID and username;
- current token and required permissions;
- current publishing quota;
- final public media URL, exact allowed hostname and reviewed immutable bytes;
- exact media SHA-256, byte size and content type recorded in the manifest;
- final caption/cover/feed choice;
- durable ledger state for the publication key;
- no existing Instagram post for the same intended release;
- no unresolved `container_requested`, `container_unknown`, `publish_requested`, `publish_unknown` or `published_unresolved` state.

Only for the approved invocation:

```powershell
$env:VCM_INSTAGRAM_WRITES_ENABLED = "true"
video-manager instagram production publish .\operator-output\instagram-reel-001.json --execute
```

Immediately restore the kill switch after the authorized operation:

```powershell
$env:VCM_INSTAGRAM_WRITES_ENABLED = "false"
```

The publisher performs read-only exact-target preflight and verifies the exact remote media bytes. If no container is durably known, it first commits a single-winner `container_requested` claim and only the winning process may call `POST /media`. After the exact container reaches `FINISHED`, it commits a single-winner `publish_requested` claim and only the winning process may call `POST /media_publish`.

## State machine

Normal path:

```text
planned
  -> container_requested
  -> container_created
  -> processing (zero or more observations)
  -> ready
  -> publish_requested
  -> published
```

Failure/reconciliation states:

```text
retryable_failure       pre-provider media verification/transient failure; no provider mutation ambiguity
container_unknown       container-create request may have taken effect; exact provider evidence is required
terminal_failure        provider/media evidence proves the operation cannot safely continue
publish_unknown         publish request may have taken effect; exact provider evidence is required
published_unresolved    provider proves the container was published but exact media ID is not yet bound
```

`container_requested` and `publish_requested` are themselves ambiguous after a process crash because the process may stop after durable intent is committed and at any point around the network call. Another process therefore cannot acquire either mutation claim while one of those states exists.

A media-verification transport/transient HTTP failure is retryable because no provider POST has occurred. Hash, size, content-type, redirect and trust-boundary mismatches are terminal for that immutable manifest/publication binding.

## Reconciliation

Inspect local state first:

```powershell
video-manager instagram production status <publication-key>
```

### Ambiguous container creation

If the ledger is `container_requested` or `container_unknown` and no container ID is known, ordinary reconciliation remains blocked. Do not call `POST /media` again. Obtain the exact container ID from independent provider evidence, then bind that exact ID:

```powershell
video-manager instagram production reconcile <publication-key> --observed-container-id <exact-provider-container-id>
```

The command then performs read-only preflight and reads that exact container's status. The container ID must come from exact provider evidence; never guess it or select a merely recent container.

### Known container before publish ambiguity

For `container_created`, `processing` or `ready`, read-only reconciliation against the exact known container interprets provider status as follows:

- provider `FINISHED` -> `ready`;
- provider `IN_PROGRESS` -> `processing`;
- provider `ERROR` or `EXPIRED` -> `terminal_failure`;
- provider `PUBLISHED` -> `published_unresolved`; never call `media_publish` again.

### Ambiguous final publish

For `publish_requested`, `publish_unknown` or `published_unresolved`, provider `FINISHED`, `IN_PROGRESS`, `ERROR` or `EXPIRED` is **not proof that the earlier `media_publish` had no effect**. These observations remain fail-closed as `publish_unknown`. In particular, `FINISHED` never reopens `ready` from an ambiguous publish state.

Provider `PUBLISHED` becomes `published_unresolved`. If independent exact provider evidence proves the resulting media ID, bind it explicitly:

```powershell
video-manager instagram production reconcile <publication-key> --published-media-id <exact-provider-media-id>
```

`--published-media-id` is accepted only when the ledger is already in an ambiguous publish state and has an exact known container. The media ID must come from exact provider evidence. Do not select the newest post, match only by visual similarity, or guess an ID.

## Emergency stop

To stop all new Instagram writes immediately:

```powershell
$env:VCM_INSTAGRAM_WRITES_ENABLED = "false"
```

This does not rewrite ledger history and does not delete, edit or roll back an already published Instagram post. Provider-side deletion/editing is intentionally outside this publisher and requires a new exact owning scope.

If a process is currently only polling a known container, stopping it creates no new mutation. If interruption happens at or after `container_requested`, assume container creation may have taken effect until exact reconciliation proves the container identity. If interruption happens at or after `publish_requested`, assume publication may have taken effect. In both cases, do not replay the provider mutation blindly.

## Evidence to retain after a live canary

Retain provider-safe evidence without secrets:

- exact repository/deployment SHA;
- exact publication key and manifest content hash;
- exact media URL hostname, SHA-256, byte size and content type;
- exact account ID and reviewed username (never token);
- `container_requested_at` and exact container ID;
- `publish_requested_at` and final provider media ID when known;
- ledger state and timestamps;
- read-only provider status/reconciliation result;
- public permalink if independently resolved;
- operation-specific approval reference;
- any provider error code/message with tokens redacted.

Do not paste raw HTTP authorization headers or access tokens into GitHub.

## CI contract

Tests use mocked HTTP only. CI must prove at minimum:

- kill switch blocks before any provider request;
- exact target mismatch fails closed;
- untrusted media hosts fail closed before media fetch/provider POST;
- media SHA-256 or size mismatch causes zero provider POSTs;
- media redirects are refused before provider POST;
- public-media verification never receives the Meta Authorization header;
- only one database client can win the container-creation CAS claim;
- only one database client can win the final-publish CAS claim;
- a lost container-create response becomes `container_unknown` and cannot trigger a blind second `POST /media`;
- exact observed container evidence can bind the ambiguous creation to one container and continue read-only reconciliation;
- successful container -> finished -> publish path persists IDs;
- rerunning a published logical publication does not publish twice;
- ambiguous publish transport outcome becomes `publish_unknown`;
- a second publish is refused while ambiguity exists;
- `FINISHED` does not reopen `ready` after an ambiguous publish;
- reconciliation of a provider `PUBLISHED` container cannot republish it;
- manual media-ID reconciliation is restricted to ambiguous publish state with a known container;
- default polling is pinned at 60 seconds × 5 attempts to match current Meta guidance;
- a publication key cannot be rebound to different canonical content.

A green CI proves repository behavior. It does not prove production credentials, permissions, target identity, public media availability or authorize a live canary.
