# Milovi Telegram permanent feed control plane

Updated: 2026-11-14 (November schedule and historical-status clarification)  
Owning workstream: Issue #353  
Provider target: `@MiloviCake`

This runbook defines the permanent Milovi Telegram feed path. It is an implementation and safety contract; it is **not** provider execution authority.

## November 2026 operational checkpoint (evidence, not authority)

The canonical November 8–22 muted15 owner-approved video schedule lives in
`.github/workflows/milovi-telegram-muted15-due-20261108.yml` and
`scripts/milovi_muted15_due.py`. The schedule delegates to the **one** permanent
publisher and never sends to Telegram itself. The gate is exactly 19:00–21:00
Moscow; neither a delayed GitHub cron nor a green `due/dispatch=false` run
proves delivery. The hardened controller adds six checks during that window and
an independent `audit-expired` alarm for older pending/impossible items, **not**
backfill or a second provider writer.

Read-only 14 November checkpoint: 15/15 state ledgers were `pending/impossible`;
the 8–13 November approved windows had expired without verified Telegram
receipts. Past release IDs cannot be re-sent or extended automatically. Only
`state/milovi-cake-telegram` and fresh exact Telegram receipts determine
current results; this dated text is never a replacement for protected state.

## One writer

`.github/workflows/milovi-telegram-feed-publisher.yml` is the only supported Milovi Telegram provider-mutation workflow.

It is `workflow_dispatch`-only, serialized by `milovi-cake-telegram-publisher`, and uses durable state branch `state/milovi-cake-telegram`. Historical bootstrap/canary/ledger-init workflows, one-off per-publication controllers, and `follow-on-*` readiness/media-proof workflows are retired and must not be restored as parallel or helper runtime paths. Their frozen manifests and evidence remain non-executable history.

Read-only target discovery remains separate and may never call the mutation runtime. Its read-only status is defined by exact transport semantics, not by whether the configured bot profile is technically capable of writes.

## Exact publication bundle

Every permanent feed publication uses identity `milovi-feed-YYYYMMDD-NNN` and an exact set of artifacts:

- `content/telegram/milovi-cake/releases/<id>-runtime.json` — immutable generic Telegram release;
- `content/telegram/milovi-cake/releases/<id>-execution-authority.json` — separate exact execution gate;
- exactly one of:
  - `<id>-media.json` for `sendPhoto`;
  - `<id>-message.json` for `sendMessage`;
  - `<id>-video.json` for accepted-reservoir `sendVideo`;
- `content/telegram/milovi-cake/feed/<id>.json` on the durable state branch — exact release ledger;
- `content/telegram/milovi-cake/feed/index.json` on the durable state branch — channel-wide duplicate guard.

The three content bindings are mutually exclusive. The validator fails closed if one publication carries more than one binding kind.

The frozen editorial/source candidate remains a separate provenance object. It never becomes provider authority by itself.

## November 2026 separate muted video transport

Issue #809 recovered the existing v12 finished-cake footage and made a
standalone transport with the soundtrack **entirely removed**, retaining the
exact H.264 stream. This is NOT a rewrite or replacement of the accepted
August 16/16 MP4 reservoir.

- Accepted additional manifest:
  content/telegram/milovi-cake/accepted-video-variants-2026-11.json
- Protected evidence ref:
  agent/milovi-video-muted-v12-3b680fe94b50
- Immutable artifact commit:
  686223b41c01ce365853f2e2bf22c20240a1df01
- Exact media identity: v12-muted, schema version 2, original accepted v12
  parent and SHA-bound provenance, zero audio streams.
- Only new ID milovi-feed-20261107-002 may bind this new transport. The
  old audio-bearing milovi-feed-20261107-001 was permanently retired due to
  a corrupted Cyrillic caption; it must not be remediated in-place or replayed.
- The media registry remains content_approved=false and
  rights_verified=false until the owner validates the actual footage.
- Sending still requires the established **single** stateful Milovi
  permanent-feed writer, exact current-main and target proof, verified rights,
  signed release, independent execution permission, durable intent and
  one no-retry send.
- For both version-1 and version-2 video bindings the canonical writer now
  fetches the media from an **immutable full Git commit**, not a branch name,
  and checks the exact accepted SHA256 and Git blob before materialization.

