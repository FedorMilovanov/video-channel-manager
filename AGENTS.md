# Repository agent instructions

Before work on Fedor Milovanov's YouTube/VK workflow, read in order:

1. `docs/operations/project-identity-registry.md`
2. `docs/operations/master-audit-marathon-v2-2026-08-04.md`
3. `docs/operations/audit-register-v4-2026-08-05.json`
4. `docs/operations/audit-register-v3-2026-08-05.json`
5. `docs/operations/audit-register-v2-2026-08-04.json`
6. `docs/operations/current-state.md`
7. `docs/operations/automation-backlog.md`
8. `.github/copilot-instructions.md`
9. GitHub issue #64 and the issue owning the exact operation
10. `docs/operations/local-credential-sources.md`
11. `docs/operations/2026-07-31-youtube-vk-transfer-postmortem.md`
12. `docs/operations/operational-artifact-standard.md`
13. `docs/operations/operational-package-acceptance.md`
14. `docs/operations/retirement-registry-v1.json`

The v4 machine-state overlay, its immutable v3/v2 predecessors, and `current-state.md` override old chats, screenshots, ZIPs, remembered counts, stale issue wording, and superseded audits. Historical material teaches; it never authorizes execution.

## Exact project and credential boundary

This repository manages two separate projects:

- `lord-god-strength` — **Господь Бог — Сила Моя**;
- `legendary-poet` — **The Legendary Poet — Легендарный Поэт**.

Canonical identities:

- `lord-god-strength`: YouTube `UCeSJsC6go2c9pdJCuUI1BYA`, OAuth alias `fedor-milovanov`, VK community `60805374`, VK owner `-60805374`;
- `legendary-poet`: YouTube `UC-78ys2S3cQ3lpqgXfo-SvQ`, OAuth alias `legendary-poet`, VK community `235216998`, VK owner `-235216998`.

VK uses one shared user access token from the external `VK_API_TOKEN` source. The local VK alias `legendary-poet` names the stored credential; it is not a project selector. The token may enumerate both managed communities. Exact `project_key`, community/owner IDs, manifests, plans, journals, results, and link profiles provide isolation.

The configured VK token remains outside this repository at `C:\Users\Fedor\Projects\mp3telegrambot\.env`. Never copy, print, commit, package, log, request manual entry of, or place its value on a command line.

The strings `fedor-milovanov` and `legendary-poet` in YouTube operations are channel-specific OAuth aliases. Using `fedor-milovanov` for #31/#32 does not imply a second VK token.

## Current verified sequence

Current Wave 12B code baseline: `main@38296d07f8b6e948a6c5c4846bb66bf116bcfb72`.

- Waves 0–8F: completed;
- Wave 9 read-only evidence contract: completed;
- Package A / Waves 9A–9B–10 tooling: completed at `read_only_package_self_tested`;
- Wave 11 operational-package truth: PR #113 `eeab53b779e5ea4af5d3dcc08d79e41812739e04`, state sync PR #114 `557ec79ce5233bd76c13c3a373738ab80a0708f8`;
- Wave 12 deterministic Windows handoffs: PR #116 `4cecaef81cb151cd8c5c019ffe5d8289aefaeee0`, state sync PR #117 `8536811779806967f14ce3b957c63b55e2ba4496`;
- Wave 12A project-bound ownership correction: PR #120, `main@30c1ec11040034f6d3ed2492afe1bc7c029db1d0`, exact head `98b4f3df7dd25918398d3544ee81d2b04a0aa21b`, CI `30971070928`, `785 passed, 1 xfailed`, evidence `self_tested_project_bound_governance`;
- Wave 12B shared credential/stale issue graph: PR #124, merge `38296d07f8b6e948a6c5c4846bb66bf116bcfb72`, exact head `ffd275e9173db5a46bdde85f318dfa08ca83adb3`, CI `30988821430`, `789 passed, 1 xfailed`, Ruff `445` files, strict mypy `145` source files, three PowerShell environments green;
- provider queries, provider writes, and write plans during Wave 12B: `0`;
- fresh live provider reconciliation remains pending exact local ledgers/results and fresh bounded read-only snapshots.

Green CI proves contracts and regression fixtures, not current YouTube/VK state.

## Package and operational truth

Supported read-only Package A commands:

```text
video-manager-package-a reconcile --manifest <package-a-manifest.json>
video-manager-package-a verify-output --output <package-a-output-directory>
```

