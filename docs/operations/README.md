# Operational documentation

Operational documents are living sources of truth. They override chat history, screenshots, remembered counts, retired ZIP packages, stale issue wording, and older audits.

## Start here

- [`project-identity-registry.md`](project-identity-registry.md) — exact projects, one shared VK credential, channel-specific YouTube aliases, numeric identities, routes, and no-mixing rules.
- [`master-audit-marathon-v2-2026-08-04.md`](master-audit-marathon-v2-2026-08-04.md) — canonical audit baseline and permanent finding history.
- [`audit-register-v4-2026-08-05.json`](audit-register-v4-2026-08-05.json) — current Wave 12B machine state, credential model, active/deferred issue graph, and write prohibition.
- [`audit-register-v3-2026-08-05.json`](audit-register-v3-2026-08-05.json) — immutable Wave 12A predecessor overlay.
- [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json) — immutable complete historical source/finding ledger.
- [`current-state.md`](current-state.md) — completed Waves 0–12B, exact blockers, and next allowed work.
- [`automation-backlog.md`](automation-backlog.md) — active reconciliation, later gates, and deferred product scope.
- [`milestone-and-credential-reconciliation-2026-08-05.md`](milestone-and-credential-reconciliation-2026-08-05.md) — Wave 12B evidence for shared VK credential semantics and stale issue dispositions.
- [`../../.github/copilot-instructions.md`](../../.github/copilot-instructions.md) — deterministic Windows handoff contract.
- [`http-client-ownership.md`](http-client-ownership.md) — reusable-client ownership, retry authority, redaction, and limiter rules.
- [`lord-god-strength-description-profile.md`](lord-god-strength-description-profile.md) — exact Lord God identities and links.
- [`legendary-poet-description-profile.md`](legendary-poet-description-profile.md) — exact Legendary Poet identities and links.
- [`project-memory-changelog.md`](project-memory-changelog.md) — durable operational-memory changes.
- [`2026-07-31-youtube-vk-transfer-postmortem.md`](2026-07-31-youtube-vk-transfer-postmortem.md) — transfer lessons and root causes.
- [`operational-artifact-standard.md`](operational-artifact-standard.md) — package/manifest/launcher/ledger requirements.
- [`operational-package-acceptance.md`](operational-package-acceptance.md) — truth levels and fail-closed acceptance.
- [`retirement-registry-v1.json`](retirement-registry-v1.json) — supported/compatibility/retired/historical execution boundaries.

Historical baselines retained for evidence:

- [`master-audit-2026-08-04.md`](master-audit-2026-08-04.md);
- [`audit-register-2026-08-04.json`](audit-register-2026-08-04.json).

## Engineering sequence

1. Waves 0–7, Audit A0, and Waves 8A–8F — completed.
2. Wave 9 and Package A / Waves 9A–10 — completed read-only reconciliation foundation.
3. Wave 11 — completed package truth, acceptance, permission, archive, and retirement governance.
4. Wave 12 — completed deterministic Windows handoffs and roadmap convergence.
5. Wave 12A / #118 — completed project-bound ownership correction.
6. Wave 12B / #122 — completed one-shared-VK-token semantics and stale issue graph reconciliation. PR #124 merged as `38296d07f8b6e948a6c5c4846bb66bf116bcfb72`; exact head `ffd275e9173db5a46bdde85f318dfa08ca83adb3`; CI `30988821430`; `789 passed, 1 xfailed`; provider queries/writes/plans `0/0/0`.

## Credential model

VK uses one shared user access token for both managed communities. The local alias `legendary-poet` is a stored credential name and never selects a project. Exact `project_key`, community ID, owner ID, manifests, plans, journals, results, and link profiles select and isolate the target.

YouTube OAuth aliases remain channel-specific:

- `fedor-milovanov` → Lord God channel `UCeSJsC6go2c9pdJCuUI1BYA`;
- `legendary-poet` → Legendary Poet channel `UC-78ys2S3cQ3lpqgXfo-SvQ`.

## Correct operational ownership

### Lord God / `lord-god-strength`

- #31 — long-form reconciliation;
- #32 — Shorts/Clips reconciliation;
- #33 — later catalog/publication gate blocked by #31/#32.

Exact VK community/owner: `60805374` / `-60805374`.

### Legendary Poet / `legendary-poet`

- #119 — Shorts/Clips reconciliation;
- #99 — separate article-wall workflow.

Exact VK community/owner: `235216998` / `-235216998`.

### Shared and deferred

- #38 — shared VK native Clip/ordinary-video provider-mode and final-type contract; no queue ownership;
- #123 — deferred YouTube playlist mutation contract; no authorization;
- #64 — canonical roadmap;
- VK Audio — separate experimental system, not core-supported.

Closed #2–#5 and #37 are not active owners. #37 completed a bounded 34-item cleanup while preserving post `12400`; its historical executor is retired and grants no future bulk-cleanup authority.

Do not group #32/#38 as Legendary Poet. #32 is Lord God, #38 is shared, and #119 is the dedicated Legendary Poet owner.

## Evidence boundaries

Retained Lord God counts 26, 108, and provisional 65/108 are historical inputs. Retained Legendary Poet `56 / 41 / 15 / 0`, “48 clips”, and old ZIP labels are historical inputs. They are not fresh provider truth or final native-Clip proof.

Issue #38 requires current primary-source evidence, exact adapter request, a processed canary, and final type readback. Geometry, duration, title, player appearance, temporary type, or absence from ordinary `video.get` never proves native Clip identity.

Green CI proves contracts and fixtures, not current provider state. Package A, acceptance, handoff governance, issue wording, dashboards, previews, retained counts, or transcript-reported outcomes never authorize writes.

## Existing runbooks and templates

- [`unified-editorial-runbook.md`](unified-editorial-runbook.md)
- [`youtube-comment-publishing-runbook.md`](youtube-comment-publishing-runbook.md)
- [`vk-description-cleanup-runbook.md`](vk-description-cleanup-runbook.md)
- [`vk-catalog-wall-and-article-runbook.md`](vk-catalog-wall-and-article-runbook.md)
- [`run-report-template.md`](run-report-template.md)
- [`incident-report-template.md`](incident-report-template.md)
- [`decision-log-template.md`](decision-log-template.md)

Historical runbooks and executors are not automatically active. Current v4/v3/v2 state, retirement registry, roadmap #64, and the exact owning issue decide whether an entrypoint may be used.

## Before any provider write

1. Read `../../AGENTS.md`, `../../.github/copilot-instructions.md`, v4/v3/v2 state, and the exact owner issue.
2. Select exactly one project and bind exact YouTube channel/OAuth alias and VK community/owner.
3. Confirm required surface coverage, immutable manifest and SHA-256, local ledger/result paths, and unknown-outcome reconciliation.
4. Run bounded read-only preflight and repository acceptance; acceptance remains non-authorizing.
5. Use only a separately reviewed immutable exact-ID mutation plan with explicit expected remote delta.
6. Persist intent before dispatch; retain durable per-operation results; verify exact postflight.
7. Keep upload, native Clip publication, catalog, metadata, thumbnail, and wall publication separately authorized.

## After every wave or run

Update current state, the current versioned machine overlay without destroying predecessors, backlog, changelog, roadmap #64, exact owning issues, and regression coverage.
