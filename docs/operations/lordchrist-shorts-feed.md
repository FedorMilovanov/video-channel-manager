# LordChrist YouTube Shorts → Telegram native-video feed

Repository implementation originated in Issue #501. The current read-only artifact/backlog wave is Issue #503.

This runbook defines a **provider-inert** intake and artifact path for moving the owner’s YouTube Shorts from the canonical `lord-god-strength` YouTube channel into a future native-video queue for `@lordchrist`.

It does **not** authorize Telegram publication, Stories, MTProto/user-session use, YouTube mutation, or automated third-party YouTube downloading.

## Canonical identities

| Surface | Exact identity |
| --- | --- |
| project | `lord-god-strength` |
| YouTube channel | `UCeSJsC6go2c9pdJCuUI1BYA` |
| YouTube handle | `@fedormilovanov` |
| YouTube OAuth alias | `fedor-milovanov` |
| Telegram channel | `@lordchrist` |
| Telegram profile | `content/telegram/channels/lordchrist.json` |
| durable Telegram state | `state/lordchrist-telegram` |

The source video ID is the durable cross-platform source identity. A Shorts publication identity is exactly:

`lordchrist-short-<youtube_video_id>`

Titles, filenames, timestamps, queue positions and generated captions never select source identity.

## Native-video cadence

The target presentation is one native Telegram `sendVideo` item per day rather than a YouTube-link-only post. The generic repository video payload binds exact project/channel profile, publication ID, MP4 path, SHA-256, byte size, filename and streaming mode.

Provider-inert default cadence:

- one Short per day;
- `17:17 Europe/Moscow`;
- oldest confirmed Short first;
- at least four hours from both existing quote/editorial slots (`09:17` primary and `21:17` catch-up).

The Shorts policy is frozen in `content/telegram/lordchrist/shorts-feed-policy.json`. `validate-policy` also reads the canonical `content/telegram/lordchrist/production-schedule.json`; policy validation fails if the required gap is no longer true.

## 1. Fresh read-only YouTube inventory

Use the existing owner OAuth account and exact channel ID:

```bash
video-manager youtube scan \
  --account fedor-milovanov \
  --channel UCeSJsC6go2c9pdJCuUI1BYA \
  --output operator-output/lordchrist-youtube-audit.json
```

The YouTube client enumerates the exact owner uploads playlist and requests `snippet,contentDetails,status,fileDetails`. If `videos.list` omits any ID that the uploads playlist enumerated, the scan fails closed instead of silently producing an incomplete channel inventory.

A Shorts snapshot is accepted only when it is both sufficiently evidenced and fresh. Default maximum age is 48 hours. The standalone diagnostic command is:

```bash
python -m video_channel_manager.lordchrist_shorts_snapshot_readiness \
  --audit operator-output/lordchrist-youtube-audit.json \
  --max-age-hours 48
```

Build the exact inventory:

```bash
python -m video_channel_manager.lordchrist_shorts inventory \
  --audit operator-output/lordchrist-youtube-audit.json \
  --max-snapshot-age-hours 48 \
  --output operator-output/lordchrist-shorts-inventory.json
```

The `inventory` command performs the readiness check itself. Running the standalone readiness command first is useful diagnostics, but it is not a bypassable safety dependency.

Inventory outcomes:

1. `short` — exact owner metadata proves the conservative Shorts classification;
2. `candidate` — owner geometry/duration are compatible with Shorts, but historical timing does not prove the surface exactly;
3. excluded — exact long-form evidence or insufficient candidate evidence.

`#Shorts`, title text, thumbnail geometry and guessed upload dates are not accepted as positive identity evidence.

The 2026-07-29 owner catalog `5b994503-6107-4cbe-adc8-740b50562075` is frozen as duration-only reconciliation evidence in `content/telegram/lordchrist/shorts-historical-duration-baseline-20260729.json`. It contains the 25 post-cutoff `<=180s` IDs found in Issue #503. That file is **not** a current Shorts inventory: it has no `fileDetails`, and the inventory/readiness path refuses that exact snapshot id even if `--max-snapshot-age-hours` is raised.

Compare a **fresh** owner snapshot to that frozen set:

