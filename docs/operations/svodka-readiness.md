# Svodka Telegram production readiness

Last reviewed: 2026-08-11 after PR #301 on `main@bca9a5de29b4c5480db4cdd7c1f09afde75b7597`; this document also records the explicit recovery opt-in hardened in the follow-up review.

## Current state

`@deep_info_life` is **activation-armed but not yet canary-proven**. The repository write gate is enabled and the exact release is approved, but the durable publication ledger still contains no Telegram dispatch intent, provider receipt or verified publication.

- channel profile: `content/telegram/channels/svodka.json`
- exact target binding: `content/telegram/channels/svodka-target-binding.json`
- canonical pilot queue: `content/telegram/svodka/draft-14-posts-2026-08.json`
- canonical release id: `svodka-pilot-2026-08`
- canonical review candidate artifact: `svodka-review-candidate`
- approval receipt: `content/telegram/svodka/release-approval-2026-08.json`
- approved release digest: `sha256:959a42e914acedc6969550ba842a12d1a2b174c940497d8a98f4ab8e2e63cdce`
- state branch: `state/svodka-telegram`
- publication ledger path on the state branch: `content/telegram/svodka/publication-ledger.json`
- current profile gate: `provider_writes_authorized=true`
- current durable ledger checkpoint: 14/14 `pending`, 14/14 `provider_effect=impossible`, no dispatch intent or provider identity recorded
- scheduled publisher: installed and fail-closed until a verified manual canary exists

The approved runtime release is materialized from the immutable approval receipt plus the current canonical queue/profile/binding. There is no committed `content/telegram/svodka/approved-release-2026-08.json` file in the current production path; documentation or automation must not depend on that obsolete path.

The current Telegram architecture intentionally uses the same posting bot for multiple channels: `@preaching_mp3_bot`, bot id `8716602202`. The token authenticates the bot; the exact profile, numeric chat id, target binding, immutable release, state branch and concurrency group select and isolate the destination channel.

The exact current `Svodka quality` result is never inferred from a source change or historical audit. Production writers independently require an actual completed successful quality run for their own exact current `GITHUB_SHA` before provider access.

All Svodka state/provider writers share `group: svodka-telegram-publisher`, cancellation is disabled, and state is isolated on `state/svodka-telegram`.

## Stable workflow split

1. `Svodka quality` — read-only CI. It runs on every push to `main`, installs the development project and exact production Telegram runtime, validates the canonical queue, renders all 14 provider payloads and uploads the target-bound write-disabled `svodka-review-candidate` for release id `svodka-pilot-2026-08`. It has no Telegram secret, repository mutation or provider mutation.
2. `Svodka Telegram preview and preflight` — manual preview / fresh read-only Telegram identity proof. It reproduces the same canonical review candidate identity before optional provider reads.
3. Release authorization — repository promotion only. `authorize-svodka-release` requires the exact review candidate, exact `--expected-candidate-sha256`, current profile, pinned target binding, reviewer identity and timezone-aware review timestamp. The committed approval receipt binds both reviewed candidate digest and approved release digest.
4. `Svodka initialize publication ledger` — manual state-only operation. It requires an exact authorized immutable release digest and creates the ledger once on `state/svodka-telegram`. The low-level generic `initialize_ledger()` helper also fails closed unless the immutable release is authorized. The current ledger is already initialized.
5. `Svodka skip expired publication windows` — manual state-only recovery. For Svodka it explicitly uses `MAX_PUBLICATION_LAG_MINUTES=120`, so a pending item becomes recoverably stale at the same deadline at which provider freshness closes. It has no Telegram secret and cannot send. The generic CLI retains structural-window-only recovery when that bound is not configured.
6. `Svodka exact manual canary` — manual one-publication provider mutation. It requires exact current-main quality, authorized release, enabled profile, exact confirmation, initialized ledger, exact requested publication and bounded freshness. The Svodka workflow explicitly opts into `--recover-stale-predecessors` in both read-only freshness preview and exact manual prepare. Only already stale consecutive pending predecessors may be traversed/recovered; ordinary generic callers do not receive this behavior implicitly.
7. `Svodka scheduled publisher` — primary runs are installed for `10:30` and `19:30` Europe/Moscow, with bounded catch-up runs at `11:17` and `20:17`. All four events use the same writer/state machine; catch-up is not a second sender. The mutating job runs only for `schedule` on `main`; manual Run workflow cannot publish. A verified manual canary is required before scheduler state mutation, Telegram preflight or provider mutation.
8. `Svodka reconcile skipped provider send` — manual provider-free recovery for an abandoned durable intent when the exact source workflow attempt proves the provider send step was **skipped**. It verifies exact run attempt/head SHA, workflow/event pairing and successful durable-intent step before recording `confirmed_absent` and restoring retryable state.
9. `Svodka reconcile archived provider outcome` — manual provider-free recovery for the different case where the provider send completed and the exact structured provider outcome was archived, but final durable state persistence did not succeed. It binds source run/attempt/workflow/head, persisted dispatch, artifact identity/bytes and structured outcome before applying the existing transition. It performs no Telegram read or write and must never be replaced by a blind provider retry.

