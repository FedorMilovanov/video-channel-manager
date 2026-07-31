# Operational documentation

Operational documents are living sources of truth. They take priority over chat history, screenshots, and remembered counts.

## Start here

- [`current-state.md`](current-state.md) — exact current identities, counts, paths, completed work, active work, blocked work, and required next actions.
- [`project-memory-changelog.md`](project-memory-changelog.md) — dated changes to durable operational memory.
- [`2026-07-31-youtube-vk-transfer-postmortem.md`](2026-07-31-youtube-vk-transfer-postmortem.md) — what succeeded, what failed, root causes, and permanent lessons.
- [`operational-artifact-standard.md`](operational-artifact-standard.md) — required structure and verification for ZIP packages, manifests, launchers, ledgers, retries, and handoffs.

## Templates

- [`run-report-template.md`](run-report-template.md) — record successful and partially successful operational runs.
- [`incident-report-template.md`](incident-report-template.md) — capture failures, reconciliation risk, root cause, and corrective action.
- [`decision-log-template.md`](decision-log-template.md) — record high-impact decisions, alternatives, evidence, and guardrails.

## Existing runbooks

- [`unified-editorial-runbook.md`](unified-editorial-runbook.md)
- [`youtube-comment-publishing-runbook.md`](youtube-comment-publishing-runbook.md)
- [`vk-description-cleanup-runbook.md`](vk-description-cleanup-runbook.md)
- [`vk-catalog-wall-and-article-runbook.md`](vk-catalog-wall-and-article-runbook.md)

## Before any provider write

1. Read `../../AGENTS.md`.
2. Confirm exact source and target IDs.
3. Confirm the inventory covers the intended provider surface.
4. Validate the immutable manifest and SHA-256.
5. Run the operational bundle verifier.
6. Run read-only preflight or dry-run.
7. Confirm ledger and result paths.
8. Confirm unknown-outcome reconciliation behavior.

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

## After every run

1. Write a run report or incident report.
2. Update `current-state.md` with timestamp, manifest SHA-256, attempted/accepted/processing/verified/rejected/unknown counts, result and ledger paths, remaining work, and whether resume is safe.
3. Append `project-memory-changelog.md`.
4. Add or update a regression test when the run exposed a tooling or packaging defect.