This extension is additive. The August transport manifest and original 16
accepted media identities are unchanged.

## Supported permanent-feed payloads

The sole writer supports three exact payload kinds through the same generic one-attempt runtime:

- `sendPhoto` — exact candidate caption plus reviewed source/transport bytes; deterministic JPEG materialization happens before `send-once`;
- `sendMessage` — exact candidate text plus SHA-256 binding; no fake media is required;
- `sendVideo` — exact candidate caption plus an MP4 from the accepted 16/16 reservoir **or** a separately approved November muted-video variant pinned to immutable media SHA-256, reviewed release, and exact authorized date; no broad media substitution.

All three pass the same current-main gate, release/content authorization, separate execution authorization, explicit state initialization, duplicate guard, freshness check, exact target preflight, durable intent-before-send, exactly one mutation attempt and exact outcome reconciliation.

Poll publication is not added to the Milovi permanent feed by this contract.

## Accepted video boundary

`content/telegram/milovi-cake/accepted-video-reservoir-2026-08.json` is the main-branch index of the exact 16 already-accepted Telegram-ready MP4s.

The bytes remain on the content-addressed artifact branch `agent/milovi-video-accepted-73c578eff825` (commit `f4f5512d7b60f1b9c61c293c07620b128536df27`). `milovi-telegram-video-artifacts.yml` never mints a ref: both jobs run `video_channel_manager.milovi_telegram_video_proof` with `contents: read`. The proof separates three claims, two of which are about us.

**Release integrity is blocking.** It reads `artifact_ref` and `artifact_commit` from the reservoir, fetches that commit *by SHA*, and requires every accepted path to hold exactly the recorded blob id, with no missing and no unreviewed artifact. A rewritten or deleted ref, a stale reservoir row, or a build that does not produce the accepted set stops the job with exit 3 and a GitHub error annotation.

**Determinism is blocking and measured, not inferred.** Each job converts the same pinned source commit twice, into two directories, and the proof requires both builds to agree byte-for-byte. If they do not, the pipeline is at fault and nothing is published from the workspace.

**Reproduction of the accepted bytes is reported.** `apt-get install ffmpeg` follows a moving Ubuntu archive, and the encoder that decides those bytes is `libavcodec`/`libx264`, which apt updates independently of the `ffmpeg` binary the evidence fingerprints. On 2026-10-22 the archive shipped such an update: all sixteen rebuilt files differed from the accepted bytes by between −414 and +4348 bytes, while the accepted set — and therefore the release — was unchanged. Because two builds of the same inputs agreed, that difference cannot be the pipeline's fault; it is reported as a warning with both digests and a `video-rebuild-proof.json` artifact, and re-accepting a new encoding remains a separate release decision. Inferring this from the recorded encoder digest instead was tried and was wrong: identical `ffmpeg` binary digests still produced different bytes.

The reservoir freezes each media idThe reservoir freezes each media id, artifact path, Git blob SHA-1, byte size and SHA-256 and binds the shared conversion evidence digest:

`sha256:73c578eff82563300c463361bd3998caeba8a083ce0de4ed29cc271617dfd6ae`

The permanent video path does not transcode at publication time and does not accept arbitrary video URLs/files. It downloads only the exact artifact named by the immutable `<id>-video.json` binding, then rechecks byte size, SHA-256 and Git blob identity before the common `send-once` call. `sendDocument` fallback is forbidden.

If this lane is ever re-accepted from a new build, the new evidence should record the `dpkg` versions of `libavcodec*`, `libavformat*`, `libavutil*`, `libx264*` and `libvpx*` next to the client binary digests: the encoding is decided by those libraries, and the `ffmpeg` binary digest alone does not identify an encoder.

Accepted artifact readiness is still not execution authority. A future video publication needs the same fresh exact release and human execution gates as a photo or text publication.

## Authority split

Release/content review and provider execution are deliberately separate.

An authorized runtime release must satisfy the generic immutable release contract, exact target binding and reviewed-candidate digest. A separate execution-authority object must then bind that exact authorized release digest and provider payload digest and explicitly carry `execution_authorized=true` plus `provider_mutation_allowed=true` with fresh human provenance.

