# Operational automation backlog

Updated: 2026-08-05  
Program state: `WAVES_0_12B_ENGINEERING_GOVERNANCE_COMPLETED_LIVE_RECONCILIATION_PENDING_NO_PROVIDER_WRITES`

This backlog is subordinate to [`current-state.md`](current-state.md), the canonical audit, the v4 machine-state overlay, and immutable v3/v2 predecessors.

## Completed program foundation

- Waves 0–7: exact identity, durable mutation journals, upload/wall separation, guarded operator, versioned Wave Engine, and fault/corruption/replay proofs.
- Audit A0 and Waves 8A–8F: authoritative ownership, exact matching, catalog/media/thumbnail correctness, and integration evidence.
- Wave 9 and Package A / Waves 9A–10: immutable bounded reconciliation, recovery ledger, read-only operator board, runbook, rollback, and retirement.
- Wave 11: operational-package truth, repository acceptance, `filter=moder`, source-bound incident archive, and retired package governance.
- Wave 12: deterministic Windows handoffs and roadmap convergence.
- Wave 12A: project-bound issue ownership correction.
- Wave 12B / #122: one shared VK credential versus channel-specific YouTube OAuth aliases; stale #2–#5 and completed #37 reconciled; PR #124 merged as `38296d07f8b6e948a6c5c4846bb66bf116bcfb72`, exact head `ffd275e9173db5a46bdde85f318dfa08ca83adb3`, CI `30988821430`, `789 passed, 1 xfailed`, provider queries/writes/plans `0/0/0`.

## Active read-only operational work

### #31 — Lord God long-form reconciliation

Binding: `lord-god-strength`, YouTube alias `fedor-milovanov`, channel `UCeSJsC6go2c9pdJCuUI1BYA`, VK community/owner `60805374` / `-60805374`.

Required: exact result JSON, SQLite ledger, exact run log, bounded source manifest, fresh YouTube/VK snapshots, Package A output, and no-blind-replay classification.

### #32 — Lord God Shorts/Clips reconciliation

Same project binding as #31. Required: exact source set; plan/result/journal/SQLite evidence; fresh ordinary-video and actual Clip snapshots; reconciliation of accepted/processing/unknown stages. Retained 108 and provisional 65/108 are historical. V1/V2/V3/V4 are retired.

### #119 — Legendary Poet Shorts/Clips reconciliation

Binding: `legendary-poet`, YouTube alias `legendary-poet`, channel `UC-78ys2S3cQ3lpqgXfo-SvQ`, VK community/owner `235216998` / `-235216998`.

Required: exact local runtime results/journals/ledgers, fresh YouTube Shorts plus VK ordinary/Clip snapshots, Package A evidence, and final native-Clip type proof. Retained `56 / 41 / 15 / 0`, “48 clips”, and old ZIPs are historical inputs only.

### #38 — shared provider-mode/final-type contract

Project-neutral and owns no queue. Requires current primary sources, versioned `external_embed` / `native_video` / `native_clip` modes, exact adapter evidence, one processed canary, final type readback, and unknown-outcome reconciliation.

## Later separately reviewed gates

### #33 — Lord God video catalog/publication

Blocked by #31/#32. Any future plan must be exact-ID, project-bound, separately authorized, and postflight-verifiable. VK Audio/MP3 and Legendary Poet are excluded.

### #99 — Legendary Poet article-wall

Separate from #119. Requires supported adapter readiness, published+postponed wall preflight, exact assets/text/schedule, one canary, durable results, and exact postflight.

## Deferred product scope

### #123 — YouTube playlist mutation contract

Deferred and unauthorized. Preserves playlist create/update, membership add/remove/reorder, and a generic guarded plan approval/execution lifecycle that was not implemented under superseded #4.

## Closed issue graph

- #2 and #5: completed;
- #3 and #4: superseded/not planned;
- #37: completed historical 34-item cleanup, protected post `12400` preserved, executor retired;
- #118: completed Wave 12A correction.

Closed issues do not authorize parallel execution or future broad cleanup.

## Permanent package and handoff rules

VK has one shared user token; exact project/community/owner selects the target. YouTube aliases remain channel-specific. Every package binds exact project/OAuth/community/owner/entrypoint, declares one evidence level, keeps `provider_writes_authorized=false` and `automatic_execution=false`, records durable per-operation results, and stops on unknown outcomes.

Every Windows handoff follows `.github/copilot-instructions.md`: self-contained PowerShell, exact paths, `-LiteralPath`, `Test-Path`, explicit extraction, full-path invocation, `$PSScriptRoot`, exact-one artifact, no `LastWriteTime`, newest ZIP, undefined variables, retired executor, or external provider client.

VK Audio remains separate and unsupported. Transcript/stdout success is not independently `batch_verified` without durable per-operation results and exact postflight.

## Definition of done

A wave closes only after focused scope, fail-closed evidence, exact-head six-job green CI, completed state sync, issue/roadmap updates, and preserved provider safety boundaries.
