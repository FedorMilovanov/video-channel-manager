# Master reliability audit and wave roadmap

**Captured:** 2026-08-04  
**Repository:** `FedorMilovanov/video-channel-manager`  
**Verified baseline:** `main@b19d4faa7e58ff4c0ae7f974092e9fd2441c571d`  
**Scope:** repository core plus the separate operational queues for `lord-god-strength`, `legendary-poet`, and the adjacent browser-based VK Audio workflow.

This document is the canonical synthesis of the 2026-08-03/04 audit marathon. It replaces chat-only priority lists and prevents later agents from treating fixed, retracted, disputed, and still-active findings as one undifferentiated backlog.

Machine-readable status is stored in [`audit-register-2026-08-04.json`](audit-register-2026-08-04.json).

## 1. Evidence order

When sources disagree, use this order:

1. current code on the verified `main` commit;
2. exact live result plus postflight/reconciliation evidence;
3. merged PR scope and exact commit;
4. current signed audit or manifest;
5. older audit;
6. unverified hypothesis or general recommendation.

A finding must not remain active merely because it appeared in an older agent report.

## 2. System boundaries

### Shared core

Reusable models, provider clients, project identity, editorial validation, persistence, guarded writers, CLI, journals, and verification belong in `src/video_channel_manager` and stable shared tooling.

### `lord-god-strength`

- YouTube channel: `UCeSJsC6go2c9pdJCuUI1BYA`
- VK community: `60805374`
- VK owner: `-60805374`

### `legendary-poet`

- YouTube channel: `UC-78ys2S3cQ3lpqgXfo-SvQ`
- VK community: `235216998`
- VK owner: `-235216998`

### VK Audio browser automation

The browser-based VK Audio canary in the adjacent `mp3telegrambot` workflow is a separate system. Its undocumented web contracts, browser state, result JSON, and unknown-outcome policy must not be silently merged into the VK Video API state machine.

## 3. Verified closed work

### Project identity and SQLite — PR #61

Merge `51cc2144508c33adf78380ab35e32ee88c10f90f` added:

- exact project resolution from registered YouTube/VK IDs;
- fail-closed unknown and cross-project combinations;
- `project_key` persistence in plans and operations;
- guarded legacy-plan upgrade after original digest verification;
- AST protection for project-bound VK publication rendering;
- SQLite WAL, `busy_timeout=5000`, `foreign_keys=ON`, and deterministic pool disposal.

### Persistent HTTP clients — PR #62 and #63

Merges `55477df06ae0ae5238634aad829ba2fe8fe70fd7` and `b19d4faa7e58ff4c0ae7f974092e9fd2441c571d` migrated the main VK/YouTube inventory paths, VK video/thumbnail writers, YouTube description writer, OAuth exchange/refresh, and VK processing polling to an owned/borrowed persistent-client lifecycle.

The migration intentionally did **not** add blind retries to ambiguous mutations.

### Theological article photo wave

The final `lord-god-strength` article photo wave is operationally complete:

- `10/10` operations verified;
- postponed post IDs `12471` through `12480`;
- scheduled from 2026-08-04 through 2026-08-13;
- photo and article URL confirmed for each post;
- repeated Apply is prohibited.

Historical link-card/photo generations are evidence and migration history, not active executors to rerun.

## 4. Active current findings

### P0 — upload reservation and resume

The current base sync still records an upload only after `video.save`, file upload, and processing verification. A crash after reservation but before the final journal write can leave a remote object without a durable local ticket and make a later run reserve another object.

The current reuse path also treats any visible journal `remote_id` as reusable without requiring a verified journal stage or a complete readiness/content reconciliation. `wait_until_available` currently accepts visibility plus false `processing`/`converting`; it does not define an exact minimum duration/type/playability/source contract.

Required correction is a journaled state machine with intent before reservation, ticket persistence immediately after `video.save`, exact reconciliation of unknown outcomes, verified-only reuse, and fault-injection tests after every state boundary. Do not invent a provider chunk/resume protocol.

### P0 — content pipeline

`cli/_content_io.py::load_records` parses records and validates collection-level uniqueness but does not run full `validate_content_record` validation. Preview and plan build must fail closed without depending on a separately invoked operator command.

