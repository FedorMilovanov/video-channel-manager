# Milovi Telegram permanent feed control plane

Updated: 2026-08-19
Owning workstream: Issue #353
Provider target: `@MiloviCake`

This runbook defines the permanent Milovi Telegram feed path. It is an implementation and safety contract; it is **not** provider execution authority.

## One writer

`.github/workflows/milovi-telegram-feed-publisher.yml` is the only supported Milovi Telegram provider-mutation workflow.

It is `workflow_dispatch`-only, serialized by `milovi-cake-telegram-publisher`, and uses durable state branch `state/milovi-cake-telegram`. Historical bootstrap/canary/ledger-init workflows and one-off per-publication controllers are retired and must not be restored as parallel provider paths.

Read-only target discovery remains separate and may never call the mutation runtime.

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

## Current exact candidate

`milovi-feed-20260819-001` is currently provider-inert:

- content candidate frozen: yes;
- exact p03 transport binding: yes;
- exact target binding: yes;
- runtime release present: yes;
- `release_authorized=false`;
- `execution_authorized=false`;
- `provider_mutation_allowed=false`;
- permanent feed ledger initialized: no;
- Telegram mutation by this consolidation: no.

Its old scheduled time is part of the frozen candidate identity and may be stale by the time a future operator considers execution. Staleness must fail closed; do not widen freshness or reinterpret the old timestamp as catch-up authority.

## Video lane

Native video readiness remains separate from the permanent photo/feed writer architecture. Current recorded status is `0 / 16` accepted Telegram-ready MP4 outputs. Materialize and verify H.264/Telegram-ready derivatives under the media contract before treating that lane as complete.

Nothing in this runbook authorizes Telegram mutation.
