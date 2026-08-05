# Operational documentation

Operational documents are living sources of truth. They take priority over chat history, screenshots, remembered counts, retired ZIP packages, and older audits.

## Start here

- [`project-identity-registry.md`](project-identity-registry.md) — the two separate projects, verified links, OAuth aliases, shared VK token model, exact numeric identities, public/admin route separation, and no-mixing rules.
- [`master-audit-marathon-v2-2026-08-04.md`](master-audit-marathon-v2-2026-08-04.md) — the canonical audit baseline and permanent finding history; later wave completion is recorded in `current-state.md` and the machine register.
- [`audit-register-v3-2026-08-05.json`](audit-register-v3-2026-08-05.json) — current compact machine state, Wave 12 evidence, active operational ownership, and write prohibitions.
- [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json) — immutable complete predecessor source/finding ledger, bound by exact blob SHA from v3.
- [`current-state.md`](current-state.md) — exact current identities, completed work, active blockers, separate project queues, and the next allowed work.
- [`automation-backlog.md`](automation-backlog.md) — current wave-aligned operational backlog and dependencies.
- [`../../.github/copilot-instructions.md`](../../.github/copilot-instructions.md) — deterministic Windows handoff rules for exact paths, ZIP extraction, PowerShell invocation, encoding, truth levels, and recovery declarations.
- [`http-client-ownership.md`](http-client-ownership.md) — reusable-client ownership, safe-read versus ambiguous-mutation retry authority, redaction, and limiter rules.
- [`lord-god-strength-description-profile.md`](lord-god-strength-description-profile.md) — exact identities, links, footer rules, and guards for Господь Бог — Сила Моя.
- [`legendary-poet-description-profile.md`](legendary-poet-description-profile.md) — exact identities, links, footer rules, VK Clips route, author-cabinet separation, and guards for The Legendary Poet.
- [`project-memory-changelog.md`](project-memory-changelog.md) — dated changes to durable operational memory.
- [`2026-07-31-youtube-vk-transfer-postmortem.md`](2026-07-31-youtube-vk-transfer-postmortem.md) — what succeeded, what failed, root causes, and permanent lessons.
- [`operational-artifact-standard.md`](operational-artifact-standard.md) — required structure and verification for ZIP packages, manifests, launchers, ledgers, retries, and handoffs.
- [`operational-package-acceptance.md`](operational-package-acceptance.md) — machine-checkable truth levels, supported-entrypoint and adapter-readiness requirements, and the prohibition on treating structural verification as write authorization.
- [`retirement-registry-v1.json`](retirement-registry-v1.json) — supported, compatibility, retired, and historical execution boundaries.

Historical baselines retained for evidence:

- [`master-audit-2026-08-04.md`](master-audit-2026-08-04.md) — pre-Wave-1 audit; no longer the current roadmap.
- [`audit-register-2026-08-04.json`](audit-register-2026-08-04.json) — pre-Wave-1 finding register; fixed/retracted statuses remain historical evidence.

## Current engineering sequence

1. **Waves 0–7 — completed.** Upload lifecycle, project/content identity, HTTP reliability, upload/wall separation, the supported PowerShell operator, versioned Wave Engine, and mutation-boundary fault/corruption/operator proofs.
2. **Audit Wave A0 — completed.** Authoritative audit/register entrypoints and source-of-truth ownership were synchronized.
3. **Waves 8A–8F — completed.** Exact-first matching, field-specific canonical identity, exact catalog/album identity, authoritative media/cache evidence, structured media validation, thumbnail postcondition, and cross-wave integration proof.
4. **Wave 9 read-only evidence contract — completed.** Bounded immutable reconciliation inputs and fail-closed classifications are implemented; this did not perform a live provider scan.
5. **Package A — completed at `read_only_package_self_tested`.** Wave 9A/9B reconciliation tooling, the no-blind-replay recovery ledger, the read-only Wave 10 operator board, and verification/runbook/rollback governance are implemented.
6. **Wave 11 — completed at `self_tested_source_bound_governance`.** Operational-package truth levels, repository-owned acceptance verification, managed-community `filter=moder` regression, source-bound incident learning, and retired external package generations are recorded.
7. **Wave 12 — completed at `self_tested_repository_governance`.** The roadmap and operations index converge on current state; deterministic Windows handoffs require exact paths, exact-one artifacts, self-contained PowerShell, explicit extraction, declared truth/capability/project binding, and fail-closed recovery.
8. **Live reconciliation — pending.** Issue #31 owns Lord God long-form; issues #32/#38 own the Shorts/Clips surface. Exact local ledgers/results and fresh bounded read-only snapshots are still required.
9. **Issue #33 — later reviewed mutation gate.** Catalog/publication work remains blocked until live reconciliation produces exact reviewed evidence.
10. **Issue #37 — independent reviewed cleanup scope only.** It does not authorize broader deletion.