The two reconciliation workflows are deliberately different. Do not use skipped-send reconciliation when the send actually ran, and do not use archived-outcome recovery when there is no exact archived outcome.

## Publication timing and stale-recovery contract

The immutable release defines a structural state window:

- start = exact `scheduled_at`;
- structural end = next item's `scheduled_at`;
- final item structural end = next local midnight.

Svodka production adds a stricter freshness gate:

- provider eligibility begins at exact `scheduled_at`;
- provider eligibility ends at the earlier of structural end or `scheduled_at + 120 minutes`;
- the same bounded deadline is used by Svodka stale recovery;
- at the exact deadline an item is no longer provider-eligible and is also recoverably stale; there is no freshness/recovery dead zone;
- primary cron runs at 10:30/19:30 Moscow and the same runtime rechecks eligibility 47 minutes later at 11:17/20:17;
- if the primary run already verified the slot, catch-up sees the next future item as not due;
- if a prior run left `dispatching`, `unknown`, `failed` or `may_exist`, neither catch-up nor canary recovery may bypass it;
- an over-late item is never backfilled merely because its structural window has not reached the next slot.

### Exact canary recovery semantics

Stale-predecessor recovery is **not a generic side effect of supplying a publication id**. It requires an explicit `--recover-stale-predecessors` switch.

For the Svodka canary the workflow uses that switch in two places:

1. **Read-only freshness preview.** It may look through only consecutive preceding entries that are still `pending` and already beyond the same 120-minute deadline. The ledger is not mutated. If the requested item is early, stale, wrong, or blocked by a non-pending unresolved entry, the canary fails before durable state advance.
2. **Exact manual prepare.** The same explicit switch is required again. The runtime applies only those bounded-stale predecessor transitions in memory, then asks the existing strict state machine to prepare the exact requested publication. The ledger is saved only if that exact prepare succeeds.

Therefore a successful canary intent commit can atomically contain `skipped/impossible` transitions for stale predecessors plus the requested item in `dispatching` with exact intent provenance. That combined durable commit is pushed and read back **before** any Telegram provider mutation. A wrong or premature requested id cannot use recovery to advance durable state.

Scheduled prepare does not opt into this manual exact-canary recovery path. Scheduled stale handling remains the scheduler's guarded state-machine path and still requires a previously verified manual canary.

## Exact provider mutation and outcome durability

Mutation transport retries are zero. A failure proven before dispatch may be `not_dispatched` or `confirmed_absent`; an ambiguous failure after a mutation may be `may_exist` and is never blindly retried.

`sendMessage` verification checks the provider-visible result, not only HTTP success:

- returned channel identity;
- exact plain text;
- exact `bold`, `italic` and `text_link` entities including Telegram UTF-16 offsets and source URLs;
- link-preview semantics where they are provider-observable and relevant;
- exact message id and canonical channel message URL.

Generic poll payload schema v4 freezes `is_anonymous`, `allows_multiple_answers`, `allows_revoting`, `members_only`, `description`, and for quizzes `correct_option_ids` plus `explanation`. Observable returned Poll semantics are checked after the provider call. Provider-visible drift after mutation is conservatively `may_exist`.

After `send-once`, canary and scheduled writers archive the exact structured provider outcome as a run/attempt-scoped GitHub Actions artifact **before** final durable state persistence. This exists so a later state push failure does not destroy exact receipt/outcome evidence.

Archived-outcome recovery validates the downloaded ZIP bytes against proved GitHub artifact size and SHA-256 and accepts only the expected single outcome JSON. The authenticated GitHub API request and temporary artifact-storage download are separated so the GitHub bearer credential is not forwarded to the storage host.

## Incident recovery matrix

### Case A — send step is proven skipped

Use `Svodka reconcile skipped provider send` only if the exact completed source attempt proves expected workflow/event/head SHA, durable dispatch intent persistence and provider send step exactly `skipped`. Then provider absence is proven for that attempt and reconciliation may record `confirmed_absent` and restore a safe retryable state.

### Case B — send ran and exact archived outcome exists