```bash
python -m video_channel_manager.lordchrist_shorts reconcile-baseline \
  --audit operator-output/lordchrist-youtube-audit.json \
  --baseline content/telegram/lordchrist/shorts-historical-duration-baseline-20260729.json \
  --output operator-output/lordchrist-shorts-baseline-reconciliation.json
```

Reconciliation is provider-inert. It cannot run against the frozen snapshot itself.

## 2. Freeze exact owner media bindings

Historical owner bytes may come only from:

- Google Takeout export of the owner’s YouTube uploads; or
- an existing local clean master owned by the project.

Do not infer a file by title, newest-file ordering or wildcard. Before preparation, calculate the exact owner-file SHA-256 and byte size and freeze them with the exact YouTube video ID:

```json
{
  "schema_name": "video-channel-manager.lordchrist-shorts-owner-media-bindings",
  "schema_version": 1,
  "project_key": "lord-god-strength",
  "youtube_channel_id": "UCeSJsC6go2c9pdJCuUI1BYA",
  "items": [
    {
      "youtube_video_id": "EXACT_VIDEO_ID",
      "source_kind": "google_takeout",
      "source_path": "C:/Users/Fedor/Downloads/Takeout/YouTube/video-file.mp4",
      "expected_source_sha256": "sha256:EXACT_64_HEX_DIGEST",
      "expected_source_byte_size": 12345678
    }
  ]
}
```

Preparation rejects a size/hash mismatch before media work and re-hashes the source after copy/transcode. If source bytes change during preparation, the output is rejected rather than accepted under stale provenance.

## 3. Prepare Telegram-ready media

Run:

```bash
python -m video_channel_manager.lordchrist_shorts prepare-media \
  --inventory operator-output/lordchrist-shorts-inventory.json \
  --bindings operator-output/lordchrist-shorts-owner-media-bindings.json \
  --output-dir operator-output/lordchrist-shorts-media \
  --output operator-output/lordchrist-shorts-media-acceptance.json
```

If source bytes are already Telegram-ready they are copied unchanged. Otherwise local FFmpeg creates an accepted derivative with:

- MP4;
- H.264;
- `yuv420p`;
- orientation baked into pixels, with no retained rotation dependency;
- AAC when audio exists;
- `+faststart`;
- even dimensions;
- at most 50,000,000 bytes;
- duration no greater than 180 seconds.

Acceptance records source SHA-256, transport SHA-256, byte sizes, probe summaries, transcode status and FFmpeg/FFprobe provenance. Provider access/write flags are hard-coded false. Exact duplicate accepted bytes across different YouTube IDs are rejected.

Record the complete Issue #503 backlog partition after inventory, and optionally after bindings/acceptance/candidate approval. Every inventory item receives exactly one of `accepted`, `media_missing`, or `candidate_unconfirmed`. Missing owner media is an explicit recorded state, not an implicit gap.

```bash
python -m video_channel_manager.lordchrist_shorts backlog-status \
  --inventory operator-output/lordchrist-shorts-inventory.json \
  --output operator-output/lordchrist-shorts-backlog-status.json
```

Optional exact inputs:

```text
--bindings operator-output/lordchrist-shorts-owner-media-bindings.json
--media operator-output/lordchrist-shorts-media-acceptance.json
--candidate-approval operator-output/lordchrist-shorts-candidate-approval.json
```

Unapproved candidates stay `candidate_unconfirmed` even if owner bytes are already bound. Proven shorts and approved candidates without accepted transport stay `media_missing`. The artifact is hard-coded `release_authorized=false` and performs no Telegram/YouTube mutation.

## 4. Historical candidate confirmation is an immutable artifact

A historical `candidate` is never promoted by a transient CLI flag. If an exact owner review confirms a candidate belongs in the backlog, create a snapshot-bound approval artifact:

```json
{
  "schema_name": "video-channel-manager.lordchrist-shorts-candidate-approval",
  "schema_version": 1,
  "project_key": "lord-god-strength",
  "youtube_channel_id": "UCeSJsC6go2c9pdJCuUI1BYA",
  "inventory_snapshot_id": "EXACT_SNAPSHOT_UUID",
  "approved_video_ids": ["EXACT_VIDEO_ID"],
  "reviewed_by": "FedorMilovanov",
  "reviewed_at": "2026-08-20T18:00:00+00:00"
}
```

