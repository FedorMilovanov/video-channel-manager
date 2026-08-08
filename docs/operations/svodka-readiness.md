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
- scheduled publisher: installed but fail-closed/inactive until the exact approved release, write gate, ledger and verified manual canary all exist

The current Telegram architecture intentionally uses the same posting bot for multiple channels: `@preaching_mp3_bot`, bot id `8716602202`. A shared bot token is expected. The token authenticates the bot; the exact profile, numeric chat id, target binding, release, state branch and concurrency group select and isolate the destination channel.

The exact current `Svodka quality` result is not inferred from source fixes. Production writers independently require an actual completed successful quality run for their own exact current `GITHUB_SHA` before provider access.

## Stable workflow split

1. `Svodka quality` — read-only CI. It runs on every push to `main` rather than using path filtering, because large audit diffs can exceed GitHub's path-filter evaluation boundary. It installs the development project and then the exact production Telegram dependency lock, checks shared Telegram runtime dependencies, validates the canonical queue, renders all 14 provider payloads and uploads the target-bound write-disabled `svodka-review-candidate` using canonical release id `svodka-pilot-2026-08`. It has no Telegram secret, repo mutation or provider mutation.
2. `Svodka Telegram preview and preflight` — manual preview / fresh read-only Telegram identity proof. It reproduces the same canonical review candidate identity before optional provider reads.
3. Release authorization — local/repository promotion only. `authorize-svodka-release` requires the exact review candidate, exact `--expected-candidate-sha256` value copied from the reviewed candidate, the current selected profile and pinned target binding, reviewer identity and timezone-aware review timestamp. The shared generic review helper independently re-proves profile/binding identity and the resulting release records and self-validates `reviewed_candidate_sha256`.
4. `Svodka initialize publication ledger` — manual state-only operation. It requires an exact committed authorized release digest and creates the ledger once on `state/svodka-telegram`. It has no Telegram secret and cannot send. It re-proves exact-current-main `Svodka quality` immediately before the durable state commit/push.
5. `Svodka skip expired publication windows` — manual state-only recovery. It may mark only already expired consecutive pending items as `skipped/impossible`; it has no Telegram secret and cannot send.
6. `Svodka exact manual canary` — manual one-publication provider mutation. Before any Telegram read it requires a completed successful `Svodka quality` for its exact current SHA, an authorized exact release, enabled profile, matching initialized ledger, an exact confirmation, the requested publication to be the strict next ledger item, and that item to be no more than 120 minutes late. Only then does it perform fresh read-only preflight, persist intent, and allow one `send-once`.
7. `Svodka scheduled publisher` — primary runs are installed for `10:30` and `19:30` Europe/Moscow on 9–15 August, with bounded catch-up runs at `11:17` and `20:17`. All four schedule events use the same single-writer runtime; catch-up is not a second sender. The mutating job runs only for the `schedule` event on `main`; pressing Run workflow manually cannot publish. It requires the same exact-SHA quality proof, release/profile/ledger gates and verified manual canary. It automatically refuses Telegram access when the strict-next item is early or more than 120 minutes late.
8. `Svodka reconcile skipped provider send` — manual provider-free recovery for an abandoned durable intent. It requires a completed original GitHub run, the exact run attempt/head SHA, the correct workflow/event pairing, a successful persisted-intent step and a provider send step proven `skipped`. Only then may it record `confirmed_absent` and return the item to a safe retryable pending state.

All Svodka state/provider-mutating workflows use the same single-writer concurrency group declared by the profile: `svodka-telegram-publisher`, with cancellation disabled.

## Publication timing contract

The generic immutable release still defines a structural state window:

- start = exact `scheduled_at`;
- structural end = next item's `scheduled_at`;
- final item structural end = next local midnight.

Svodka production adds a stricter freshness gate on top of that generic state model:

- automatic/manual provider eligibility begins at exact `scheduled_at`;
- provider eligibility ends at the earlier of the structural end or `scheduled_at + 120 minutes`;
- canary must be the strict next item before Telegram preflight;
- scheduled execution checks strict-next freshness before Telegram preflight;
- primary cron runs at the exact 10:30/19:30 Moscow slots and a same-runtime catch-up rechecks eligibility 47 minutes later;
- if the primary run already verified the slot, the catch-up sees the next future item as not due and remains provider-ineligible;
- if a prior run persisted an unresolved/ambiguous dispatch intent, the catch-up cannot bypass the blocking state or blindly retry it;
- an over-late item is not backfilled automatically merely because its structural state window has not reached the next slot yet;
- at the next structural window boundary, stale pending items can become `skipped/impossible` through state-only recovery.

This bounded lag tolerates ordinary GitHub Actions scheduling delay or a primary pre-intent failure without allowing a morning Svodka post to appear near the evening slot.

## Exact provider postflight

`sendMessage` verification freezes and checks the provider-visible result, not only HTTP success:

