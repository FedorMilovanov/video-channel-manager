# Current operational state

Updated: 2026-08-05  
Verified main: `8536811779806967f14ce3b957c63b55e2ba4496`  
Package A baseline: `8f8b224f0386cf9f1ed89e0983e8af440e96cdd4`  
Package A state sync: `024a978f7c57a52f03e4cae8e6cb8175d8e96976`  
Wave 11 code/state: `eeab53b779e5ea4af5d3dcc08d79e41812739e04` / `557ec79ce5233bd76c13c3a373738ab80a0708f8`  
Wave 12 code/state: `4cecaef81cb151cd8c5c019ffe5d8289aefaeee0` / `8536811779806967f14ce3b957c63b55e2ba4496`  
Program state: `WAVES_0_12_COMPLETED_WAVE_12A_OWNERSHIP_CORRECTION_ACTIVE_LIVE_RECONCILIATION_PENDING_NO_PROVIDER_WRITES`  
Canonical audit: [`master-audit-marathon-v2-2026-08-04.md`](master-audit-marathon-v2-2026-08-04.md)  
Current machine state: [`audit-register-v3-2026-08-05.json`](audit-register-v3-2026-08-05.json)  
Complete predecessor ledger: [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json)

This file overrides old chats, screenshots, ZIPs, remembered counts, stale issue wording, and superseded audits.

## Program status

- Audit A0 and Waves 0–8F: completed.
- Wave 9 read-only evidence contract: completed at `read_only_contract_self_tested`.
- Package A Wave 9A/9B/10 tooling: completed at `read_only_package_self_tested`.
- Wave 11 package truth: completed at `self_tested_source_bound_governance`.
- Wave 12 roadmap/Windows handoff governance: completed at `self_tested_repository_governance`.
- Wave 12 code CI `30969551134`: `784 passed, 1 xfailed` on Python 3.11/3.12/3.13.
- Wave 12 state-sync CI `30970123683`: `785 passed, 1 xfailed` on Python 3.11/3.12/3.13.
- Dependency audit, Ruff across 441 files, strict mypy across 145 source files, Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux were green.
- Wave 12A / issue #118: active narrow source-of-truth correction after the actual issue bodies proved that #31/#32 are Lord God scopes and #119 must own Legendary Poet Shorts/Clips.
- Provider queries during Wave 12A: `0`.
- Provider writes during Wave 12A: `0`.
- Write plans during Wave 12A: `0`.
- Actual fresh live provider reconciliation: pending.

Waves 0–12 prove architecture, evidence, package truth, operator governance, and deterministic handoff contracts. They do not prove current provider state or independently verify transcript-reported outcomes.

## Current machine-state model

`audit-register-v3-2026-08-05.json` is the compact current-state overlay. It binds immutable predecessor `audit-register-v2-2026-08-04.json` by exact Git blob SHA `739146b63cfb3207a6b8d2d7a12698b3e54c28dd`.

The v2 register remains the complete historical source/finding ledger. The v3.1 overlay records current project-bound issue ownership, Wave 12/12A evidence, and continued write prohibition.

## Package A read-only architecture

Supported CLI:

```text
video-manager-package-a reconcile --manifest <package-a-manifest.json>
video-manager-package-a verify-output --output <package-a-output-directory>
```

Allowed classifications: `present`, `duplicate`, `missing`, `unknown`, `requires_attention`. Intent-persisted, accepted, processing, verified, duplicate, unknown, or incomplete evidence never authorizes blind retransmission.

## Operational-package truth

Repository-owned verifier:

```text
python -m video_channel_manager.tools.operational_package_acceptance <archive.zip> ...
```

Evidence levels remain distinct:

1. `editorial_prepared`;
2. `preview_validated`;
3. `self_tested`;
4. `canary_verified`;
5. `batch_verified`.

Every acceptance result fixes `provider_writes_authorized=false` and `automatic_execution=false`. Structural acceptance never authorizes provider writes.

## Deterministic Windows handoffs

Canonical contract: [`../../.github/copilot-instructions.md`](../../.github/copilot-instructions.md).

Every handoff uses exact paths, defines all variables, uses `-LiteralPath`, `Test-Path`, explicit ZIP extraction, exact full-path invocation, and `$PSScriptRoot`; it fails on zero/multiple artifacts and rejects `LastWriteTime`, newest-ZIP selection, broad generation wildcards, inherited variables, external provider executors, and retired packages.

Every handoff declares truth level, read/write capability, exact project/community/owner, output paths, canary behavior, and safe recovery behavior. Russian `.ps1` and human-readable `.txt` use UTF-8 with BOM; JSON remains valid UTF-8.

## VK managed-community permission contract

Managed-community enumeration uses exact `groups.get(filter=moder, extended=1, count=1000, offset=0)`. The v2 use of `filter=admin` produced a false rejection. Response normalization does not replace exact project/community/owner binding.

## Historical sermon-month incident

Archive: [`../history/operational-attempts/lord-god-sermon-month-2026-08-05/`](../history/operational-attempts/lord-god-sermon-month-2026-08-05/).

Source `Вставленный текст(290).txt`: SHA-256 `2fd8cbd46e5b39b2baa0b4adcebba3cbfc6e57e445cddd5a8d16dbb5795bfb1d`.

