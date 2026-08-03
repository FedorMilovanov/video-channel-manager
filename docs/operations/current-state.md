# Current operational state

Updated: 2026-08-04  
Verified code baseline: `main@cf44f64ab9333f512a054a283005fa262f043dc3`  
Wave 0 status: `completed`  
Wave 1 status: `PR #66 IN REVIEW — NO LIVE PROVIDER WRITES`  
Canonical audit: [`master-audit-2026-08-04.md`](master-audit-2026-08-04.md)  
Machine register: [`audit-register-2026-08-04.json`](audit-register-2026-08-04.json)

This is the first state board to read before YouTube/VK work. Chat history, screenshots, remembered counts, retired packages, and older agent audits do not override it.

## Current engineering mode

`WAVE_1_UPLOAD_STATE_MACHINE_PR_66`

Wave 0 performed no VK or YouTube writes. Wave 1 is an offline reliability refactor in PR #66. Broad upload continuation and retransmission remain blocked until the PR is merged and the relevant local ledgers are reconciled.

## Project boundary

### `lord-god-strength`

- YouTube channel: `UCeSJsC6go2c9pdJCuUI1BYA`
- OAuth alias: `fedor-milovanov`
- documented access: read-only
- VK community: `60805374`
- VK owner: `-60805374`
- shared VK credential alias: `legendary-poet` — credential label only

### `legendary-poet`

- YouTube channel: `UC-78ys2S3cQ3lpqgXfo-SvQ`
- OAuth alias: `legendary-poet`
- VK community: `235216998`
- VK owner: `-235216998`

Every operation must bind `project_key`, exact provider IDs, and the matching registered link profile. The shared VK alias never selects a project.

## Verified repository state

### Closed reliability work

PR #61, merge `51cc2144508c33adf78380ab35e32ee88c10f90f`:

- exact project identity and cross-project fail-closed guards;
- project-bound publication rendering and guarded legacy-plan upgrades;
- SQLite WAL, `busy_timeout=5000`, and `foreign_keys=ON`.

PR #62, merge `55477df06ae0ae5238634aad829ba2fe8fe70fd7`:

- persistent owned/borrowed clients for VK and YouTube inventory reads.

PR #63, merge `b19d4faa7e58ff4c0ae7f974092e9fd2441c571d`:

- persistent clients for VK video/thumbnail writers, YouTube description writer, OAuth exchange/refresh, and VK processing polling;
- ambiguous mutations remain non-retryable by default.

### Wave 1 implementation under review

PR #66 addresses the three upload-lifecycle P0 defects present on the verified `main` baseline:

1. reservation intent and exact upload ticket were not durably committed before the next network boundary;
2. a visible journal `remote_id` could be reused without a verified stage and exact readiness/content reconciliation;
3. upload readiness lacked exact identity, minimum duration, final type, stable processing state, title evidence, and playability requirements.

The PR adds a versioned state machine, exact legacy-journal migration, crash fault injection, reconciliation-only unknown states, and verified replay no-op behavior. It performs no live VK or YouTube write.

### Remaining blockers after Wave 1

- content preview/plan loading does not run full per-record validation;
- the supported textsafe wrapper still monkeypatches a directly executable Poet-hardcoded base sync;
- YouTube safe reads have no bounded transient retry;
- provider transport/limiter, Windows runners, wave generations, risk coverage, album identity, matching, and media-cache work remain in later waves.

Issue #65 owns Wave 1. Issue #64 owns the remaining roadmap.

## `lord-god-strength` operational state

### Closed — never rerun

- reviewed VK duplicate cleanup: `confirmed_deleted=403`, `planned=0`, `unresolved=0`, `run=completed`;
- YouTube `KobOzfBqzic` is the already-present transfer boundary;
- YouTube `s512Opa8Eu4` maps to VK `-60805374_456241938`;
- 34 reviewed low-view Shorts were replaced by ordinary videos, their generated wall posts were removed, and protected post `12400` remained present;
- theological article photo wave: `10/10` postponed posts verified, IDs `12471–12480`, scheduled 2026-08-04 through 2026-08-13; Apply is retired;
- draft PR #29 is superseded and closed without merge; its historical deletion executors are prohibited.

### Requires exact local/live reconciliation

Long-form queue:

- reviewed newer-than-boundary items: `27`;
- already present: `1`;
- verified missing: `26`;
- SHA-256: `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`;
- local evidence: `C:\Users\Fedor\Projects\video-channel-manager\data\vk-upload\verified-longform-26`;
- owner issue: #31;
- accepted, processing, or unknown rows must not be retransmitted before reconciliation.

Shorts/Clips:

- canonical source inventory recorded as `108` Shorts;
- final accepted/processing objects and final `short_video` types still require exact reconciliation;
- owner issues: #32 and #38;
- long-form and Shorts remain separate manifests and ledgers.

Wall:

- wall mutation status: `BLOCKED_PENDING_ISSUE_36_AND_FRESH_READ_ONLY_WALL_AUDIT`;
- upload and wall publication remain separate operations;
- immediate publication is blocked by default;
- issue #36 owns the universal upload/wall contract and fresh published+postponed audit;
- issue #37 is limited to its exact approved cleanup scope;
- `guid` is an additional guard, not complete idempotency.

Catalog/publishing:

- issue #33 remains blocked until upload, Shorts, and wall unknowns are resolved;
- do not combine catalog, description, wall, and audio mutation work.

## `legendary-poet` operational state

Latest retained reviewed Shorts matrix:

- 56 exact YouTube Shorts;
- 41 exact YouTube→VK pairs;
- 15 confirmed missing;
- 0 ambiguous;
- 0 extra vertical VK objects;
- `BXZeRiEOHmQ` maps to VK `-235216998_456239039`;
- old `59/40/19/1` matrix is retired;
- two protective stops performed no new VK writes;
- V3 canary preparation is evidenced, but completed V3 Apply/postflight is not.

Status: `REVIEWED_MANIFEST_PREPARED / UPLOAD_COMPLETION_NOT_PROVEN`.

Do not run the old package or upload the 15 candidates until the exact V3 canary/apply state is recovered, Wave 1 is merged, and the corresponding journal is reconciled.

## Separate VK Audio browser workflow

The browser-based VK Audio workflow belongs to the adjacent `mp3telegrambot` system and uses undocumented web contracts. Keep it separate until a formal manifest/result/unknown-outcome interface exists.

## Active issue graph

- #31 — long-form result and ledger reconciliation;
- #32 — exact VK Clips inventory and Shorts queue;
- #33 — catalog and publishing after dependencies;
- #36 — wall safety and postponed publishing;
- #37 — exact approved wall-cleanup scope;
- #38 — Shorts upload modes and final type/player behavior;
- #64 — master reliability roadmap;
- #65 — Wave 1 journaled upload state machine and recovery;
- PR #66 — focused Wave 1 implementation.

## Next allowed work

1. Complete exact-head CI and review for PR #66.
2. Merge only when dependency audit, compileall, Ruff, formatting, strict mypy, and full pytest pass on Python 3.11, 3.12, and 3.13.
3. Perform no live queue retransmission in the refactor PR.
4. After Wave 1 merge, inspect and reconcile local journals before any canary or resume.
5. Begin Wave 2 only from the merged Wave 1 baseline.

## Update protocol

After every wave or operational run record:

- verified code baseline and owning issue/PR;
- selected `project_key` and exact provider IDs;
- manifest/plan digest;
- planned, reserved, accepted, processing, verified, rejected, and unknown counts;
- result and ledger paths;
- whether retry is safe;
- exact remaining work;
- new provider-contract, identity, media, wall, wrapper, or packaging failures.
