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
8. The durable ledger is updated before the irreversible `media_publish` request.
9. `publish_requested`, `publish_unknown` and `published_unresolved` are fail-closed states. They prohibit another publish until reconciliation proves what happened.
10. A network failure or 5xx around `media_publish` is treated as an ambiguous provider effect, not as permission to retry.
11. A provider-confirmed `PUBLISHED` container without an exact media ID is recorded as `published_unresolved`; never infer or fabricate the media ID.
12. Provider writes never occur in CI tests.

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

Production kill switch, default false:

```text
VCM_INSTAGRAM_WRITES_ENABLED=false
```

Operational tuning:

```text
VCM_INSTAGRAM_REQUEST_TIMEOUT_SECONDS=30
VCM_INSTAGRAM_POLL_INTERVAL_SECONDS=5
VCM_INSTAGRAM_POLL_ATTEMPTS=24
```

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
  "caption": "Reviewed caption",
  "share_to_feed": true,
  "cover_url": null,
  "thumb_offset_ms": null
}
```

The URL must be HTTPS and publicly reachable by Meta; localhost and non-global IP targets are rejected. The publication key is an idempotency boundary, not a display label. Never reuse it for changed caption/media/account content.

Before a canary, the URL must point at the reviewed final Reel bytes, not an editor preview, mutable local tunnel, temporary authenticated URL that may expire during Meta ingestion, or an unreviewed source master. The exact technical/media evidence remains upstream authority for those bytes.

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

Failure is blocking. Do not bypass identity mismatch by editing a manifest to whichever account the token happened to return.

## Provider-inert plan

After the `0002` migration, bind a reviewed manifest into the durable ledger without any provider request:

```powershell
video-manager instagram production plan .\operator-output\instagram-reel-001.json
video-manager instagram production status legendary-poet.2026-09-08.reel-001
```

Expected initial state: `planned`.

Re-running the same manifest is idempotent. Reusing the same publication key with different canonical content is rejected.

## Canary execution

A live canary is a separate operational act from implementation completion.

Before enabling writes, independently verify:

- exact current `main` and deployed revision;
- exact issue/release/operation identity authorized for the canary;
- exact Instagram account ID and username;
- current token and required permissions;
- current publishing quota;
- final public media URL and reviewed bytes;
- final caption/cover/feed choice;
- durable ledger state for the publication key;
- no existing Instagram post for the same intended release;
- no unresolved `publish_requested`, `publish_unknown` or `published_unresolved` state.

Only for the approved invocation:

```powershell
$env:VCM_INSTAGRAM_WRITES_ENABLED = "true"
video-manager instagram production publish .\operator-output\instagram-reel-001.json --execute
```

Immediately restore the kill switch after the authorized operation:

```powershell
$env:VCM_INSTAGRAM_WRITES_ENABLED = "false"
```

The publisher performs read-only exact-target preflight before writes, creates one Reel container if no container is already durably known, polls that exact container, persists `publish_requested`, then performs one `media_publish` request.

## State machine

Normal path:

```text
planned
  -> container_created
  -> processing (zero or more observations)
  -> ready
  -> publish_requested
  -> published
```

Failure/reconciliation states:

```text
retryable_failure       creation/known pre-publish failure; no publish ambiguity
terminal_failure        provider proves the operation cannot safely continue
publish_unknown         publish request outcome is ambiguous
published_unresolved    provider proves the container was published but exact media ID is not yet bound
```

`publish_requested` itself is treated as ambiguous after a restart. This is deliberate: a crash can occur after the durable state commit and at any point around the network call.

## Reconciliation

Inspect local state first:

```powershell
video-manager instagram production status <publication-key>
```

Then reconcile read-only against the exact known container:

```powershell
video-manager instagram production reconcile <publication-key>
```

Interpretation:

- provider `FINISHED` -> ledger returns to `ready`; the container is not published and a separately authorized later publish can use that same container;
- provider `IN_PROGRESS` -> ledger becomes `processing`; do not create another container;
- provider `ERROR` or `EXPIRED` -> `terminal_failure`;
- provider `PUBLISHED` -> `published_unresolved`; do not call `media_publish` again.

If independent exact provider evidence proves the media ID for a `PUBLISHED` result, bind it explicitly:

```powershell
video-manager instagram production reconcile <publication-key> --published-media-id <exact-provider-media-id>
```

The media ID must come from exact provider evidence. Do not select the newest post, match only by visual similarity, or guess an ID.

## Emergency stop

To stop all new Instagram writes immediately:

```powershell
$env:VCM_INSTAGRAM_WRITES_ENABLED = "false"
```

This does not rewrite ledger history and does not delete, edit or roll back an already published Instagram post. Provider-side deletion/editing is intentionally outside this publisher and requires a new exact owning scope.

If a process is currently waiting on a container, stopping the process is safe with respect to duplicate publication: the known container ID is durable. If interruption happens at or after `publish_requested`, treat the effect as ambiguous and reconcile before doing anything else.

## Evidence to retain after a live canary

Retain provider-safe evidence without secrets:

- exact repository/deployment SHA;
- exact publication key and manifest content hash;
- exact account ID and reviewed username (never token);
- container ID;
- final provider media ID when known;
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
- successful container -> finished -> publish path persists IDs;
- rerunning a published logical publication does not publish twice;
- ambiguous publish transport outcome becomes `publish_unknown`;
- a second publish is refused while ambiguity exists;
- reconciliation of a provider `PUBLISHED` container cannot republish it;
- a publication key cannot be rebound to different canonical content.

A green CI proves repository behavior. It does not prove production credentials, permissions, target identity, public media availability or authorize a live canary.
