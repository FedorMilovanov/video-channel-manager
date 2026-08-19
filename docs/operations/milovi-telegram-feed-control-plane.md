# Milovi Telegram permanent feed control plane

Updated: 2026-08-19
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
- `content/telegram/milovi-cake/releases/<id>-media.json` — exact source/transport binding for media publications;
- `content/telegram/milovi-cake/feed/<id>.json` on the durable state branch — exact release ledger;
- `content/telegram/milovi-cake/feed/index.json` on the durable state branch — channel-wide duplicate guard.

The frozen editorial/source candidate may remain a separate provenance object. It never becomes provider authority by itself.

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
11. exact reviewed media materialization when applicable;
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

## Video lane

PR #487 merged the permanent provider-free video artifact builder on `main` at `87c41dd6912ba4c83ed25b631df673daa7844c09`. The builder is designed to materialize and prove all 16 H.264/MP4 derivatives on a content-addressed review branch without Telegram access.

Do not treat the builder merge itself as 16/16 completion. The video lane becomes complete only after a real main-push run produces and preserves exact accepted 16/16 conversion evidence. Until that evidence is observed, the previously recorded accepted-output state remains unconfirmed and must not be upgraded by assumption.

Nothing in this runbook authorizes Telegram mutation.
