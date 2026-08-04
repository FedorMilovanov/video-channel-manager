# Current operational state

Updated: 2026-08-04  
Verified code baseline: `main@b3b121f1c40b397d29c213d69a623b55641d020e`  
Wave 7 baseline: `df956bbbf19af6652f8711f95fb4fecf272e9951`  
Wave 8A baseline: `09babd9176049d8271c50b6f5e44b7b0fd10d39f`  
Wave 8B baseline: `c28aee4177d6f99e8f52fd82b60f4c1d93d50c29`  
Wave 8C baseline: `ee7766a651cd55a0f51bd3cd5acfbe3f29bfbaed`  
Wave 8D baseline: `b3b121f1c40b397d29c213d69a623b55641d020e`  
Program state: `WAVE_8D_COMPLETED_WAVE_8E_ACTIVE`  
Canonical audit: [`master-audit-marathon-v2-2026-08-04.md`](master-audit-marathon-v2-2026-08-04.md)  
Machine register: [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json)

This file overrides old chats, screenshots, packages, remembered counts, and superseded audits.

## Completed reliability program

- Audit A0 — PR #89, merge `a06a93e1ec16b4ddb0f578a92e47ce76b4ee78a5`, CI `30925523584`, provider writes 0.
- Waves 0–4 — canonical boundaries, journaled upload lifecycle, exact project identity, shared HTTP/retry/redaction, upload/wall separation; Wave 4 merge `d85f7cf94b8ba0b30947291b3a08491239438843`.
- Wave 5 — one supported operator `scripts/operator/Invoke-VideoManager.ps1`, merge `1a62779293a404e4654b6230644dfc78e9b20dc1`.
- Wave 6 — versioned source/plan/apply/result/reconciliation engine, merge `c4c4d3233ec20b8f939343c5d667d8687d7ff040`.
- Wave 7 — 15 supported mutation boundaries, 27 cross-cutting fault/corruption/replay scenarios, merge `df956bbbf19af6652f8711f95fb4fecf272e9951`, CI `30918639372`, `657 passed, 1 xfailed`, Pester `25/25`.
- Wave 8A — exact-first conflict-explicit matching, PR #91, merge `09babd9176049d8271c50b6f5e44b7b0fd10d39f`, CI `30933582322`, `664 passed, 1 xfailed`, provider writes 0.
- Wave 8A state sync — PR #92, merge `160382e4dea51d2691081e42c86c878a58ccdd97`, CI `30934601690`, `665 passed, 1 xfailed`.
- Wave 8B — versioned canonical text and URL identity, PR #93, merge `c28aee4177d6f99e8f52fd82b60f4c1d93d50c29`, CI `30936757433`, `680 passed, 1 xfailed` on Python 3.11/3.12/3.13; three PowerShell environments green; provider writes 0.
- Wave 8B state sync — PR #94, merge `801cc108043cd592dc0620c9996bda16d2cf5b55`.
- Wave 8C — exact catalog and album identity, PR #95, merge `ee7766a651cd55a0f51bd3cd5acfbe3f29bfbaed`, exact-head CI `30940734221`, `694 passed, 1 xfailed` on Python 3.11/3.12/3.13; three PowerShell environments green; provider writes 0.
- Wave 8C state sync — PR #97, merge `654c6521faa8d20dafe37fa1aaa33326902e0d03`, CI `30941230667`.
- Wave 8D — authoritative media/cache evidence and safe VK upload facade, PR #98, merge `b3b121f1c40b397d29c213d69a623b55641d020e`, exact-head CI `30944159147`, `713 passed, 1 xfailed` on Python 3.11/3.12/3.13; Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux green; provider writes 0.

## Wave 8A guarantees

The old fuzzy-first full-cartesian greedy matcher is retired. Supported order:

1. reviewed one-to-one source ID → target ID mapping;
2. unique exact canonical-title pairs;
3. bounded token/trigram-indexed fuzzy fallback.

`duplicate_exact_title`, `exact_title_duration_mismatch`, and `non_unique_fallback` are conflicts. Conflicts create no selected match, mapping, missing/upload candidate, or collection placement. Results are deterministic under input permutation.

## Wave 8B guarantees

The identity ruleset is `wave-8b-v1`.

Separate typed canonicalizers exist for identity title, display title, description comparison, collection title, version/variation, and HTTP/public/project URL identity. Every canonical result preserves the original value, canonical value, ruleset version, ordered transformations, and deterministic SHA-256 evidence digest.

