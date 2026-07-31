# Operations index

Operational documents are living sources of truth. They take priority over chat history, screenshots, and remembered counts.

## Start here

- [`current-state.md`](current-state.md) — exact current identities, counts, paths, completed work, active work, and next actions.
- [`2026-07-31-youtube-vk-transfer-postmortem.md`](2026-07-31-youtube-vk-transfer-postmortem.md) — what succeeded, what failed, root causes, and permanent lessons.
- [`operational-artifact-standard.md`](operational-artifact-standard.md) — required structure and verification for ZIP packages, manifests, launchers, ledgers, and handoffs.

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

## After every run

Update `current-state.md` with:

- timestamp;
- manifest SHA-256;
- attempted, accepted, processing, verified, rejected, and unknown counts;
- result and ledger paths;
- remaining work;
- whether resume is safe;
- any newly observed provider limitation or packaging defect.
