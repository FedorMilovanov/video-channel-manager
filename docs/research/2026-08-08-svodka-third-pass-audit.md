# СВОДКА — third-pass runtime + scheduler audit — 2026-08-08

This overlay records defects and hardening discovered after the earlier 70-source technical/factual ledger and the second-pass audit. It is intentionally implementation-focused: provider-visible fidelity, publication timing, recovery and scheduler safety.

## Current safety state

- `@deep_info_life` is still not live-enabled.
- `content/telegram/channels/svodka.json` remains `provider_writes_authorized=false`.
- `content/telegram/svodka/approved-release-2026-08.json` is still intentionally absent.
- `state/svodka-telegram` exists but its publication ledger remains absent until an exact authorized release is committed.
- No Telegram provider mutation was performed by this audit.
- The scheduled workflow is now installed, but the current missing approved release and disabled profile gate make it provider-free/inactive.
- One shared bot (`@preaching_mp3_bot`, bot id `8716602202`) intentionally serves multiple channels. Shared credentials are not a channel selector.

## Additional defects found and closed

| # | Finding | Severity | Resolution |
|---:|---|---|---|
| 11 | `sendMessage` verified only returned plain text, not whether bold/italic/source links survived Telegram HTML parsing. A changed source URL could therefore be accepted as verified. | P1 provider fidelity | Added generic Telegram HTML entity parser using Telegram UTF-16 offsets. Message payload schema v2 freezes expected `bold`, `italic`, `text_link` entities and exact link URLs into the provider digest. Returned Message entities are checked; unrelated auto-generated hashtag entities are ignored. Drift is `may_exist`. |
| 12 | Link previews are deliberately disabled in the request but were not checked in returned Message semantics. | P1 provider fidelity | Returned `link_preview_options.is_disabled` must be `true`; otherwise postflight becomes `may_exist`. |
| 13 | Native quiz rendering exposed sources but lost much of the canonical Svodka visual/editorial identity. | P1 editorial quality | Poll description now preserves Svodka header, title, post-vote prompt, visible sources, tagline and the full canonical topical hashtag line. It never reveals the correct answer before voting. |
| 14 | Manual canary could publish a real pilot item before its scheduled slot because manual mode originally bypassed the due-time check. | blocking activation | Added a deterministic immutable publication window shared by manual and scheduled dispatch. No provider intent exists before the window opens or after it expires. |
| 15 | A missed morning post could block strict ordering forever, tempting a late backfill or manual ledger editing. | blocking scheduler recovery | Added `skip_expired_pending`: only consecutive expired pending items may move to `skipped/impossible`, with no provider effect. Added state-only CLI and manual recovery workflow. |
| 16 | A scheduled publisher added only after the canary would create a last-minute deployment change exactly when production activation should be frozen. | operational risk | Installed scheduler in advance, but made it fail-closed. Missing approved release, disabled profile gate or missing ledger produces a provider-free no-op. Generic scheduled prepare still requires a verified manual canary. |
| 17 | A manual `workflow_dispatch` of the scheduler could select a non-`main` ref and then write production state. | P1 branch integrity | Scheduler job is restricted to `github.ref == 'refs/heads/main'`; scheduled events already use the default branch. |
| 18 | Authorized release provenance could be syntactically present but manually forged. | P1 release provenance | Generic release now reconstructs its write-disabled candidate representation and requires `reviewed_candidate_sha256 == candidate_digest()`. A forged reviewed-candidate digest is rejected by the model itself. |
| 19 | Safe pre-provider local failures initially became terminal `failed` even though provider absence was proven. | recovery quality | Local/pre-provider `ValueError` outcomes are `not_dispatched`, `retryable=true`; applying the exact outcome clears intent and restores `pending`. This does not apply to `may_exist`. |
| 20 | The initial quality gate had no regression for UTF-16 formatting/source-link verification. | CI coverage | Added focused HTML entity tests and wired the helper into Svodka quality's Ruff/format/mypy/pytest scope. |

## Deterministic publication-window rule

The runtime uses the immutable release itself rather than a magic grace period:

- window start = exact item `scheduled_at`;
- window end = next item's `scheduled_at`;
- final item end = next local midnight in the release timezone.

For the first pilot item this is exactly `2026-08-09T10:30:00+03:00` through, but not including, `2026-08-09T19:30:00+03:00`.

Consequences:

- an early manual canary cannot create an intent;
- a stale morning item cannot be sent at the evening slot;
- a delayed cron within the item's own window is still eligible;
- an expired pending item may only become `skipped/impossible`;
- strict-next ordering remains deterministic after stale recovery.

## Fail-closed scheduler contract

Workflow: `.github/workflows/svodka-scheduled-publisher.yml`.

Pilot cron in UTC:

- `30 7 9-15 8 *` = 10:30 Europe/Moscow;
- `30 16 9-15 8 *` = 19:30 Europe/Moscow.

The workflow is safe to exist before activation because it requires all of the following before a provider mutation can occur:

1. execution on `main`;
2. committed approved release exists;
3. release is authorized and has reviewed-candidate provenance;
4. release matches current profile and exact pinned target binding;
5. profile write gate is true;
6. current time is inside the immutable pilot publication span;
7. exact ledger exists and validates against the release;
8. expired pending windows are reconciled state-only before provider access;
9. fresh read-only exact bot/channel preflight succeeds;
10. generic scheduled prepare proves run attempt 1, strict-next eligibility, current publication window, daily limit and a verified manual canary for the same bot/channel;
11. exact intent is committed to `state/svodka-telegram` and remote-verified before `send-once`;
12. exactly one provider payload is attempted;
13. exact provider outcome is durably persisted afterward;
14. `may_exist` blocks blind retry.

Current repo state fails gates 2 and 5 by design, so the installed scheduler is inactive and cannot even perform the Telegram preflight.

## Provider-visible message fidelity

For normal Svodka `sendMessage`, the immutable payload now commits to:

- exact HTML source text;
- exact plain text after Telegram-compatible HTML parsing;
- exact `bold`, `italic` and `text_link` entities using UTF-16 offsets;
- exact source-link destinations;
- disabled link previews.

Postflight verifies those returned Message semantics plus exact chat/message identity. A successful HTTP response with changed formatting, source link or preview behavior is not accepted as verified.

For polls/quizzes, schema v4 commits to and verifies observable current Bot API semantics: anonymity, multiple answers, revoting, members-only, description, quiz correct ids and explanation. Input-only fields that Telegram does not return are not falsely claimed as postflight-verifiable.

## Sources re-used for this pass

The primary-source set remains the exact 37+ references listed in the second-pass ledger, including Telegram Bot API/current changelog, GitHub Actions security/concurrency documentation and the primary/official scientific sources for all 14 pilot posts. This pass additionally relies on the current Telegram Message entity and link-preview contracts from the same canonical Bot API reference.

## Remaining proof gates, not known implementation defects

The following remain intentionally unproven and must not be described as completed:

1. an actual green `Svodka quality` GitHub Actions run on the exact current `main` SHA;
2. a fresh read-only Telegram preflight against the exact shared bot and `@deep_info_life`;
3. operator review of the exact canonical 14-item candidate and its digest;
4. committed exact authorized release generated from that candidate;
5. profile write gate enabled;
6. exact initialized ledger;
7. one manual canary inside the strict-next publication window;
8. durable canary receipt with `published + provider_effect=verified`.

After item 8, the scheduler does not need a new deployment. Its existing fail-closed gates become satisfiable automatically, while all timing/identity/state checks remain in force.
