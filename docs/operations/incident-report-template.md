# Operational incident report

Date/time:
Operator:
Operation:
Mode: read-only / dry-run / canary / execute

## Identities

- Source platform/channel ID:
- Source canonical URL:
- Target platform/community ID:
- Target canonical URL:
- Account alias:

## Immutable inputs

- Manifest path:
- Manifest SHA-256:
- Source snapshot ID/SHA-256:
- Target snapshot ID/SHA-256:

## Expected behavior

- Intended operation count:
- Covered surfaces:
- Explicitly excluded surfaces:
- Expected ledger path:
- Expected result path:

## Observed behavior

- Last successful stage:
- Exact error text:
- Attempted:
- Accepted:
- Processing:
- Verified:
- Rejected:
- Unknown:

## Safety assessment

- Could remote bytes have been accepted before the failure?
- Is automatic retry safe?
- Which exact IDs require reconciliation?
- Was any unrelated surface affected?

## Evidence

- Log path:
- Ledger path:
- Result path:
- Provider response artifact:
- Screenshot or UI evidence:

## Root cause

State the direct cause and the underlying design/process cause separately.

## Corrective action

- Immediate recovery:
- Code or documentation fix:
- Regression test:
- New permanent rule:

## Current state update

Record the exact changes made to `docs/operations/current-state.md`.
