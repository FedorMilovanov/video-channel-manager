# Current operational state

Updated: 2026-08-04  
Verified code baseline: `main@a0230ea156eeb1717e15c6523d0b6b28e90f6d8e`  
Wave 7 baseline: `df956bbbf19af6652f8711f95fb4fecf272e9951`  
Wave 8A baseline: `09babd9176049d8271c50b6f5e44b7b0fd10d39f`  
Wave 8B baseline: `c28aee4177d6f99e8f52fd82b60f4c1d93d50c29`  
Wave 8C baseline: `ee7766a651cd55a0f51bd3cd5acfbe3f29bfbaed`  
Wave 8D baseline: `b3b121f1c40b397d29c213d69a623b55641d020e`  
Wave 8E baseline: `a0230ea156eeb1717e15c6523d0b6b28e90f6d8e`  
Program state: `WAVE_8E_COMPLETED_WAVE_8F_ACTIVE`  
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
- Wave 8E — exact thumbnail evidence and selected-thumbnail delayed postflight, PR #102, merge `a0230ea156eeb1717e15c6523d0b6b28e90f6d8e`, exact-head CI `30947556457`, `722 passed, 1 xfailed` on Python 3.11/3.12/3.13; Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux green; provider writes 0.

## Completed Wave 8 guarantees

### Wave 8A — matching

Supported order is reviewed source ID → target ID, then unique exact canonical title, then bounded token/trigram fuzzy fallback. `duplicate_exact_title`, `exact_title_duration_mismatch`, and `non_unique_fallback` are conflicts. Conflicts create no selected match, upload candidate, mapping, or collection placement.

### Wave 8B — canonical identity

The ruleset is `wave-8b-v1`. Purpose-specific canonicalizers exist for identity title, display title, description, collection title, version/variation, public URL, and project URL. `already_correct` requires exact per-field readback. Substring, prefix, combined-row text, author/admin routes, foreign-project URLs, and unknown URL profiles fail closed.

### Wave 8C — catalog identity

The schema is `video-manager.catalog-identity-evidence`, ruleset `wave-8c-v1`; Cross-platform comparison schema is `3.0`; VK catalog plan version is 3. A reviewed source collection ID → exact target album ID is the only existing-album authority. `duplicate_canonical_target_title` and `unreviewed_existing_candidate` are conflicts. Conflict decisions create no album operation or placement operation. Membership compares exact target video ID sets; provider ordering is not identity.

### Wave 8D — media authority

The schema is `video-manager.media-artifact-evidence`, version `1.0`, ruleset `wave-8d-v1`; default profile `vk-h264-aac-v1`.

- One exact structured-result field path is final-path authority.
- Directory glob fallback, wildcard paths, extension guessing, and first-match selection are prohibited.
- Cache reuse requires project/source/path/file-size/SHA-256/manifest/fresh ffprobe agreement.
- MP4 is only a container signal; remux does not prove codec compatibility.
- The public VK package exports the Wave 8D authority facade.
- The manifest digest is included in reservation intent and freshly revalidated before file transfer.
- Changed bytes after reservation block transfer, preserve the exact remote ID, leave the journal at `RESERVED`, and resume the same reservation after the authoritative artifact is restored.

### Wave 8E — thumbnail authority

The schema is `video-manager.vk-thumbnail-evidence`, version `1.0`, ruleset `wave-8e-v1`.

- Evidence binds exact project key, VK owner/video ID, and local image absolute path, size, SHA-256, format, width, and height.
- The lifecycle persists `prepared`, `upload_intent_recorded`, `save_intent_recorded`, `saved`, `verified`, and `unknown_requires_reconciliation`.
- Upload and save intent are persisted before dispatch. A restart from either intent never replays the mutation.
- The save receipt records exact photo owner/id/hash, canonical image descriptors, and response digest.
- `video.saveUploadedThumb` acceptance is not success.
- Verified requires an independent retry-safe `video.get` readback for the exact owner/video and a non-empty exact canonical descriptor-set match.
- CDN query strings and fragments are volatile and excluded from descriptor identity; exact scheme, host, path, width, and height remain identity.
- A mismatch, incomplete receipt, ambiguous upload/save, interrupted dispatch, or insufficient readback becomes `unknown_requires_reconciliation`.
- Saved or unknown operations with an exact receipt reconcile by readback only; upload/save is not repeated.
- The journal is atomic, digest-protected, and project/video/image bound.
- The public VK package exports `VerifiedVkThumbnailWriter` and `execute_thumbnail_operation`; production imports of the low-level save-only writer are AST-guarded.

