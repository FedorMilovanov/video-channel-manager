# Telegram multi-channel migration

Last reviewed: 2026-08-08

## Goal

One Telegram transport/runtime must be able to serve multiple independently configured channels without copying provider code, sharing state, or hardcoding `@lordchrist` in the generic layer.

## Current architecture

The generic layer is config-driven through `TelegramChannelProfile` and currently has profiles for:

- `content/telegram/channels/svodka.json` → `@deep_info_life`, state `state/svodka-telegram`;
- `content/telegram/channels/lordchrist.json` → `@lordchrist`, state `state/lordchrist-telegram`.

Generic provider code does not select either channel by a module constant. The selected profile supplies project key, channel username, publication prefix, timezone, daily verified limit, state branch, concurrency group and environment-variable names for bot/target identity.

## Compatibility boundary

The existing production `@lordchrist` publisher predates the generic layer and still uses its legacy editorial/runtime adapter (`telegram_models.py`, `telegram_cli.py`, `telegram_presentation.py`). It remains untouched for now because it already has a hardened live state/ledger and changing the active publisher before the generic path has a verified canary would create unnecessary migration risk.

The new `lordchrist.json` profile is therefore a **migration contract**, not a second enabled publisher. Its write gate is false. No generic workflow is allowed to publish to `@lordchrist` yet.

This staged boundary is intentional:

1. prove generic transport + durable state on Svodka;
2. verify one Svodka canary and scheduled run;
3. compare generic and legacy Lordchrist rendering/identity/state contracts offline;
4. migrate Lordchrist only with a dedicated exact release/state migration plan;
5. never run legacy and generic mutating publishers for `@lordchrist` concurrently.

## Invariants for every channel

- one profile = one exact channel username;
- one state branch per channel;
- one concurrency group per mutating publisher;
- one exact target binding per profile digest;
- no token or chat id hardcoded in transport code;
- read-only preflight before provider mutation;
- immutable provider payload digest;
- durable dispatch intent persisted before `sendMessage`/`sendPoll`;
- ambiguous provider effect blocks blind retry;
- scheduled mutation requires a verified manual canary;
- a channel-specific renderer/editorial adapter may vary, but transport/state/release mechanics stay generic.

## What still counts as legacy debt

The old Lordchrist editorial models contain Lordchrist-specific literals and primary-source rules. They are no longer the template for new channels, but they have not yet been deleted because the live Lordchrist publisher depends on them. Removal happens only after a proven generic migration, not as part of the Svodka activation.
