# Current operational state

Updated: 2026-08-04  
Verified code baseline: `main@c28aee4177d6f99e8f52fd82b60f4c1d93d50c29`  
Wave 7 baseline: `df956bbbf19af6652f8711f95fb4fecf272e9951`  
Wave 8A baseline: `09babd9176049d8271c50b6f5e44b7b0fd10d39f`  
Wave 8B baseline: `c28aee4177d6f99e8f52fd82b60f4c1d93d50c29`  
Program state: `WAVE_8B_COMPLETED_WAVE_8C_ACTIVE`  
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
- Wave 8B — versioned canonical text and URL identity, PR #93, merge `c28aee4177d6f99e8f52fd82b60f4c1d93d50c29`, exact-head CI `30936757433`, `680 passed, 1 xfailed` on Python 3.11/3.12/3.13; Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux green; provider writes 0.

## Wave 8A guarantees

The old fuzzy-first full-cartesian greedy matcher is retired. Supported order:

1. reviewed one-to-one source ID → target ID mapping;
2. unique exact canonical-title pairs;
3. bounded token/trigram-indexed fuzzy fallback.

Explicit conflicts:

- `duplicate_exact_title`;
- `exact_title_duration_mismatch`;
- `non_unique_fallback`.

Conflicts create no selected match, mapping, missing/upload candidate, or collection placement. Results are deterministic under input permutation.

## Wave 8B guarantees

The identity ruleset is `wave-8b-v1`. Cross-platform comparison schema is `2.1`.

Separate typed canonicalizers now exist for:

- identity title;
- display title;
- description comparison;
- collection title;
- version/variation;
- HTTP/public/project URL identity.

Every canonical result preserves:

- original value;
- canonical value;
- ruleset version;
- ordered transformations;
- deterministic SHA-256 evidence digest.

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

## Active engineering wave

Wave 8 / issue #86 remains the only active core-engineering owner. Waves 8A and 8B are complete. **Wave 8C is active.**

### Wave 8C — exact catalog and album identity

Required outcomes:

- reviewed one-to-one source collection ID → exact target album ID mapping;
- validate every reviewed source/target ID against the exact snapshots;
- reject reused target album IDs;
- duplicate canonical target album names are conflicts, never dictionary overwrite;
- renamed or unmapped existing albums require review, not automatic selection;
- album creation is allowed only for an explicitly approved source collection with no reviewed target ID and no conflicting target candidates;
- collection mapping evidence is immutable, versioned, project/snapshot bound, and digest protected;
- semantic membership compares sets of exact target video IDs; provider position churn is ignored;
- unresolved collection conflicts produce no album or placement operation;
- issue #33 receives exact catalog evidence later but no live writes occur in Wave 8C.

Later phases:

- Wave 8D — authoritative downloader path, SHA/size/fingerprint and structured ffprobe validation;
- Wave 8E — exact thumbnail identity and selected-thumbnail delayed postflight;
- Wave 8F — integration proof and final Wave 8 state sync.

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

## Permanent stage/evidence rules

- `file_selected` is not `upload_completed`.
- `upload_completed` is not `remote_object_visible`.
- `remote_object_visible` is not complete workflow verification.
- A verified early upload is never replayed because a later playlist, metadata, catalog, or wall stage failed.
- Batch state is per item and per stage, never one Boolean.
- A UI click requires an observed intended state transition.
- Parser/observer self-test does not prove attachment to the correct browser target, frame, request, or network event.
- PowerShell boundaries explicitly test zero, one, and many outputs under strict mode.
- A URL-shaped value is not an upload ticket; validate the exact response field and allowlisted scheme/host/path before media transfer.
- Evidence levels remain distinct: designed, self-tested, canary-verified, and batch-verified.
- Any accepted, processing, verified, or `unknown_requires_reconciliation` mutation is not blindly replayed.

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
- #86 active Wave 8, Wave 8C;
- #88 completed audit;
- #91 merged Wave 8A;
- #92 merged Wave 8A state sync;
- #93 merged Wave 8B.

## Global prohibitions

- Never mix project identities, credentials, IDs, journals, links, or manifests.
- Do not repeat completed Waves 0–8B through retired scripts or ZIP packages.
- Do not infer success from green CI, stdout, a visible object, duration/orientation, stale counts, substring matching, or title-only album lookup.
- Do not blind-retry ambiguous mutations.
- Do not perform bulk deletion outside issue #37.
- Do not treat vertical format/duration as proof of VK Clip type.
- Do not import VK Audio web/browser attempts into core without a reviewed adapter contract.
