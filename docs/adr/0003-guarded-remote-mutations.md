# ADR 0003: Guarded remote mutations with immutable evidence

- Status: **Accepted**
- Date: **2026-07-25**
- Scope: YouTube and VK metadata/media mutations

## Context

Remote platforms expose APIs with different consistency, quota, normalization and failure behaviour. A successful HTTP response does not prove that the intended state became visible. Conversely, a revision or whole-record hash can drift even when the field under review has not changed.

The project also runs primarily on a Windows workstation and may have multiple PowerShell windows or agents working in separate Git worktrees. A correct remote mutation can therefore fail because of:

- two local writers targeting one channel/community;
- a manual Studio edit between audit and execute;
- server-side normalization or delayed visibility;
- partial batch completion;
- a crash after remote object reservation but before journal persistence;
- a stale, truncated or manually changed plan;
- an incomplete inventory caused by pagination;
- a media file that exists but lacks audio/video or is corrupt.

## Decision

Every nontrivial remote mutation follows this protocol:

```text
1. complete read-only snapshot
2. deterministic proposal
3. immutable, self-validating plan
4. human-readable diff
5. dry-run against live state
6. exact operator confirmations
7. per-target single-writer lock
8. complete re-preflight after lock acquisition
9. backup before first mutation
10. durable attempt journal before/after each transition
11. field-level postcondition verification
12. full-batch postflight
13. guarded rollback from known after to known before
14. immutable final result
```

### Plan identity

A plan contains:

- schema and policy version;
- source/live snapshot ID;
- exact target channel/community;
- complete target remote-ID coverage digest;
- operation before/after values and hashes;
- plan self-digest;
- explicit review-only exclusions.

Any mismatch blocks execution.

### Concurrency

The lock key is platform target identity, not repository path:

```text
youtube:<account>:<channel-id>
vk:<account>:<community-id>
```

Different platforms may write concurrently. Two writers for the same remote target may not.

On Windows, PID liveness must use non-destructive process query APIs. Unix `kill(pid, 0)` semantics must not be emulated with `os.kill(pid, 0)` on Windows.

### Idempotence

Every operation classifies live state as:

```text
expected before → ready
expected after  → already applied
anything else   → conflict
```

Whole-record revisions are advisory when unrelated fields can drift. The field being changed remains authoritative.

### Journal order

When an API reserves a remote object before the upload is complete, the reservation is journaled immediately:

```text
planned
→ upload_reserved
→ uploaded_processing
→ uploaded_and_verified
```

A retry reuses a visible reserved/journaled object whenever safely possible and never silently creates a duplicate.

### Media evidence

Before upload, the local file must pass:

- nonempty file check;
- SHA-256 calculation;
- ffprobe parse success;
- at least one video stream;
- at least one audio stream;
- positive duration.

The resulting fingerprint is part of the confirmed transfer manifest.

## Consequences

### Positive

- safe reruns and explicit conflicts;
- reversible metadata batches;
- reliable forensic history;
- protection against incomplete pagination and stale plans;
- no dependence on a single API success response;
- clearer separation between editorial review and execution;
- platform adapters can share safety invariants without sharing text formats.

### Negative

- more reads and slower execution;
- additional JSON artifacts and hashes;
- write commands require several exact confirmations;
- a newly added/removed video invalidates a whole-community plan;
- some failures require a fresh audit rather than an automatic continuation.

These costs are accepted because the project edits public channels and the expected batch sizes are moderate.

## Rejected alternatives

### Blind best-effort batch

Rejected: fast but cannot distinguish success, partial success, normalization and manual drift.

### Revision-only optimistic concurrency

Rejected: whole-record revisions change for unrelated fields and produce false conflicts.

### Rebuild every VK description from YouTube

Rejected: would overwrite manual VK-specific text and old links. Whole-library cleanup transforms the current live VK description instead.

### One global lock for all platforms

Rejected: unnecessarily blocks independent YouTube and VK work.

### Distributed queue immediately

Rejected: Celery/Redis/Temporal would add infrastructure without repairing missing idempotence or postconditions.

### Store only mutable state in JSON

Rejected for the long term: JSON is retained as immutable evidence, while a future SQLite ledger will manage mutable task state transactionally.

## Follow-up

- add SQLite operation ledger after current VK cleanup stabilizes;
- add dependency/secret scans in CI;
- add state-machine tests for upload and rollback transitions;
- introduce observability only after redacting token/content fields;
- keep all unattended remote writes disabled.
