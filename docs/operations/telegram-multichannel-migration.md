# Telegram multi-channel migration

Last reviewed: 2026-08-08

## Goal

One Telegram transport/runtime must be able to serve multiple independently configured channels without copying provider code, sharing state, or hardcoding `@lordchrist` in the generic layer.

## Current architecture

The generic layer is config-driven through `TelegramChannelProfile` and currently has profiles for:

- `content/telegram/channels/svodka.json` → `@deep_info_life`, state `state/svodka-telegram`;
- `content/telegram/channels/lordchrist.json` → `@lordchrist`, state `state/lordchrist-telegram`.

Generic provider code does not select either channel by a module constant. The selected profile supplies project key, channel username, publication prefix, timezone, daily verified limit, state branch, concurrency group and environment-variable names for bot/target identity.

## Shared Telegram bot invariant

The current Telegram architecture intentionally uses **one shared posting bot** (`@preaching_mp3_bot`, bot id `8716602202`) to administer and publish to multiple project channels, including `@lordchrist` and `@deep_info_life` / `СВОДКА`.

This is deliberate and must not be treated by future agents as accidental cross-channel credential coupling:

- one bot credential may be shared by several channel profiles;
- a shared bot token does **not** select the destination channel;
- exact channel isolation is provided by the channel profile, pinned numeric `chat_id`, target binding, immutable release identity, per-channel state branch, per-channel concurrency group, publication prefix and daily limit;
- read-only preflight must prove both the exact shared bot identity and the exact selected channel before any mutation;
- the same bot being an administrator of more than one channel is expected;
- do not create a second Telegram bot, duplicate a token, or rename/rotate credentials merely to make them channel-specific unless an explicit migration/security decision requires it;
- a legacy secret name such as `LORDCHRIST_TELEGRAM_BOT_TOKEN` may still refer to this shared bot credential. The name is cosmetic migration debt, not evidence that the credential is restricted to `@lordchrist`.

The security boundary is therefore **shared credential, isolated targets and durable state**, not one credential per channel.

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
- one shared bot may serve multiple profiles, but each mutation must prove the exact bot **and** exact channel target;
- no token or chat id hardcoded in transport code;
- read-only preflight before provider mutation;
- immutable provider payload digest;
- durable dispatch intent persisted before `sendMessage`/`sendPoll`;
- ambiguous provider effect blocks blind retry;
- scheduled mutation requires a verified manual canary;
- a channel-specific renderer/editorial adapter may vary, but transport/state/release mechanics stay generic.

## What still counts as legacy debt

The old Lordchrist editorial models contain Lordchrist-specific literals and primary-source rules. They are no longer the template for new channels, but they have not yet been deleted because the live Lordchrist publisher depends on them. Removal happens only after a proven generic migration, not as part of the Svodka activation.