- exact returned channel identity;
- exact plain text;
- exact `bold`, `italic` and `text_link` entities including Telegram UTF-16 offsets and source URLs;
- link previews remain explicitly disabled;
- exact message id and canonical channel message URL.

Generic poll payload schema v4 freezes `is_anonymous`, `allows_multiple_answers`, `allows_revoting`, `members_only`, `description`, and for quizzes `correct_option_ids` plus `explanation`. Observable returned Poll semantics are checked after the provider call. Any provider-visible drift after a mutation is conservatively `may_exist` and never blindly retried.

## Activation checklist

The next production activation must happen in this order:

1. Obtain an actual completed successful `Svodka quality` run on the exact intended current `main` SHA. The original formatting defect being fixed is not equivalent to green CI.
2. Run manual read-only preflight against chat `-1003527567039`, shared bot `8716602202`, `@preaching_mp3_bot`.
3. Confirm that quality and preflight produced the same canonical `svodka-review-candidate` digest for release id `svodka-pilot-2026-08`.
4. Review that exact 14-item candidate.
5. Authorize that exact candidate with the current profile and pinned binding and pass its exact reviewed digest via `--expected-candidate-sha256`. The approved release must contain `reviewed_candidate_sha256` equal to its exact reconstructed candidate digest; never rebuild from changed draft data during deployment.
6. Commit the authorized immutable release at `content/telegram/svodka/approved-release-2026-08.json`.
7. Change only the profile write gate to `true`. The profile stable digest intentionally ignores the write-enable bit, so binding identity remains unchanged.
8. Obtain a successful `Svodka quality` run for the new exact activation SHA. Canary and scheduler will independently enforce this through the GitHub Actions REST API.
9. Initialize the state ledger once with `INITIALIZE:<release_digest>`.
10. If an earlier structural publication window has expired before canary, record it as `skipped/impossible`; never send it late.
11. Run one exact manual canary for the strict next item between its scheduled time and its 120-minute freshness deadline using `CANARY:<publication_id>:<release_digest>`.
12. Verify durable ledger state `published`, `provider_effect=verified`, exact message id/url, chat id, bot id and manual dispatch provenance.
13. No separate scheduler deployment is needed. The installed primary/catch-up cron events become eligible only when all exact-SHA quality, release, profile, ledger, canary, freshness and target-preflight gates succeed.

## Blocking conditions

Do not schedule, dispatch or blindly retry if any of these are true:

- no completed successful `Svodka quality` proves the exact current writer SHA;
- quality or read-only preflight is not green;
- quality/preflight candidate digest differs;
- approved release is absent, unauthorized, has invalid reviewed-candidate provenance, or digest differs;
- profile remains write-disabled;
- ledger is absent or belongs to another release digest;
- first unresolved entry is `dispatching`, `unknown` or `failed`;
- provider outcome is `may_exist`;
- manual canary is not verified;
- a scheduled workflow is a rerun rather than attempt 1;
- a scheduled workflow was started manually rather than by `schedule`;
- the requested canary item is not the strict next item;
- the strict next item is early or more than 120 minutes late;
- daily verified limit is already consumed.

A proven local/pre-provider no-effect failure such as a missing token may return `not_dispatched` and be safely restored to `pending` after applying its exact durable outcome. This exception does not apply to `may_exist`.

A provider-free reconciliation may return an abandoned intent to `pending` only when the original completed GitHub run itself proves the exact send step was skipped after durable intent persistence. A cancelled, in-progress, wrong-event, wrong-SHA or otherwise ambiguous run is not sufficient evidence.

## Library-level defense-in-depth note

The operational CLI and all committed workflows require an authorized immutable release before creating durable remote state. The low-level Python helper `initialize_ledger(release)` itself does not yet repeat the authorization check. This cannot send or mutate Telegram and is not used as an authorization boundary by the production workflows, but adding the same guard directly to that helper remains a small P2 defense-in-depth improvement. Avoid a large untested rewrite of the state module solely for this duplication.

## Editorial boundary

The pilot facts were hardened directly in the canonical queue. The previous self-mutating repair workflow was removed. Source and wording changes must be committed as ordinary reviewed content changes before candidate generation. Dynamic web results are never auto-published.

Canonical draft validation now also requires strict chronological timestamps, exact minute boundaries, unique per-day configured slots, unique normalized quiz/poll options and exact visible source URL agreement.

Native quiz rendering preserves the Svodka header, title, vote prompt, visible sources, tagline and full topical hashtag line without revealing the correct answer before voting.

Research/audit records:

- `docs/research/2026-08-08-svodka-technical-verification-ledger.md`
- `docs/research/2026-08-08-svodka-second-pass-audit.md`
- add the newest full restart audit record before activation; it must include the exact current SHA, unresolved CI observability limitation and fresh primary-source revalidation.
