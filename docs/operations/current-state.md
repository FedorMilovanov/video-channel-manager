# Current operational state

Updated: 2026-08-05  
Verified code baseline: `main@4cecaef81cb151cd8c5c019ffe5d8289aefaeee0`  
Package A baseline: `8f8b224f0386cf9f1ed89e0983e8af440e96cdd4`  
Package A state-sync baseline: `024a978f7c57a52f03e4cae8e6cb8175d8e96976`  
Wave 11 baseline: `eeab53b779e5ea4af5d3dcc08d79e41812739e04`  
Wave 11 state-sync baseline: `557ec79ce5233bd76c13c3a373738ab80a0708f8`  
Wave 12 baseline: `4cecaef81cb151cd8c5c019ffe5d8289aefaeee0`  
Program state: `WAVES_0_12_ENGINEERING_COMPLETED_LIVE_RECONCILIATION_PENDING_NO_PROVIDER_WRITES`  
Canonical audit: [`master-audit-marathon-v2-2026-08-04.md`](master-audit-marathon-v2-2026-08-04.md)  
Current machine state: [`audit-register-v3-2026-08-05.json`](audit-register-v3-2026-08-05.json)  
Complete predecessor finding ledger: [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json)

This file overrides old chats, screenshots, ZIPs, remembered counts, and superseded audits.

## Program status

- Audit A0 and Waves 0–8F: completed.
- Wave 9 read-only evidence contract: completed at `read_only_contract_self_tested`.
- Package A — Wave 9A + Wave 9B + Wave 10 tooling/governance: completed at `read_only_package_self_tested`.
- Package A PR #110 merged as `8f8b224f0386cf9f1ed89e0983e8af440e96cdd4`; state sync PR #111 merged as `024a978f7c57a52f03e4cae8e6cb8175d8e96976`.
- Wave 11 operational-package truth and managed-community preflight: completed at `self_tested_source_bound_governance`.
- Wave 11 PR #113 merged as `eeab53b779e5ea4af5d3dcc08d79e41812739e04`; state sync PR #114 merged as `557ec79ce5233bd76c13c3a373738ab80a0708f8`.
- Wave 12 roadmap convergence and deterministic Windows handoffs: completed at `self_tested_repository_governance`.
- Wave 12 PR #116 merged as `4cecaef81cb151cd8c5c019ffe5d8289aefaeee0`.
- Exact-head CI `30969551134`: Python 3.11/3.12/3.13 each passed with `784 passed, 1 xfailed`; dependency audit, Ruff across 441 files, strict mypy across 145 source files, Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux were green.
- Provider queries during Wave 12 implementation and CI: `0`.
- Provider writes during Wave 12 implementation and CI: `0`.
- Write plans created during Wave 12 implementation and CI: `0`.
- Actual fresh Wave 9A/9B live provider reconciliation: pending.

Waves 0–12 prove architecture, evidence, package truth, operator governance, and deterministic handoff contracts. They do not prove current provider state or independently verify transcript-reported provider outcomes.

## Current machine-state model

`audit-register-v3-2026-08-05.json` is the current compact machine-state overlay. It binds its immutable predecessor `audit-register-v2-2026-08-04.json` by exact Git blob SHA `739146b63cfb3207a6b8d2d7a12698b3e54c28dd`.

The v2 register remains the complete historical source/finding ledger. The v3 overlay records current program state, Wave 12 controls, quality evidence, active operational owners, and the continued prohibition on provider writes. Do not flatten or discard the predecessor register.

## Package A read-only architecture

Supported CLI:

```text
video-manager-package-a reconcile --manifest <package-a-manifest.json>
video-manager-package-a verify-output --output <package-a-output-directory>
```

Package A produces immutable project-bound Wave 9A reconciliation evidence, Wave 9B recovery decisions, and a Wave 10 operator board. The output directory is evidence, not mutation authority.

Allowed reconciliation classifications remain `present`, `duplicate`, `missing`, `unknown`, and `requires_attention`. Intent-persisted, accepted, processing, verified, duplicate, unknown, or incomplete evidence never authorizes blind retransmission.

## Wave 11 operational-package truth

Acceptance contract: [`operational-package-acceptance.md`](operational-package-acceptance.md).

Repository-owned verifier:

```text
python -m video_channel_manager.tools.operational_package_acceptance <archive.zip> ...
```

Five evidence levels are distinct:

1. `editorial_prepared`;
2. `preview_validated`;
3. `self_tested`;
4. `canary_verified`;
5. `batch_verified`.

Every passing acceptance result fixes `provider_writes_authorized=false` and `automatic_execution=false`. Structural acceptance never authorizes a provider write.

## Wave 12 Windows handoff contract

Canonical contract: [`../../.github/copilot-instructions.md`](../../.github/copilot-instructions.md).

Every Windows copy-paste handoff must be deterministic and independent of the operator's current directory or previous shell state. It must define exact paths and every variable, use `-LiteralPath`, validate inputs with `Test-Path`, explicitly extract ZIPs, invoke the exact full entrypoint, use `$PSScriptRoot` for sibling files, and fail on zero or multiple artifact matches.

The following are prohibited:

- selection by `LastWriteTime` or “newest ZIP”;
- broad wildcard generation selection;
- undefined or inherited variables;
- assuming a download is already in the repository;
- generated external provider implementations;
- reviving retired package families;
- treating a preview, CI result, self-test, or command block as mutation authorization;
- blind retry after an unknown provider outcome.

Every handoff declares evidence level, read/write capability, exact project/community/owner, entrypoint, result paths, canary behavior, and safe recovery behavior. Russian `.ps1` and human-readable `.txt` artifacts use UTF-8 with BOM; JSON remains valid UTF-8.

## VK managed-community permission contract

Managed-community enumeration uses exact `groups.get(filter=moder, extended=1, count=1000, offset=0)` semantics. The documented v2 use of `filter=admin` produced a false rejection for a valid management token. Response shapes are normalized, but exact project/community/owner binding remains a separate fail-closed gate.

## Historical sermon-month incident

Archive: [`../history/operational-attempts/lord-god-sermon-month-2026-08-05/`](../history/operational-attempts/lord-god-sermon-month-2026-08-05/).

Source `Вставленный текст(290).txt`:

- lines recorded by file service: `367`;
- SHA-256: `2fd8cbd46e5b39b2baa0b4adcebba3cbfc6e57e445cddd5a8d16dbb5795bfb1d`.

The archive records:

- editorial/preview material represented beyond its operational capability;
- a parallel external Python/PowerShell v2 publisher family;
- v2 false permission rejection caused by `filter=admin` and reported zero writes;
- v3 correction to `filter=moder`, response normalization, canary-first execution, and per-operation results;
- transcript-reported `FINAL_OK — 30/30`, first post `-60805374_12482`, last post `-60805374_12511`.

The original v3 archive, result directory, thirty per-operation result files, canary readback, and fresh postflight wall snapshot were not supplied. The outcome therefore remains `operator_transcript_reported`, not independently `batch_verified`.

`LordGod-VK-SERMON-MONTH` v1/v2/v3 is retired and must not be rerun. Historical PowerShell/Python examples remain non-executable Markdown only.

## Live Wave 9A — Lord God remains pending

Owner issue: #31.

Required local/external inputs:

- `data\vk-upload\verified-longform-26\upload-result.json`;
- `data\vk-upload\verified-longform-26\upload-ledger.db`;
- latest `data\vk-upload\verified-longform-26\upload-run-*.log`;
- exact bounded source manifest;
- fresh bounded read-only YouTube/VK snapshots.

Retained inputs, not fresh conclusions:

- `KobOzfBqzic` is already present and must not be uploaded again;
- `s512Opa8Eu4` → `-60805374_456241938`;
- reviewed queue count 26 after exclusions;
- manifest SHA `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`;
- status `BLOCKED_PENDING_FRESH_READ_ONLY_WALL_AUDIT_AND_LOCAL_LEDGER_RECONCILIATION`.

## Live Wave 9B — Legendary Poet remains pending

Owner issues: #32 and #38.

Retained matrix, not fresh conclusions:

- 56 exact YouTube Shorts;
- 41 exact retained pairs;
- 15 retained missing candidates;
- 0 retained ambiguous;
- `BXZeRiEOHmQ` → `-235216998_456239039`;
- status `REVIEWED_MANIFEST_PREPARED / UPLOAD_COMPLETION_NOT_PROVEN`.

Shorts/Clips remain separate from long-form. Retired V1/V2/V3/V4 and the historical “48 clips” package are prohibited.

## Later reviewed action gate

Issue #33 owns later catalog/publication work. Any canary or batch mutation requires:

1. completed fresh Wave 9A/9B evidence;
2. reviewed exact source and target IDs;
3. a separate immutable mutation plan;
4. explicit expected remote delta;
5. guarded execution and exact postflight.

Green CI, Package A output, a preview, acceptance report, retained counts, visible objects, screenshots, historical packages, or transcript-reported success never authorize writes.

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

- #31 — pending fresh Lord God reconciliation;
- #32/#38 — pending fresh Legendary Poet reconciliation;
- #33 — later reviewed exact-ID catalog/publication gate;
- #37 — exact approved cleanup only;
- #64 — canonical roadmap;
- #115/#116 — Wave 12 issue/code PR, completed after state sync;
- #112/#113/#114 — completed Wave 11 issue/code/state sync;
- #110/#111 — completed Package A code/state sync.

## Permanent prohibitions

- Never mix project identities, credentials, IDs, journals, links, or manifests.
- Never infer live success from CI, stdout, screenshots, visible objects, stale counts, titles, ZIP names, file extensions, containers, save responses, or CDN URLs.
- Never blind-retry accepted, processing, verified, or unknown mutations.
- Never use Package A, Wave 11 acceptance, or Wave 12 handoff output as mutation authorization.
- Never rerun sermon-month v1/v2/v3 or other historical executors.
- Never collapse editorial, preview, self-tested, canary-verified, and batch-verified evidence.
- Never allow PowerShell to become a parallel provider implementation.
- Never treat `filter=admin` as equivalent to the supported managed-community `filter=moder` preflight.
- Never hand off Windows commands that depend on current directory, inherited variables, broad wildcard selection, or newest-file ordering.
