# Current operational state

Updated: 2026-08-04  
Verified repository baseline before state sync: `main@09babd9176049d8271c50b6f5e44b7b0fd10d39f`  
Wave 7 code baseline: `df956bbbf19af6652f8711f95fb4fecf272e9951`  
Wave 8A code baseline: `09babd9176049d8271c50b6f5e44b7b0fd10d39f`  
Program state: `WAVE_8A_COMPLETED_WAVE_8B_ACTIVE`  
Canonical audit: [`master-audit-marathon-v2-2026-08-04.md`](master-audit-marathon-v2-2026-08-04.md)  
Machine register: [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json)

This is the first state board to read before YouTube/VK work. Chat history, screenshots, remembered counts, retired packages, and older agent audits do not override it.

## Completed program work

- Audit A0: PR #89, merge `a06a93e1ec16b4ddb0f578a92e47ce76b4ee78a5`, exact-head CI `30925523584`, `657 passed, 1 xfailed` on Python 3.11/3.12/3.13, all three PowerShell environments green, provider writes 0.
- Wave 0: canonical state and issue ownership.
- Wave 1: durable journaled VK upload lifecycle and exact-ID recovery — PR #66.
- Wave 2: fail-closed project/content identity and supported sync entrypoint — PR #68.
- Wave 3: shared HTTP ownership, safe-read retry taxonomy, redaction, and limiter infrastructure — PR #70.
- Wave 4: upload/wall separation — PR #71, merge `d85f7cf94b8ba0b30947291b3a08491239438843`.
- Wave 5: one tested fail-closed Windows/PowerShell operator — PR #75, merge `1a62779293a404e4654b6230644dfc78e9b20dc1`.
- Wave 6: one stable versioned source/plan/apply/result/reconciliation engine — PR #78, merge `c4c4d3233ec20b8f939343c5d667d8687d7ff040`.
- Wave 7: 15 supported mutation boundaries, exact proof ownership, corruption/fault/replay tests — PR #84, merge `df956bbbf19af6652f8711f95fb4fecf272e9951`, exact-head CI `30918639372`, `657 passed, 1 xfailed`, Pester `25/25`.
- Wave 8A: exact-first conflict-explicit video matching — PR #91, merge `09babd9176049d8271c50b6f5e44b7b0fd10d39f`, exact-head CI `30933582322`, `664 passed, 1 xfailed` on Python 3.11/3.12/3.13, all three PowerShell environments green, provider writes 0.

## Wave 8A guarantees now in `main`

The old full-cartesian fuzzy-first greedy matcher is retired.

The supported comparison order is now:

1. reviewed one-to-one source-ID → target-ID mapping;
2. unique exact-normalized-title pairs;
3. bounded token/trigram-indexed fuzzy fallback only for unresolved objects.

Permanent outcomes:

- duplicate exact titles are explicit `duplicate_exact_title` conflicts;
- exact-title pairs with an excessive duration delta are explicit `exact_title_duration_mismatch` conflicts;
- every non-unique fuzzy connected component is an explicit `non_unique_fallback` conflict;
- conflicts do not create a selected pair, source→target mapping, missing/upload candidate, or collection placement;
- matching is deterministic under source/target input permutation;
- reviewed mappings must reference existing objects and be one-to-one;
- result schema is `video-manager.cross-platform-comparison` version `2.0`;
- title-only collection lookup remains deliberately isolated and unresolved for Wave 8C rather than being silently treated as exact identity.

## Active engineering wave

Wave 8 / issue #86 remains the only active core-engineering owner. Wave 8A is complete; **Wave 8B is active**.

### Wave 8B — field-specific canonical identity

Required outcomes:

- separate canonicalizers for identity title, display title, description comparison, public URL, collection title, and version/variation token;
- preserve original value, canonical value, ruleset version, applied transformations, and digest;
- reject cross-project links, author/admin routes in public fields, and unknown URL profiles;
- do not collapse semantically distinct versions, collections, projects, or public/admin resources;
- exact per-field readback rather than substring, prefix, or combined-row heuristics;
- provider writes in development and CI remain `0`.

