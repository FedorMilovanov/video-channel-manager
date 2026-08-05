# Repository agent instructions

Before work on Fedor Milovanov's YouTube/VK workflow, read in order:

1. `docs/operations/project-identity-registry.md`
2. `docs/operations/master-audit-marathon-v2-2026-08-04.md`
3. `docs/operations/current-state.md`
4. `docs/operations/audit-register-v7-2026-08-05.json`
5. `docs/operations/audit-register-v6-2026-08-05.json`
6. `docs/operations/audit-register-v5-2026-08-05.json`
7. `docs/operations/audit-register-v4-2026-08-05.json`
8. `docs/operations/audit-register-v3-2026-08-05.json`
9. `docs/operations/audit-register-v2-2026-08-04.json`
10. `docs/operations/automation-backlog.md`
11. `docs/operations/repository-integrity-audit-2026-08-05.md`
12. `.github/copilot-instructions.md`
13. `docs/operations/local-credential-sources.md`
14. `docs/operations/operational-artifact-standard.md`
15. `docs/operations/operational-package-acceptance.md`
16. `docs/operations/retirement-registry-v1.json`

The v7 machine-state overlay, its immutable v6/v5/v4/v3/v2 predecessors, and `current-state.md` override old chats, screenshots, ZIPs, remembered counts, stale issue wording, and superseded audits. Historical material teaches; it never authorizes execution.

## Exact project and credential boundary

This repository manages two separate projects:

- `lord-god-strength` — **Господь Бог — Сила Моя**;
- `legendary-poet` — **The Legendary Poet — Легендарный Поэт**.

Canonical identities:

- `lord-god-strength`: YouTube `UCeSJsC6go2c9pdJCuUI1BYA`, OAuth alias `fedor-milovanov`, VK community `60805374`, VK owner `-60805374`;
- `legendary-poet`: YouTube `UC-78ys2S3cQ3lpqgXfo-SvQ`, OAuth alias `legendary-poet`, VK community `235216998`, VK owner `-235216998`.

VK uses one shared user access token from the external `VK_API_TOKEN` source. The local VK alias `legendary-poet` names the stored credential; it is not a project selector. Exact `project_key`, community/owner IDs, manifests, plans, journals, results, and link profiles provide isolation.

The configured VK token remains outside this repository at `C:\Users\Fedor\Projects\mp3telegrambot\.env`. Never copy, print, commit, package, log, request manual entry of, or place its value on a command line.

The strings `fedor-milovanov` and `legendary-poet` in YouTube operations are channel-specific OAuth aliases. They do not imply separate VK tokens.

## Current verified sequence

Current Wave 14 repository-polish code baseline: `main@626f83c6e5c068d7faa8b6d14163b42916faa769`.

- Waves 0–8F: completed;
- Wave 9 read-only evidence contract: completed;
- Package A / Waves 9A–10 tooling: completed;
- Wave 11 operational-package truth: completed;
- Wave 12 deterministic Windows handoffs: completed;
- Wave 12A project-bound ownership correction: completed at `self_tested_project_bound_governance`;
- Wave 12B shared credential/stale issue graph: completed;
- Wave 12C issue-contract convergence: completed;
- Wave 13 final evidence-backed operational closure: PR #128, exact head `731cc247a0c757c7103cd1ce5336adaf125d04d0`, merge `8d6a5ba243788e7b95b0e8a57eb02fb10eaf12ba`, CI `30992600857`, `792 passed, 1 xfailed`, Ruff and strict mypy green, all three PowerShell environments green;
- Wave 13 completed-state sync: PR #129, exact head `44a1590fac0e8fe8b563d35cfd68f2bed4727743`, merge `07388521e8d3a2c5d501382227c35bdce6e6470e`, CI `30994245235`, `796 passed, 1 xfailed`;
- Wave 14 repository-wide documentation and integrity polish: PR #131, exact head `80f701b6926a5a9c788b99c69634b54d63ed1862`, merge `626f83c6e5c068d7faa8b6d14163b42916faa769`, CI `31000834701`, `801 passed, 1 xfailed`, coverage `78%` across `14,306` statements, Ruff `451 files already formatted`, strict mypy `145 source files`, dependency audit clean, all three PowerShell environments green;
- provider queries, provider writes, write plans, and historical executor runs during Wave 14: `0/0/0/0`;
- active operational issues after the Wave 14 state-sync merge: `0`.

Green CI proves contracts and regression fixtures, not authorization to mutate VK or YouTube.

## Final issue graph

Completed:

- #31 — exact Lord God 26-item long-form reconciliation;
- #119 — Legendary Poet Shorts/Clips reconciliation with unsupported long scope preserved as non-replayable;
- #38 — shared VK native Clip/ordinary-video final-type contract.

Retired/not planned:

- #32 — Lord God non-authoritative 108-item Shorts auto-upload scope;
- #33 — broad Lord God catalog/publication continuation;
- #99 — unproved Legendary Poet article-wall launcher continuation;
- #123 — deferred YouTube playlist mutation scope.

