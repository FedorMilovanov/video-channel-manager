# Current operational state

Updated: 2026-08-04  
Verified code baseline: `main@dc3b25fdbbdb7d87e34f0f52e29fc9e3856190ae`  
Wave 7 baseline: `df956bbbf19af6652f8711f95fb4fecf272e9951`  
Wave 8A baseline: `09babd9176049d8271c50b6f5e44b7b0fd10d39f`  
Wave 8B baseline: `c28aee4177d6f99e8f52fd82b60f4c1d93d50c29`  
Wave 8C baseline: `ee7766a651cd55a0f51bd3cd5acfbe3f29bfbaed`  
Wave 8D baseline: `b3b121f1c40b397d29c213d69a623b55641d020e`  
Wave 8E baseline: `a0230ea156eeb1717e15c6523d0b6b28e90f6d8e`  
Wave 8F baseline: `dc3b25fdbbdb7d87e34f0f52e29fc9e3856190ae`  
Program state: `WAVE_8_COMPLETED_WAVE_9_READ_ONLY_RECONCILIATION_ACTIVE`  
Canonical audit: [`master-audit-marathon-v2-2026-08-04.md`](master-audit-marathon-v2-2026-08-04.md)  
Machine register: [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json)

This file overrides old chats, screenshots, packages, remembered counts, and superseded audits.

## Completed reliability program

- Audit A0 — PR #89, merge `a06a93e1ec16b4ddb0f578a92e47ce76b4ee78a5`, CI `30925523584`, provider writes 0.
- Waves 0–4 — canonical boundaries, journaled upload lifecycle, exact project identity, shared HTTP/retry/redaction, and upload/wall separation.
- Wave 5 — one supported operator `scripts/operator/Invoke-VideoManager.ps1`.
- Wave 6 — versioned source/plan/apply/result/reconciliation engine.
- Wave 7 — 15 supported mutation boundaries, 27 cross-cutting fault/corruption/replay scenarios, merge `df956bbbf19af6652f8711f95fb4fecf272e9951`, CI `30918639372`, `657 passed, 1 xfailed`, Pester `25/25`.
- Wave 8A — exact-first conflict-explicit matching, PR #91, merge `09babd9176049d8271c50b6f5e44b7b0fd10d39f`, CI `30933582322`, `664 passed, 1 xfailed`, provider writes 0.
- Wave 8B — versioned canonical text and URL identity, PR #93, merge `c28aee4177d6f99e8f52fd82b60f4c1d93d50c29`, CI `30936757433`, `680 passed, 1 xfailed`, provider writes 0.
- Wave 8C — exact catalog and album identity, PR #95, merge `ee7766a651cd55a0f51bd3cd5acfbe3f29bfbaed`, CI `30940734221`, `694 passed, 1 xfailed`, provider writes 0.
- Wave 8D — authoritative media/cache evidence and safe VK upload facade, PR #98, merge `b3b121f1c40b397d29c213d69a623b55641d020e`, CI `30944159147`, `713 passed, 1 xfailed`, provider writes 0.
- Wave 8E — exact thumbnail evidence and selected-thumbnail delayed postflight, PR #102, merge `a0230ea156eeb1717e15c6523d0b6b28e90f6d8e`, CI `30947556457`, `722 passed, 1 xfailed`, provider writes 0.
- Wave 8F — cross-wave integration evidence, PR #104, merge `dc3b25fdbbdb7d87e34f0f52e29fc9e3856190ae`, exact-head CI `30950259625`, `744 passed, 1 xfailed` on Python 3.11/3.12/3.13; Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux green; provider writes 0.

## Wave 8 completed guarantees

Wave 8 is complete at the `self_tested` evidence level. This proves local contracts and mocked composition, not current live-provider completion, canary verification, or batch verification.

### Wave 8A — matching

