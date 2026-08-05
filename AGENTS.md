# Repository agent instructions

Before work on Fedor Milovanov's YouTube/VK workflow, read in order:

1. `docs/operations/project-identity-registry.md`
2. `docs/operations/master-audit-marathon-v2-2026-08-04.md`
3. `docs/operations/audit-register-v3-2026-08-05.json`
4. `docs/operations/audit-register-v2-2026-08-04.json`
5. `docs/operations/current-state.md`
6. `docs/operations/automation-backlog.md`
7. `.github/copilot-instructions.md`
8. GitHub issue #64 and the issue owning the exact operation
9. `docs/operations/local-credential-sources.md`
10. `docs/operations/2026-07-31-youtube-vk-transfer-postmortem.md`
11. `docs/operations/operational-artifact-standard.md`
12. `docs/operations/operational-package-acceptance.md`
13. `docs/operations/retirement-registry-v1.json`

The v3 machine-state overlay, its immutable v2 predecessor register, and `current-state.md` override old chats, screenshots, ZIPs, remembered counts, stale issue wording, and superseded audits. Historical material teaches; it never authorizes execution.

## Exact project boundary

This repository manages two separate projects:

- `lord-god-strength` — **Господь Бог — Сила Моя**;
- `legendary-poet` — **The Legendary Poet — Легендарный Поэт**.

Canonical identities:

- `lord-god-strength`: YouTube `UCeSJsC6go2c9pdJCuUI1BYA`, OAuth alias `fedor-milovanov`, VK community `60805374`, VK owner `-60805374`;
- `legendary-poet`: YouTube `UC-78ys2S3cQ3lpqgXfo-SvQ`, OAuth alias `legendary-poet`, VK community `235216998`, VK owner `-235216998`.

Never mix channels, OAuth aliases, communities, owners, credentials, links, manifests, ledgers, results, comments, descriptions, or footers. The shared VK token source is a credential boundary, not a project selector.

## Credential boundary

The configured VK token source remains outside this repository:

- file: `C:\Users\Fedor\Projects\mp3telegrambot\.env`;
- key: `VK_API_TOKEN`.

Never copy, print, commit, package, log, or place the token value on a command line. Do not request manual token entry while the configured source exists.

## Current verified sequence

Verified Wave 12A code baseline: `main@30c1ec11040034f6d3ed2492afe1bc7c029db1d0`.

- Waves 0–8F: completed;
- Wave 9 read-only evidence contract: completed;
- Package A / Waves 9A–9B–10 tooling: completed at `read_only_package_self_tested`;
- Package A PR #110: `8f8b224f0386cf9f1ed89e0983e8af440e96cdd4`;
- Package A state sync PR #111: `024a978f7c57a52f03e4cae8e6cb8175d8e96976`;
- Wave 11 operational-package truth: PR #113 `eeab53b779e5ea4af5d3dcc08d79e41812739e04`, state sync PR #114 `557ec79ce5233bd76c13c3a373738ab80a0708f8`;
- Wave 12 deterministic Windows handoffs: PR #116 `4cecaef81cb151cd8c5c019ffe5d8289aefaeee0`, state sync PR #117 `8536811779806967f14ce3b957c63b55e2ba4496`;
- Wave 12A project-bound ownership correction: PR #120 `30c1ec11040034f6d3ed2492afe1bc7c029db1d0`;
- Wave 12A exact head `98b4f3df7dd25918398d3544ee81d2b04a0aa21b`;
- Wave 12A exact-head CI `30971070928`: `785 passed, 1 xfailed` on Python 3.11/3.12/3.13;
- dependency audit, Ruff across 441 files, strict mypy across 145 source files, Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux were green;
- Wave 12A evidence level: `self_tested_project_bound_governance`;
- provider queries, provider writes, and write plans during Wave 12A: `0`;
- fresh live provider reconciliation remains pending exact local ledgers/results and fresh bounded read-only snapshots.

Green CI proves contracts and regression fixtures, not current YouTube/VK state.

