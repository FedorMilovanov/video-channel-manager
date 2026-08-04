# Current operational state

Updated: 2026-08-05  
Verified code baseline: `main@604b962a9936ab173e41602bd9ab10b2dfaa9e59`  
Wave 7 baseline: `df956bbbf19af6652f8711f95fb4fecf272e9951`  
Wave 8F baseline: `dc3b25fdbbdb7d87e34f0f52e29fc9e3856190ae`  
Wave 9 contract baseline: `604b962a9936ab173e41602bd9ab10b2dfaa9e59`  
Program state: `WAVE_9_READ_ONLY_RECONCILIATION_CONTRACT_COMPLETED_LIVE_RECONCILIATION_PENDING_NO_PROVIDER_WRITES`  
Canonical audit: [`master-audit-marathon-v2-2026-08-04.md`](master-audit-marathon-v2-2026-08-04.md)  
Machine register: [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json)

This file overrides old chats, screenshots, packages, remembered counts, and superseded audits.

## Program status

- Audit A0: completed.
- Waves 0–7: completed.
- Waves 8A–8F: completed at evidence level `self_tested`.
- Wave 9 read-only reconciliation contract: completed at evidence level `read_only_contract_self_tested`.
- Actual fresh Wave 9A/9B provider reconciliation: pending.
- Provider queries during Wave 9 contract implementation and CI: `0`.
- Provider writes during Wave 9 contract implementation and CI: `0`.
- Write plans created during Wave 9 contract implementation and CI: `0`.

Wave 9 contract PR #107 merged as `604b962a9936ab173e41602bd9ab10b2dfaa9e59`. Exact-head CI `30954499845` passed on Python 3.11/3.12/3.13 with `761 passed, 1 xfailed`; Ruff correctness, Ruff formatting, strict mypy, dependency audit, Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux were green.

The Wave 9 code proves a fail-closed reconciliation contract and regression fixtures. It does not prove current live YouTube/VK state, availability of all local ledgers, current processing completion, canary verification, batch verification, or permission to mutate providers.

## Completed reliability contracts

### Waves 0–7

The completed base program provides exact project identity, durable journals, separated upload/wall operations, one supported operator `scripts/operator/Invoke-VideoManager.ps1`, versioned plan/result/reconciliation models, 15 supported mutation boundaries, and fault/corruption/replay coverage. Wave 7 merge `df956bbbf19af6652f8711f95fb4fecf272e9951`, CI `30918639372`, baseline `657 passed, 1 xfailed`, Pester `25/25`.

### Wave 8A — exact-first matching

Reviewed source ID → target ID is preferred, then unique exact canonical title, then bounded token/trigram fallback. Duplicate exact titles, duration conflicts, and non-unique fallback candidates are conflicts. A conflict creates no mapping, upload candidate, or collection placement.

### Wave 8B — canonical identity

Ruleset `wave-8b-v1`. Purpose-specific canonicalizers exist for identity/display title, description, collection, version/variation, public URL, and project URL. `already_correct` requires exact per-field readback. Substring, prefix, combined-row, author/admin, foreign-project, and unknown URL evidence fail closed.

### Wave 8C — catalog identity

Schema `video-manager.catalog-identity-evidence`, ruleset `wave-8c-v1`. A reviewed source collection ID → exact target album ID is the only existing-album authority. Duplicate canonical titles and unreviewed candidates are conflicts; membership compares exact target video ID sets.

### Wave 8D — media authority

Schema `video-manager.media-artifact-evidence`, ruleset `wave-8d-v1`. One exact structured-result field is authoritative. Cache reuse requires exact project/source/path/size/SHA-256/manifest/fresh-ffprobe agreement. Directory globs, first-match selection, extensions, MP4 container names, and remux status do not prove media identity or compatibility.

### Wave 8E — thumbnail authority

Schema `video-manager.vk-thumbnail-evidence`, ruleset `wave-8e-v1`. Upload/save intent is durable before dispatch. Save acceptance is not success. Verified requires exact `video.get` readback and a non-empty exact descriptor-set match. Unknown outcomes reconcile by readback and are never blindly replayed.

### Wave 8F — cross-wave integration proof

Schema `video-manager.operation-integration-evidence`, ruleset `wave-8f-v1`. One immutable object binds exact project, comparison snapshots/digest, catalog digest, WavePlan source/self/operation-set digests, WaveResult digest, bounded source set, media manifests, upload journals, thumbnail journals, expected remote delta, and exact totals for `planned`, `uploaded`, `verified`, `duplicate`, `failed`, and `requires_attention`. A verified early mutation followed by a later failure remains uploaded and becomes `requires_attention`; it is not replayable.

## Completed Wave 9 read-only reconciliation contract

Schema `video-manager.read-only-reconciliation-evidence`, version `1`, ruleset `wave-9-v1`.

Public boundary:

- `build_read_only_reconciliation_evidence`;
- `ReadOnlyReconciliationEvidence`;
- `BoundedSourceSnapshot`;
- `BoundedTargetSnapshot`;
- `LocalReconciliationRecord`;
- `RemoteReconciliationObservation`.

The contract binds exact project identity, one sorted bounded source set, fresh deterministic source/target snapshots, local mutation stages, exact remote observations, snapshot IDs, self-digests, and deterministic totals.

Every source item is classified as one of:

- `present`;
- `duplicate`;
- `missing`;
- `unknown`;
- `requires_attention`.

Safety guarantees:

- upload intent, accepted, processing, verified, or unresolved mutation evidence cannot become safely `missing`;
- duplicate live objects, processing objects, local/remote ID mismatches, and missing claimed-present objects are replay-prohibited;
- stale snapshots, cross-project remote IDs, incomplete local coverage, and one remote ID associated with multiple sources fail closed;
- exact reserved-ID lookup cannot prove absence for a source without a known exact remote ID;
- verified remote evidence requires exact final media type, duration, and postflight evidence;
- `provider_writes` is structurally `0`;
- `write_plan_created` is structurally `false`;
- each item has `future_write_authorized=false`;
- the module imports no `WavePlan`, mutation engine, writer, upload facade, or thumbnail writer.

The test matrix includes the retained Lord God processing/API-22/untouched boundaries and the Legendary Poet `56 / 41 / 15 / 0` matrix. These are regression fixtures, not fresh provider snapshots.

## Active Wave 9A — Lord God live read-only reconciliation

Owner issue: #31.

Required sequence:

1. locate and validate exact local Wave 6 plans/results, upload journals, media manifests, and retained reconciliation files;
2. take a fresh bounded read-only YouTube snapshot for the exact source set;
3. take a fresh bounded read-only VK snapshot covering the relevant target surface;
4. build one immutable `ReadOnlyReconciliationEvidence` object;
5. publish duplicate, present, missing, unknown, and requires-attention totals;
6. do not create a write plan.

Retained facts, not fresh conclusions:

- YouTube `KobOzfBqzic` is already present and must not be uploaded again;
- `s512Opa8Eu4` → VK `-60805374_456241938`;
- 27 reviewed, 1 present, previously verified missing: `26`;
- local evidence path `data\vk-upload\verified-longform-26`;
- manifest SHA `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`;
- retained operational outcome: 23 confirmed, 2 processing (`4wmCcHMcP90`, `Vs__dbIlVqU`), 1 explicit API 22 failure (`84puu6MnLZs`);
- status `BLOCKED_PENDING_FRESH_READ_ONLY_WALL_AUDIT_AND_LOCAL_LEDGER_RECONCILIATION`.

The old 26-item launcher remains prohibited. A partial endpoint cannot prove absence.

## Active Wave 9B — Legendary Poet live read-only reconciliation

Owner issues: #32 and #38.

Shorts/Clips remain separate from long-form. Retired V1/V2/V3/V4 and historical “48 clips” packages are not valid inputs.

Retained matrix, not fresh conclusions:

- 56 exact YouTube Shorts;
- 41 exact pairs;
- 15 confirmed missing;
- 0 ambiguous;
- `BXZeRiEOHmQ` → `-235216998_456239039`;
- completed V3 Apply/postflight is not proven;
- status `REVIEWED_MANIFEST_PREPARED / UPLOAD_COMPLETION_NOT_PROVEN`.

Actual completion requires fresh bounded provider snapshots plus exact local ledger/result reconciliation.

## Later Wave 9C reviewed action gate

Issue #33 owns later catalog/publication work. A canary or batch write requires a separate reviewed exact-ID plan after Wave 9A/9B evidence. Green CI, old counts, screenshots, visible objects, fixtures, ZIP names, or historical packages never authorize writes.

## Permanent operation contract

1. Validate only the supplied source set.
2. Take a fresh bounded read-only snapshot of the exact target surface.
3. Reconcile local durable stages and exact remote identities.
4. Produce immutable evidence and deterministic totals.
5. Review unknown, duplicate, processing, and requires-attention items before any future plan.
6. Create a write plan only in a later separately reviewed scope.
7. Persist mutation intent before dispatch and verify exact remote postconditions.

Permanent distinctions:

- `file_selected` is not `upload_completed`;
- `upload_completed` is not `remote_object_visible`;
- a save/upload response is not a selected-thumbnail postcondition;
- `unknown_requires_reconciliation` is not retry authorization;
- green CI proves contracts, not current provider state;
- evidence levels remain designed, self-tested, canary-verified, and batch-verified;
- PowerShell boundaries explicitly test zero, one, and many outputs under strict mode;
- a URL-shaped value is not an upload ticket.

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

VK Audio browser/internal-web attempts remain `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`. They are not part of Wave 9 video reconciliation.

## Active issue graph

- #31 active Wave 9A Lord God reconciliation;
- #32/#38 active Wave 9B Legendary Poet reconciliation;
- #33 later reviewed catalog/publication gate;
- #37 exact approved cleanup only;
- #64 master roadmap;
- #85 draft history archive;
- #86 completed Wave 8;
- #107 merged Wave 9 read-only contract.

## Global prohibitions

- Never mix project identities, credentials, IDs, journals, links, or manifests.
- Do not repeat completed Waves 0–8 or the Wave 9 contract through retired scripts or packages.
- Do not infer live success from CI, fixtures, stdout, screenshots, visible objects, stale counts, titles, file extensions, containers, save responses, or CDN URLs.
- Do not blind-retry intent-persisted, accepted, processing, verified, or unknown mutations.
- Do not perform provider writes during Wave 9 live read-only reconciliation.
- Do not create a write plan during Wave 9A/9B.
- Do not perform bulk deletion outside issue #37.
- Do not import VK Audio browser attempts into supported video core.