Supported order is reviewed source ID → target ID, unique exact canonical title, then bounded token/trigram fuzzy fallback. `duplicate_exact_title`, `exact_title_duration_mismatch`, and `non_unique_fallback` are conflicts. Conflicts create no selected match, upload candidate, mapping, or collection placement.

### Wave 8B — canonical identity

Ruleset `wave-8b-v1`. Purpose-specific canonicalizers exist for identity title, display title, description, collection title, version/variation, public URL, and project URL. `already_correct` requires exact per-field readback. Substring, prefix, combined-row text, author/admin routes, foreign-project URLs, and unknown URL profiles fail closed.

### Wave 8C — catalog identity

Schema `video-manager.catalog-identity-evidence`, ruleset `wave-8c-v1`; Cross-platform comparison schema is `3.0`; VK catalog plan version is 3. A reviewed source collection ID → exact target album ID is the only existing-album authority. `duplicate_canonical_target_title` and `unreviewed_existing_candidate` are conflicts. Conflict decisions create no album operation or placement operation. Membership compares exact target video ID sets.

### Wave 8D — media authority

Schema `video-manager.media-artifact-evidence`, version `1.0`, ruleset `wave-8d-v1`; default profile `vk-h264-aac-v1`.

- One exact structured-result field path is final-path authority.
- Directory glob fallback, wildcard paths, extension guessing, and first-match selection are prohibited.
- Cache reuse requires project/source/path/file-size/SHA-256/manifest/fresh ffprobe agreement.
- MP4 is only a container signal; remux does not prove codec compatibility.
- The public VK package exports the Wave 8D authority facade.
- The manifest digest is included in reservation intent and freshly revalidated before transfer.
- Changed bytes after reservation preserve the exact remote ID and journal stage `RESERVED`; recovery resumes the same reservation after restoring the authoritative artifact.

### Wave 8E — thumbnail authority

Schema `video-manager.vk-thumbnail-evidence`, version `1.0`, ruleset `wave-8e-v1`.

- Evidence binds exact project key, VK owner/video ID, and local image path/size/SHA-256/format/dimensions.
- Durable stages include `upload_intent_recorded`, `save_intent_recorded`, `verified`, and `unknown_requires_reconciliation`.
- Intent is persisted before dispatch; restart never blindly replays the mutation.
- `video.saveUploadedThumb` acceptance is not selected-thumbnail success.
- Verified requires retry-safe exact `video.get` readback and a non-empty exact canonical descriptor-set match.
- CDN query strings and fragments are volatile; exact scheme, host, path, width, and height remain identity.
- Saved or unknown operations with an exact receipt reconcile by readback only.
- Public exports use `VerifiedVkThumbnailWriter` and `execute_thumbnail_operation`.

### Wave 8F — integration proof

Schema `video-manager.operation-integration-evidence`, version `1`, ruleset `wave-8f-v1`.

- One immutable evidence object binds exact project, comparison snapshots/digest, catalog digest, WavePlan source/self/operation-set digests, WaveResult digest, bounded source set, media manifest digests, upload journal identities, thumbnail operation identities, expected remote delta, and operation-scoped totals.
- Every plan operation carries exact normalized `source_video_id` and an explicit integration stage.
- Operations and stage evidence outside the bounded source set fail closed.
- Matched, missing, and conflict items form a non-overlapping partition.
- Conflict items create zero later operations/evidence; matched items create no upload or thumbnail evidence.
- Missing items require exactly one upload operation and authoritative media evidence.
- Succeeded or unknown WaveResult stages must agree with durable upload and thumbnail stages.
- A verified upload followed by later metadata, catalog, thumbnail, wall, or reporting failure remains uploaded and becomes `requires_attention`; it is never classified as failed/replayable.
- Totals partition exact source items into `planned`, `uploaded`, `verified`, `duplicate`, `failed`, and `requires_attention`.
- The supported public boundary is `build_operation_integration_evidence` and `OperationIntegrationEvidence`; private helper imports and duplicate schema authority are AST-guarded.
- `provider_writes` is structurally `0`; evidence level is `self_tested`, not canary-verified or batch-verified.

