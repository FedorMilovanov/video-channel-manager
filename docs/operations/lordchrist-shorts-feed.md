# LordChrist YouTube Shorts → Telegram native-video feed

Owning scope: Issue #501.

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

## Why the feed uses native Telegram video

The target presentation is one native Telegram `sendVideo` item per day rather than a YouTube-link-only post. The generic repository video payload already binds:

- exact project/channel profile;
- exact publication ID;
- reviewed MP4 path;
- SHA-256;
- byte size;
- filename;
- streaming mode.

Issue #501 only prepares data compatible with that runtime. It never calls the provider transport.

Default editorial cadence:

- one Short per day;
- `18:17 Europe/Moscow`;
- oldest confirmed Short first;
- at least four hours of separation from the existing editorial/quote lane.

The policy is frozen in `content/telegram/lordchrist/shorts-feed-policy.json`.

## 1. Read-only YouTube inventory

Use the existing owner OAuth account and exact channel ID:

```bash
video-manager youtube scan \
  --account fedor-milovanov \
  --channel UCeSJsC6go2c9pdJCuUI1BYA \
  --output operator-output/lordchrist-youtube-audit.json
```

The existing YouTube client requests owner-visible `fileDetails`. The Shorts classifier uses exact geometry, duration, rotation and owner file creation-time evidence where available.

Build the LordChrist Shorts inventory:

```bash
python -m video_channel_manager.lordchrist_shorts inventory \
  --audit operator-output/lordchrist-youtube-audit.json \
  --output operator-output/lordchrist-shorts-inventory.json
```

The inventory has three relevant outcomes:

1. `short` — exact owner metadata is sufficient for conservative Shorts classification;
2. `candidate` — square/vertical duration evidence is compatible with Shorts but historical timing is insufficient for exact positive classification;
3. excluded — exact long-form evidence or insufficient candidate evidence.

Historical `candidate` items are **not silently promoted**. They require exact owner review by video ID before a future release is built.

`#Shorts`, title text, thumbnail geometry and guessed upload dates are not accepted as positive identity evidence.

## 2. Obtain owner media

For historical owner bytes, use either:

- Google Takeout export of the owner’s YouTube uploads; or
- an existing local clean master owned by the project.

Do not make the repository infer a file by title. Create an explicit binding manifest:

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
      "source_path": "C:/Users/Fedor/Downloads/Takeout/YouTube/video-file.mp4"
    }
  ]
}
```

The binding is exact `youtube_video_id → owner file path`. There is no title-only, newest-file or wildcard fallback.

## 3. Prepare Telegram-ready media

Run:

```bash
python -m video_channel_manager.lordchrist_shorts prepare-media \
  --inventory operator-output/lordchrist-shorts-inventory.json \
  --bindings operator-output/lordchrist-shorts-owner-media-bindings.json \
  --output-dir operator-output/lordchrist-shorts-media \
  --output operator-output/lordchrist-shorts-media-acceptance.json
```

Every source is read-only probed and hashed first.

If the source is already Telegram-ready, the exact bytes are copied unchanged. Otherwise a local FFmpeg conversion creates an accepted derivative with:

- MP4;
- H.264;
- `yuv420p`;
- orientation baked into pixels, no retained rotation dependency;
- AAC audio when audio exists;
- `+faststart`;
- even dimensions;
- at most 50,000,000 bytes;
- duration no greater than 180 seconds.

The acceptance artifact records source SHA-256, accepted transport SHA-256, source/transport probe summaries, whether transcoding occurred, and FFmpeg/FFprobe provenance. Provider access/write flags are hard-coded false.

If exact duplicate accepted bytes are bound to different YouTube IDs, preparation fails instead of filling the channel with duplicate video.

## 4. Historical candidate confirmation

A `candidate` may enter a release only by exact video ID:

```text
--approve-candidate EXACT_VIDEO_ID
```

Approval is scoped only to that inventory candidate. A typo, a non-candidate ID, or a title cannot authorize another item.

This is an editorial/source classification decision, **not** Telegram execution authority.

## 5. Build an unauthorized release preview

Before release construction, materialize/read the durable LordChrist state branch and pass every active LordChrist ledger to the builder. The current legacy paths are:

```text
content/telegram/lordchrist/publication-ledger.json
content/telegram/lordchrist/research-v2/publication-ledger.json
```

Example:

```bash
python -m video_channel_manager.lordchrist_shorts build-release \
  --inventory operator-output/lordchrist-shorts-inventory.json \
  --media operator-output/lordchrist-shorts-media-acceptance.json \
  --start-date 2026-08-21 \
  --existing-ledger .state/lordchrist/content/telegram/lordchrist/publication-ledger.json \
  --existing-ledger .state/lordchrist/content/telegram/lordchrist/research-v2/publication-ledger.json \
  --output operator-output/lordchrist-shorts-release-preview.json
```

The result is the repository’s existing generic `telegram-release-queue` schema with `GenericVideoPayload` items, one item per day at 18:17 Moscow time.

By construction under Issue #501:

```text
release_authorized = false
target_binding_sha256 = null
chat_id = null
bot_id = null
bot_username = null
```

The canonical LordChrist profile itself is also required to remain `provider_writes_authorized=false`.

Therefore the preview cannot be sent by the generic Telegram runtime.

## Channel-wide safety

The generalized LordChrist effect guard accepts any number of writer tracks. Before a future Shorts writer can mutate Telegram, all active LordChrist ledgers must satisfy:

- no `dispatching` effect;
- no `provider_effect=may_exist`;
- no candidate publication ID already present in durable state.

An ambiguous legacy/research/Shorts outcome blocks **all** LordChrist writers until read-only reconciliation or an exact terminal disposition resolves it.

This extends the existing no-blind-replay principle rather than creating an independent Shorts publisher.

## Stories and Telegram “Scheduled Messages”

They are intentionally outside Issue #501.

Bot-based native-video publication can use the existing guarded Telegram transport, but server-side channel Scheduled Messages and ordinary channel Stories require a different Telegram authority model (MTProto/user session or another separately reviewed capability). That broader credential surface must not be introduced as a shortcut for this backlog.

If Stories are added later, they should be a secondary promotion lane for selected already-reviewed Shorts, not the canonical archive.

## Provider boundary

Allowed under Issue #501:

- read-only YouTube inventory;
- local/Takeout owner-file binding;
- local FFprobe/FFmpeg;
- hashing and exact-media acceptance;
- provider-inert release preview;
- GitHub CI/tests/docs.

Forbidden:

- Telegram send/edit/delete/pin;
- Telegram Story publication;
- MTProto/user-session creation or use;
- YouTube mutation;
- automated third-party YouTube download;
- release/execution authorization;
- live schedule activation.

A future live rollout must get a new exact owning scope, fresh current-main proof, exact state reconciliation, target preflight, immutable reviewed release, separate human execution authority, durable intent before one provider attempt, and exact provider-visible postflight.