Later Wave 8 phases:

- Wave 8C — exact reviewed catalog/album identity and semantic membership;
- Wave 8D — authoritative downloader final path, cache SHA/size/fingerprint, structured ffprobe validation;
- Wave 8E — exact thumbnail identity and selected-thumbnail postflight;
- Wave 8F — integration proof and living-state synchronization.

Issue #33 remains the later catalog/publication workflow and is not authorized by Wave 8.

## Operation-scoped manager contract

The manager must solve the requested operation, not maintain a permanent perfect model of every provider account.

For a concrete upload/sync request it should:

1. validate only the supplied source set: file presence, video/audio streams, duration, container/codec policy, corruption, orientation, and SHA-256;
2. take a short fresh read-only snapshot only of the exact target community/channel surface needed for duplicate prevention and postflight;
3. produce a clear immutable plan with exact object identities, titles, descriptions, target collections, and expected delta;
4. execute through the supported operator with per-item durable stages and no wall publication unless separately authorized;
5. verify only the objects and remote delta created or changed by that operation;
6. return simple per-item totals for planned, uploaded, verified, duplicate, failed, and requires-attention states.

Do not require a global provider rescan, visual fingerprint of the whole library, GitHub commit of live provider state after every operation, or a multi-hour historical audit before a small bounded task.

A fresh provider snapshot is temporary operation evidence. GitHub stores schemas, policies, reviewed immutable manifests, and durable results — not a continuously mirrored mutable provider database.

## Permanent stage and evidence rules

- `file_selected` is not `upload_completed`.
- `upload_completed` is not `remote_object_visible`.
- `remote_object_visible` is not complete workflow verification.
- A later playlist, metadata, catalog, or wall failure does not erase an already verified upload and does not authorize retransmission.
- Batch state is per item and per stage, never one global Boolean.
- `already_correct` requires exact field-by-field readback; substring, prefix, or artist text inside a combined row is insufficient.
- A UI click is successful only after the intended control state changes; the visually nearest row/control is not identity.
- An observer/parser self-test does not prove attachment to the correct browser target, frame, request, or network event.
- PowerShell boundaries must explicitly test zero, one, and many pipeline results under strict mode.
- A URL-shaped value is not an upload ticket. The exact response field, allowlisted scheme/host/path, expiry and intended operation must be validated before sending media.
- Evidence levels remain distinct: designed, self-tested, canary-verified, and batch-verified.
- An accepted, processing, verified, or `unknown_requires_reconciliation` mutation is never replayed because a later stage failed or a current read did not find it.

## Supported reliability surface

- The only supported production operator remains `scripts/operator/Invoke-VideoManager.ps1`.
- Ambiguous provider mutations remain one-attempt and externally non-retryable.
- Existing journals form durable replay barriers.
- Any unknown outcome remains `unknown_requires_reconciliation`.
- Malformed, truncated, stale, wrong-digest, cross-project, wrong-owner, wrong-snapshot, wrong-policy, duplicate, or incomplete evidence fails closed.
- No completed Wave 0–8A work may be reimplemented through retired V1/V2/V3/current scripts or historical ZIP packages.

## Live-operation gate

Green architecture CI does not prove current remote state. Broad live upload/publication remains blocked until the exact project has:

1. a fresh operation-scoped read-only inventory;
2. reconciliation of local result/ledger files not stored in GitHub;
3. immutable Wave 6 source, plan, apply-intent, and policy evidence with exact digests;
4. one project-bound canary;
5. exact postflight proving only the expected remote delta.

No accepted, processing, unknown, or previously verified upload may be replayed from an old package, retired executor, remembered count, stale global snapshot, or pre-Wave-6 journal.

## Project boundaries

### `lord-god-strength`

- YouTube channel: `UCeSJsC6go2c9pdJCuUI1BYA`;
- OAuth alias: `fedor-milovanov`;
- VK community: `60805374`;
- VK owner: `-60805374`;
- shared VK credential alias `legendary-poet` is a credential label only, never project selection.

Closed facts that must not be rerun:

