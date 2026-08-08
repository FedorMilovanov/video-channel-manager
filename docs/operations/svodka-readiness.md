# Svodka Telegram production readiness

Last reviewed: 2026-08-08 after post-hardening `main@71fbaaac132c1bd337d915a02a2a20f7f987629f`

## Current state

`@deep_info_life` is **not live-enabled** yet.

- channel profile: `content/telegram/channels/svodka.json`
- exact target binding: `content/telegram/channels/svodka-target-binding.json`
- canonical pilot queue: `content/telegram/svodka/draft-14-posts-2026-08.json`
- canonical release id: `svodka-pilot-2026-08`
- canonical review candidate artifact: `svodka-review-candidate`
- state branch: `state/svodka-telegram`
- approved release path: `content/telegram/svodka/approved-release-2026-08.json`
- publication ledger path on the state branch: `content/telegram/svodka/publication-ledger.json`
- current profile gate: `provider_writes_authorized=false`
- approved release: absent at the review point above
- publication ledger: absent at the review point above
- scheduled publisher: installed but fail-closed until the exact approved release, write gate, ledger and verified manual canary all exist

The current Telegram architecture intentionally uses the same posting bot for multiple channels: `@preaching_mp3_bot`, bot id `8716602202`. The token authenticates the bot; the exact profile, numeric chat id, target binding, immutable release, state branch and concurrency group select and isolate the destination channel.

The exact current `Svodka quality` result is never inferred from a source change or historical audit. Production writers independently require an actual completed successful quality run for their own exact current `GITHUB_SHA` before provider access.

Every permanent `svodka-*.yml` workflow is pinned to `ubuntu-24.04`. All six state-writing workflows use `group: svodka-telegram-publisher`, `cancel-in-progress: false` and `queue: max`.

## Stable workflow split

1. `Svodka quality` — read-only CI. It runs on every push to `main`, installs the development project and exact production Telegram runtime, validates the canonical queue, renders all 14 provider payloads and uploads the target-bound write-disabled `svodka-review-candidate` for release id `svodka-pilot-2026-08`. It has no Telegram secret, repository mutation or provider mutation.
2. `Svodka Telegram preview and preflight` — manual preview / fresh read-only Telegram identity proof. It reproduces the same canonical review candidate identity before optional provider reads.
3. Release authorization — repository promotion only. `authorize-svodka-release` requires the exact review candidate, exact `--expected-candidate-sha256`, current profile, pinned target binding, reviewer identity and timezone-aware review timestamp. The compatibility wrapper and production path use the same generic exact-review contract.
4. `Svodka initialize publication ledger` — manual state-only operation. It requires an exact committed authorized release digest and creates the ledger once on `state/svodka-telegram`. The low-level generic `initialize_ledger()` helper itself also fails closed unless the immutable release is authorized. The workflow has no Telegram secret and re-proves exact-current-main quality before durable state commit/push.
5. `Svodka skip expired publication windows` — manual state-only recovery. It may mark only already expired consecutive pending items as `skipped/impossible`; it has no Telegram secret and cannot send. Its state write is serialized with the other Svodka writers and is current-main quality-proven before persistence.
6. `Svodka exact manual canary` — manual one-publication provider mutation. Before Telegram access it requires successful exact-current-main `Svodka quality`, an authorized exact release, enabled profile, matching initialized ledger, exact confirmation, strict-next ordering and a publication no more than 120 minutes late. It performs fresh read-only preflight, persists durable intent, re-proves current-main quality immediately before mutation, then permits one `send-once`.
7. `Svodka scheduled publisher` — primary runs are installed for `10:30` and `19:30` Europe/Moscow on 9–15 August, with bounded catch-up runs at `11:17` and `20:17`. All four events use the same writer/state machine; catch-up is not a second sender. The mutating job runs only for `schedule` on `main`; manual Run workflow cannot publish. A verified manual canary is required before automatic stale-window state mutation, Telegram preflight or provider mutation.
8. `Svodka reconcile skipped provider send` — manual provider-free recovery for an abandoned durable intent when the exact source workflow attempt proves the provider send step was **skipped**. It verifies the exact run attempt/head SHA, workflow/event pairing and successful durable-intent step. Only then may it record `confirmed_absent` and return the item to a safe retryable state.
9. `Svodka reconcile archived provider outcome` — manual provider-free recovery for the different case where the provider send completed and the exact structured provider outcome was archived, but final durable state persistence did not succeed. It binds the exact source run/attempt/workflow/head, persisted dispatch, artifact id/digest/size, downloaded artifact bytes and structured outcome before applying the existing state transition. It performs no Telegram read or write and must never be replaced by a blind provider retry.

