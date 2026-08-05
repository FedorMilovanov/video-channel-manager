# Current operational state

Updated: 2026-08-05  
Verified code baseline: `main@8f8b224f0386cf9f1ed89e0983e8af440e96cdd4`  
Wave 8F baseline: `dc3b25fdbbdb7d87e34f0f52e29fc9e3856190ae`  
Wave 9 contract baseline: `604b962a9936ab173e41602bd9ab10b2dfaa9e59`  
Package A baseline: `8f8b224f0386cf9f1ed89e0983e8af440e96cdd4`  
Program state: `PACKAGE_A_WAVE_9A_9B_WAVE_10_TOOLING_AND_GOVERNANCE_COMPLETED_LIVE_RECONCILIATION_PENDING_NO_PROVIDER_WRITES`  
Canonical audit: [`master-audit-marathon-v2-2026-08-04.md`](master-audit-marathon-v2-2026-08-04.md)  
Machine register: [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json)

This file overrides old chats, screenshots, packages, remembered counts, and superseded audits.

## Program status

- Audit A0: completed.
- Waves 0–8F: completed at evidence level `self_tested`.
- Wave 9 read-only evidence contract: completed at evidence level `read_only_contract_self_tested`.
- Package A — Wave 9A + Wave 9B + Wave 10 tooling/governance: completed at evidence level `read_only_package_self_tested`.
- Package A PR #110 merged as `8f8b224f0386cf9f1ed89e0983e8af440e96cdd4`.
- Exact-head CI `30958445398`: Python 3.11/3.12/3.13 each passed with `773 passed, 1 xfailed`; Ruff correctness, Ruff formatting, strict mypy, dependency audit, Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux were green.
- Provider queries during Package A implementation and CI: `0`.
- Provider writes during Package A implementation and CI: `0`.
- Write plans created during Package A implementation and CI: `0`.
- Actual fresh Wave 9A/9B live provider reconciliation: pending.

Package A proves read-only contracts, deterministic artifacts, recovery policy, operator presentation, and governance. It does not prove the current YouTube/VK state, availability or integrity of every local ledger, completion of historical uploads, canary verification, batch verification, or permission to mutate providers.

## Package A architecture

Supported CLI:

```text
video-manager-package-a reconcile --manifest <package-a-manifest.json>
video-manager-package-a verify-output --output <package-a-output-directory>
```

Package A consumes explicit local files and bounded read-only snapshot evidence. It does not discover queues from directories, titles, screenshots, old packages, or remembered counts.

Produced artifacts are immutable and project-bound:

1. Wave 9A reconciliation evidence;
2. Wave 9B recovery-decision ledger;
3. Wave 10 operator board;
4. checksummed output index suitable for `verify-output`.

The output directory is evidence, not mutation authority. No Package A command uploads, deletes, edits metadata, creates albums, changes thumbnails, publishes wall posts, or constructs a provider write plan.

## Wave 9A — exact bounded reconciliation

Schema `video-manager.read-only-reconciliation-evidence`, version `1`, ruleset `wave-9-v1`.

The runner binds:

- one registered project key and exact channel/community/owner identities;
- one sorted bounded source-ID set;
- deterministic source and target snapshot digests;
- snapshot freshness and complete-surface declarations;
- exact local plan/result/journal stages;
- exact remote observations;
- per-source classifications and deterministic totals.

Allowed classifications:

- `present`;
- `duplicate`;
- `missing`;
- `unknown`;
- `requires_attention`.

Fail-closed rules:

- local `intent`, `accepted`, `processing`, `verified`, or unresolved mutation evidence is never safely missing;
- incomplete or stale snapshots cannot prove absence;
- reserved-ID-only absence claims require a known exact remote ID and complete relevant coverage;
- duplicate remote objects, local/remote ID mismatch, cross-project IDs, incomplete local coverage, and digest tampering fail closed;
- no reconciliation result creates a write plan.

## Wave 9B — safe recovery decisions

Schema `video-manager.recovery-decision-ledger`, version `1`, ruleset `wave-9b-v1`.

Every exact source item receives a deterministic recovery decision derived from Wave 9A evidence. Decisions preserve accepted, processing, verified, duplicate, unknown, and requires-attention states. Blind retransmission is prohibited.

A later mutation may be considered only when fresh complete evidence proves the exact source is absent and a separate reviewed exact-ID plan authorizes the action. Package A does not create that plan.

## Wave 10 — operator board and governance

Schema `video-manager.operator-board`, version `1`, ruleset `wave-10-v1`.

