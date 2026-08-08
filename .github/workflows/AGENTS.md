# GitHub Actions Telegram workflow instructions

These instructions supplement the repository-root `AGENTS.md` for workflow files in `.github/workflows/`.

## Shared Telegram bot is intentional

The repository intentionally allows one Telegram bot (`@preaching_mp3_bot`, bot id `8716602202`) to serve multiple channels, including `@lordchrist` and `@deep_info_life` (`СВОДКА`).

Do not flag the same underlying Telegram bot secret being mapped into multiple channel workflows as cross-channel contamination by itself. The bot credential authenticates the shared bot; the destination is selected and protected separately by the exact channel profile, numeric `chat_id`, target binding, release digest, state branch, concurrency group, publication prefix and preflight proof.

A legacy GitHub secret name such as `LORDCHRIST_TELEGRAM_BOT_TOKEN` may contain this shared bot credential and may be mapped to the profile-specific environment variable expected by the runtime. Treat the legacy name as cosmetic migration debt unless an explicit security migration says otherwise.

Never compensate for a shared credential by weakening target checks. Every provider-capable workflow must still prove the exact bot and exact channel, persist intent before mutation, preserve ambiguous outcomes, and avoid blind retries.

Do not create a second bot, duplicate/rotate the shared token, or split credentials per channel merely for naming symmetry without an explicit reviewed migration.