The two reconciliation workflows are deliberately different. Do not use skipped-send reconciliation when the send actually ran, and do not use archived-outcome recovery when there is no exact archived outcome.

## Publication timing contract

The immutable release defines a structural state window:

- start = exact `scheduled_at`;
- structural end = next item's `scheduled_at`;
- final item structural end = next local midnight.

Svodka production adds a stricter freshness gate:

- provider eligibility begins at exact `scheduled_at`;
- provider eligibility ends at the earlier of the structural end or `scheduled_at + 120 minutes`;
- canary must be the strict next item before Telegram preflight;
- scheduler verifies a published/verified/manual canary before any scheduler state mutation or Telegram preflight;
- scheduled execution checks strict-next freshness before Telegram preflight;
- primary cron runs at 10:30/19:30 Moscow and the same runtime rechecks eligibility 47 minutes later at 11:17/20:17;
- if the primary run already verified the slot, catch-up sees the next future item as not due;
- if a prior run left `dispatching/may_exist`, catch-up cannot bypass the blocking state or blindly retry;
- an over-late item is not automatically backfilled merely because its structural window has not reached the next slot;
- stale pending items can become `skipped/impossible` only through the guarded state-only path.

## Exact provider mutation and outcome durability

Mutation transport retries are zero. A failure proven before dispatch may be `not_dispatched`; an ambiguous failure after a mutation may be `may_exist` and is never blindly retried.

`sendMessage` verification checks the provider-visible result, not only HTTP success:

- returned channel identity;
- exact plain text;
- exact `bold`, `italic` and `text_link` entities including Telegram UTF-16 offsets and source URLs;
- disabled link previews;
- exact message id and canonical channel message URL.

Generic poll payload schema v4 freezes `is_anonymous`, `allows_multiple_answers`, `allows_revoting`, `members_only`, `description`, and for quizzes `correct_option_ids` plus `explanation`. Observable returned Poll semantics are checked after the provider call. Provider-visible drift after mutation is conservatively `may_exist`.

After `send-once`, canary and scheduled writers archive the exact structured provider outcome as a run/attempt-scoped GitHub Actions artifact **before** final durable state persistence. This exists so a later state push failure does not destroy the exact receipt/outcome evidence.

Archived-outcome recovery validates the actual downloaded ZIP bytes against the proved GitHub artifact size and SHA-256 and accepts only the expected single outcome JSON. The authenticated GitHub API request and the temporary artifact-storage download are separated so the GitHub bearer credential is not forwarded to the storage host.

## Incident recovery matrix

### Case A — send step is proven skipped

Use `Svodka reconcile skipped provider send` only if the exact completed source attempt proves:

- expected workflow/event/head SHA;
- durable dispatch intent persisted;
- provider send step is exactly `skipped`.

Then provider absence is proven for that attempt and reconciliation may record `confirmed_absent` and restore a safe retryable state.

### Case B — send ran and exact archived outcome exists

Use archived-provider-outcome recovery when the exact source attempt archived its structured provider outcome but final state persistence failed or did not succeed.

Recovery must prove exact run/attempt/workflow/head, dispatch identity, publication id, provider payload digest, artifact metadata, downloaded bytes and structured outcome. It then applies the archived result without Telegram access.

After a possible provider effect, unrelated later `Svodka quality` drift is not allowed to erase the fact that the provider result already exists. Archived-outcome recovery therefore does not require a later current-quality success; it does require its own exact evidence and rejects stale queued runtime before durable state commit by requiring `origin/main == $GITHUB_SHA`.

