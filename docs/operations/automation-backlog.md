# Operational automation backlog

Updated: 2026-08-04  
Program state: `WAVE_6_COMPLETED_WAVE_7_ACTIVE`

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
- fail-closed historical journal migration;
- postponed-only wall publication and exact ambiguous-response reconciliation;
- `586 passed, 1 xfailed` on Python 3.11/3.12/3.13.

Provider writes during implementation/CI: 0.

### Wave 5 — reliable Windows/PowerShell operator layer

Completed by PR #75, merge `1a62779293a404e4654b6230644dfc78e9b20dc1`, exact-head CI run `30900532613`:

- 1 supported manifest-driven operator, 3 compatibility-only non-write wrappers, and 19 fail-closed retired provider-write wrappers;
- canonical wrapper SHA-256 stable across CRLF/LF;
- one repository/Python/venv bootstrap;
- exact request/manifest/project/snapshot/count/type confirmation;
- native exit codes and atomic UTF-8 structured evidence;
- no newest-file selection, user-home hardcode, or hidden nested PowerShell in the supported path;
- CI-prohibited apply and explicit provider-write switch;
- Python: `591 passed, 1 xfailed` on 3.11/3.12/3.13;
- Pester: `17/17` on Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux.

Provider writes during implementation/CI: 0.

### Wave 6 — stable versioned wave engine

Completed by PR #78, merge `c4c4d3233ec20b8f939343c5d667d8687d7ff040`, exact-head CI run `30908185487`:

- strict immutable v1 source/plan/apply/result/reconciliation schemas;
- exact project/community/owner/source/policy/file/operation-set/self-digest binding;
- deterministic ordered operation identities and exact result coverage;
- atomic preflight, operation journal, result, and reconciliation evidence;
- existing journals block automatic replay;
- ambiguous mutations remain one-attempt, non-retry-safe, and reconciliation-required when unknown;
- all 91 Python scripts classified and canonical-SHA-bound;
- 26 direct provider-write executors retired before functions, credentials, paths, or dispatch;
- historical private imports confined to compatibility adapters;
- supported engine has no historical `scripts.*` imports;
- Wave 5 provider mutations restricted to the complete Wave 6 `wave apply` contract;
- no implicit production provider adapter in the CLI;
- Python: `611 passed, 1 xfailed` on 3.11/3.12/3.13;
- Pester: `20/20` on Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux.

Provider writes during implementation/CI: 0.

## Active next work

### Wave 7 — risk-based fault injection and mutation-boundary tests

Owner: issue #80.

Required outcomes:

- inventory every supported mutation boundary and bind it to owning fault/replay tests;
- inject deterministic failures before/after intent, dispatch, provider acceptance, response persistence, processing, postflight, result commit, and reconciliation;
- prove ambiguous mutations are attempted at most once under every tested crash path;
- prove safe reads retry only through the classified bounded policy;
- reject truncated, malformed, stale, reordered, cross-project, wrong-owner, wrong-snapshot, wrong-policy, wrong-digest, duplicate, and incomplete evidence;
- test interrupted atomic writes, orphan temporary files, existing journals, and partial historical migration;
- expand Windows PowerShell 5.1/7 tests for child nonzero, missing/malformed result, encoding, unsupported Python, interrupted child, CI apply block, and unknown mutation result;
- introduce a machine-readable mutation-boundary registry and risk-specific test gate;
- provider writes in development/CI: 0.

Exit criteria:

1. every supported mutation boundary has an owned deterministic fault test;
2. no ambiguous provider mutation can be replayed by a tested crash path;
3. corrupted/stale/cross-project evidence fails closed;
4. exact-head Python and PowerShell CI green;
5. current state, register, changelog, and issue #64 synchronized after merge.

## Later waves

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
- separate immutable Wave 6 manifests and canaries per project.

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
