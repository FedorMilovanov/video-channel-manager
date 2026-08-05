# Operational automation backlog

Updated: 2026-08-05  
Program state: `WAVES_0_13_COMPLETED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES`

This backlog is subordinate to [`current-state.md`](current-state.md), the current v6 machine-state overlay, and immutable v5/v4/v3/v2 predecessors.

## Completed program foundation

- Waves 0–7: exact identity, durable mutation journals, upload/wall separation, guarded operator, versioned Wave Engine, and fault/corruption/replay proofs.
- Waves 8A–8F — completed exact matching, catalog/media/thumbnail correctness, and integration evidence.
- Wave 9 read-only contract — completed.
- Package A / Waves 9A–10 — completed immutable bounded reconciliation, recovery ledger, read-only operator board, runbook, rollback, and retirement.
- Wave 11 — completed package truth, repository acceptance, `filter=moder`, source-bound archive, and retired-package governance.
- Wave 12 — completed deterministic Windows handoffs and roadmap convergence.
- Wave 12A / #118 — completed project-bound ownership correction at `self_tested_project_bound_governance`.
- Wave 12B / #122 — completed one shared VK credential versus channel-specific YouTube OAuth aliases and stale issue reconciliation.
- Wave 12C / #126 — completed issue-contract convergence.
- Wave 13 / #127 — completed final evidence-backed operational closure through PR #128, merge `8d6a5ba243788e7b95b0e8a57eb02fb10eaf12ba`, exact head `731cc247a0c757c7103cd1ce5336adaf125d04d0`, CI `30992600857`, `792 passed, 1 xfailed`, provider queries/writes/plans `0/0/0`.

## Active backlog

None.

There is no active reconciliation, transfer queue, catalog wave, article-wall wave, playlist mutation design, cleanup, reset, recovery, or provider-mode research issue after the completed-state merge.

## Final issue dispositions

- #31 — long-form reconciliation: completed; exact Lord God queue `26/26`, missing `0`, thumbnails `26/26`.
- #119 — Shorts/Clips reconciliation: completed with a documented unsupported long scope; this does not claim all 56 are native Clips.
- #38 — shared VK native Clip/ordinary-video provider-mode: completed fail-closed contract.
- #32 — Shorts/Clips reconciliation: retired/not planned; non-authoritative Lord God 108-item auto-upload scope must not be replayed.
- #33 — catalog/publication continuation: retired/not planned.
- #99 — Legendary Poet article-wall launcher continuation: cancelled/not planned.
- #123 — YouTube playlist mutations: retired/not planned.

Do not group #32/#38 as Legendary Poet. Historically #32 belonged to Lord God, #38 was shared, and #119 belonged to Legendary Poet. Their closure reasons are preserved in v6.

## Credential and package boundary

VK has one shared user access token. Exact project/community/owner IDs select the target. YouTube OAuth alias `fedor-milovanov` belongs to Lord God and OAuth alias `legendary-poet` belongs to Legendary Poet.

Provider writes remain unauthorized. Every package remains non-authorizing unless a new explicit user request creates a new exact issue and separately reviewed immutable plan.

Never select artifacts by `LastWriteTime`, newest ZIP, broad wildcard, or remembered count. Never rerun retired launchers. Unknown outcomes remain non-replayable.

## Future work rule

This backlog is closed, not waiting. A future task starts as a new user-requested scope with a new project-bound issue; it must not reactivate a closed issue or historical executor.