Historical bootstrap authorization, successful canary evidence, credentials, a writable channel profile, CI success, workflow dispatch, accepted media evidence or automation never inherit into this gate.

## Provider-free state initialization

Durable state is created only as an explicit separate operation after the exact release is authorized:

`operation=initialize-state`

with confirmation:

`INITIALIZE:@MiloviCake:<publication_id>`

This operation performs no Telegram access. It initializes the exact release ledger and registers the immutable publication identity/payload in the channel-wide feed index. Re-running initialization is idempotent only when those immutable identities match exactly; any collision fails closed.

A `publish` operation never auto-initializes missing state.

## One exact publish attempt

A provider attempt requires:

1. exact current `main`;
2. exact `Milovi Telegram feed quality` success for that SHA;
3. immutable authorized runtime release;
4. separate fresh exact human execution authority;
5. exact initialized release ledger;
6. channel-wide index agreement and publishable state;
7. strict publication freshness;
8. fresh read-only exact target preflight;
9. one durable prepared intent persisted to both release state and channel-wide index before mutation;
10. current-main/quality reproof immediately before provider mutation;
11. payload-specific exact byte materialization when needed: JPEG for photo, accepted MP4 for video, none for message;
12. one `telegram_multichannel_cli send-once` call;
13. exact outcome applied to the ledger and channel-wide index.

Mutation transport retries remain zero. A missing/ambiguous outcome is not permission to replay. `may_exist` or otherwise unknown provider effect remains blocking pending exact read-only reconciliation.

## Stale dated identities — do not catch up

These identities remain immutable history. The timestamp is part of each publication identity; staleness must fail closed. Do **not** widen freshness, edit an old timestamp, transfer authorization, initialize later as catch-up, or reinterpret any of them as a later send.

- `milovi-feed-20260819-001` — scheduled `2026-08-19T10:30:00+03:00`; never authorized; no provider mutation.
- `milovi-feed-20260820-001` — scheduled `2026-08-20T10:30:00+03:00`; `release_authorized=false` / `execution_authorized=false`; frozen `p16` bytes only; no durable intent.
- `milovi-feed-20260820-002` — scheduled `2026-08-20T20:00:00+03:00`; PR #500 set `release_authorized=true` and `execution_authorized=true` for marathon position 1 (`sendPhoto` / `p06`); the permanent publisher had no initialize-state or publish run; durable feed state was not initialized; the 120-minute lag gate has expired. Do not publish this identity now.

## Historical August 21 exact photo publication (expired)

`milovi-feed-20260821-001` was an August 2026 exact photo publication, not a current executable release: `2026-08-21T10:30:00+03:00`, marathon position 1, media `p06`, same reviewed source/transport as expired `20260820-002`, tighter public caption, no new claims. Runtime `release_authorized=true` and execution `execution_authorized=true` are bound to this identity only. The content candidate JSON remains provider-inert by contract. That historical 10:30–12:30 Europe/Moscow window has expired. Do not use this old record as present execution authority or silently catch it up; later November schedules have their own separately reviewed identities.

## Marathon editorial source

`content/telegram/milovi-cake/marathon-wave-2026-08.json` is the canonical provider-inert 12-item Cake + School sequence consolidated by PR #497. It freezes sequence/provenance, not future dates or publication ids.

Its three School positions can be promoted through the exact `sendMessage` binding added by PR #498. The accepted-video reservoir is additional ready media for later reviewed editorial promotion; this runbook does not silently rewrite the already-frozen 12-item marathon into a different sequence.

## Video evidence provenance

PR #491 completed the provider-free video artifact lane. The durable proof on `agent/milovi-video-accepted-73c578eff825` records `status=accepted_16_of_16`, `accepted_output_count=16`, `declared_video_count=16`, `provider_access_performed=false` and `provider_write_performed=false`.

Every accepted output is MP4/H.264/yuv420p with exactly one AAC 48 kHz stereo stream. The main-branch reservoir index makes those exact accepted identities discoverable without reviving the old conversion/persistence workflow as a publisher.

Nothing in this runbook authorizes Telegram mutation.
