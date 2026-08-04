# Stable versioned wave engine contract

Updated: 2026-08-04
Owner: Wave 6 / issue #76

## Supported surface

The supported orchestration surface is the package:

```text
video_channel_manager.wave_engine
```

and its CLI namespace:

```text
video-manager wave
```

The supported commands are:

- `wave source verify`;
- `wave plan build`;
- `wave plan validate`;
- `wave preview`;
- `wave apply`;
- `wave reconcile`;
- `wave result verify`;
- `wave result verify-reconciliation`.

The PowerShell operator may route provider-mutating manifests only to a complete `wave apply` invocation containing exact `--source`, `--plan`, `--intent`, `--repository-root`, and `--enable-provider-writes` arguments. Historical Python executors may not be selected as an alternative apply route.

## Versioned evidence

Wave 6 defines immutable schema version 1 documents for:

- source evidence;
- deterministic plan;
- apply intent;
- result;
- reconciliation request;
- reconciliation result.

Every document is strict, rejects extra fields, and carries a canonical SHA-256 self-digest. Numeric strings are not accepted for project IDs, counts, or sequence numbers.

Project identity is hard-bound:

- `legendary-poet` → community `235216998`, owner `-235216998`;
- `lord-god-strength` → community `60805374`, owner `-60805374`.

Source evidence contains a sorted unique list of exact repository-relative artifact paths and raw-file SHA-256 values. Its `source_snapshot_id` is derived deterministically from the project, policy version, and artifact list. `source verify`, `plan build`, and engine apply all re-hash the referenced files; agreement between two stale JSON documents is not sufficient.

Each operation specification includes an explicit unique `order_key`. The engine sorts by that key before assigning contiguous sequence values. Each operation identity includes its exact project, source snapshot, policy version, order key, sequence, operation kind, mutation class, and canonical JSON payload. Plans require exact ordering, unique operation IDs, an operation-set digest, and a plan self-digest.

## Apply and unknown outcomes

An apply intent repeats the exact:

- source-evidence path, raw-file SHA-256, and self-digest;
- plan path, raw-file SHA-256, and self-digest;
- project/community/owner;
- source snapshot;
- operation count;
- operation-set digest;
- provider-write confirmation.

The engine rejects paths outside the declared repository root, changed source artifacts, changed source/plan evidence, and any pre-existing journal directory. An old or partial journal is reconciliation evidence, never automatic replay authority.

Before each adapter call the engine commits atomic UTF-8 stages for `intent_committed` and `dispatch_started`; after a known result it commits `result_committed`. Every operation receives at most one adapter call.

For an ambiguous mutation:

- provider writes require the signed intent confirmation, runtime confirmation, and a non-CI environment;
- a known rejection before dispatch may be retry-safe;
- an unknown or unclassified post-dispatch failure becomes `unknown_requires_reconciliation`;
- `attempt_count` is exactly `1`;
- dispatched ambiguous outcomes are never retry-safe;
- subsequent operations are `not_attempted`;
- no automatic replay occurs.

Result validation derives the allowed overall status from the operation statuses, rejects safe-read `unknown` outcomes, rejects dispatched ambiguous failures presented as ordinary retryable failures, and requires exact ordered operation coverage.

Production provider adapters are not registered by this wave. The CLI validates exact documents and fails closed for `apply` and `reconcile` until a reviewed dependency-injected adapter is connected. Tests use fakes only.

## Reconciliation

A reconciliation request binds the exact plan digest, result digest, project, source snapshot, and ordered SHA-256 operation IDs that are currently `unknown_requires_reconciliation`. A reconciliation result must exactly cover that request with `reconciled` operations. Existing reconciliation output is never overwritten.

Reconciliation uses exact remote identity and expected-delta evidence through a dependency-injected adapter. It does not retransmit the original mutation.

## Historical executor registry

`scripts/wave-executors.json` binds every tracked Python file under `scripts/` to:

- canonical UTF-8/LF SHA-256;
- one status: `supported_engine`, `compatibility_adapter`, `retired`, or `independent_tool`;
- direct-entrypoint status;
- provider-write capability;
- project ownership;
- known callers and private imports.

The current reviewed surface contains:

- 26 `retired` direct provider-write executors;
- 29 `compatibility_adapter` modules/read-only recovery paths;
- 36 `independent_tool` audit/build/verify utilities;
- the supported engine under `src/video_channel_manager/wave_engine`.

Retired direct executors remain importable for parity fixtures, but direct execution stops before historical credential, child-process, or provider-write authority. Historical files are not deleted until reference and parity evidence permits archival.

## CI boundary

CI verifies:

- every Python script is uniquely classified;
- every registry digest matches canonical LF text;
- every retired direct executor has an early guard;
- supported engine modules import no historical `scripts` modules;
- private cross-script imports are confined to compatibility adapters;
- deterministic source snapshots and operation ordering;
- source-artifact and evidence-file tamper rejection;
- exact plan/apply/result/reconciliation coverage;
- journal replay rejection and one-attempt ambiguous outcomes;
- atomic UTF-8 evidence;
- CLI build/validate/preview/verify behavior;
- PowerShell provider mutation routing only through the complete `wave apply` contract.

Development and CI perform zero VK or YouTube provider writes.