## Active engineering wave

Wave 8 / issue #86 remains the only active core-engineering owner. Waves 8A–8E are complete. **Wave 8F is active.**

### Wave 8F — cross-wave integration proof

Required outcomes:

- prove one bounded source set can flow through exact matching, canonical field identity, reviewed catalog identity, authoritative media evidence, upload intent, and thumbnail result evidence without weakening any stage;
- bind project key, exact source/target IDs, source snapshot, expected remote delta, plan digest, media manifest digest, upload journal identity, and thumbnail operation ID in one integration evidence object;
- prove conflicts and `unknown_requires_reconciliation` at any boundary create no unauthorized later operation;
- prove a verified or accepted early mutation is never replayed because catalog placement, thumbnail readback, metadata, wall publication, or another later stage fails;
- distinguish designed/self-tested evidence from canary-verified and batch-verified provider evidence;
- guard all supported public entrypoints against legacy bypasses;
- validate operation-scoped result totals: planned, uploaded, verified, duplicate, failed, and requires-attention;
- keep all tests local/mocked and provider writes at 0;
- do not perform Wave 9 live reconciliation, wall publication, catalog publication, or VK Audio work in Wave 8F.

After the Wave 8F code merge, a final narrow state sync may close Wave 8 and activate Wave 9 read-only reconciliation.

## Permanent operation contract

The manager solves the requested operation, not a permanent whole-account mirror.

1. Validate only the supplied source set.
2. Take a fresh bounded read-only snapshot of the exact target surface.
3. Produce an immutable project-bound plan with exact identities and expected delta.
4. Persist mutation intent before dispatch.
5. Execute per item and per stage; video upload never implies wall publication.
6. Verify only the objects and delta created by that operation.
7. Preserve accepted, processing, verified, or unknown stages and reconcile rather than replay.

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

Retained facts:

- duplicate cleanup `confirmed_deleted=403`, `run=completed`;
- boundary `KobOzfBqzic`;
- `s512Opa8Eu4` → `-60805374_456241938`;
- 27 reviewed, 1 present, verified missing: `26`;
- SHA `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`;
- local evidence `data\vk-upload\verified-longform-26`;
- live status `BLOCKED_PENDING_FRESH_READ_ONLY_WALL_AUDIT_AND_LOCAL_LEDGER_RECONCILIATION`.

### `legendary-poet`

- YouTube: `UC-78ys2S3cQ3lpqgXfo-SvQ`;
- OAuth alias: `legendary-poet`;
- VK community: `235216998`;
- VK owner: `-235216998`.

Latest retained matrix:

- 56 exact YouTube Shorts;
- 41 exact pairs;
- 15 confirmed missing;
- 0 ambiguous;
- `BXZeRiEOHmQ` → `-235216998_456239039`;
- old `59/40/19/1` and historical `48` queues are retired;
- completed V3 Apply/postflight is not proven.

Status: `REVIEWED_MANIFEST_PREPARED / UPLOAD_COMPLETION_NOT_PROVEN`.

## Separate VK Audio state

VK Audio browser/internal-web attempts remain a separate experimental system, not supported video-core. Status: `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`.

Do not import them into core until a reviewed adapter defines versioned source/plan/result schemas, exact per-item stages, durable ledger, browser-session boundary, allowlisted upload-ticket host/path, exact field identity, bounded deadlines, partial/unknown reconciliation, canary, and exact postflight.

## Active issue graph

- #31 Lord God long-form reconciliation;
- #32/#38 Legendary Poet Shorts/Clips reconciliation;
- #33 later catalog/publication;
- #37 exact approved cleanup only;
- #64 master roadmap;
- #85 draft history archive;
- #86 active Wave 8F;
- #88 completed audit;
- #91/#92 completed Wave 8A;
- #93/#94 completed Wave 8B;
- #95/#97 completed Wave 8C;
- #98/#101 completed Wave 8D and state sync;
- #102 completed Wave 8E.

## Global prohibitions

- Never mix project identities, credentials, IDs, journals, links, or manifests.
- Do not repeat completed Waves 0–8E through retired scripts or ZIP packages.
- Do not infer live success from CI, stdout, screenshots, visible objects, stale counts, titles, file extensions, container names, save responses, or CDN URLs.
- Do not blind-retry ambiguous or unknown mutations.
- Do not perform bulk deletion outside issue #37.
- Do not import VK Audio browser attempts into supported core.
- Do not resume broad provider queues until Wave 8 is closed and Wave 9 completes exact read-only reconciliation.