### P0 — supported sync entrypoint

`sync_youtube_to_vk_textsafe.py` now resolves and binds the exact project, but it still monkeypatches the executable, Poet-hardcoded `sync_youtube_to_vk.py`. The base executor remains a direct bypass. It must become project-aware internally or become a non-executable internal module behind one supported entrypoint.

### P1 — provider reliability

- `YouTubeApiClient._get` has no bounded retry/backoff for transient read failures.
- VK reader/writer/wave transports still duplicate request construction, parsing, and error classification.
- no configurable proactive VK limiter is shared across long scans and wave reads;
- `YouTubeCommentWriter` and remaining direct `httpx.Client()` sites still need lifecycle inventory;
- mutation retry policy must remain separate from transport reuse.

### P1 — identity and media correctness

- base sync maps albums by normalized title, so duplicate or renamed albums can hide ambiguity;
- the media cache chooses from `{video_id}.*` candidates before an authoritative final-path/fingerprint contract;
- position churn must not define semantic membership postconditions;
- IDs must be parsed strictly and reject booleans.

### P1 — Windows/operator layer

Fresh re-verification is required, but the audited failure class remains open: multiple Python launchers, stdout parsing for mandatory counts, code-page differences, absolute paths, nested `pwsh`, inconsistent exit codes, and selecting the newest ZIP by modification time instead of exact identity and digest.

### P1 — test concentration

Green CI does not cover the most dangerous boundaries sufficiently. Future coverage gates must be risk-based: upload reservation/recovery, executor preflight, provider ambiguity, wall deduplication, wrappers, and failure injection.

## 5. Retracted or disputed claims

- **System `Uploads` playlist creates a VK album:** retracted after primary-source verification; do not implement a fix for it.
- **VK chunk/resume upload:** no verified provider-supported protocol; do not invent one.
- **All exact IDs/counts are magic numbers:** false for digest-locked one-shot policies, where they are safety guards.
- **`guid` is complete wall idempotency:** false; it supplements, but does not replace, published+postponed preflight and exact postflight.
- **`auto_publish` and `repeat` are universally proven `video.save` flags:** provider-contract evidence conflicts. Preserve proven `wallpost=0`; research the other parameters before creating a universal mandate.
- **Project branding is fully solved:** supported paths are strongly hardened, but the executable base sync remains a bypass.

## 6. Current operational queues

### `lord-god-strength`

Closed:

- reviewed 403-video cleanup;
- 34-item Shorts reset and protected post `12400` preservation;
- article photo wave `12471–12480`;
- PR #61–63 reliability phases.

Still requires exact local/live reconciliation:

- issue #31 — 26-item long-form result and ledger;
- issue #32/#38 — final Shorts/Clips identities and types;
- issue #36 — universal wall separation contract and fresh read-only wall audit;
- issue #37 — only the exact approved post-boundary cleanup scope;
- issue #33 — catalog/publishing work after all dependencies have exact states.

No accepted, processing, or unknown upload may be retransmitted before reconciliation.

### `legendary-poet`

Latest supplied reviewed Shorts state:

- 56 exact YouTube Shorts;
- 41 exact YouTube→VK pairs;
- 15 confirmed missing;
- 0 ambiguous;
- 0 extra vertical VK objects;
- old matrix `59/40/19/1` is retired;
- preparation of a V3 canary package is evidenced, but completed V3 Apply/postflight is not.

Status: `reviewed_manifest_prepared / upload_completion_not_proven`.

## 7. Wave order

### Wave 0 — canonical state and issue graph

- add this synthesis and machine-readable register;
- update `current-state.md`, operations index, backlog, and memory changelog;
- expand issue #64 with the omitted current P0 findings;
- create a focused Wave 1 issue;
- close superseded PR #29 after preserving its reusable ledger/reconciliation lessons;
- perform no provider writes.

### Wave 1 — upload state machine and recovery

Stages must include at least:

`planned → media_verified → reservation_intent_committed → reserved → upload_started → upload_response_received → processing → verified`, with explicit `rejected` and `unknown_requires_reconciliation` terminal/blocked states.