Use archived-provider-outcome recovery when the exact source attempt archived its structured provider outcome but final state persistence failed or did not succeed. Recovery must prove exact run/attempt/workflow/head, dispatch identity, publication id, provider payload digest, artifact metadata, downloaded bytes and structured outcome. It then applies the archived result without Telegram access.

After a possible provider effect, unrelated later `Svodka quality` drift is not allowed to erase the fact that the provider result already exists. Archived-outcome recovery therefore does not require a later current-quality success; it does require its own exact evidence and rejects stale queued runtime before durable state commit by requiring `origin/main == $GITHUB_SHA`.

### Case C — neither proof exists

Do not guess and do not retry. A `may_exist` dispatch remains blocking until there is sufficient evidence to prove absence or recover the exact provider outcome.

## Activation checklist

The repository preparation stages are already complete at this review point: exact candidate review, approval receipt, write-enabled profile and initialized ledger all exist. The remaining rollout sequence is:

1. Obtain completed successful Svodka quality proofs on the exact `main` SHA that will execute the canary.
2. During a fresh publication window, run `Svodka exact manual canary` with exact `CANARY:<publication_id>:<release_digest>` confirmation. The requested publication may be beyond stale pending predecessors only because this workflow explicitly enables bounded stale recovery.
3. Verify the durable state transition: any recovered predecessors are exactly `skipped/impossible`; the requested publication is `published` with `provider_effect=verified`, exact message id/url, chat id, bot id and manual dispatch provenance.
4. Do not deploy a second scheduler. The installed primary/catch-up scheduler becomes eligible only after the verified manual canary and all existing quality/release/profile/state/freshness/target gates pass.
5. Keep issue #235 open until at least one **autonomous scheduled** publication is durably verified; a successful manual canary alone does not satisfy the closing criterion.

If no fresh canary window is currently open, do not send early and do not backfill a stale item. Wait for the next reviewed slot or use the provider-free stale-recovery workflow only when there is an operational need to advance state separately.

## Blocking conditions

Do not dispatch or blindly retry if any of these are true:

- no completed successful quality proof exists for the exact current writer SHA;
- read-only target preflight is not green;
- approved release/approval receipt is absent, unauthorized or has invalid reviewed-candidate provenance;
- profile write gate is disabled;
- ledger is absent or belongs to another release digest;
- first unresolved nonterminal entry is `dispatching`, `unknown` or `failed`;
- provider outcome is `may_exist` without sufficient recovery evidence;
- requested canary is early, itself stale, absent from the release, or not strict-next after removing only explicitly recoverable bounded-stale predecessors;
- stale-predecessor recovery was requested without exact manual mode, exact publication id or explicit max-lag configuration;
- scheduled workflow is a rerun rather than attempt 1;
- scheduled workflow was started manually rather than by `schedule`;
- manual canary is not verified for scheduled mutation;
- daily verified limit is consumed.

A proven local/pre-provider no-effect failure may be safely restored only after applying its exact durable outcome. This exception never converts ambiguous `may_exist` evidence into retry permission.

## Repository and supply-chain boundary

The production/minimal Telegram dependency closure is exact-version pinned **and hash-checked**. `requirements/telegram-publisher.txt` enables pip `--require-hashes` for the supported runtime closure, while production workflow installs continue to require binary packages. General CI builds an isolated Python 3.11 Telegram runtime from this lock, runs `pip check`, smoke-tests the guarded CLI without provider access and audits the pinned closure. Treat any future dependency update as a lock regeneration/review event; never remove hashes or introduce an unhashed dependency into this runtime path.

Repository branch-protection/ruleset state is an external GitHub setting and is not inferred from repository files. Before provider activation independently verify protection of `main` and `state/svodka-telegram` against deletion/force-push while preserving the intended fast-forward state writer path.

## Editorial boundary

Source/wording changes must be ordinary reviewed content changes before candidate generation. Dynamic web results are never auto-published. The obsolete self-mutating Svodka migration workflows were removed and regressions forbid their return.

The rich-v1 editorial successor set is a separate provider-inert content layer. Reader-first rich articles do not alter the approved `svodka-pilot-2026-08` provider payloads or release digest merely by existing in the repository.

## Audit records

Use historical audit records as an immutable chain, not as substitutes for exact runtime proof:

- `docs/research/2026-08-08-svodka-technical-verification-ledger.md`
- `docs/research/2026-08-08-svodka-second-pass-audit.md`
- `docs/research/2026-08-08-svodka-full-restart-audit.md`
- `docs/research/2026-08-08-svodka-current-main-continuation-audit.md`
- `docs/research/2026-08-08-svodka-post-hardening-continuation-audit.md`

Historical audit files never substitute for a successful exact-SHA quality proof, current durable ledger readback, or exact provider outcome evidence.