The transcript reports `FINAL_OK — 30/30`, first post `-60805374_12482`, last post `-60805374_12511`. The original per-operation result files and exact provider postflight were not supplied, so the outcome remains `operator_transcript_reported`, not independently `batch_verified`. `LordGod-VK-SERMON-MONTH` v1/v2/v3 is retired.

## Correct active ownership graph

### #31 — Lord God long-form reconciliation

Exact project:

- `project_key`: `lord-god-strength`;
- YouTube `UCeSJsC6go2c9pdJCuUI1BYA`;
- OAuth alias `fedor-milovanov`;
- VK community `60805374`;
- VK owner `-60805374`.

Required local evidence:

- `data\vk-upload\verified-longform-26\upload-result.json`;
- `data\vk-upload\verified-longform-26\upload-ledger.db`;
- latest exact `upload-run-*.log`;
- exact bounded source manifest;
- fresh bounded read-only YouTube/VK snapshots.

Retained inputs, not fresh conclusions:

- queue count 26;
- `KobOzfBqzic` already present;
- `s512Opa8Eu4` → `-60805374_456241938`;
- manifest SHA `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`;
- status `BLOCKED_PENDING_FRESH_READ_ONLY_WALL_AUDIT_AND_LOCAL_LEDGER_RECONCILIATION`.

### #32 — Lord God Shorts/Clips reconciliation

Exact project is also `lord-god-strength`, OAuth alias `fedor-milovanov`, community `60805374`, owner `-60805374`. The retained source count 108 and old provisional 65/108 missing outputs are historical/non-authoritative.

V1/V2/V3/V4 attempts are retired. Fresh read-only reconciliation must cover the actual Clip surface and ordinary-video surface, reconcile accepted/processing/unknown local outcomes, and use exact-first matching. Issue #32 is not a Legendary Poet owner.

### #119 — Legendary Poet Shorts/Clips reconciliation

Exact project:

- `project_key`: `legendary-poet`;
- YouTube `UC-78ys2S3cQ3lpqgXfo-SvQ`;
- OAuth alias `legendary-poet`;
- VK community `235216998`;
- VK owner `-235216998`.

Retained matrix, not fresh conclusions:

- 56 YouTube Shorts;
- 41 retained exact pairs;
- 15 retained missing candidates;
- 0 retained ambiguous;
- `BXZeRiEOHmQ` → `-235216998_456239039`;
- status `REVIEWED_MANIFEST_PREPARED / UPLOAD_COMPLETION_NOT_PROVEN`.

Retired V1/V2/V3/V4 and the historical “48 clips” package are prohibited. Old ordinary VK Video copies remain untouched unless separately reviewed.

### #38 — shared provider-mode/final-type contract

Issue #38 owns no project queue. It maintains shared evidence for `external_embed`, `native_video`, and `native_clip` modes, current primary-source policy, one-canary classification, processing completion, and exact final surface/type readback.

Conflicting historical claims of 60 versus 180 seconds are not a stable contract. Duration, geometry, player appearance, title, temporary type, or ordinary `video.get` absence never proves native Clip identity.

### #33 — later Lord God catalog/publication gate

Issue #33 is blocked by exact completion of #31 and #32. It is not the Legendary Poet Clip owner and does not authorize provider writes by itself.

### #99 — separate Legendary Poet article-wall workflow

Issue #99 remains a separate approved editorial workflow bound to community `235216998`. It requires a supported adapter, exact published+postponed wall preflight, durable results, canary, and postflight; it must not be mixed with #119 Clips reconciliation.

### #37 — independent exact cleanup

Issue #37 owns only its explicitly reviewed object set.

## Project identities

### `lord-god-strength`

- YouTube `UCeSJsC6go2c9pdJCuUI1BYA`;
- OAuth alias `fedor-milovanov`;
- VK community `60805374`;
- VK owner `-60805374`.

### `legendary-poet`

- YouTube `UC-78ys2S3cQ3lpqgXfo-SvQ`;
- OAuth alias `legendary-poet`;
- VK community `235216998`;
- VK owner `-235216998`.

## Separate VK Audio state

VK Audio browser/internal-web attempts remain `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`.

## Active issue graph

- #31 — Lord God long-form reconciliation;
- #32 — Lord God Shorts/Clips reconciliation;
- #119 — Legendary Poet Shorts/Clips reconciliation;
- #38 — shared Clip/provider-mode and final-type contract;
- #33 — later Lord God catalog/publication gate;
- #99 — separate Legendary Poet article-wall workflow;
- #37 — exact approved cleanup only;
- #64 — canonical roadmap;
- #118 — active Wave 12A ownership correction.

## Permanent prohibitions

- Never mix project identities, OAuth aliases, credentials, IDs, journals, links, or manifests.
- Never infer live success from CI, stdout, screenshots, visible objects, stale counts, titles, ZIP names, file extensions, containers, save responses, or CDN URLs.
- Never blind-retry accepted, processing, verified, or unknown mutations.
- Never use Package A, acceptance, dashboard, preview, canary claim, issue body, or command handoff as mutation authorization.
- Never rerun sermon-month v1/v2/v3, V1/V2/V3/V4 Shorts executors, the historical “48 clips” package, or other retired executors.
- Never collapse evidence levels or project owners.
- Never allow PowerShell to become a parallel provider implementation.
- Never treat `filter=admin` as equivalent to `filter=moder`.
- Never hand off commands dependent on current directory, inherited variables, broad wildcard selection, or newest-file ordering.
- Never use a shared provider-mode issue as a project-bound queue owner.
