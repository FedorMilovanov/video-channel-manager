# Operational documentation

Operational documents are living sources of truth. They override chat history, screenshots, remembered counts, retired ZIP packages, stale issue wording, old README/roadmap status blocks, and older audits.

## Start here

- [`project-identity-registry.md`](project-identity-registry.md) — exact projects, one shared VK credential, channel-specific YouTube aliases, numeric identities, routes, and no-mixing rules.
- [`current-state.md`](current-state.md) — final Waves 0–14 state and permanent safety boundaries.
- [`audit-register-v7-2026-08-05.json`](audit-register-v7-2026-08-05.json) — current machine state after repository-wide polish with projected zero open issues and PRs after the state-sync merge.
- [`audit-register-v6-2026-08-05.json`](audit-register-v6-2026-08-05.json) — immutable Wave 13 completed operational-graph contract.
- [`audit-register-v5-2026-08-05.json`](audit-register-v5-2026-08-05.json) — immutable Wave 13 disposition contract.
- [`audit-register-v4-2026-08-05.json`](audit-register-v4-2026-08-05.json) — immutable Wave 12B predecessor.
- [`audit-register-v3-2026-08-05.json`](audit-register-v3-2026-08-05.json) — immutable Wave 12A predecessor.
- [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json) — immutable complete historical source/finding ledger.
- [`automation-backlog.md`](automation-backlog.md) — closed backlog and future-work rule.
- [`repository-integrity-audit-2026-08-05.md`](repository-integrity-audit-2026-08-05.md) — Wave 14 stale-state and integrity findings.
- [`final-operational-disposition-2026-08-05.md`](final-operational-disposition-2026-08-05.md) — human-readable final dispositions.
- [`master-audit-marathon-v2-2026-08-04.md`](master-audit-marathon-v2-2026-08-04.md) — canonical audit baseline and permanent finding history.
- [`../../.github/copilot-instructions.md`](../../.github/copilot-instructions.md) — deterministic Windows handoff contract.
- [`operational-artifact-standard.md`](operational-artifact-standard.md) — package/manifest/launcher/ledger requirements.
- [`operational-package-acceptance.md`](operational-package-acceptance.md) — truth levels and fail-closed acceptance.
- [`retirement-registry-v1.json`](retirement-registry-v1.json) — supported/compatibility/retired/historical execution boundaries.
- [`project-memory-changelog.md`](project-memory-changelog.md) — durable historical memory.

## Engineering, governance, and polish sequence

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
11. Wave 13 completed-state sync — PR #129, merge `07388521e8d3a2c5d501382227c35bdce6e6470e`, CI `30994245235`, `796 passed, 1 xfailed`.
12. Wave 14 / #130 — completed repository-wide documentation and integrity polish.

Wave 14 proof:

- PR #131;
- exact head `80f701b6926a5a9c788b99c69634b54d63ed1862`;
- merge/code baseline `626f83c6e5c068d7faa8b6d14163b42916faa769`;
- CI `31000834701`;
- `801 passed, 1 xfailed`;
- coverage `78%` across `14,306` statements;
- Ruff correctness green and `451 files already formatted`;
- strict mypy `145 source files`;
- dependency audit: no known vulnerabilities;
- all three PowerShell environments green;
- changed files `7`, runtime/provider code files `0`;
- provider queries/writes/write plans/historical executor runs `0/0/0/0`.

Wave 14 removed stale initial-roadmap text, stale CI counts, and retired playlist scope from current-work language; made provider-write authorization boundaries prominent; added repository-wide JSON and local Markdown-link checks; and froze a wall-clock-sensitive test without changing production provider behavior.

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
- #64 — canonical roadmap completed; its closed metadata is refreshed after Wave 14 state sync.
- #130 — repository-wide polish completed through PR #131 and closed by the state-sync merge.
- VK Audio — separate experimental system, not core-supported.

Do not group #32/#38 as Legendary Poet. Historical ownership was #32 Lord God, #38 shared, and #119 Legendary Poet. All are now closed.

Closed #2–#5, #37, #118, #122, #126, and #127 remain historical and provide no execution authority. #37 completed a bounded 34-item cleanup while preserving post `12400`; its executor is retired.

## Final native Clip contract

Native Clip success requires:

1. exact final `type=short_video`;
2. processing complete;
3. `is_draft` absent or zero;
4. exact public visibility proof.

Ordinary `video`, duration, geometry, title, preview, player appearance, temporary processing state, or absence from ordinary `video.get` never proves native Clip identity. `M5hNecL_MsQ → -235216998_456239160` remains ordinary-video/draft evidence and is non-replayable. Automatic over-60-second native Clip publication is unsupported.

## Repository integrity and provider boundary

Every tracked JSON file must parse. Local Markdown links must resolve after fenced/inline code, anchors, external URLs, and explicit placeholders are excluded. README and security documents must distinguish implemented capability from current authorization. Wall-clock-sensitive tests must freeze their own test clock.

Provider writes remain unauthorized. Green CI proves contracts and fixtures, not permission to mutate a provider. Package A, acceptance reports, dashboards, previews, issue bodies, retained counts, ZIP names, transcript output, save responses, visible objects, README commands, or roadmap entries never authorize writes.

Never rerun retired V1/V2/V3/V4, reset, recovery, cleanup, article-wave, transfer, or playlist executors. Never blind-retry accepted, processing, verified, or unknown operations. Existing remote objects remain untouched by Waves 13–14.

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
