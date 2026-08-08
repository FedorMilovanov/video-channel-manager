# GitHub Actions Telegram workflow instructions

These instructions supplement the repository-root `AGENTS.md` for workflow files in `.github/workflows/`.

## Shared Telegram bot is intentional

The repository intentionally allows one Telegram bot (`@preaching_mp3_bot`, bot id `8716602202`) to serve multiple channels, including `@lordchrist` and `@deep_info_life` (`СВОДКА`).

Do not flag the same underlying Telegram bot secret being mapped into multiple channel workflows as cross-channel contamination by itself. The bot credential authenticates the shared bot; the destination is selected and protected separately by the exact channel profile, numeric `chat_id`, target binding, release digest, state branch, concurrency group, publication prefix and preflight proof.

A legacy GitHub secret name such as `LORDCHRIST_TELEGRAM_BOT_TOKEN` may contain this shared bot credential and may be mapped to the profile-specific environment variable expected by the runtime. Treat the legacy name as cosmetic migration debt unless an explicit security migration says otherwise.

Never compensate for a shared credential by weakening target checks. Every provider-capable workflow must still prove the exact bot and exact channel, persist intent before mutation, preserve ambiguous outcomes, and avoid blind retries.

Do not create a second bot, duplicate/rotate the shared token, or split credentials per channel merely for naming symmetry without an explicit reviewed migration.

## Svodka provider-write invariants

For `@deep_info_life`, provider-capable workflows must remain stricter than read-only or state-only workflows:

- `Svodka quality` runs on every push to `main`; do not reintroduce a `paths` filter. GitHub path filtering evaluates only a bounded diff and can skip a relevant change in a large audit wave.
- Canary and scheduled publication require a successful completed `Svodka quality` run for their exact current `GITHUB_SHA` before any Telegram preflight, durable dispatch intent, or provider mutation.
- A visible `workflow_dispatch` trigger on the scheduled publisher is diagnostic only. The publishing job must require `github.event_name == 'schedule'`; a manual Run workflow invocation must never become a scheduled provider mutation.
- All Svodka state/provider writers share `svodka-telegram-publisher` with `cancel-in-progress: false`.
- The automatic publication freshness limit is 120 minutes after the immutable `scheduled_at`. A stale item may not be backfilled automatically just because the broader generic state window is still open.
- The manual canary must be both the strict next ledger item and inside the same 120-minute freshness window before any Telegram provider read.
- The scheduled publisher checks strict-next freshness before Telegram preflight. If the item is too early, too stale, blocked, or absent, provider access is skipped.
- Reconciliation of an abandoned intent is provider-free and may produce `confirmed_absent` only when the original GitHub run is completed, its workflow/event match the expected canary or schedule contract, the durable intent step succeeded, and the provider send step is proven `skipped` for the exact run attempt and head SHA.
- Never weaken an exact-SHA quality failure, stale-window failure, or `may_exist` outcome into a retry path for availability.

The production dependency surface includes the shared `telegram_models.py` / `telegram_transport.py` modules and `requirements/telegram-publisher.txt`; Svodka quality must continue to test those dependencies rather than only files whose names contain `svodka` or `multichannel`.