## Active Wave 9 — read-only reconciliation

Wave 9 is active only for bounded read-only inventory and local ledger/result reconciliation. No upload, deletion, metadata mutation, catalog placement, thumbnail save, wall publication, or other provider write is authorized by this state transition.

### Wave 9A — Lord God reconciliation

Owner issue: #31.

Required sequence:

1. inventory local Wave 6 plans/results, upload journals, media manifests, and retained reconciliation files;
2. take fresh bounded read-only YouTube/VK snapshots of the exact supplied source set and relevant target surfaces;
3. reconcile exact source IDs, target IDs, stages, unknown outcomes, accepted/processing/verified items, and expected remote delta;
4. produce a read-only integration/reconciliation report with duplicate, present, missing, unknown, and requires-attention totals;
5. do not create a write plan until the report is reviewed separately.

Retained facts:

- YouTube `KobOzfBqzic` is already present and must not be uploaded again;
- `s512Opa8Eu4` maps to VK `-60805374_456241938`;
- 27 reviewed, 1 present, previously verified missing: `26`;
- local evidence path `data\vk-upload\verified-longform-26`;
- manifest SHA `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`;
- live status remains `BLOCKED_PENDING_FRESH_READ_ONLY_WALL_AUDIT_AND_LOCAL_LEDGER_RECONCILIATION`.

### Wave 9B — Legendary Poet reconciliation

Owner issues: #32 and #38.

Required sequence mirrors Wave 9A but keeps Shorts/Clips separate from long-form and does not use retired V1/V2/V3/V4 or historical “48 clips” packages.

Latest retained matrix:

- 56 exact YouTube Shorts;
- 41 exact pairs;
- 15 confirmed missing;
- 0 ambiguous;
- `BXZeRiEOHmQ` → `-235216998_456239039`;
- completed V3 Apply/postflight is not proven.

Status remains `REVIEWED_MANIFEST_PREPARED / UPLOAD_COMPLETION_NOT_PROVEN` until read-only reconciliation proves otherwise.

### Wave 9C — reviewed next-action gate

Issue #33 owns later catalog/publication work. A canary or batch write requires a separate reviewed exact-ID plan after Wave 9A/9B reconciliation. Green CI, old counts, visible objects, screenshots, or historical packages never authorize writes.

## Permanent operation contract

1. Validate only the supplied source set.
2. Take a fresh bounded read-only snapshot of the exact target surface.
3. Produce an immutable project-bound plan with exact identities and expected delta.
4. Persist mutation intent before dispatch.
5. Execute per item and per stage; video upload never implies wall publication.
6. Verify only objects and delta from that operation.
7. Preserve accepted, processing, verified, and unknown stages; reconcile rather than replay.

Permanent distinctions:

- `file_selected` is not `upload_completed`;
- `upload_completed` is not `remote_object_visible`;
- a save/upload response is not a selected-thumbnail postcondition;
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
- #86 completed Wave 8 after final state sync;
- #88 completed audit;
- #91/#92 completed Wave 8A;
- #93/#94 completed Wave 8B;
- #95/#97 completed Wave 8C;
- #98/#101 completed Wave 8D;
- #102/#103 completed Wave 8E;
- #104 completed Wave 8F.

## Global prohibitions

- Never mix project identities, credentials, IDs, journals, links, or manifests.
- Do not repeat completed Waves 0–8 through retired scripts or ZIP packages.
- Do not infer live success from CI, stdout, screenshots, visible objects, stale counts, titles, file extensions, containers, save responses, or CDN URLs.
- Do not blind-retry ambiguous or unknown mutations.
- Do not perform bulk deletion outside issue #37.
- Do not import VK Audio browser attempts into supported video core.
- Do not perform provider writes during Wave 9 read-only reconciliation.