The approval must match the exact inventory snapshot and may contain only IDs that are actually `candidate` records in that snapshot. This is source/editorial confirmation, **not** Telegram release or execution authority.

## 5. Materialize complete durable LordChrist state

Release preview construction no longer accepts an optional hand-picked ledger list. Materialize the complete `content/telegram/lordchrist` tree from durable branch `state/lordchrist-telegram` into a local state root, for example:

```text
.state/lordchrist/content/telegram/lordchrist
```

The builder requires, at minimum, the canonical legacy ledger, research-v2 ledger + exact retirement disposition, and rich-v1 live-canary ledger. It recursively inspects provider-effect JSON under that root, including one-off state and any future ledger JSON.

The historical research-v2 `retired_no_replay` disposition is honored only when its exact retirement artifact is present and says `provider_retry_forbidden=true`. Other `dispatching` / `provider_effect=may_exist` records remain channel-wide blockers.

## 6. Build an unauthorized release preview

Example without historical candidates:

```bash
python -m video_channel_manager.lordchrist_shorts build-release \
  --inventory operator-output/lordchrist-shorts-inventory.json \
  --media operator-output/lordchrist-shorts-media-acceptance.json \
  --state-root .state/lordchrist/content/telegram/lordchrist \
  --start-date 2026-08-21 \
  --output operator-output/lordchrist-shorts-release-preview.json
```

If reviewed historical candidates are included, add:

```text
--candidate-approval operator-output/lordchrist-shorts-candidate-approval.json
```

The result is the existing generic `telegram-release-queue` with `GenericVideoPayload` items, one item per day at 17:17 Moscow time. The release ID is content-addressed from the exact snapshot, selected ordered publication IDs, accepted media digests, profile, cadence and start date; two materially different previews on the same date do not share one release identity.

By construction:

```text
release_authorized = false
target_binding_sha256 = null
chat_id = null
bot_id = null
bot_username = null
```

The canonical LordChrist profile must remain `provider_writes_authorized=false`. Therefore this preview is not a provider mutation artifact and cannot be treated as standing Telegram authority.

## Channel-wide safety

Before any future Shorts writer can mutate Telegram, the complete LordChrist state must prove:

- no unresolved `dispatching` effect;
- no unresolved `provider_effect=may_exist` except an exact terminal `retired_no_replay` disposition;
- no selected Shorts `publication_id` already present in durable state.

Missing state is not equivalent to empty state. An incomplete materialized state root fails closed.

## Stories and Telegram Scheduled Messages

They remain outside this artifact scope. Bot-based native-video publication can reuse the guarded Telegram transport, but server-side channel Scheduled Messages and ordinary channel Stories require a different Telegram authority model such as a separately reviewed MTProto/user session. Do not introduce that credential surface as a shortcut for this backlog.

If Stories are added later, they should be a secondary promotion lane for selected already-reviewed Shorts, not the canonical archive.

## Provider boundary

Allowed in the current artifact scope:

- read-only owner YouTube inventory;
- reconciliation against the frozen 2026-07-29 duration-only baseline;
- explicit `accepted` / `media_missing` / `candidate_unconfirmed` backlog recording;
- local/Takeout owner-file binding;
- local FFprobe/FFmpeg;
- hashing and exact-media acceptance;
- immutable candidate-review artifacts;
- complete durable-state readback/materialization;
- provider-inert release preview;
- GitHub CI/tests/docs.

Forbidden without a new exact rollout scope and authorization:

- Telegram send/edit/delete/pin;
- Telegram Story publication;
- MTProto/user-session creation or use;
- YouTube mutation;
- automated third-party YouTube download;
- release/execution authorization;
- live schedule activation.

A future live rollout requires a new exact owning scope, fresh current-main proof, fresh durable state, exact target preflight, immutable reviewed release, separate human execution authority, durable intent before one provider attempt, zero blind mutation retries and exact provider-visible postflight.