Permanent exactness rules:

- `already_correct` requires exact field-by-field readback;
- substring, prefix, artist text inside a title, or a combined visible row cannot prove a field correct;
- missing and unexpected fields are recorded separately;
- public links reject author/admin routes;
- project links must belong to the exact approved project profile;
- cross-project and unknown-profile URLs fail closed;
- display titles preserve case and punctuation while identity titles use purpose-specific normalization;
- collection titles and video titles do not share one authority contract;
- version numbers remain identity-significant.

## Wave 8C guarantees

The catalog identity schema is `video-manager.catalog-identity-evidence`, ruleset `wave-8c-v1`. Cross-platform comparison schema is `3.0`; VK catalog plan version is 3.

- A reviewed one-to-one source collection ID → exact target album ID is the only automatic existing-album authority.
- Reviewed source and target IDs must exist in the exact bound snapshots.
- A target album ID cannot be reused by multiple source collections.
- A single title candidate without reviewed ID is `unreviewed_existing_candidate`, not an automatic match.
- Duplicate canonical target album titles are `duplicate_canonical_target_title`, never last-write-wins dictionary entries.
- Album creation requires explicit approval and no conflicting existing candidate.
- `mapped`, `create`, and `conflict` are mutually exclusive decisions.
- Conflict decisions create no album operation and no placement operation.
- Renamed reviewed albums remain bound to exact ID and record title drift.
- Membership is compared as exact target video ID sets; provider order/position churn is ignored.
- Evidence records mapped, unmapped, actual, missing, and extra IDs and is project/snapshot/channel bound with a deterministic digest.
- Extra membership is evidence only; Wave 8C does not delete anything.
- Detailed comparison rendering is attached to stable document structure, not a brittle exact wording replacement.

## Wave 8D guarantees

The media artifact schema is `video-manager.media-artifact-evidence`, schema version `1.0`, ruleset `wave-8d-v1`. The default compatibility profile is `vk-h264-aac-v1`.

### Immutable evidence

Each artifact binds:

- exact project key;
- exact source platform, channel ID, video ID, source URL/revision when available, and expected duration;
- acquisition method and path authority;
- requested output path and authoritative final path;
- file size and SHA-256;
- structured ffprobe evidence;
- container formats, stream counts, video/audio codecs, dimensions, sample rate, audio channels, and duration tolerance;
- deterministic manifest digest.

### Authoritative acquisition and cache reuse

- Downloader or transform output is accepted only from one exact structured-result field path.
- Directory glob fallback, wildcard paths, extension guessing, and first-match selection are prohibited as authority.
- `yt-dlp` cannot claim a controlled-master path; its final path must come from structured result evidence.
- Cache reuse requires exact agreement among project/source identity, manifest digest, authoritative path, file existence, file size, SHA-256, and a fresh ffprobe result.
- Missing, renamed, stale, wrong-source, wrong-project, substituted, or tampered entries fail closed.
- MP4 is only a container signal. Remux is only container conversion. Neither proves H.264/AAC or any selected compatibility profile.

### VK upload boundary

- The public VK package exports the Wave 8D authority facade; production code is guarded against direct imports of the legacy executor.
- A versioned artifact manifest is required before provider reservation or file dispatch.
- The manifest is journaled before reservation and its digest is included in reservation intent and intent digest.
- The file is freshly revalidated immediately before upload dispatch.
- Legacy path/size/SHA-only media journal entries are not cache authority.
- The manifest cannot change after `MEDIA_VERIFIED`.
- If bytes change after reservation, no file bytes are sent, the journal remains at `RESERVED`, the exact remote ID is preserved, and recovery restores the authoritative artifact and resumes the same reservation instead of creating a second one.

## Active engineering wave

Wave 8 / issue #86 remains the only active core-engineering owner. Waves 8A–8D are complete. **Wave 8E is active.**

### Wave 8E — exact thumbnail identity and selected-thumbnail postflight

Required outcomes:

- define a versioned immutable thumbnail source/plan/result evidence schema;
- bind exact project key and exact target owner/video ID;
- bind source image absolute path, size, SHA-256, format, dimensions, mode, and local quality findings from `inspect_image`;
- persist mutation intent before thumbnail upload/save dispatch;
- preserve exact upload response and save response without treating either as the final postcondition;
- model stages `planned`, `source_verified`, `upload_url_acquired`, `image_uploaded`, `save_started`, `save_accepted`, `postflight_verified`, and `unknown_requires_reconciliation`;
- perform bounded delayed readback against the exact owner/video ID;
- when stable provider photo fields are present, compare exact photo owner/id/hash and normalized image descriptors;
- do not treat a CDN URL or volatile URL query string as immutable thumbnail identity;
- if provider readback lacks sufficient stable proof, record `unknown_requires_reconciliation`, preserve accepted mutation evidence, and prohibit blind replay;
- a late readback or unrelated later-stage failure must not repeat an already accepted thumbnail mutation;
- do not invent undocumented provider fields as guaranteed contracts;
- implementation and tests remain local/mocked; provider writes remain 0;
- do not mix Wave 8F integration proof or Wave 9 live reconciliation into Wave 8E.

Later phase:

- Wave 8F — cross-wave integration proof and final Wave 8 state sync.

## Operation-scoped manager contract

The manager solves the requested operation, not a permanent global provider mirror.

For each operation:

1. validate only the supplied source set;
2. take a fresh short read-only snapshot of the exact target surface;
3. produce an immutable plan with exact identities and expected delta;
4. execute with per-item durable stages and no wall post unless separately authorized;
5. verify only the objects and delta from that operation;
6. report planned, uploaded, verified, duplicate, failed, and requires-attention totals.

Do not require a whole-account rescan, full-library visual fingerprint, GitHub commit of mutable provider state after each operation, or a multi-hour audit for a bounded task.

## Permanent stage and evidence rules

- `file_selected` is not `upload_completed`.
- `upload_completed` is not `remote_object_visible`.
- `remote_object_visible` is not complete workflow verification.
- A verified or accepted early mutation is never replayed because a later playlist, metadata, catalog, thumbnail-readback, or wall stage failed.
- Batch state is per item and per stage, never one Boolean.
- A UI click requires an observed intended state transition.
- Parser/observer self-test does not prove attachment to the correct browser target, frame, request, or network event.
- PowerShell boundaries explicitly test zero, one, and many outputs under strict mode.
- A URL-shaped value is not an upload ticket; validate the exact response field and allowlisted scheme/host/path before media transfer.
- Evidence levels remain distinct: designed, self-tested, canary-verified, and batch-verified.
- Any accepted, processing, verified, or `unknown_requires_reconciliation` mutation is not blindly replayed.
- A save/upload response is not a selected-thumbnail postcondition.

## Live-operation gate

Green CI proves contracts, not current provider state. Live work remains blocked until the exact project has:

1. operation-scoped read-only inventory;
2. reconciliation of local result/ledger files;
3. immutable Wave 6 evidence and digests;
4. one project-bound canary;
5. exact expected-delta postflight.

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
- owner issue #31;
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

VK Audio browser/internal-web attempts are a separate experimental system, not supported video-core.

Retained lessons:

- one MP3 reached `upload_verified`; a later playlist failure did not authorize retransmission;
- read-only probe found exact audio identity without persisting cookie values;
- 10 source positions reduced to 8 unique tracks;
- per-item states included existing, verified, and deferred;
- false `already_correct`, wrong-control clicks, hangs, and observer attachment failures occurred;
- wrong `vk.ru` upload endpoint returned HTTP 413 while observed `pu.vk.ru` succeeded.

Status: `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`.

## Active issue graph

- #31 long-form reconciliation;
- #32/#38 Legendary Poet Shorts/Clips reconciliation;
- #33 later catalog/publication;
- #37 exact approved cleanup only;
- #64 master roadmap;
- #85 draft history archive;
- #86 active Wave 8, Wave 8E;
- #88 completed audit;
- #91/#92 completed Wave 8A;
- #93/#94 completed Wave 8B;
- #95/#97 completed Wave 8C and state sync;
- #98 completed Wave 8D.

## Global prohibitions

- Never mix project identities, credentials, IDs, journals, links, or manifests.
- Do not repeat completed Waves 0–8D through retired scripts or ZIP packages.
- Do not infer success from green CI, stdout, a visible object, duration/orientation, stale counts, substring matching, title-only album lookup, file extension, container name, thumbnail upload/save response, or CDN URL.
- Do not blind-retry ambiguous or unknown mutations.
- Do not perform bulk deletion outside issue #37.
- Do not treat vertical format/duration as proof of VK Clip type.
- Do not import VK Audio web/browser attempts into core without a reviewed adapter contract.
