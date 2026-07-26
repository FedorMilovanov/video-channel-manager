# Security and safety model

## Threats considered

- accidental mass edits;
- AI-generated or manually mistyped IDs;
- stale plans overwriting recent manual changes;
- duplicate uploads or playlist memberships;
- leaked OAuth credentials;
- destructive operations hidden among safe operations;
- replay of an already executed plan;
- provider API partial-update semantics erasing omitted fields.

## Controls in the foundation

- strict Pydantic models with unknown fields rejected;
- allowlisted operation enum;
- unique operation IDs;
- per-operation rationale and risk;
- destructive operations disabled by default;
- configurable maximum operations per plan;
- expected revisions required for existing-object mutations;
- plan preview separated from execution;
- secrets excluded from Git and exchange packages;
- operation and attempt persistence model;
- adapter boundaries that do not expose arbitrary HTTP calls to imported plans.

## Future execution controls

Before each remote mutation the executor must:

1. re-read the remote object;
2. compare the current revision with `expected_revision`;
3. check that the operation is still necessary;
4. calculate an idempotency key;
5. persist an attempt before calling the provider;
6. apply a complete provider-safe update payload;
7. re-read and verify the result;
8. persist response metadata without secrets.

Deletion will require both a global setting and an explicit interactive confirmation token.
