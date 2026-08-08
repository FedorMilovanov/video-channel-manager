# Telegram runtime agent instructions

These instructions supplement the repository-root `AGENTS.md` for files under `src/video_channel_manager/`.

## Shared Telegram bot invariant

The Telegram multi-channel runtime intentionally supports one shared posting bot across multiple channels. The current shared bot is `@preaching_mp3_bot` (bot id `8716602202`) and may administer/publish to both `@lordchrist` and `@deep_info_life` (`СВОДКА`).

Do **not** treat reuse of the same bot token across channel profiles as a defect by itself. A token authenticates the bot; it does not select the destination channel.

Channel isolation must instead remain fail-closed through all of these independent bindings:

- exact `TelegramChannelProfile` / `project_key` / `channel_username`;
- pinned numeric `chat_id` and target-binding digest;
- exact bot id + bot username verified in read-only preflight;
- immutable release digest and provider-payload digests;
- channel-specific publication prefix and daily limit;
- separate durable state branch and ledger;
- separate concurrency group;
- strict next-item ordering and no blind retry after an ambiguous provider effect.

A shared secret may therefore be mapped into the environment-variable name expected by a selected profile. A legacy secret name such as `LORDCHRIST_TELEGRAM_BOT_TOKEN` may still contain the shared bot credential; that naming is cosmetic migration debt, not proof that the credential must only be used with `@lordchrist`.

Do not create a second Telegram bot, rotate/duplicate the shared token, or weaken exact-target checks merely to make credentials channel-specific unless an explicit reviewed migration requires it.

Provider writes remain governed by the root repository safety rules and per-profile/release write gates.