Acceptance:

- crash after every boundary cannot cause a second `video.save`;
- unknown never becomes blind retry;
- visible empty/incomplete objects are not accepted;
- verified replay is a no-op;
- one isolated canary only after offline fault-injection tests and exact-head CI.

### Wave 2 — fail-closed content and project pipeline

- full per-record validation inside every load/preview/plan path;
- no implicit project default in reusable parsing;
- complete targets↔operations coverage;
- one project-aware supported sync entrypoint;
- cross-project and direct-bypass behavioral tests.

### Wave 3 — transport, retry taxonomy, and limiter

- complete HTTP ownership migration;
- central request/parse/redaction/error taxonomy;
- bounded safe-read retries;
- configurable proactive limiter;
- no mutation blind retry;
- fake-clock deterministic tests.

### Wave 4 — wall safety subsystem

- provider-contract research for upload flags;
- manifest `wall_mutation_authorized=false`;
- before/after wall delta verification;
- postponed publishing as default;
- published+postponed duplicate and slot coverage;
- one stable wall executor.

### Wave 5 — Windows operator contract

- one Python/venv bootstrap;
- structured preflight/result JSON;
- no mandatory stdout parsing;
- `$PSScriptRoot` and exact artifact paths/digests;
- shared PowerShell guards;
- automatic operational-bundle verification;
- correct exit-code tests on PowerShell 7.

### Wave 6 — stable wave engine

- policy/data-driven waves over shared `SourceAuditor`, `PlanBuilder`, `Preflight`, `Executor`, `Reconciler`, `Postflight`, and `BundleWriter` interfaces;
- dependency injection instead of monkeypatch;
- no private cross-script imports;
- versioned journal migrations;
- retired executors archived read-only after reference proof.

### Wave 7 — risk-based tests

- module-specific thresholds for provider clients, writers, CLI, and executors;
- failure matrix after intent, provider acceptance, lost response, delayed consistency, journal write, and restart;
- property tests for idempotency and project isolation;
- Windows wrapper tests;
- random order/repeat stability where useful.

### Wave 8 — matching, catalog, and media correctness

- exact reviewed mappings before fuzzy fallback;
- maximum-weight or equivalent globally consistent matching;
- duplicate normalized album titles become conflicts;
- semantic membership comparison ignores position churn;
- authoritative final media path, ffprobe, duration, A/V, and fingerprint validation.

### Wave 9 — finish live queues separately

Only after Waves 1–4 gates:

1. reconcile local `lord-god-strength` long-form result/ledger;
2. reconcile all accepted/processing Shorts and exact final types;
3. confirm `legendary-poet` V3 canary/apply state before any upload;
4. build catalog/editorial/postponed plans per project with separate manifests and ledgers.

### Wave 10 — retirement and governance

- explicit supported/retired entrypoint registry;
- remove or archive dead generations only after reference scans;
- generated-doc/CLI consistency checks;
- architecture decisions for state machine, retry taxonomy, project identity, and wave engine;
- each live incident becomes a regression test and durable rule.

## 8. Non-negotiable invariants

1. No blind retry after an ambiguous mutation.
2. Exact project, source channel, VK community/owner, and link profile are required before rendering or mutation.
3. Read-only by default; reviewed exact-ID scope for writes.
4. Intent, provider result, and postflight are durable states, not console prose.
5. Upload and wall publication are separate operations.
6. Long-form and Shorts/Clips use separate manifests and ledgers.
7. Historical completed destructive executors are never rerun.
8. Unknown or unregistered links fail closed.
9. Operational ZIPs pass the repository verifier before handoff.
10. Every wave updates `current-state.md`, this register, the changelog, issue state, and regression coverage.

## 9. Wave 0 completion gate

Wave 0 is complete only when:

- this document and the register exist in `main`;
- `current-state.md` names the verified baseline and current blockers;
- the operations index and backlog point here;
- issue #64 includes upload reservation/resume, content validation, and base-sync bypass;
- a focused Wave 1 issue exists;
- superseded PR #29 is closed without merging historical destructive code;
- no VK or YouTube write has occurred.