The operator board exposes:

- exact project identity;
- evidence level and snapshot freshness;
- reconciliation totals;
- replay-prohibited count;
- blockers and warnings;
- exact safe next action;
- provider-query, provider-write, and write-plan counters fixed to the execution evidence.

The board is not a control plane for mutations. It has no writer adapter, provider dispatch, queue launcher, or write-plan generator.

Wave 10 governance now distinguishes:

- supported runtime code;
- historical/archive code;
- operational evidence;
- runbooks and recovery instructions;
- release and rollback boundaries.

Historical PR #85 and literal historical executors are archive evidence, not supported runtime entrypoints. The supported mutation operator remains `scripts/operator/Invoke-VideoManager.ps1`, and it is not invoked by Package A.

## Live Wave 9A — Lord God reconciliation remains pending

Owner issue: #31.

Required external/local inputs:

- `data\vk-upload\verified-longform-26\upload-result.json`;
- `data\vk-upload\verified-longform-26\upload-ledger.db`;
- latest `data\vk-upload\verified-longform-26\upload-run-*.log`;
- exact bounded source manifest;
- fresh read-only YouTube/VK snapshots covering the relevant surfaces.

Retained historical inputs:

- YouTube `KobOzfBqzic` is already present and must not be uploaded again;
- `s512Opa8Eu4` maps to VK `-60805374_456241938`;
- reviewed queue count: 26 after exclusions;
- reviewed manifest SHA `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`;
- status remains `BLOCKED_PENDING_FRESH_READ_ONLY_WALL_AUDIT_AND_LOCAL_LEDGER_RECONCILIATION`.

These facts are retained inputs, not a fresh live result. The old launcher must not be rerun.

## Live Wave 9B — Legendary Poet reconciliation remains pending

Owner issues: #32 and #38.

Retained historical matrix:

- 56 exact YouTube Shorts;
- 41 exact retained pairs;
- 15 retained missing candidates;
- 0 retained ambiguous;
- `BXZeRiEOHmQ` → `-235216998_456239039`;
- completed V3 Apply/postflight remains unproven.

Status remains `REVIEWED_MANIFEST_PREPARED / UPLOAD_COMPLETION_NOT_PROVEN` until fresh bounded read-only snapshots and local result evidence prove otherwise.

Shorts/Clips remain separate from long-form. Retired V1/V2/V3/V4 and historical “48 clips” packages are prohibited.

## Later reviewed action gate

Issue #33 owns later catalog/publication work. Any canary or batch mutation requires:

1. completed fresh Wave 9A/9B evidence;
2. reviewed exact source and target IDs;
3. a separate immutable mutation plan;
4. explicit expected remote delta;
5. guarded execution and exact postflight.

Green CI, Package A output, retained counts, visible objects, screenshots, historical packages, or an operator board never authorize writes.

## Project boundaries

### `lord-god-strength`

- YouTube: `UCeSJsC6go2c9pdJCuUI1BYA`;
- OAuth alias: `fedor-milovanov`;
- VK community: `60805374`;
- VK owner: `-60805374`.

Reviewed duplicate cleanup remains complete: `confirmed_deleted=403`, `run=completed`.

### `legendary-poet`

- YouTube: `UC-78ys2S3cQ3lpqgXfo-SvQ`;
- OAuth alias: `legendary-poet`;
- VK community: `235216998`;
- VK owner: `-235216998`.

## Separate VK Audio state

VK Audio browser/internal-web attempts remain `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`. They are not part of Package A video reconciliation.

## Active issue graph

- #31 — pending fresh Lord God live reconciliation;
- #32/#38 — pending fresh Legendary Poet live reconciliation;
- #33 — later reviewed exact-ID catalog/publication gate;
- #37 — exact approved cleanup only;
- #64 — canonical roadmap;
- #85 — historical archive boundary, not supported runtime;
- #86 — completed Wave 8;
- #107/#108 — completed Wave 9 contract and state sync;
- #110 — completed Package A implementation.

## Permanent prohibitions

- Never mix project identities, credentials, IDs, journals, links, or manifests.
- Never infer live success from CI, stdout, screenshots, visible objects, stale counts, titles, file extensions, containers, save responses, or CDN URLs.
- Never blind-retry accepted, processing, verified, or unknown mutations.
- Never use Package A output as mutation authorization.
- Never perform provider writes from Wave 9A/9B read-only reconciliation.
- Never import VK Audio browser attempts into supported video core.
- Never reactivate historical executors because they are preserved in archive documentation.
