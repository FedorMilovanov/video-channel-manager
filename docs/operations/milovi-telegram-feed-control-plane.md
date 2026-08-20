# Milovi Telegram permanent feed control plane

Updated: 2026-08-20  
Owning workstream: Issue #353  
Provider target: `@MiloviCake`

This runbook defines the permanent Milovi Telegram feed path. It is an implementation and safety contract; it is **not** provider execution authority.

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

## Supported permanent-feed payloads

The sole writer supports three exact payload kinds through the same generic one-attempt runtime:

- `sendPhoto` — exact candidate caption plus reviewed source/transport bytes; deterministic JPEG materialization happens before `send-once`;
- `sendMessage` — exact candidate text plus SHA-256 binding; no fake media is required;
- `sendVideo` — exact candidate caption plus an MP4 identity from the accepted 16/16 reservoir only.

All three pass the same current-main gate, release/content authorization, separate execution authorization, explicit state initialization, duplicate guard, freshness check, exact target preflight, durable intent-before-send, exactly one mutation attempt and exact outcome reconciliation.

Poll publication is not added to the Milovi permanent feed by this contract.

## Accepted video boundary

`content/telegram/milovi-cake/accepted-video-reservoir-2026-08.json` is the main-branch index of the exact 16 already-accepted Telegram-ready MP4s.

The bytes remain on the content-addressed artifact branch `agent/milovi-video-accepted-73c578eff825`. The reservoir freezes each media id, artifact path, Git blob SHA-1, byte size and SHA-256 and binds the shared conversion evidence digest:

`sha256:73c578eff82563300c463361bd3998caeba8a083ce0de4ed29cc271617dfd6ae`

The permanent video path does not transcode at publication time and does not accept arbitrary video URLs/files. It downloads only the exact artifact named by the immutable `<id>-video.json` binding, then rechecks byte size, SHA-256 and Git blob identity before the common `send-once` call. `sendDocument` fallback is forbidden.

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

## Stale predecessor — do not catch up

`milovi-feed-20260819-001` remains immutable provider-inert history. Its frozen scheduled time is `2026-08-19T10:30:00+03:00`, which has passed. The timestamp is part of that publication identity; staleness must fail closed.

Do **not** widen freshness, edit the old timestamp, transfer authorization, initialize it later as a catch-up publication, or reinterpret it as a later send. No provider mutation was performed for that identity.

## Existing exact photo candidate

`milovi-feed-20260820-001` remains a provider-inert photo candidate. Its exact source/transport/caption identities are already frozen, but `release_authorized=false`, `execution_authorized=false`, `provider_mutation_allowed=false`, permanent feed state is not initialized and there is no durable execution intent.

This runbook does not authorize that publication or any successor.

## Marathon editorial source

`content/telegram/milovi-cake/marathon-wave-2026-08.json` is the canonical provider-inert 12-item Cake + School sequence consolidated by PR #497. It freezes sequence/provenance, not future dates or publication ids.

Its three School positions can be promoted through the exact `sendMessage` binding added by PR #498. The accepted-video reservoir is additional ready media for later reviewed editorial promotion; this runbook does not silently rewrite the already-frozen 12-item marathon into a different sequence.

## Video evidence provenance

PR #491 completed the provider-free video artifact lane. The durable proof on `agent/milovi-video-accepted-73c578eff825` records `status=accepted_16_of_16`, `accepted_output_count=16`, `declared_video_count=16`, `provider_access_performed=false` and `provider_write_performed=false`.

Every accepted output is MP4/H.264/yuv420p with exactly one AAC 48 kHz stereo stream. The main-branch reservoir index makes those exact accepted identities discoverable without reviving the old conversion/persistence workflow as a publisher.

Nothing in this runbook authorizes Telegram mutation.