- reviewed duplicate cleanup: `confirmed_deleted=403`, `run=completed`;
- YouTube boundary `KobOzfBqzic`;
- YouTube `s512Opa8Eu4` maps to VK `-60805374_456241938`;
- theological article photo wave: 10/10 postponed posts, IDs 12471–12480;
- draft PR #29 is superseded and prohibited.

Long-form local evidence requiring exact reconciliation:

- reviewed newer-than-boundary items: `27`;
- already present: `1`;
- verified missing: `26`;
- SHA-256: `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`;
- local evidence: `data\vk-upload\verified-longform-26`;
- owner issue: #31.

Wall/live status: `BLOCKED_PENDING_FRESH_READ_ONLY_WALL_AUDIT_AND_LOCAL_LEDGER_RECONCILIATION`.

### `legendary-poet`

- YouTube channel: `UC-78ys2S3cQ3lpqgXfo-SvQ`;
- OAuth alias: `legendary-poet`;
- VK community: `235216998`;
- VK owner: `-235216998`.

Latest retained reviewed Shorts matrix:

- 56 exact YouTube Shorts;
- 41 exact YouTube→VK pairs;
- 15 confirmed missing;
- 0 ambiguous;
- 0 extra vertical VK objects;
- `BXZeRiEOHmQ` maps to VK `-235216998_456239039`;
- old `59/40/19/1` and historical `48` queues are retired as current authority;
- completed V3 Apply/postflight is not proven.

Status: `REVIEWED_MANIFEST_PREPARED / UPLOAD_COMPLETION_NOT_PROVEN`.

Do not upload the retained candidates until the exact canary/apply state and journal are recovered and reconciled through current evidence and the supported operator.

## Separate VK Audio state

VK Audio browser/internal-web experiments are not part of the supported core YouTube→VK Video engine.

Retained facts:

- one MP3 canary upload reached `upload_verified`; a later playlist failure did not authorize another upload;
- read-only browser-session probing found the exact audio object without persisting cookie values;
- one source series was reduced from 10 positions to 8 unique tracks;
- one later batch demonstrated per-item states: existing, verified, and deferred rather than one batch Boolean;
- playlist/metadata UI automation produced wrong-control clicks, false-positive `already_correct`, hangs, and observer attachment failures;
- observed upload tickets differed: a wrong `vk.ru` endpoint returned HTTP 413 while an observed `pu.vk.ru` endpoint succeeded.

Status: `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`.

Historical Audio ZIP versions are evidence only. A future incubation issue must first define versioned schemas, exact per-item stages, adapter boundaries, an allowlisted upload-ticket contract, bounded deadlines, canary, postflight, and reconciliation.

## Active issue graph

- #31 — long-form result and ledger reconciliation;
- #32 — exact VK Clips inventory and Shorts queue;
- #33 — catalog and publishing after dependencies;
- #37 — exact approved wall-cleanup scope;
- #38 — Shorts upload modes and final type/player behavior;
- #64 — master reliability roadmap;
- #85 — draft non-executable operational-history archive; archive/CI boundary remains Wave 10 scope;
- #86 — active Wave 8; Wave 8A completed, Wave 8B active;
- #88 — completed Audit Marathon V2;
- #91 — merged Wave 8A PR.

## Global prohibitions

- Do not mix `lord-god-strength` and `legendary-poet` IDs, credentials, links, journals, or manifests.
- Do not repeat completed Waves 0–7, Audit A0, or Wave 8A.
- Do not blind-retry `video.save`, upload-server POST, `wall.post`, `wall.edit`, `wall.delete`, or any ambiguous mutation.
- Do not execute a retired Python or PowerShell provider-write wrapper.
- Do not infer live success from green CI, an old package, format/duration/orientation, a visible object, stdout wording, a stale count, or substring matching.
- Do not perform bulk deletion outside issue #37’s exact immutable scope.
- Do not treat the historical `48 clips` package as a current manifest.
- Do not treat vertical format or duration as proof of VK Clip type/surface.
- Do not import VK Audio browser/internal-web attempts into core without a reviewed adapter contract.