Roadmap #64, Wave 13 #127, and Wave 14 #130 are closed program/governance records, not future execution owners.

Do not group #32/#38 as Legendary Poet. Historical ownership was #32 Lord God, #38 shared, and #119 Legendary Poet. All are now closed.

## Native Clip and unknown-outcome contract

Native Clip success requires exact final `type=short_video`, processing complete, `is_draft` absent or zero, and exact public visibility proof.

`M5hNecL_MsQ → -235216998_456239160` was observed as ordinary `video` with `is_draft=1`. It is not native Clip success and must not be retransmitted. The six undispatched long Legendary Poet items remain intentionally unexecuted. Automatic over-60-second native Clip publication is unsupported.

Geometry, duration, title, player appearance, temporary type, preview, save response, or ordinary `video.get` absence never proves native Clip identity.

## Package and operational truth

Package A output never authorizes a provider mutation by itself. It creates immutable reconciliation evidence, a no-blind-replay recovery ledger, and a read-only operator board.

Every package declares exactly one evidence level: `editorial_prepared`, `preview_validated`, `self_tested`, `canary_verified`, or `batch_verified`. Repository acceptance fixes `provider_writes_authorized=false` and `automatic_execution=false`. A filename, ZIP, preview, green CI, issue body, dashboard, confirmation prompt, stdout line, README command, or roadmap entry cannot promote evidence or authorize execution.

PowerShell orchestrates one repository-owned implementation. It does not become a second provider client. Generated external provider executors are unsupported.

## Repository integrity contract

- Every tracked JSON file must parse as UTF-8 or UTF-8-BOM JSON.
- Local Markdown links must resolve after fenced and inline code, anchors, external URLs, and explicit placeholders are excluded.
- README and security documentation must distinguish implemented capability from current authorization.
- Initial-roadmap wording, stale CI counts, and retired playlist scope must not reappear as current work.
- Tests that depend on scheduled timestamps must freeze their test clock rather than drift with wall time.

## Deterministic Windows handoffs

`.github/copilot-instructions.md` remains canonical. Every copy-paste PowerShell block defines all variables, works from any current directory, uses exact absolute paths, `-LiteralPath`, `Test-Path`, explicit extraction, exact invocation, and `$PSScriptRoot`; requires exactly one artifact; rejects `LastWriteTime`, newest-ZIP selection, broad wildcards, undefined/inherited variables, retired packages, and external provider executors; and declares evidence level, capability, exact community ID and owner ID, output/result paths, canary, and recovery behavior.

## VK permission and separate-system rules

Managed-community enumeration uses `groups.get(filter=moder, extended=1)` with bounded pagination. `filter=admin` is not equivalent and must not replace it.

VK Audio browser/internal-web work remains `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`. It is not Package A, the core YouTube→VK Video engine, or an active Wave 14 scope.

## Branch and merge discipline

Substantial work uses one `agent/{description}` branch and one focused PR. Merge only after exact-head six-job green CI, unchanged expected head, reviewed scope, and clean review threads. Synchronize operational memory separately after code/runtime or governance baselines change.

## Non-negotiable safety rules

1. Never mix project identities, OAuth aliases, credentials, IDs, journals, links, or manifests.
2. Never expose or request manual entry of the configured VK token.
3. Never rerun completed, retired, deletion, reset, recovery, article-wave, cleanup, transfer, or playlist executors.
4. Never infer absence from an endpoint that does not cover the relevant surface.
5. Use exact IDs and bounded inventories, not screenshots, titles, relative dates, or retained counts.
6. Never upload an ambiguous match.
7. Never repeat an intent-persisted, accepted, processing, verified, or unknown mutation; reconcile first.
8. Keep long-form and Shorts/Clips in separate manifests and ledgers.
9. Keep Lord God and Legendary Poet manifests, ledgers, snapshots, OAuth aliases, and issues separate.
10. Video upload, Clip publication, catalog, metadata, thumbnail, and wall publication are separate operations.
11. Never commit tokens, media, local exports, ledgers, logs, backups, or generated upload packages.
12. A successful HTTP response is not a postcondition; verify the exact remote effect.
13. Machine state belongs in journals/results, not only stdout.
14. Historical code is never a supported entrypoint.
15. `already_correct` requires exact per-field readback.
16. Cache reuse requires exact manifest/file/source/probe agreement.
17. Unknown outcomes stop automatic execution and require reconciliation.
18. Every batch operation requires its own durable result; one final console line is supplementary only.
19. A shared provider-mode issue never substitutes for a project-bound queue owner.
20. Provider writes remain unauthorized unless a new explicit user request creates a new exact owning issue, a reviewed immutable exact-ID plan, expected remote delta, durable per-operation results, and exact postflight.

No operational continuation is pending. Future work begins only from a new explicit user request and a new exact issue; closed issues and historical packages never authorize execution.
