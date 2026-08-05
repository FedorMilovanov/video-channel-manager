# Security and safety model

## Current authorization boundary

Provider writes, replay, deletion, and mutation plans are currently unauthorized. Green CI, package names, previews, dry-runs, dashboards, issue text, retained counts, or historical executors never grant execution authority.

The canonical operational boundary is [`operations/current-state.md`](operations/current-state.md). Any future provider mutation requires a new explicit user request, a new exact project-bound issue, a reviewed immutable exact-ID plan, and separate authorization.

## Threats considered

- accidental mass edits;
- AI-generated or manually mistyped IDs;
- stale plans overwriting recent manual changes;
- duplicate uploads or playlist memberships;
- leaked OAuth credentials;
- destructive operations hidden among safe operations;
- replay of an already executed or unknown operation;
- provider API partial-update semantics erasing omitted fields;
- treating HTTP success, preview output, or visible UI state as a verified postcondition;
- mixing Lord God and Legendary Poet identities, OAuth aliases, manifests, ledgers, or evidence.

## Controls in the foundation

- strict Pydantic models with unknown fields rejected;
- allowlisted operation enum;
- unique operation IDs;
- per-operation rationale and risk;
- destructive operations disabled by default;
- configurable maximum operations per plan;
- exact project/channel/community binding;
- expected revisions and exact-before values for existing-object mutations;
- plan preview separated from execution;
- secrets excluded from Git and exchange packages;
- persisted intent, operation, attempt, and reconciliation state;
- single-writer locks and locked re-preflight;
- adapter boundaries that do not expose arbitrary HTTP calls to imported plans;
- unknown outcomes classified as non-replayable until reconciled;
- exact provider readback required for success.

## Mandatory controls for any future explicitly authorized mutation

Before each remote mutation the executor must:

1. bind the exact project, account alias, channel/community, owner, manifest, and operation class;
2. re-read the complete relevant provider surface;
3. reconcile intent-persisted, accepted, processing, verified, failed, and unknown prior outcomes;
4. compare current state with the reviewed exact-before state;
5. check that the operation is still necessary and unambiguous;
6. calculate and persist an idempotency key and mutation intent before dispatch;
7. acquire the exact target lock and repeat preflight after the lock;
8. apply a complete provider-safe update payload exactly once;
9. persist response metadata without secrets;
10. re-read and verify the exact remote effect;
11. persist a durable per-operation result and bounded batch postflight.

A timeout or lost response after dispatch is an unknown outcome, not a retry signal. Deletion additionally requires a dedicated policy gate, exact target inventory, explicit interactive confirmation, and verified rollback or recovery evidence.