Green CI proves contracts and regression fixtures, not current YouTube/VK state. Provider writes remain unauthorized by Package A, Wave 11 acceptance, Wave 12 handoff governance, dashboards, previews, retained counts, or transcript-reported outcomes.

Do not begin from a retired ZIP, historical executor, old numeric matrix, or chat-only instruction. The historical “48 clips” package is not a current queue contract. The retained Legendary Poet matrix is `56 Shorts / 41 exact pairs / 15 missing / 0 ambiguous`; it remains an input that requires fresh reconciliation before any apply plan.

## Separate VK Audio boundary

Browser/internal-web VK Audio experiments are not a supported part of the core YouTube→VK Video engine. Existing canaries, playlist/metadata attempts, read-only probes, and batch versions are historical/experimental evidence.

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

Historical runbooks and executors are not automatically active. `current-state.md`, the v3 machine-state overlay, its v2 predecessor register, the retirement registry, issue #64, and the exact owning issue decide whether an entrypoint may still be used.

## Before any provider write

1. Read `../../AGENTS.md` and `../../.github/copilot-instructions.md`.
2. Read the master audit, v3 machine-state overlay, and immutable v2 predecessor register.
3. Read `current-state.md` and confirm that the exact owning issue permits design of a provider write.
4. Select exactly one `project_key` from `project-identity-registry.md`.
5. Read the matching project-specific description profile.
6. Confirm exact YouTube channel ID and VK community/owner IDs.
7. Confirm the inventory covers the intended provider surface.
8. Validate that every project/footer link belongs to the selected project's link profile.
9. Keep public links separate from operational/admin URLs.
10. Validate the immutable manifest and SHA-256.
11. Run the operational-package acceptance verifier.
12. Confirm acceptance evidence still states `provider_writes_authorized=false` and `automatic_execution=false`.
13. Run bounded read-only preflight or dry-run.
14. Confirm exact ledger and per-operation result paths.
15. Confirm unknown-outcome reconciliation behavior.
16. Confirm that no intent-persisted, accepted, processing, verified, or unknown mutation is being retransmitted.
17. Confirm matching, catalog identity, media authority, and thumbnail evidence satisfy the completed Wave 8 contracts.
18. Use a separately reviewed exact-ID mutation plan and explicit expected remote delta.
19. For any upload, confirm `wall_mutation_authorized=false`, explicit `wallpost=0`, and bound published+postponed before/postflight evidence.
20. Execute only through the registered repository-owned operator and adapter; PowerShell is not a second provider implementation.

Validate every user-facing operational ZIP before handoff:

```powershell
python -m video_channel_manager.tools.operational_package_acceptance `
  C:\Users\Fedor\Downloads\EXACT-PACKAGE.zip `
  --entrypoint run-operation.ps1 `
  --require manifest.json `
  --require README.txt `
  --require SHA256SUMS.txt `
  --require-flat
```

Replace every placeholder with the exact reviewed filename before presenting the command. The acceptance verifier first runs the stable digest-bound structural verifier, then checks truth level, exact project binding, supported entrypoint, adapter readiness, canary dependency, per-operation results, and unknown-outcome reconciliation. A passing result never authorizes provider writes.

## After every wave or run

1. Write a run report, incident report, or architecture decision as appropriate.
2. Update `current-state.md` with exact repository baseline, selected project, provider IDs, timestamp, manifest digest, state counts, result and ledger paths, remaining work, and whether resume is safe.
3. Update the current machine-state overlay while preserving its immutable predecessor ledger when a finding changes state or ownership.
4. Append `project-memory-changelog.md`.
5. Update issue #64, the owning GitHub issue, and the PR.
6. Add or update a regression test when the work exposed a tooling, identity, link-profile, state-machine, transport, wall, provider-contract, wrapper, packaging, matching, catalog, media, thumbnail, archive, governance, or handoff defect.
