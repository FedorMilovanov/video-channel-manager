# Operational automation backlog

Updated: 2026-08-04  
Program state: `WAVE_5_COMPLETED_WAVE_6_ACTIVE`

This backlog is subordinate to [`master-audit-2026-08-04.md`](master-audit-2026-08-04.md) and the machine-readable [`audit-register-2026-08-04.json`](audit-register-2026-08-04.json). It must not re-activate retracted findings, retired executors, or completed destructive operations.

## Completed waves

### Wave 0 — canonical state

Completed with synchronized sources of truth, project boundaries, issue ownership, and retirement of superseded destructive work. Provider writes: 0.

### Wave 1 — upload state machine and recovery

Completed by PR #66, merge `56da03247f60ec9d25f1646fb9ccdfbb651aff9c`:

- reservation intent before `video.save`;
- exact ticket persistence before media transfer;
- explicit `unknown_requires_reconciliation`;
- no second reservation or blind upload retransmission;
- exact-ID recovery and crash-boundary tests.

Provider writes during implementation/CI: 0.

### Wave 2 — fail-closed project/content pipeline

Completed by PR #68, merge `19c2671bf91c8376def527a592e0bb7674841d03`:

- exact registered project identity for records, plans, and runtime;
- mixed/unknown project rejection;
- project-bound operation identities and digests;
- internal-only legacy base sync;
- one supported dependency-injected entrypoint.

Provider writes during implementation/CI: 0.

### Wave 3 — transport, retries, and limiter

Completed by PR #70, merge `995167bdadc90d8d53414570cc3e5010bc4a93f2`:

- explicit HTTP client ownership;
- classified bounded retries only for safe reads;
- redacted transport failures;
- one-attempt ambiguous mutations;
- injectable zero-default limiter;
- Python 3.11/3.12/3.13 exact-head CI.

Provider writes during implementation/CI: 0.

### Wave 4 — upload/wall separation

Completed by PR #71, merge `d85f7cf94b8ba0b30947291b3a08491239438843`, exact-head CI run `30895905586`:

- immutable self-digested upload wall policy;
- explicit `wallpost=0`, `auto_publish=0`, `repeat=0`;
- complete published+postponed wall snapshots;
- one batch baseline bound to every upload operation;
- mandatory clean wall postflight before `verified`;
- pre-dispatch-only missing-policy migration with rehashed operation identity;
- fail-closed handling of historical provider-dispatched journals;
- postponed-only default wall publication;
- deterministic `guid`, duplicate/schedule collision checks, and exact ambiguous-response reconciliation;
- no automatic cleanup;
- `586 passed, 1 xfailed` on Python 3.11/3.12/3.13.

Provider writes during implementation/CI: 0.

### Wave 5 — reliable Windows/PowerShell operator layer

Completed by PR #75, merge `1a62779293a404e4654b6230644dfc78e9b20dc1`, exact-head CI run `30900532613`:

- complete registry for 23 production PowerShell wrappers plus the Pester test file;
- 1 supported manifest-driven operator, 3 compatibility-only non-write wrappers, and 19 fail-closed retired provider-write wrappers;
- canonical UTF-8/LF wrapper digests stable across Windows and Linux checkouts;
- one repository/Python/venv bootstrap for Python 3.11/3.12/3.13;
- exact request/manifest paths, raw-file SHA-256, exact project/snapshot/count confirmation, and strict JSON types;
- native exit-code handling and sanitized structured child evidence, never stdout-based success parsing;
- UTF-8 without BOM and atomic JSON replacement;
- no newest-file/`LastWriteTime`, user-home hardcode, or hidden nested PowerShell in the supported path;
- CI-prohibited apply and explicit `-EnableProviderWrites` gate;
- ambiguous nonzero outcomes remain `unknown_requires_reconciliation` and non-retry-safe;
- Python: `591 passed, 1 xfailed` on 3.11/3.12/3.13;
- Pester: `17/17` on Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux.

Provider writes during implementation/CI: 0.

## Active next work

### Wave 6 — stable versioned wave engine

Owner: issue #76.

Required outcomes:

- inventory every tracked Python wave/prepare/apply/recover/reconcile script and all callers;
- classify each as `supported_engine`, `compatibility_adapter`, `retired`, or `independent_tool`;
- fail CI when a wave executor is unclassified;
- one immutable versioned source/plan/apply/result/reconciliation contract;
- exact project/community/owner/snapshot/operation-set/policy/digest binding;
- deterministic operation ordering and exact bidirectional plan coverage;
- one supported Python API and CLI for `plan`, `preview`, `apply`, `reconcile`, and `result verify`;
- no private cross-script imports in supported paths;
- legacy adapters remain read-only;
- retired executors fail before credentials/provider dispatch;
- Wave 5 operator calls only the supported engine for apply-capable work;
- crash/replay and exact reconciliation tests;
- provider writes in development/CI: 0.

Exit criteria:

1. one focused branch and PR;
2. every historical generation classified and reference-scanned;
3. supported engine contracts versioned and self-digested;
4. exact-head Python and PowerShell CI green;
5. current state, register, changelog, and issue #64 synchronized after merge.

## Later waves

### Wave 7 — risk-based tests

- broader fault injection at mutation/journal boundaries;
- Windows encoding and process-exit integration tests;
- risk-specific coverage gates and order stability.

### Wave 8 — matching, catalog, and media correctness

- scalable exact-first matching;
- canonical text/URL normalization;
- authoritative media/cache/ffprobe validation;
- exact thumbnail/catalog postconditions.

### Wave 9 — finish live project queues separately

Only after required architecture and fresh read-only reconciliation:

- issue #31: long-form local result/ledger reconciliation;
- issues #32/#38: exact Clips/Shorts/video-type reconciliation;
- issue #33: verified catalog/publication planning;
- separate immutable manifests and canaries per project.

### Wave 10 — retirement and governance

- archive superseded scripts/wrappers/policies after reference proof;
- maintain supported/compatibility/retired registries;
- formal release, runbook, rollback, reconciliation, and provider-contract review rules.

## Independent cleanup track

Issue #37 owns only its exact reviewed cleanup scope. This backlog does not authorize bulk deletion.

## Definition of done

A code wave is complete only when:

- exact issue scope and non-goals are preserved;
- no unrelated provider mutation is included;
- exact-head CI is green on all supported runtimes;
- every ambiguous provider outcome remains fail closed and externally non-retryable;
- `current-state.md`, audit register, changelog, and issue state are synchronized;
- live canary work, when separately authorized, has exact before/after evidence and a safe recovery decision.
