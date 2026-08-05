# Current operational state

Updated: 2026-08-05  
Verified Wave 12B code baseline: `main@38296d07f8b6e948a6c5c4846bb66bf116bcfb72`  
Program state: `WAVES_0_12B_ENGINEERING_GOVERNANCE_COMPLETED_LIVE_RECONCILIATION_PENDING_NO_PROVIDER_WRITES`  
Canonical audit: [`master-audit-marathon-v2-2026-08-04.md`](master-audit-marathon-v2-2026-08-04.md)  
Current machine state: [`audit-register-v4-2026-08-05.json`](audit-register-v4-2026-08-05.json)  
Wave 12A predecessor overlay: [`audit-register-v3-2026-08-05.json`](audit-register-v3-2026-08-05.json)  
Complete historical ledger: [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json)

This file and the v4 machine state override old chats, screenshots, ZIP names, remembered counts, stale issue wording, and superseded audits.

## Completed engineering/governance program

- Audit A0 and Waves 0–8F: completed.
- Wave 9 read-only evidence contract: completed at `read_only_contract_self_tested`.
- Package A / Waves 9A–9B–10 tooling: completed at `read_only_package_self_tested`.
- Wave 11 package truth: completed at `self_tested_source_bound_governance`.
- Wave 12 Windows handoff/roadmap governance: completed at `self_tested_repository_governance`.
- Wave 12A project-bound ownership correction: completed at `self_tested_project_bound_governance`.
- Wave 12B shared VK credential and stale issue-graph reconciliation: completed at `self_tested_credential_and_issue_graph_governance`.

Wave 12A retained proof remains:

- `main@30c1ec11040034f6d3ed2492afe1bc7c029db1d0`;
- PR #120, exact head `98b4f3df7dd25918398d3544ee81d2b04a0aa21b`;
- CI `30971070928`;
- `785 passed, 1 xfailed`;
- evidence level `self_tested_project_bound_governance`.

Wave 12B proof:

- issue #122 and PR #124;
- merge/current code baseline `38296d07f8b6e948a6c5c4846bb66bf116bcfb72`;
- exact head `ffd275e9173db5a46bdde85f318dfa08ca83adb3`;
- exact-head CI `30988821430`;
- Python 3.11/3.12/3.13: `789 passed, 1 xfailed`;
- coverage: `78%` across `14,306` statements;
- Ruff correctness green; `445 files already formatted`;
- strict mypy: `145 source files`;
- dependency audit: no known vulnerabilities;
- Windows PowerShell 5.1, PowerShell 7 Windows, PowerShell 7 Linux: green;
- provider queries/writes/write plans: `0/0/0`.

Green CI proves contracts and fixtures. It does not prove current provider state, live queue completion, or authorization to mutate VK/YouTube.

## Credential model

VK uses one shared **user access token** from external `VK_API_TOKEN`. The local stored alias `legendary-poet` names that credential; it is not a project selector. The same token may enumerate both managed communities.

Project selection requires exact:

- `project_key`;
- VK `community_id` and `owner_id`;
- manifest, plan, journal, result, and link profile.

YouTube uses channel-specific OAuth aliases:

- Lord God: OAuth alias `fedor-milovanov` → `UCeSJsC6go2c9pdJCuUI1BYA`;
- Legendary Poet: OAuth alias `legendary-poet` → `UC-78ys2S3cQ3lpqgXfo-SvQ`.

Therefore #31/#32 correctly use `fedor-milovanov`; this does not imply a second VK token.

## Closed stale issue graph

After PR #124:

- #2 — closed `completed`; current architecture supplies YouTube OAuth and immutable read-only inventory/export.
- #3 — closed `not_planned`; superseded by specialized deterministic audit/editorial contracts.
- #4 — closed `not_planned`; guarded description/comment writers exist, while playlist mutation scope moved to deferred #123.
- #5 — closed `completed`; VK organizer/transfer foundation is implemented and remaining live truth is project-bound.
- #37 — closed `completed`; 34 reviewed Shorts were replaced, generated wall posts removed, protected post `12400` remained, and the historical executor is retired.

#37 is not an active operational owner. Future cleanup requires a new exact reviewed object set and separate authorization.

## Correct active operational graph

### #31 — Lord God long-form reconciliation

- `project_key`: `lord-god-strength`;
- OAuth alias `fedor-milovanov`;
- YouTube `UCeSJsC6go2c9pdJCuUI1BYA`;
- VK community/owner `60805374` / `-60805374`;
- status: `requires_reconciliation`.

Required: exact `upload-result.json`, `upload-ledger.db`, exact run log, bounded source manifest, fresh bounded YouTube/VK snapshots, and Package A output. Retained count 26, `KobOzfBqzic`, `s512Opa8Eu4 → -60805374_456241938`, and the old manifest SHA are inputs, not fresh conclusions.

### #32 — Lord God Shorts/Clips reconciliation

- `project_key`: `lord-god-strength`;
- OAuth alias `fedor-milovanov`;
- YouTube `UCeSJsC6go2c9pdJCuUI1BYA`;
- VK community/owner `60805374` / `-60805374`;
- status: `requires_reconciliation`.

Retained source count 108 and provisional 65/108 outputs are historical. Fresh reconciliation must cover ordinary-video and actual Clip surfaces and every accepted, processing, or unknown local state. Issue #32 is not a Legendary Poet owner.

### #119 — Legendary Poet Shorts/Clips reconciliation

- `project_key`: `legendary-poet`;
- OAuth alias `legendary-poet`;
- YouTube `UC-78ys2S3cQ3lpqgXfo-SvQ`;
- VK community/owner `235216998` / `-235216998`;
- status: `requires_reconciliation`.

Retained `56 / 41 / 15 / 0` and `BXZeRiEOHmQ → -235216998_456239039` are historical inputs. Supplied archives contain no durable apply results/ledger/final-type postflight, and saved VK records do not prove native Clip type.

### #38 — shared provider-mode/final-type contract

Project-neutral and owns no queue. Current primary-source evidence, exact adapter request, processed canary, and final surface/type readback are required. Historical 60/180-second claims, geometry, duration, title, player appearance, temporary type, or ordinary `video.get` absence never proves native Clip identity.

### #33 — Lord God video catalog/publication gate

Blocked by #31 and #32. It owns only Lord God video catalog, album/membership, metadata repair, and separately authorized wall publication. VK Audio/MP3 and Legendary Poet are excluded.

### #99 — Legendary Poet article-wall workflow

Separate from #119. It requires supported adapter readiness, published+postponed wall preflight, exact assets/text/schedule, one canary, durable per-operation results, and exact postflight.

### #123 — deferred YouTube playlist mutation contract

Not part of the live reconciliation graph and not authorized. It preserves playlist create/update and membership add/remove/reorder plus a generic guarded approval/execution lifecycle.

## Package, handoff, and safety boundaries

Package A output never authorizes a provider mutation by itself. PowerShell orchestrates one repository-owned implementation; it does not become a second provider client. Managed-community discovery uses `filter=moder`; `filter=admin` is not equivalent. Windows handoffs use exact paths, `-LiteralPath`, `Test-Path`, `$PSScriptRoot`, exact-one artifact selection, and never `LastWriteTime` or newest-ZIP discovery.

VK Audio remains `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`.

Never blind-retry accepted, processing, verified, or unknown operations. Never infer live success from CI, stdout, screenshots, titles, retained counts, ZIP names, extensions, save responses, or CDN URLs. Every provider write requires a separately reviewed exact-ID plan, durable per-operation results, and exact postflight.

Actual fresh live provider reconciliation: pending.