## Package A boundaries

Supported read-only commands:

```text
video-manager-package-a reconcile --manifest <package-a-manifest.json>
video-manager-package-a verify-output --output <package-a-output-directory>
```

Package A output never authorizes a provider mutation by itself. It creates immutable reconciliation evidence, a no-blind-replay recovery ledger, and a read-only operator board.

## Operational-package truth

Every package declares exactly one evidence level:

1. `editorial_prepared`;
2. `preview_validated`;
3. `self_tested`;
4. `canary_verified`;
5. `batch_verified`.

Use:

```text
python -m video_channel_manager.tools.operational_package_acceptance <archive.zip> ...
```

A passing result fixes `provider_writes_authorized=false` and `automatic_execution=false`. A filename, ZIP, preview, confirmation prompt, final stdout line, green CI, issue body, or dashboard cannot promote evidence or authorize execution.

PowerShell orchestrates one repository-owned implementation. It does not duplicate provider permission, retry, pagination, postflight, or state-classification logic. A generated Downloads-only `executor.py` is not a supported provider adapter.

## Deterministic Windows handoffs

`.github/copilot-instructions.md` is the canonical Windows handoff contract. Every copy-paste PowerShell block must:

- work from an arbitrary current directory;
- define every variable in the same block;
- use exact absolute paths, `-LiteralPath`, `Test-Path`, explicit ZIP extraction, and exact full-path invocation;
- use `$PSScriptRoot` for sibling files;
- require exactly one artifact when discovery is unavoidable;
- reject `LastWriteTime`, “newest ZIP”, broad generation wildcards, and inherited variables;
- declare evidence level, capability, exact project/community/owner, output paths, canary behavior, and unknown-outcome recovery;
- preserve UTF-8/BOM for Russian Windows `.ps1` and human-readable `.txt` files;
- never revive a retired package family or create an external provider executor.

## VK managed-community permission rule

Managed-community enumeration uses exactly `groups.get(filter=moder, extended=1)` with bounded pagination. `filter=admin` is not an equivalent capability check. The returned list is normalized, then exact project/community/owner identity is verified separately.

## Historical sermon-month incident

`LordGod-VK-SERMON-MONTH` v1/v2/v3 is retired. Do not rerun it.

The transcript reports `FINAL_OK — 30/30`, first post `-60805374_12482`, and last post `-60805374_12511`. Original per-operation results and exact provider postflight were not supplied, so the outcome remains `operator_transcript_reported`, not independently `batch_verified`.

## Correct live ownership graph

Issue bodies and project identity must agree exactly:

- #31 — `lord-god-strength` long-form reconciliation; OAuth alias `fedor-milovanov`;
- #32 — `lord-god-strength` Shorts/Clips reconciliation; OAuth alias `fedor-milovanov`;
- #119 — `legendary-poet` Shorts/Clips reconciliation; OAuth alias `legendary-poet`;
- #38 — shared VK native Clip/ordinary-video provider-mode and final-type contract; it owns no project queue;
- #33 — later Lord God video catalog/publication gate blocked by #31 and #32;
- #99 — separate Legendary Poet article-wall workflow;
- #37 — independent exact reviewed cleanup only;
- #64 — canonical roadmap;
- #118 — completed Wave 12A ownership correction.

Do not group #32/#38 as Legendary Poet ownership. #32 is Lord God, #38 is shared, and #119 is the dedicated Legendary Poet queue owner.

Retained Lord God facts are inputs, not fresh conclusions:

- long-form count 26;
- `KobOzfBqzic` already present;
- `s512Opa8Eu4` → `-60805374_456241938`;
- local evidence directory `data\vk-upload\verified-longform-26`;
- manifest SHA `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`;
- Shorts source count 108 and old provisional 65/108 missing outputs are historical/non-authoritative.

Retained Legendary Poet facts are inputs, not fresh conclusions:

