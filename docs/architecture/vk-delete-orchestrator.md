# Durable VK delete orchestrator

## Status

This module replaces the one-process-per-attempt `V1`–`V10` runners. It is deliberately built around **at-most-once mutation dispatch** and **asynchronous set reconciliation**.

The old invariant was invalid for VK:

```text
one video.delete response
→ immediate owner count - 1
→ attribute the count change to the last request
```

VK can expose late effects from earlier accepted requests, return a `count` that differs from visible paginated items, and return exact-ID shells that are not a reliable liveness signal. The orchestrator therefore never binds one global count transition to one mutation.

## Components

```text
signed policy + signed wall audit ZIP
                 │
                 ▼
        durable SQLite ledger (WAL)
                 │
        ┌────────┴────────┐
        ▼                 ▼
sequential dispatcher  set reconciler
        │                 │
        ▼                 ▼
video.delete once      stable owner ID sets
                          + exact protected fallbacks
                          + wall and album guards
```

### Dispatcher

For one operation the dispatcher:

1. validates the signed candidate and primary against a stable owner inventory;
2. validates zero engagement, view threshold, wall state and managed albums;
3. commits `DISPATCH_INTENT` in SQLite;
4. sends `video.delete` once;
5. records `ACCEPTED`, `UNKNOWN_OUTCOME` or `REJECTED_PERMANENT`;
6. never retries an accepted or unknown mutation automatically.

A crash after `DISPATCH_INTENT` cannot produce an automatic duplicate write. The operation is reconciled by observation.

### Reconciler

The reconciler reads two identical full owner-ID sets and checks all due operations together. If operations 30 and 31 become absent in the same observation, both are confirmed independently; no global `count - 1` arithmetic is used.

A candidate becomes `CONFIRMED_DELETED` only after two absent observations separated by the configured confirmation interval. The primary must remain present.

### Protected content

The signed source wall-audit ZIP supplies the complete original video set and full immutable guards. All non-candidate IDs are protected.

At each epoch:

- protected IDs must be present in the stable owner inventory;
- a protected ID omitted from pagination is checked through an exact lookup and must match its full signed guard;
- signed published and postponed wall attachments must still exist;
- primary immutable fields and managed memberships must still match.

The global owner `count` is retained only as diagnostic data.

## State machines

### Run

```text
created → validated → running → cooldown → reconciling
                                  │
                                  ├→ paused_transient → reconciling
                                  ├→ paused_fatal
                                  └→ completed / completed_with_quarantine
```

### Operation

```text
planned → prechecked → dispatch_intent
                          ├→ accepted
                          ├→ unknown_outcome
                          └→ rejected_permanent

accepted / unknown_outcome / dispatch_intent
  → waiting_visibility
  → observed_absent
  → confirmed_deleted
```

`manual_review` and `quarantined` are terminal, explicit states. Legacy V10 quarantine based on immediate count arithmetic is imported as `accepted`, not trusted as terminal.

## Epochs

Only one epoch is active. The first two epochs contain five operations; later epochs contain ten. A new epoch is not opened until the active epoch becomes terminal. The number of unresolved legacy operations is settled before new writes.

## Persistence

The dedicated SQLite ledger uses:

```text
PRAGMA journal_mode = WAL
PRAGMA synchronous = FULL
PRAGMA foreign_keys = ON
PRAGMA busy_timeout = 5000
```

Tables:

- `delete_runs`
- `delete_epochs`
- `delete_operations`
- `delete_attempts`
- `delete_observations`
- `delete_events`

Events form a SHA-256 hash chain. A lease and the existing filesystem VK write lock prevent two local writers.

## Safety boundary

The executable requires all of the following:

- `--execute`;
- `VCM_ALLOW_DESTRUCTIVE_OPERATIONS=true`;
- exact policy SHA confirmation;
- exact community confirmation;
- exact operation-count confirmation;
- signed policy and signed wall-audit ZIP validation;
- local per-community writer lock;
- durable SQLite lease.

Without `--execute`, the command performs only bootstrap/import/reconciliation.
