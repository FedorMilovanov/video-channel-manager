# Svodka provider outcome recovery design — 2026-08-08

Purpose: preserve the exact structured provider result when a Telegram send has completed but a later durable-state write may fail.

## Failure boundary

The existing publisher already persists dispatch intent before a Telegram mutation. If provider effect is ambiguous, blind retry is forbidden.

A second failure boundary exists after the provider call: `send-once` may have produced a complete structured outcome while the later state-branch commit or push fails. In that case the persisted intent remains safely blocking, but runner-local outcome evidence should not be the only copy of the provider result.

## Recovery model

Canary and scheduled writers attempt to archive `.runtime/svodka-outcome.json` as a run/attempt-scoped GitHub Actions artifact immediately after the send step and before final ledger persistence.

The state branch remains the primary durable publication record. Artifact storage is a recovery copy, not an alternate ledger and not a second provider path.

A manual provider-free recovery workflow may consume an archived outcome only when all of these are proven:

- exact approved release digest and publication id;
- exact persisted dispatch run id and attempt;
- source run is a recognized Svodka canary or scheduled publisher run from `main`;
- source event matches that workflow contract;
- source run head SHA matches persisted dispatch provenance;
- durable intent step succeeded;
- provider send step completed;
- outcome artifact step succeeded;
- final state-persistence step did not already succeed;
- exactly one matching artifact exists and is not expired;
- artifact metadata carries the exact source workflow-run id/head SHA and a sha256 artifact digest;
- downloaded outcome parses as the immutable provider-outcome schema;
- outcome publication id and provider-payload digest match the persisted dispatch exactly.

Only after those checks is the existing state `apply-outcome` transition used. Recovery performs no Telegram provider read or write.

A recovered `may_exist` outcome remains blocking/unknown. Recovery is evidence restoration, never permission to retry an ambiguous mutation.

## GitHub Actions artifact references

Primary documentation reviewed for the implementation:

- https://docs.github.com/en/rest/actions/artifacts
- https://docs.github.com/en/rest/actions/workflow-runs
- https://github.com/actions/upload-artifact
- https://github.com/actions/download-artifact

The artifact copy is retained for 30 days for the short Svodka pilot/recovery horizon.

## Current activation boundary

This design does not activate Svodka. Profile write authorization, approved release, initialized ledger and verified manual canary remain independent required gates.