- 56 YouTube Shorts;
- 41 retained exact pairs;
- 15 retained missing candidates;
- 0 retained ambiguous;
- `BXZeRiEOHmQ` → `-235216998_456239039`.

Do not use retired V1/V2/V3/V4, the historical “48 clips” package, or sermon-month v1/v2/v3.

## Shared Clip-mode boundary

Issue #38 must not freeze a duration limit or upload endpoint from memory. Historical materials conflict between 60 and 180 seconds and between dispatch surfaces. Current primary-source evidence, exact adapter request, one processed canary, and final surface/type readback are required before a provider-mode contract is current.

Geometry, duration, title, player appearance, temporary processing type, or ordinary `video.get` absence never proves native Clip identity.

## Separate VK Audio boundary

VK Audio browser/internal-web work remains `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`. It is not part of Package A, Waves 11–12A, #33, or the core YouTube→VK Video engine.

## Branch and merge discipline

- Substantial work uses one `agent/{description}` branch and one focused PR.
- Keep at most one active working branch for the current wave.
- Merge only after exact-head six-job green CI.
- Synchronize operational memory in a separate narrow PR when code/runtime changed.
- Guard squash merges by unchanged expected head, reviewed scope, and clean review threads.
- Never mix live provider reconciliation with reliability, archive, governance, or ownership refactors.

## Non-negotiable safety rules

1. Never mix project identities, OAuth aliases, credentials, IDs, journals, links, or manifests.
2. Never expose or request manual entry of the configured VK token.
3. Never rerun completed deletion, reset, article-wave, transfer, or retired executors.
4. Never infer absence from an endpoint that does not cover the relevant surface.
5. Use exact IDs and bounded inventories, not screenshots, titles, relative dates, or retained counts.
6. Never upload an ambiguous match.
7. Never repeat an intent-persisted, accepted, processing, verified, or unknown mutation; reconcile first.
8. Keep long-form and Shorts/Clips in separate manifests and ledgers.
9. Keep Lord God and Legendary Poet manifests, ledgers, snapshots, OAuth aliases, and issues separate.
10. Video upload and wall publication are separate operations.
11. Never commit tokens, media, local exports, ledgers, logs, backups, or generated upload packages.
12. Public text may use only the selected project's registered links; unknown links fail closed.
13. A successful HTTP response is not a postcondition; verify the exact remote effect.
14. Machine state belongs in journals/results, not only stdout.
15. Counts, ZIP names, final console lines, extensions, containers, save responses, and CDN URLs are not immutable identity.
16. Historical code is never a supported entrypoint.
17. `already_correct` requires exact per-field readback.
18. Cache reuse requires exact manifest/file/source/probe agreement.
19. Thumbnail success requires exact selected-thumbnail postflight.
20. Package A and live reconciliation remain read-only.
21. A dashboard, acceptance report, preview, canary claim, or green CI is not mutation authorization.
22. Evidence levels must not be collapsed or upgraded without retained machine evidence.
23. PowerShell must not become a second provider implementation.
24. VK managed-community discovery uses `filter=moder`; exact project identity is a separate gate.
25. Unknown outcomes stop automatic execution and require reconciliation.
26. Every batch operation requires its own durable result; one `FINAL_OK` line is supplementary only.
27. Windows handoffs never depend on current directory, undefined variables, newest-file selection, or inherited shell state.
28. A shared provider-mode issue never substitutes for a project-bound queue owner.

## Execution and handoff rules

- Read-only inventory first; writes only from a separately reviewed exact-ID plan.
- Persist mutation intent before dispatch and preserve unknown outcomes.
- Preserve successful intermediate stages and resume from durable state.
- Every handoff states truth level, project, exact entrypoint, manifest/archive SHA-256, inputs, outputs, result paths, canary behavior, and recovery behavior.
- Operational ZIPs are flat unless launch instructions explicitly say otherwise.
- Launchers verify their own location and required siblings before network work.
- After every wave, update `current-state.md`, machine state, backlog, issue #64, exact owning issues, and regression coverage.