### Case C — neither proof exists

Do not guess and do not retry. A `may_exist` dispatch remains blocking until there is sufficient evidence to prove absence or recover the exact provider outcome.

## Activation checklist

Activation must happen in this order:

1. Obtain completed successful `Svodka quality` on the exact intended current `main` SHA.
2. Run manual read-only preflight against chat `-1003527567039`, bot `8716602202`, `@preaching_mp3_bot`.
3. Confirm quality and preflight produced the same canonical `svodka-review-candidate` digest for release `svodka-pilot-2026-08`.
4. Review that exact 14-item candidate.
5. Authorize that exact candidate with current profile/binding and pass the exact reviewed digest via `--expected-candidate-sha256`.
6. Commit the authorized immutable release at `content/telegram/svodka/approved-release-2026-08.json`.
7. Change only the profile write gate to `true`.
8. Obtain successful `Svodka quality` on the new exact activation SHA.
9. Initialize the state ledger once using `INITIALIZE:<release_digest>`.
10. If an earlier structural window already expired, use the guarded manual skip-expired operation; never send it late.
11. Run one exact manual canary for the strict next item inside its 120-minute freshness window using `CANARY:<publication_id>:<release_digest>`.
12. Verify durable `published`, `provider_effect=verified`, exact message id/url, chat id, bot id and manual dispatch provenance.
13. No separate scheduler deployment is needed. Installed primary/catch-up cron events become eligible only after all gates above succeed.

## Blocking conditions

Do not schedule, dispatch or blindly retry if any of these are true:

- no completed successful `Svodka quality` proves the exact current writer SHA;
- quality or read-only preflight is not green;
- quality/preflight candidate digest differs;
- approved release is absent, unauthorized or has invalid reviewed-candidate provenance;
- profile remains write-disabled;
- ledger is absent or belongs to another release digest;
- first unresolved entry is `dispatching`, `unknown` or `failed`;
- provider outcome is `may_exist` without sufficient recovery evidence;
- manual canary is not verified;
- a scheduled workflow is a rerun rather than attempt 1;
- scheduled workflow was started manually rather than by `schedule`;
- requested canary item is not the strict next item;
- strict next item is early or more than 120 minutes late;
- daily verified limit is consumed.

A proven local/pre-provider no-effect failure may be safely restored only after applying its exact durable outcome. This exception never converts ambiguous `may_exist` evidence into retry permission.

## Repository and supply-chain boundary

The production Telegram dependency closure is exact-version pinned and installed with binary-only packages, but package hashes are not yet enforced. Treat a complete `--require-hashes` lock as a remaining supply-chain hardening item; do not introduce a partial hash set.

Repository branch-protection/ruleset state is an external GitHub setting and is not inferred from repository files. Before activation independently verify protection of `main` and `state/svodka-telegram` against deletion/force-push while preserving the intended fast-forward state writer path.

## Editorial boundary

Source/wording changes must be ordinary reviewed content changes before candidate generation. Dynamic web results are never auto-published. The obsolete self-mutating Svodka migration workflows were removed and regressions forbid their return.

Canonical draft validation requires strict chronological timestamps, exact minute boundaries, unique configured daily slots, unique normalized quiz/poll options and exact visible source URL agreement. Native quiz rendering preserves the Svodka header, title, vote prompt, visible sources, tagline and topical hashtag line without revealing the correct answer before voting.

## Audit records

Use the records as an immutable chain, not as substitutes for exact runtime proof:

- `docs/research/2026-08-08-svodka-technical-verification-ledger.md`
- `docs/research/2026-08-08-svodka-second-pass-audit.md`
- `docs/research/2026-08-08-svodka-full-restart-audit.md`
- `docs/research/2026-08-08-svodka-current-main-continuation-audit.md`
- `docs/research/2026-08-08-svodka-post-hardening-continuation-audit.md`

Before activation, use the newest continuation record together with an actual successful `Svodka quality` for the exact activation `main` SHA. Historical audit files never substitute for that proof.
