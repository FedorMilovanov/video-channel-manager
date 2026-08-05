# Operational documentation

Operational documents are living sources of truth. They take priority over chat history, screenshots, remembered counts, retired ZIP packages, stale issue wording, and older audits.

## Start here

- [`project-identity-registry.md`](project-identity-registry.md) — two separate projects, OAuth aliases, exact numeric identities, routes, and no-mixing rules.
- [`master-audit-marathon-v2-2026-08-04.md`](master-audit-marathon-v2-2026-08-04.md) — canonical audit baseline and permanent finding history.
- [`audit-register-v3-2026-08-05.json`](audit-register-v3-2026-08-05.json) — compact current machine state and exact operational ownership.
- [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json) — immutable complete predecessor source/finding ledger.
- [`current-state.md`](current-state.md) — exact current identities, completed work, blockers, and next allowed work.
- [`automation-backlog.md`](automation-backlog.md) — current operational owners and dependencies.
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

1. **Waves 0–7 — completed.** Identity, lifecycle, HTTP, upload/wall separation, operator, Wave Engine, and fault/replay proofs.
2. **Audit A0 — completed.** Authoritative audit/register ownership synchronized.
3. **Waves 8A–8F — completed.** Exact matching, canonical/catalog/media/thumbnail correctness and integration proof.
4. **Wave 9 read-only contract — completed.** Bounded immutable reconciliation input and classifications.
5. **Package A — completed at `read_only_package_self_tested`.** Reconciliation runner, recovery ledger, operator board, runbook/rollback/governance.
6. **Wave 11 — completed at `self_tested_source_bound_governance`.** Package truth, acceptance, permission regression, incident archive, retirement.
7. **Wave 12 — completed at `self_tested_repository_governance`.** Deterministic Windows handoffs and roadmap convergence.
8. **Wave 12A / #118 — active correction.** Repair stale issue ownership discovered by reading actual issue bodies; provider queries/writes/plans remain zero.

## Correct operational ownership

### Lord God / `lord-god-strength`

- #31 — long-form reconciliation;
- #32 — Shorts/Clips reconciliation;
- #33 — later catalog/publication gate blocked by #31 and #32.

Exact identity:

- YouTube `UCeSJsC6go2c9pdJCuUI1BYA`;
- OAuth alias `fedor-milovanov`;
- VK community `60805374`;
- VK owner `-60805374`.

### Legendary Poet / `legendary-poet`

- #119 — Shorts/Clips reconciliation;
- #99 — separate article-wall scheduling workflow.

Exact identity:

- YouTube `UC-78ys2S3cQ3lpqgXfo-SvQ`;
- OAuth alias `legendary-poet`;
- VK community `235216998`;
- VK owner `-235216998`.

### Shared/separate owners

- #38 — shared VK native Clip/ordinary-video provider-mode and final-type contract; no project queue ownership;
- #37 — independent exact reviewed cleanup only;
- #64 — canonical roadmap;
- VK Audio — separate experimental system, not core-supported.

Do not group #32/#38 as Legendary Poet. #32 is Lord God; #38 is shared; #119 is the dedicated Legendary Poet queue owner.

Green CI proves contracts and fixtures, not current provider state. Provider writes remain unauthorized by Package A, acceptance, handoff governance, issue wording, dashboards, previews, retained counts, or transcript-reported outcomes.

## Retained inputs are not fresh truth

Lord God retained inputs include long-form count 26 and Shorts source count 108. Legendary Poet retained inputs include `56 / 41 / 15 / 0` and `BXZeRiEOHmQ → -235216998_456239039`. Historical “48 clips”, Lord God provisional 65/108 missing lists, and all old package counts require fresh reconciliation.

## Shared Clip-mode evidence

Issue #38 must retain current primary-source evidence and exact canary/final-type proof. Historical duration claims conflict between 60 and 180 seconds and do not form a stable contract. Geometry, duration, player appearance, title, temporary processing type, or absence from ordinary `video.get` never proves native Clip identity.

## Separate VK Audio boundary

Browser/internal-web VK Audio experiments are not a supported part of the core YouTube→VK Video engine. Do not continue them as production automation until a reviewed adapter defines versioned schemas, exact per-item ledger, session boundary, upload-ticket validation, identity, deadlines, reconciliation, canary, and postflight.

## Link and identity audits

- [`project-link-audit-20260801.md`](project-link-audit-20260801.md) — public/compatibility/admin routes and remaining synchronization.

## Templates

- [`run-report-template.md`](run-report-template.md)
- [`incident-report-template.md`](incident-report-template.md)
- [`decision-log-template.md`](decision-log-template.md)

## Existing runbooks

- [`unified-editorial-runbook.md`](unified-editorial-runbook.md)
- [`youtube-comment-publishing-runbook.md`](youtube-comment-publishing-runbook.md)
- [`vk-description-cleanup-runbook.md`](vk-description-cleanup-runbook.md)
- [`vk-catalog-wall-and-article-runbook.md`](vk-catalog-wall-and-article-runbook.md)

Historical runbooks and executors are not automatically active. Current state, v3/v2 registers, retirement registry, roadmap #64, and the exact project-bound issue decide whether an entrypoint may be used.

## Before any provider write

1. Read `../../AGENTS.md` and `../../.github/copilot-instructions.md`.
2. Read the audit, current v3 overlay, immutable v2 register, and current state.
3. Select exactly one project and exact owning issue.
4. Confirm YouTube channel, OAuth alias, VK community, and owner all belong to that project.
5. Confirm inventory coverage for the required provider surface.
6. Validate immutable manifest and SHA-256.
7. Run operational-package acceptance and confirm `provider_writes_authorized=false` / `automatic_execution=false`.
8. Run bounded read-only preflight.
9. Confirm ledger, per-operation result paths, and unknown-outcome reconciliation.
10. Confirm no intent-persisted, accepted, processing, verified, or unknown mutation is being retransmitted.
11. Use a separately reviewed exact-ID mutation plan and expected remote delta.
12. Keep video upload, Clip publication, catalog, metadata, thumbnail, and wall operations separately authorized and evidenced.
13. Execute only through the registered repository-owned operator/adapter.

Validate each user-facing ZIP with the exact reviewed filename:

```powershell
python -m video_channel_manager.tools.operational_package_acceptance `
  C:\Users\Fedor\Downloads\EXACT-PACKAGE.zip `
  --entrypoint run-operation.ps1 `
  --require manifest.json `
  --require README.txt `
  --require SHA256SUMS.txt `
  --require-flat
```

A passing result never authorizes provider writes.

## After every wave or run

1. Write a run/incident/decision report.
2. Update current state with exact project, provider IDs, timestamp, manifest digest, state counts, evidence paths, and safe-resume status.
3. Update the v3 overlay without destroying the v2 ledger.
4. Append project-memory changelog.
5. Update #64, the exact owning issue, and the PR.
6. Add regression coverage for every identity, provider, packaging, state, archive, governance, or handoff defect.
