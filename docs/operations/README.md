# Operational documentation

Operational documents are living sources of truth. They take priority over chat history, screenshots, and remembered counts.

## Start here

- [`project-identity-registry.md`](project-identity-registry.md) — the two separate projects, their verified links, YouTube OAuth aliases, shared VK token model, exact numeric identities, public/admin route separation, and no-mixing rules.
- [`master-audit-2026-08-04.md`](master-audit-2026-08-04.md) — canonical synthesis of the audit marathon, active/retracted/disputed findings, system boundaries, wave order, and acceptance gates.
- [`audit-register-2026-08-04.json`](audit-register-2026-08-04.json) — machine-readable finding status, severity, owner issue, and target wave.
- [`current-state.md`](current-state.md) — selected project, exact current identities, completed work, active blockers, separate project queues, and the next allowed work.
- [`lord-god-strength-description-profile.md`](lord-god-strength-description-profile.md) — exact identities, links, footer rules, and guards for Господь Бог — Сила Моя.
- [`legendary-poet-description-profile.md`](legendary-poet-description-profile.md) — exact identities, links, footer rules, VK Clips route, author-cabinet separation, and guards for The Legendary Poet.
- [`project-memory-changelog.md`](project-memory-changelog.md) — dated changes to durable operational memory.
- [`2026-07-31-youtube-vk-transfer-postmortem.md`](2026-07-31-youtube-vk-transfer-postmortem.md) — what succeeded, what failed, root causes, and permanent lessons.
- [`operational-artifact-standard.md`](operational-artifact-standard.md) — required structure and verification for ZIP packages, manifests, launchers, ledgers, retries, and handoffs.
- [`automation-backlog.md`](automation-backlog.md) — wave-aligned implementation backlog and issue dependencies.

## Current engineering sequence

1. Wave 0 canonical-state baseline — documentation and issue graph only, no provider writes.
2. Issue #65 — journaled VK upload state machine and recovery.
3. Issue #64 — Waves 2–10 reliability roadmap.
4. Issues #31/#32/#36/#38 — exact live reconciliation only after the required core gates.
5. Issue #33 — catalog and publishing after all dependency unknowns are resolved.

Do not begin from a retired ZIP, historical executor, old numeric matrix, or chat-only instruction.

## Link and identity audits

- [`project-link-audit-20260801.md`](project-link-audit-20260801.md) — verified public routes, compatibility routes, operational/admin routes, resolved inconsistencies, and remaining implementation synchronization.

## Templates

- [`run-report-template.md`](run-report-template.md) — record successful and partially successful operational runs.
- [`incident-report-template.md`](incident-report-template.md) — capture failures, reconciliation risk, root cause, and corrective action.
- [`decision-log-template.md`](decision-log-template.md) — record high-impact decisions, alternatives, evidence, and guardrails.

## Existing runbooks

- [`unified-editorial-runbook.md`](unified-editorial-runbook.md)
- [`youtube-comment-publishing-runbook.md`](youtube-comment-publishing-runbook.md)
- [`vk-description-cleanup-runbook.md`](vk-description-cleanup-runbook.md)
- [`vk-catalog-wall-and-article-runbook.md`](vk-catalog-wall-and-article-runbook.md)

Historical runbooks and executors are not automatically active. `current-state.md` and the master audit decide whether an entrypoint may still be used.

## Before any provider write

1. Read `../../AGENTS.md`.
2. Read the master audit and machine finding register.
3. Read `current-state.md` and confirm that the intended wave permits a provider write.
4. Select exactly one `project_key` from `project-identity-registry.md`.
5. Read the matching project-specific description profile.
6. Confirm exact YouTube channel ID and VK community/owner IDs.
7. Confirm the inventory covers the intended provider surface.
8. Validate that every project/footer link belongs to the selected project's link profile.
9. Keep public links separate from operational/admin URLs.
10. Validate the immutable manifest and SHA-256.
11. Run the operational bundle verifier.
12. Run read-only preflight or dry-run.
13. Confirm ledger and result paths.
14. Confirm unknown-outcome reconciliation behavior.
15. Confirm that no accepted, processing, or unknown mutation is being retransmitted.

Validate every user-facing operational ZIP before handoff:

```powershell
python .\scripts\verify_operational_bundle.py `
  .\path\package.zip `
  --entrypoint run-operation.ps1 `
  --require executor.py `
  --require manifest.json `
  --require README.txt `
  --require SHA256SUMS.txt `
  --require-flat
```

The verifier checks archive structure, exact entrypoints, required files, path traversal, nested roots, PowerShell self-location, secret-like filenames and manifest fields, CRC, and listed SHA-256 values.

## After every wave or run

1. Write a run report, incident report, or architecture decision as appropriate.
2. Update `current-state.md` with exact repository baseline, selected project, provider IDs, timestamp, manifest digest, state counts, result and ledger paths, remaining work, and whether resume is safe.
3. Update `audit-register-2026-08-04.json` when a finding changes state or ownership.
4. Append `project-memory-changelog.md`.
5. Update the owning GitHub issue and PR.
6. Add or update a regression test when the work exposed a tooling, identity, link-profile, state-machine, provider-contract, wrapper, or packaging defect.
