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
- `content/telegram/milovi-cake/releases/<id>-media.json` — exact source/transport binding for `sendPhoto` publications;
- `content/telegram/milovi-cake/releases/<id>-message.json` — exact candidate/text binding for `sendMessage` publications;
- `content/telegram/milovi-cake/feed/<id>.json` on the durable state branch — exact release ledger;
- `content/telegram/milovi-cake/feed/index.json` on the durable state branch — channel-wide duplicate guard.

A photo publication must not carry a message binding. A text publication must not carry a media binding. The permanent validator fails closed on an ambiguous dual binding.

The frozen editorial/source candidate may remain a separate provenance object. It never becomes provider authority by itself.

## Supported permanent-feed payloads

The permanent writer supports two exact payload kinds through the same generic one-attempt runtime:

- `sendPhoto` — candidate caption plus exact reviewed source/transport bytes; the workflow materializes the deterministic JPEG before `send-once`;
- `sendMessage` — exact candidate text plus SHA-256 binding; no media file, Pillow install or media download is part of this path.

Both payload kinds pass the same current-main gate, release/content authorization, separate execution authorization, state initialization, duplicate guard, freshness check, exact target preflight, durable intent-before-send, one-attempt mutation and outcome reconciliation. Supporting text does **not** create a second writer or standing authority.

Poll/video payloads are not made publishable by this contract. The separate accepted-video artifact lane remains artifact readiness only until a separately reviewed permanent-feed video transport is implemented.

## Authority split

Release/content review and provider execution are deliberately separate.

An authorized runtime release must satisfy the generic immutable release contract, exact target binding and reviewed-candidate digest. A separate execution-authority object must then bind that exact authorized release digest and provider payload digest and explicitly carry `execution_authorized=true` plus `provider_mutation_allowed=true` with fresh human provenance.

Historical bootstrap authorization, successful canary evidence, credentials, a writable channel profile, CI success, workflow dispatch, or automation never inherit into this gate.

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
11. exact reviewed photo materialization when the payload is `sendPhoto`; `sendMessage` has no media materialization step;
12. one `telegram_multichannel_cli send-once` call;
13. exact outcome applied to the ledger and channel-wide index.

Mutation transport retries remain zero. A missing/ambiguous outcome is not permission to replay. `may_exist` or otherwise unknown provider effect remains blocking pending exact read-only reconciliation.

## Stale predecessor — do not catch up

`milovi-feed-20260819-001` remains immutable provider-inert history. Its frozen scheduled time is `2026-08-19T10:30:00+03:00`, which has passed. The timestamp is part of that publication identity; staleness must fail closed.

Do **not** widen freshness, edit the old timestamp, transfer authorization, initialize it later as a catch-up publication, or reinterpret it as a 20-August send. No provider mutation was performed for that identity.

## Current exact candidate

`milovi-feed-20260820-001` is the next provider-inert publication candidate:

- scheduled time: `2026-08-20T10:30:00+03:00`;
- editorial source: position 2 of `first-screen-continuation-copy-2026-08.json`;
- operation: `sendPhoto`;
- exact media: `p16` / `img/gallery/gallery-16-hd.webp`;
- exact source SHA-256: `sha256:51321ee2ef2c3ee1b91a9e449ade9d8886747f3cf3aae85f0cfe8e1bd1dcd6e7`;
- deterministic JPEG: `506080` bytes, SHA-256 `sha256:19ba49ed001ea0c7c79ad9f475be0ad4c4c41b5790ee195e363df7981cfb6b9e`;
- exact caption SHA-256: `sha256:40708552f2899f3c236b5ff63370d556e97701d7495ffe3b753229d69de1f587`;
- runtime release present: yes;
- `release_authorized=false`;
- `execution_authorized=false`;
- `provider_mutation_allowed=false`;
- permanent feed ledger initialized: no;
- durable execution intent: no;
- Telegram mutation by preparation: no.

The bundle is readiness only. It may be merged provider-free during quiet hours, but a future provider operation still requires a fresh exact-current-main release review/execution authorization, daylight-window check, state initialization and the one-attempt publisher path.

## Marathon editorial source

`content/telegram/milovi-cake/marathon-wave-2026-08.json` is the canonical provider-inert 12-item Cake + School sequence consolidated by PR #497. Its School positions use `sendMessage`; the permanent message binding described above is the supported path for promoting one such item into a future exact `milovi-feed-*` publication. The marathon file itself does not freeze future dates, create release IDs or supply execution authority.

## Video lane

PR #491 merged the hardened provider-free video artifact lane on `main` as `0c643aac244406acc1e17bef6885279b6e22e0d7` after exact-head CI, source-probe, feed-quality, Pillow and 16/16 conversion proof all passed.

The post-merge `main` persistence run then completed the durable proof on content-addressed branch `agent/milovi-video-accepted-73c578eff825`. That branch is exactly one artifact commit ahead of `main` and adds only 16 MP4 outputs plus `content/telegram/milovi-cake/video-conversion-evidence-2026-08.json`.

The durable evidence records `status=accepted_16_of_16`, `accepted_output_count=16`, `declared_video_count=16`, `provider_access_performed=false`, `provider_write_performed=false`, exact source commit `c4eb3bf6ed6fd5c3c9e4c2d857e53d8bae093370`, and evidence digest `sha256:73c578eff82563300c463361bd3998caeba8a083ce0de4ed29cc271617dfd6ae`. Every accepted output is MP4/H.264/yuv420p with exactly one AAC 48 kHz stereo stream derived from the reviewed single Opus 48 kHz stereo source stream.

The native-video readiness lane is therefore complete. This evidence grants no Telegram execution authority and does not authorize `sendVideo` or any other provider mutation.

Nothing in this runbook authorizes Telegram mutation.
