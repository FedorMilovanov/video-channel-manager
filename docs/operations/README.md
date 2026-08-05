# Operational documentation

Operational documents are living sources of truth. They override chat history, screenshots, remembered counts, retired ZIP packages, stale issue wording, and older audits.

## Start here

- [`project-identity-registry.md`](project-identity-registry.md) — exact projects, one shared VK credential, channel-specific YouTube aliases, numeric identities, routes, and no-mixing rules.
- [`current-state.md`](current-state.md) — final Waves 0–13 state and permanent safety boundaries.
- [`audit-register-v6-2026-08-05.json`](audit-register-v6-2026-08-05.json) — current final machine state with zero active operational issues.
- [`audit-register-v5-2026-08-05.json`](audit-register-v5-2026-08-05.json) — immutable Wave 13 disposition contract.
- [`audit-register-v4-2026-08-05.json`](audit-register-v4-2026-08-05.json) — immutable Wave 12B predecessor.
- [`audit-register-v3-2026-08-05.json`](audit-register-v3-2026-08-05.json) — immutable Wave 12A predecessor.
- [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json) — immutable complete historical source/finding ledger.
- [`automation-backlog.md`](automation-backlog.md) — closed backlog and future-work rule.
- [`final-operational-disposition-2026-08-05.md`](final-operational-disposition-2026-08-05.md) — human-readable final dispositions.
- [`master-audit-marathon-v2-2026-08-04.md`](master-audit-marathon-v2-2026-08-04.md) — canonical audit baseline and permanent finding history.
- [`../../.github/copilot-instructions.md`](../../.github/copilot-instructions.md) — deterministic Windows handoff contract.
- [`operational-artifact-standard.md`](operational-artifact-standard.md) — package/manifest/launcher/ledger requirements.
- [`operational-package-acceptance.md`](operational-package-acceptance.md) — truth levels and fail-closed acceptance.
- [`retirement-registry-v1.json`](retirement-registry-v1.json) — supported/compatibility/retired/historical execution boundaries.
- [`project-memory-changelog.md`](project-memory-changelog.md) — durable historical memory.

## Engineering and governance sequence

1. Waves 0–7 — completed.
2. Waves 8A–8F — completed.
3. Wave 9 read-only contract — completed.
4. Package A / Waves 9A–10 — completed.
5. Wave 11 — completed.
6. Wave 12 — completed.
7. Wave 12A / #118 — completed at `self_tested_project_bound_governance`.
8. Wave 12B / #122 — completed one-shared-VK-token semantics and stale issue reconciliation.
9. Wave 12C / #126 — completed issue-contract convergence.
10. Wave 13 / #127 — completed final evidence-backed operational closure.

Wave 13 proof:

- PR #128;
- exact head `731cc247a0c757c7103cd1ce5336adaf125d04d0`;
- merge/code baseline `8d6a5ba243788e7b95b0e8a57eb02fb10eaf12ba`;
- CI `30992600857`;
- `792 passed, 1 xfailed`;
- coverage `78%` across `14,306` statements;
- Ruff correctness and formatting green;
- strict mypy `145 source files`;
- all three PowerShell environments green;
- provider queries/writes/write plans `0/0/0`.

## Credential model

VK uses one shared user access token for both managed communities. The local VK alias `legendary-poet` is a stored credential name and never selects a project. Exact `project_key`, community ID, owner ID, manifests, plans, journals, results, and link profiles select and isolate the target.

YouTube aliases are channel-specific:

- OAuth alias `fedor-milovanov` → Lord God channel `UCeSJsC6go2c9pdJCuUI1BYA`;
- OAuth alias `legendary-poet` → Legendary Poet channel `UC-78ys2S3cQ3lpqgXfo-SvQ`.

## Final operational ownership and disposition

### Lord God / `lord-god-strength`

- #31 — long-form reconciliation: completed, exact queue `26/26`.
- #32 — Shorts/Clips reconciliation: retired/not planned; non-authoritative 108-item auto-upload scope remains non-replayable.
- #33 — catalog/publication continuation: retired/not planned.

Exact VK community/owner: `60805374` / `-60805374`.

### Legendary Poet / `legendary-poet`

- #119 — Shorts/Clips reconciliation: completed with documented unsupported long scope; not all 56 are proven native Clips.
- #99 — article-wall launcher continuation: cancelled/not planned.

Exact VK community/owner: `235216998` / `-235216998`.

### Shared and retired product scope

- #38 — shared VK native Clip/ordinary-video provider-mode: completed fail-closed contract; no project queue.
- #123 — YouTube playlist mutation design: retired/not planned.
- #64 — canonical roadmap closed by the completed-state merge.
- VK Audio — separate experimental system, not core-supported.

Do not group #32/#38 as Legendary Poet. Historical ownership was #32 Lord God, #38 shared, and #119 Legendary Poet. All are now closed.

Closed #2–#5, #37, #118, #122, and #126 remain historical and provide no execution authority. #37 completed a bounded 34-item cleanup while preserving post `12400`; its executor is retired.

## Final native Clip contract

Native Clip success requires:

1. exact final `type=short_video`;
2. processing complete;
3. `is_draft` absent or zero;
4. exact public visibility proof.

Ordinary `video`, duration, geometry, title, preview, player appearance, temporary processing state, or absence from ordinary `video.get` never proves native Clip identity. `M5hNecL_MsQ → -235216998_456239160` remains ordinary-video/draft evidence and is non-replayable. Automatic over-60-second native Clip publication is unsupported.

## Package and provider boundary

Provider writes remain unauthorized. Green CI proves contracts and fixtures, not permission to mutate a provider. Package A, acceptance reports, dashboards, previews, issue bodies, retained counts, ZIP names, transcript output, save responses, or visible objects never authorize writes.

Never rerun retired V1/V2/V3/V4, reset, recovery, cleanup, article-wave, transfer, or playlist executors. Never blind-retry accepted, processing, verified, or unknown operations. Existing remote objects remain untouched by the closure.

## Before any future provider write

A future operation requires all of:

1. a new explicit user request;
2. a new exact project-bound owning issue;
3. exact YouTube channel/OAuth alias and VK community/owner binding;
4. fresh bounded read-only preflight and reconciled unknown outcomes;
5. a reviewed immutable exact-ID plan with expected remote delta;
6. persisted intent, durable per-operation results, and exact postflight;
7. separate authorization for upload, Clip publication, catalog, metadata, thumbnail, or wall publication.

Closed issues and historical packages must not be reopened as execution authority.
