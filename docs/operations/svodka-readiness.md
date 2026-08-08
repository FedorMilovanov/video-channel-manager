# Svodka Telegram production readiness

Last reviewed: 2026-08-08

## Current state

`@deep_info_life` is **not live-enabled** yet.

- channel profile: `content/telegram/channels/svodka.json`
- exact target binding: `content/telegram/channels/svodka-target-binding.json`
- canonical pilot queue: `content/telegram/svodka/draft-14-posts-2026-08.json`
- canonical release id: `svodka-pilot-2026-08`
- canonical review candidate artifact: `svodka-review-candidate`
- state branch: `state/svodka-telegram`
- approved release path (must not exist before review): `content/telegram/svodka/approved-release-2026-08.json`
- current profile gate: `provider_writes_authorized=false`
- scheduled publisher: intentionally absent until a verified manual canary exists

The current Telegram architecture intentionally uses the same posting bot for multiple channels: `@preaching_mp3_bot`, bot id `8716602202`. A shared bot token is expected. The token authenticates the bot; the exact profile, numeric chat id, target binding, release, state branch and concurrency group select and isolate the destination channel.

## Stable workflow split

1. `Svodka quality` — read-only CI. No Telegram secret, no repo mutation, no provider mutation. It validates the canonical queue, renders all 14 provider payloads and uploads the target-bound write-disabled `svodka-review-candidate` using canonical release id `svodka-pilot-2026-08`.
2. `Svodka Telegram preview and preflight` — manual preview / fresh read-only Telegram identity proof. It reproduces the same canonical review candidate identity before optional provider reads.
3. Release authorization — local/repository promotion only. `authorize-svodka-release` requires the exact review candidate, the current pinned binding, reviewer identity and timezone-aware review timestamp. The resulting release records `reviewed_candidate_sha256`.
4. `Svodka initialize publication ledger` — manual state-only operation. It requires an exact committed authorized release digest and creates the ledger once on `state/svodka-telegram`. It has no Telegram secret and cannot send.
5. `Svodka exact manual canary` — manual one-publication provider mutation. It is fail-closed unless the profile is write-enabled, the committed release is authorized, the exact release digest/publication/confirmation match, the ledger already exists, and a fresh Telegram preflight passes. It persists intent before `send-once` and persists the exact outcome afterward.
6. Scheduled publication — added only after the ledger contains a verified manual canary for the same bot/channel. The generic state layer also enforces this invariant.

All Svodka state/provider-mutating workflows use the same single-writer concurrency group declared by the profile: `svodka-telegram-publisher`, with cancellation disabled.

## Activation checklist

The next production activation must happen in this order:

1. `Svodka quality` green on the exact current `main` SHA. A formatting failure observed earlier was fixed, but do not infer green from the fix alone; retain the actual successful run as evidence.
2. Manual read-only preflight green against chat `-1003527567039`, shared bot `8716602202`, `@preaching_mp3_bot`.
3. Confirm that quality and preflight produced the same canonical `svodka-review-candidate` digest for release id `svodka-pilot-2026-08`.
4. Review that exact 14-item candidate.
5. Authorize it with the current pinned binding. The approved release must contain `reviewed_candidate_sha256` equal to the exact reviewed candidate digest; never rebuild from changed draft data during deployment.
6. Commit the authorized immutable release at `content/telegram/svodka/approved-release-2026-08.json`.
7. Change only the profile write gate to `true`. The profile stable digest intentionally ignores the write-enable bit, so binding identity remains unchanged.
8. Initialize the state ledger once with `INITIALIZE:<release_digest>`.
9. Run one exact manual canary with `CANARY:<publication_id>:<release_digest>`.
10. Verify durable ledger state `published`, `provider_effect=verified`, exact message id/url, chat id, bot id and manual dispatch provenance.
11. Only then add/enable the 10:30 and 19:30 Europe/Moscow scheduled publisher for the approved release.

## Blocking conditions

Do not schedule or retry automatically if any of these are true:

- quality or preflight is not green;
- quality/preflight candidate digest differs;
- approved release is absent, unauthorized, has no reviewed-candidate provenance, or digest differs;
- profile remains write-disabled;
- ledger is absent or belongs to another release digest;
- first unresolved entry is `dispatching`, `unknown` or `failed`;
- provider outcome is `may_exist`;
- manual canary is not verified;
- a scheduled workflow is a rerun rather than attempt 1;
- the requested item is not the strict next item;
- daily verified limit is already consumed.

## Poll contract

Current generic poll payload schema is v4. Svodka freezes the Telegram semantics used by the release instead of depending on provider defaults: `is_anonymous`, `allows_multiple_answers`, `allows_revoting`, `members_only`, `description`, and for quizzes `correct_option_ids` plus `explanation`. Observable returned Poll semantics are verified after the provider call; a mismatch is conservatively treated as `may_exist` and is never blindly retried.

## Editorial boundary

The pilot facts were hardened directly in the canonical queue. The previous self-mutating repair workflow was removed. Source and wording changes must be committed as ordinary reviewed content changes before candidate generation. Dynamic web results are never auto-published.

Research/audit records:

- `docs/research/2026-08-08-svodka-technical-verification-ledger.md`
- `docs/research/2026-08-08-svodka-second-pass-audit.md`
