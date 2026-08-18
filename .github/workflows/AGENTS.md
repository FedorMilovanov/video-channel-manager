# GitHub Actions Telegram workflow instructions

These instructions supplement the repository-root `AGENTS.md` for workflow files in `.github/workflows/`.

## Shared Telegram bot is intentional

The repository intentionally allows one Telegram bot (`@preaching_mp3_bot`, bot id `8716602202`) to serve multiple channels, including `@lordchrist` and `@deep_info_life` (`СВОДКА`).

Do not flag the same underlying Telegram bot secret being mapped into multiple channel workflows as cross-channel contamination by itself. The bot credential authenticates the shared bot; the destination is selected and protected separately by the exact channel profile, numeric `chat_id`, target binding, release digest, state branch, concurrency group, publication prefix and preflight proof.

A legacy GitHub secret name such as `LORDCHRIST_TELEGRAM_BOT_TOKEN` may contain this shared bot credential and may be mapped to the profile-specific environment variable expected by the runtime. Treat the legacy name as cosmetic migration debt unless an explicit security migration says otherwise.

Never compensate for a shared credential by weakening target checks. Every provider-capable workflow must still prove the exact bot and exact channel, persist intent before mutation, preserve ambiguous outcomes, and avoid blind retries.

Do not create a second bot, duplicate/rotate the shared token, or split credentials per channel merely for naming symmetry without an explicit reviewed migration.

## Svodka post-rollout invariants

The exact August 2026 Svodka rollout is historical. Its completed rich publications and retired experiments are evidence, not standing provider-write authority.

- `content/telegram/channels/svodka.json` is write-disabled after the completed rollout. The write gate is intentionally excluded from stable channel identity, so disabling it must not change the reviewed profile digest, target binding or historical release digest.
- Do not restore the retired August manual canary, legacy publisher, ledger initializer, generic outcome-recovery writers, rich successor/finalizer, native Rich Message canary, custom-emoji capability canary, or custom-emoji harvest workflow as executable Actions surfaces merely because their source/evidence remains in the repository.
- The historical custom-emoji capability attempt remains `unknown / provider_effect=may_exist`. That ambiguity is preserved honestly and is never retry authority. No second capability-canary send is permitted from that historical identity.
- The verified native Rich Message canary and verified rich successor messages are terminal historical provider evidence; they are not replayable release authority.
- While the legacy `svodka-pilot-2026-08` publication ledger still contains expired `pending / provider_effect=impossible` entries, `svodka-skip-expired.yml` may remain as the sole Svodka state-writer. It is provider-free: no Telegram credential, preflight or send call is permitted on that path.
- `svodka-skip-expired.yml` must require the exact historical release digest plus explicit `SKIP-EXPIRED:<digest>` confirmation and exact-current-main Svodka quality proofs before committing only the stale-window state transition.
- Svodka quality, approved-release quality, rollout-candidate checks and Telegram preflight are provider-free/read-only surfaces. They must not become a hidden provider mutation path.
- Any later Svodka provider publication requires a new exact owning issue, fresh reviewed release/execution authority and current target proof. Do not reactivate the August workflows or infer authority from the old profile, approval, state branch, bot credential, message 28/29 success or historical issue #235.
- Never weaken an exact-SHA quality failure, stale-window failure, or `may_exist` outcome into a retry path for availability.

The production dependency surface includes the shared `telegram_models.py` / `telegram_transport.py` modules and `requirements/telegram-publisher.txt`; Svodka quality must continue to test those dependencies rather than only files whose names contain `svodka` or `multichannel`.