Package A output never authorizes a provider mutation by itself. It creates immutable reconciliation evidence, a no-blind-replay recovery ledger, and a read-only operator board.

Every package declares exactly one evidence level: `editorial_prepared`, `preview_validated`, `self_tested`, `canary_verified`, or `batch_verified`. Repository acceptance fixes `provider_writes_authorized=false` and `automatic_execution=false`. A filename, ZIP, preview, green CI, issue body, dashboard, confirmation prompt, or stdout line cannot promote evidence or authorize execution.

PowerShell orchestrates one repository-owned implementation. It does not duplicate provider permission, retry, pagination, postflight, or state-classification logic. Generated external provider executors are unsupported.

## Deterministic Windows handoffs

`.github/copilot-instructions.md` is canonical. Every copy-paste PowerShell block defines all variables, works from any current directory, uses exact absolute paths, `-LiteralPath`, `Test-Path`, explicit extraction, exact invocation, and `$PSScriptRoot`; requires exactly one artifact; rejects `LastWriteTime`, newest-ZIP selection, broad wildcards, undefined/inherited variables, retired packages, and external provider executors; and declares evidence level, capability, project/community/owner, output/result paths, canary, and recovery behavior.

## VK permission rule

Managed-community enumeration uses `groups.get(filter=moder, extended=1)` with bounded pagination. `filter=admin` is not equivalent. Exact project/community/owner verification is a separate gate.

## Correct live ownership graph

- #31 — `lord-god-strength` long-form reconciliation; OAuth alias `fedor-milovanov`;
- #32 — `lord-god-strength` Shorts/Clips reconciliation; OAuth alias `fedor-milovanov`;
- #119 — `legendary-poet` Shorts/Clips reconciliation; OAuth alias `legendary-poet`;
- #38 — shared VK native Clip/ordinary-video provider-mode and final-type contract; no project queue;
- #33 — later Lord God video catalog/publication gate blocked by #31 and #32;
- #99 — separate Legendary Poet article-wall workflow;
- #123 — deferred YouTube playlist-mutation contract, not authorized;
- #64 — canonical roadmap.

Do not group #32/#38 as Legendary Poet ownership. #32 is Lord God, #38 is shared, and #119 is the dedicated Legendary Poet queue owner.

Closed stale issues are not parallel owners:

- #2 and #5: completed;
- #3 and #4: superseded/not planned; #123 retains the unimplemented playlist portion;
- #37: completed historical 34-item cleanup; protected post `12400` remained; executor retired; no broad future cleanup authorization;
- #118: completed Wave 12A correction;
- #122 closes only after the Wave 12B completed-state sync.

Retained Lord God counts 26, 108, and provisional 65/108 are inputs, not fresh conclusions. Retained Legendary Poet `56 / 41 / 15 / 0` and `BXZeRiEOHmQ → -235216998_456239039` are historical inputs, not current Clip-type proof.

Issue #38 must not freeze a duration limit or endpoint from memory. Current primary-source evidence, exact adapter request, a processed canary, and final surface/type readback are required. Geometry, duration, title, player appearance, temporary type, or ordinary `video.get` absence never proves native Clip identity.

## Separate systems and retired incidents

VK Audio browser/internal-web work remains `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`. It is not Package A, #33, or the core YouTube→VK Video engine.

`LordGod-VK-SERMON-MONTH` v1/v2/v3 and Shorts V1/V2/V3/V4 are retired. Do not rerun them. Transcript-reported `FINAL_OK` is not independently `batch_verified` without durable per-operation results and exact provider postflight.

## Branch and merge discipline

Substantial work uses one `agent/{description}` branch and one focused PR. Merge only after exact-head six-job green CI, unchanged expected head, reviewed scope, and clean review threads. Synchronize operational memory separately after code/runtime or governance baselines change. Never mix live provider reconciliation with reliability, archive, governance, or ownership refactors.

## Non-negotiable safety rules

1. Never mix project identities, OAuth aliases, credentials, IDs, journals, links, or manifests.
2. Never expose or request manual entry of the configured VK token.
3. Never rerun completed, retired, deletion, reset, article-wave, or transfer executors.
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
20. Every live write requires one exact owning issue, a reviewed immutable exact-ID plan, expected remote delta, durable per-operation results, and exact postflight.

After every wave, update `current-state.md`, the versioned machine overlay, backlog, issue #64, exact owning issues, changelog, and regression coverage.
