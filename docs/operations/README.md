# Operational documentation

Operational documents are living sources of truth. They take priority over chat history, screenshots, remembered counts, retired ZIP packages, and older audits.

## Start here

- [`project-identity-registry.md`](project-identity-registry.md) — the two separate projects, verified links, OAuth aliases, shared VK token model, exact numeric identities, public/admin route separation, and no-mixing rules.
- [`master-audit-marathon-v2-2026-08-04.md`](master-audit-marathon-v2-2026-08-04.md) — current synthesis after Waves 0–7: exact baseline, fixed/active/retracted/separate-system matrix, newly missed gaps, and the Waves 8–10 marathon.
- [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json) — current machine-readable findings and ownership.
- [`current-state.md`](current-state.md) — exact current identities, completed work, active blockers, separate project queues, and the next allowed work.
- [`automation-backlog.md`](automation-backlog.md) — current wave-aligned implementation backlog and dependencies.
- [`http-client-ownership.md`](http-client-ownership.md) — reusable-client ownership, safe-read versus ambiguous-mutation retry authority, redaction, and limiter rules.
- [`lord-god-strength-description-profile.md`](lord-god-strength-description-profile.md) — exact identities, links, footer rules, and guards for Господь Бог — Сила Моя.
- [`legendary-poet-description-profile.md`](legendary-poet-description-profile.md) — exact identities, links, footer rules, VK Clips route, author-cabinet separation, and guards for The Legendary Poet.
- [`project-memory-changelog.md`](project-memory-changelog.md) — dated changes to durable operational memory.
- [`2026-07-31-youtube-vk-transfer-postmortem.md`](2026-07-31-youtube-vk-transfer-postmortem.md) — what succeeded, what failed, root causes, and permanent lessons.
- [`operational-artifact-standard.md`](operational-artifact-standard.md) — required structure and verification for ZIP packages, manifests, launchers, ledgers, retries, and handoffs.
- [`operational-package-acceptance.md`](operational-package-acceptance.md) — machine-checkable truth levels, supported-entrypoint and adapter-readiness requirements, and the prohibition on treating structural verification as write authorization.

Historical baselines retained for evidence:

- [`master-audit-2026-08-04.md`](master-audit-2026-08-04.md) — pre-Wave-1 audit; no longer the current roadmap.
- [`audit-register-2026-08-04.json`](audit-register-2026-08-04.json) — pre-Wave-1 finding register; fixed/retracted statuses remain historical evidence.

## Current engineering sequence

1. **Waves 0–7 — completed.** Upload lifecycle, project/content identity, HTTP reliability, upload/wall separation, supported PowerShell operator, versioned wave engine, mutation-boundary fault/corruption/operator proofs.
2. **Audit Wave A0 / issue #88 — completed in PR #89.** The master audit/register v2 and authoritative entrypoints are synchronized; exact-head CI `30925523584` was green; provider writes were `0`.
3. **Wave 8 / issue #86 — active core engineering.** Exact-first matching, field-specific canonical identity, exact album/catalog mapping, authoritative media/cache evidence, structured media validation, exact thumbnail postcondition.
4. **Wave 9 — live reconciliation.** Issues #31/#32/#33/#38, each project and surface separately, only after Wave 8 and fresh read-only evidence.
5. **Issue #37 — independent reviewed cleanup scope only.** It does not authorize broader deletion.
6. **Wave 10 — retirement and production governance.** Archive, release, runbook, rollback, reconciliation and audit-expiry rules.

Do not begin from a retired ZIP, historical executor, old numeric matrix, or chat-only instruction. The historical “48 clips” package is not a current queue contract. The latest recorded Legendary Poet matrix is `56 Shorts / 41 exact pairs / 15 missing / 0 ambiguous`, and it still requires fresh reconciliation before apply.

## Separate VK Audio boundary

Browser/internal-web VK Audio experiments are not a supported part of the core YouTube→VK Video engine. Existing canaries, playlist/metadata attempts, read-only probes and batch versions are historical/experimental evidence.

Do not continue them as production automation until a reviewed adapter defines:

- versioned source/plan/result schemas;
- exact per-item stages and durable ledger;
- browser-session acquisition boundary;
- allowlisted upload-ticket host/path contract;
- exact artist/title/playlist identity;
- bounded deadlines/heartbeat;
- partial/unknown reconciliation;
- canary and exact postflight.

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

Historical runbooks and executors are not automatically active. `current-state.md`, the v2 master audit, issue #64, and the exact owning issue decide whether an entrypoint may still be used.

## Before any provider write

1. Read `../../AGENTS.md`.
2. Read the v2 master audit and v2 machine finding register.
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
16. For any upload, confirm `wall_mutation_authorized=false`, explicit `wallpost=0`, and bound published+postponed before/postflight evidence.
17. Confirm that matching, album identity, media authority and thumbnail evidence satisfy the current Wave 8 contracts.

Validate every user-facing operational ZIP before handoff:

```powershell
python -m video_channel_manager.tools.operational_package_acceptance `
  .\path\package.zip `
  --entrypoint run-operation.ps1 `
  --require manifest.json `
  --require README.txt `
  --require SHA256SUMS.txt `
  --require-flat
```

The acceptance verifier first runs the stable digest-bound structural verifier, then checks truth level, exact project binding, supported entrypoint, adapter readiness, canary dependency, per-operation results, and unknown-outcome reconciliation. A passing result never authorizes provider writes.

## After every wave or run

1. Write a run report, incident report, or architecture decision as appropriate.
2. Update `current-state.md` with exact repository baseline, selected project, provider IDs, timestamp, manifest digest, state counts, result and ledger paths, remaining work, and whether resume is safe.
3. Update the current machine audit register when a finding changes state or ownership.
4. Append `project-memory-changelog.md`.
5. Update issue #64, the owning GitHub issue, and the PR.
6. Add or update a regression test when the work exposed a tooling, identity, link-profile, state-machine, transport, wall, provider-contract, wrapper, packaging, matching, catalog, media, thumbnail, archive, or governance defect.
