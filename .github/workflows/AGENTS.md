# GitHub Actions Telegram workflow instructions

These instructions supplement the repository-root `AGENTS.md` for workflow files in `.github/workflows/`.

## Shared Telegram bot is intentional

The repository intentionally allows one Telegram bot (`@preaching_mp3_bot`, bot id `8716602202`) to serve multiple channels, including `@lordchrist` and `@deep_info_life` (`СВОДКА`).

Do not flag the same underlying Telegram bot secret being mapped into multiple channel workflows as cross-channel contamination by itself. The bot credential authenticates the shared bot; the destination is selected and protected separately by the exact channel profile, numeric `chat_id`, target binding, release digest, state branch, concurrency group, publication prefix and preflight proof.

A legacy GitHub secret name such as `LORDCHRIST_TELEGRAM_BOT_TOKEN` may contain this shared bot credential and may be mapped to the profile-specific environment variable expected by the runtime. Treat the legacy name as cosmetic migration debt unless an explicit security migration says otherwise.

Never compensate for a shared credential by weakening target checks. Every provider-capable workflow must still prove the exact bot and exact channel, persist intent before mutation, preserve ambiguous outcomes, and avoid blind retries.

Do not create a second bot, duplicate/rotate the shared token, or split credentials per channel merely for naming symmetry without an explicit reviewed migration.

## Svodka post-rollout workflow invariants

The August `@deep_info_life` rollout is historical completed work. Its exact release/runtime/evidence remain where needed for reproducibility; that history is **not** standing authorization for another Telegram mutation.

- `Svodka quality` runs on every push to `main`; do not reintroduce a `paths` filter. GitHub path filtering evaluates only a bounded diff and can skip a relevant change in a large audit wave.
- `.github/workflows/svodka-scheduled-publisher.yml` is **manual recovery only**. It must remain `workflow_dispatch`-only, main-only and protected by the exact confirmation `SVODKA-LEGACY-RECOVERY:@deep_info_life`. Do **not** restore a `schedule:` or `push:` trigger merely because the filename says `scheduled-publisher`.
- The expired August queue is not an automatic catch-up queue. A stale or expired item must never become publishable just because an operator runs a recovery workflow later.
- `.github/workflows/svodka-canary.yml` is an exact manual historical-release canary surface. It must remain `workflow_dispatch`-only and retain exact release digest/publication-id confirmation, strict-next freshness, current-main quality proof, exact target proof, durable intent-before-send and zero blind retry.
- `.github/workflows/svodka-native-rich-message-canary.yml` and `.github/workflows/svodka-custom-emoji-capability-canary.yml` are historical one-attempt capability surfaces. Their durable state records permanently block every second attempt. Do not weaken, delete or reinterpret that no-replay boundary merely to simplify workflow inventory.
- `.github/workflows/svodka-skip-expired.yml` is provider-free/state-only recovery. It may terminalize expired historical ledger entries but must not call Telegram or create provider authority.
- Provider-free reconciliation may produce `confirmed_absent` only from exact evidence for the original run/attempt. A `may_exist` or unknown provider effect remains blocking and never becomes retry authority.
- Every provider-capable Svodka workflow that remains for historical/recovery reproducibility must stay serialized through `svodka-telegram-publisher` with `cancel-in-progress: false`, prove exact current-main quality and exact target identity, and persist durable intent before any mutation.
- Never turn an exact-SHA quality failure, stale-window failure, consumed one-attempt canary, or `may_exist` outcome into an availability retry path.
- Completed rich successor/reconciliation one-shot workflows that were retired from `main` must not be restored as parallel writers. Reusable source modules and durable evidence are not executable provider authority.

The production dependency surface includes the shared `telegram_models.py` / `telegram_transport.py` modules and `requirements/telegram-publisher.txt`; Svodka quality must continue to test those dependencies rather than only files whose names contain `svodka` or `multichannel`.

## Milovi permanent feed invariants

Milovi Telegram Issue #353 has one permanent provider-mutation path: `.github/workflows/milovi-telegram-feed-publisher.yml`.

- The publisher remains `workflow_dispatch`-only. Do not add `schedule:` or `cron:` triggers. A reviewed schedule value in an immutable release is a freshness constraint, not standing autonomous execution authority.
- All Milovi provider mutations share `state/milovi-cake-telegram` and concurrency group `milovi-cake-telegram-publisher` with `cancel-in-progress: false`.
- The exact feed identity is `milovi-feed-YYYYMMDD-NNN`. Runtime release, exact media-or-message binding, durable ledger, execution authority and channel-wide index must all bind that exact identity and exact payload digest.
- `sendPhoto` uses the exact media/source/transport binding and deterministic materialization path. `sendMessage` uses an exact candidate/text SHA-256 binding and must not be forced through a fake media artifact. The two binding kinds are mutually exclusive for one publication.
- Release/content authorization and execution/provider authorization are separate gates. Old bootstrap or canary authorization, credentials, automation, a green workflow, or a profile with technical write capability never supplies fresh execution authority.
- State initialization is explicit and provider-free. The publisher must not auto-create a missing release ledger during a `publish` operation.
- `content/telegram/milovi-cake/feed/index.json` is the channel-wide duplicate guard. It must agree with the exact immutable release ledger before another provider attempt is eligible.
- `.github/workflows/milovi-telegram-target-discovery.yml` is read-only target discovery and must never gain `send-once` or become a second writer. Its validity depends on exact project/target identity and read-only transport semantics, not on whether the bot profile is technically capable of writes.
- Historical bootstrap, one-off canary, live-canary-v2, ledger-init, per-publication controller/quality/media-proof, and `follow-on-*` readiness/media-proof workflow families are retired from executable `main`. Their JSON, frozen manifests, receipts and durable state remain evidence only; do not restore those workflows as helper/runtime surfaces.
- The canonical writer prepares and durably persists one exact intent before `send-once`, performs zero blind mutation retries, writes the exact outcome, and leaves `may_exist`/unknown effects blocking.
- `milovi-feed-20260819-001` remains provider-inert until a separate change explicitly authorizes its immutable release and a fresh exact human execution authority. This instruction file does not perform or authorize that change.

Nothing in this instruction file authorizes a new Svodka, LordChrist, or Milovi Telegram provider mutation.
