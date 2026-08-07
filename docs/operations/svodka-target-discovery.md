# Svodka target discovery and pinning

Status: `@preaching_mp3_bot` is intentionally reused for `@deep_info_life`; Telegram provider writes remain disabled for Svodka.

## Why discovery exists

A public Telegram username is convenient for configuration, but production should ultimately bind to the immutable numeric channel ID as well. The discovery stage therefore performs **read-only** Bot API calls only:

1. `getMe` — prove the token belongs to the expected bot;
2. `getChat(@deep_info_life)` — resolve the public username to a numeric channel ID;
3. `getChat(<numeric-id>)` — round-trip the ID back to the same username/channel;
4. `getChatAdministrators(return_bots=true)` — prove the bot is an administrator;
5. require `can_post_messages=true`.

No `sendMessage`, `sendPoll`, edit, delete, or other Telegram mutation is used by discovery.

## Shared bot credential fallback

The normal Svodka preflight workflow accepts a dedicated `SVODKA_TELEGRAM_BOT_TOKEN`, `SVODKA_TELEGRAM_BOT_ID`, and `SVODKA_TELEGRAM_BOT_USERNAME`, but when those are absent it can reuse the already configured Lordchrist bot identity:

- secret fallback: `LORDCHRIST_TELEGRAM_BOT_TOKEN`;
- variable fallback: `LORDCHRIST_TELEGRAM_BOT_ID`;
- variable fallback: `LORDCHRIST_TELEGRAM_BOT_USERNAME`.

Only the bot credential is shared. Channel profile, numeric chat ID, release queue, state branch, daily quota and publication ledger remain separate.

## One-time binding

`.github/workflows/svodka-target-discover-once.yml` is a temporary read-only workflow. On success it creates `content/telegram/channels/svodka-target-binding.json`, commits the non-secret binding, and removes itself.

The binding stores:

- `project_key` and exact public `@username`;
- channel profile SHA-256;
- exact negative numeric Telegram chat ID;
- exact bot ID and username;
- proof that the bot had posting permission at discovery time;
- discovery timestamp/method;
- `provider_write_performed=false`.

`telegram_target_binding.py` validates this artifact against the selected channel profile. `telegram_binding_cli.py preflight` then re-checks the live Telegram target from the pinned ID immediately before any future provider mutation.

## Safety boundary after binding

A successful binding **does not authorize publishing**. Svodka still requires all of the following before the first canary:

- reviewed immutable release artifact;
- profile-level provider write authorization;
- release-level authorization;
- isolated `state/svodka-telegram` ledger;
- fresh pinned target preflight;
- exact manual `publication_id` confirmation;
- durable dispatch intent persisted before Telegram mutation.

Only after a verified same-bot/same-chat manual canary can scheduled production be considered.
