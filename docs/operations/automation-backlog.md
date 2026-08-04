# Operational automation backlog

Updated: 2026-08-04  
Program state: `WAVE_7_COMPLETED_WAVE_8_ACTIVE`

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

### Wave 7 — risk-based fault injection and mutation-boundary tests

Completed by PR #84, merge `df956bbbf19af6652f8711f95fb4fecf272e9951`, exact-head CI run `30918639372`:

- versioned inventory of all 15 supported mutation boundaries;
- AST discovery gate for unregistered/stale provider mutation markers;
- exact fault-proof register binding required stages to pytest node IDs and Pester `It` titles;
- exact equality gate between boundary and proof sets;
- 27 required cross-cutting corruption, migration, identity, bounded-read, operator, and replay scenarios;
- dependency-injected WaveEngine crash points with durable apply/reconciliation replay barriers;
- one-attempt ambiguous mutation proofs for VK upload/album/wall/text/thumbnail and YouTube comment/description boundaries;
- malformed/truncated/reordered/stale/wrong-digest/cross-project/wrong-owner/wrong-snapshot/wrong-policy/duplicate/incomplete evidence rejection;
- interrupted atomic-write and orphan-temp cleanup tests;
- bounded PowerShell child timeout, compatible process termination, concurrent stdout/stderr draining, and structured-result validation;
- Python: `657 passed, 1 xfailed` on 3.11/3.12/3.13;
- Pester: `25/25` on Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux.

Provider writes during implementation/CI: 0.

## Active next work

### Wave 8 — exact matching, catalog identity, and media correctness

Owner: issue #86.

Required outcomes:

- deterministic exact-first source/target matching with explicit ambiguous/conflict outcomes;
- fuzzy or weighted fallback only after exact evidence is exhausted and with retained scores/evidence;
- field-specific canonical text, Unicode, punctuation, whitespace, and URL normalization without collapsing distinct identities;
- exact album/catalog mapping rather than normalized-title-only selection;
- duplicate and renamed albums become explicit conflicts;
- semantic membership comparison ignores provider position churn;
- authoritative downloader final-path evidence rather than glob-first cache selection;
- cache binding to source ID, exact path, SHA-256, size, and structured media fingerprint;
- ffprobe-equivalent validation for duration, streams, codecs/container, playability, partial/corrupt/audio-only cases;
- exact local thumbnail identity and caller-owned selected-thumbnail postflight;
- provider writes in development/CI: 0.

Exit criteria:

1. exact-first matching is deterministic and conflict-explicit;
2. ambiguous normalized album titles cannot select a target;
3. media/cache reuse requires authoritative path and structured integrity evidence;
4. catalog/thumbnail postconditions are exact and machine-readable;
5. exact-head Python and PowerShell CI green;
6. current state, register, changelog, and issue #64 synchronized after merge.

Issue #33 remains the later catalog/publication workflow and is not authorized by Wave 8. It remains blocked by issues #31 and #32.

## Later waves

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