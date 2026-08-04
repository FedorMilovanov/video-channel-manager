# Package A release checklist

This checklist governs the self-tested release of the Wave 9A/9B reconciliation runner and Wave 10 read-only control plane.

It does not authorize a live provider query or write.

## Scope gate

- [ ] The PR is based on the current verified `main`.
- [ ] Exactly one issue owns the Package A implementation scope.
- [ ] Issues #31, #32 and #38 remain owners of actual live conclusions.
- [ ] Long-form and Shorts/Clips remain separate input sets and outputs.
- [ ] Lord God and Legendary Poet identities are never mixed.
- [ ] VK Audio remains a separate archived/experimental system.

## Code boundary

- [ ] The supported entrypoint is `video-manager-package-a`.
- [ ] The CLI exposes no provider-write enable flag.
- [ ] Package A imports no provider writer, upload adapter, `WaveEngine`, or `WavePlan`.
- [ ] SQLite input uses `mode=ro`, `PRAGMA query_only = ON`, simple identifiers and a reviewed stage map.
- [ ] No table/column/status discovery heuristic exists.
- [ ] Every input path is relative to one explicit input root and bound by SHA-256.
- [ ] Every output is deterministic and its SHA-256 is recorded in `run-summary.json`.
- [ ] The HTML board is static and has no script, form or provider control.

## Reconciliation and recovery gate

- [ ] Stale, incomplete, cross-project and digest-tampered snapshots fail closed.
- [ ] Local records exactly and uniquely cover the bounded source set.
- [ ] `present`, `duplicate`, `missing`, `unknown` and `requires_attention` partition the source set.
- [ ] Accepted, processing, verified, intent-persisted and unknown outcomes never become replay authorization.
- [ ] Recovery decisions are limited to `no_action`, `reconcile_only`, `blocked` and `eligible_after_separate_review`.
- [ ] Every recovery item has `provider_write_authorized=false` and `automatic_execution=false`.
- [ ] Proven missing items require a later separate reviewed exact-ID plan.

## Archive and retirement gate

- [ ] `docs/history/operational-attempts/` contains only Markdown and JSON.
- [ ] No `.py`, `.ps1`, executable, ZIP, token, cookie, browser profile, media, mutable ledger or live snapshot is committed there.
- [ ] Historical source snapshots remain fenced documentation, not supported entrypoints.
- [ ] `retirement-registry-v1.json` marks V1/V2/V3/V4, “48 clips”, old long-form launchers and browser/internal-web VK Audio attempts non-executable.
- [ ] The archive import preserves exact Git blob content from superseded PR #85 without importing its old base.
- [ ] PR #85 may be closed only after the current-main archive replacement is merged and exact-head CI is green.

## CI gate

- [ ] The exact PR head is recorded.
- [ ] Dependency audit is green.
- [ ] Ruff correctness is green.
- [ ] Ruff formatting is green.
- [ ] strict mypy is green.
- [ ] Full pytest passes on Python 3.11, 3.12 and 3.13.
- [ ] PowerShell tests pass on Windows PowerShell 5.1, PowerShell 7 Windows and PowerShell 7 Linux.
- [ ] Provider queries performed by implementation/CI are `0`.
- [ ] Provider writes are `0`.
- [ ] Write plans created are `0`.

## Merge and state synchronization

- [ ] Head SHA is unchanged after CI.
- [ ] Changed-file scope is reviewed.
- [ ] Review threads are resolved or absent.
- [ ] Code/governance PR is merged with the exact expected head SHA.
- [ ] A separate narrow state-sync PR updates `AGENTS.md`, `current-state.md`, the machine register and operational-memory regression tests.
- [ ] Issue #109 is closed only after state sync.
- [ ] Issues #31, #32 and #38 remain open until actual fresh inputs are reconciled.
- [ ] Issue #64 records Package A completion and the remaining live-data dependency.

## Rollback

Because Package A performs no provider mutation, rollback is repository- and artifact-local:

1. Revert the Package A merge commit if the released contract is invalid.
2. Do not delete previously generated evidence; mark it superseded and retain its digests.
3. Restore the prior supported entrypoint registry.
4. Re-run exact-head CI.
5. Update canonical state and owning issues with the reason and replacement path.
6. Never use rollback as authority to replay any provider mutation.
