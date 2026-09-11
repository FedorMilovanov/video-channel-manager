# VK upload and wall safety contract

Updated: 2026-09-10  
Owner: Wave 4 / issue #36

## Invariant

A VK video upload and a VK wall publication are separate remote mutations. The supported upload path never authorizes a wall mutation implicitly.

Every upload plan or runtime contract must therefore bind:

- `project_key`;
- exact VK `community_id` and negative `owner_id`;
- `wall_mutation_authorized: false`;
- a read-only bounded published+postponed upload-wall guard captured before execution;
- an exact bounded postflight guard and delta after any upload request may have reached VK.

Missing, true, coerced, wrong-project, wrong-community, wrong-owner, or digest-tampered wall authorization fails before media verification or provider dispatch.

## Upload reservation

Primary VK API schema 5.199 confirms all three relevant `video.save` parameters. Every supported reservation therefore sends explicitly:

- `wallpost=0`;
- `auto_publish=0`;
- `repeat=0` for the generic upload path.

`repeat` controls playback looping rather than wall publication, but the generic upload contract still fixes it to zero so behavior is not inherited from an implicit provider default. Any future loop exception requires a separate reviewed policy type; it cannot be inferred from a loose mapping or truthy value.

The upload wall firewall is the combination of:

1. all three explicit zero-valued `video.save` switches;
2. versioned, self-digested `wall_mutation_authorized=false` bound to operation identity;
3. published+postponed bounded before-guard digest;
4. mandatory bounded postflight guard/delta;
5. terminal reconciliation when any unexpected or incomplete wall delta appears.

Upload recovery never auto-deletes an unexpected post.

## Batch baseline and per-operation evidence

The supported native-video path captures one bounded two-surface upload-wall guard for the exact community before the first batch mutation and stores it once in durable batch evidence. The guard reads one head page from `filter=owner` and one head page from `filter=postponed`, with the provider-reported total counts bound into the digest.

Each upload operation stores the immutable guard digest and capture evidence, then persists its own bounded after-guard digest and delta. This proves that `wallpost=0` / `auto_publish=0` did not create or transition a head wall object without crawling the complete wall before every video. A total-count change, created/removed/changed head identity, wrong owner, invalid payload, or unavailable postflight is non-clean and stops the wave.

A historical `reserved`, `upload_started`, `processing`, `unknown`, or `verified` record without a pre-dispatch baseline is not granted a fresh baseline retroactively. It stops with `unknown_requires_reconciliation`/recovery-required semantics. A previously verified record is reusable only when its stored wall delta is explicitly `clean`.

## Snapshot scope

Two distinct read models are intentional.

For video-upload isolation, the bounded upload-wall guard covers the head of both surfaces for one exact VK owner:

- published posts (`filter=owner`);
- postponed posts (`filter=postponed`).

Each normalized entry binds:

- owner ID;
- post ID;
- published/postponed surface;
- publication timestamp;
- normalized text digest;
- normalized attachment identities.

The upload-guard digest is calculated over canonical stable ordering plus provider-reported surface totals. Its purpose is narrow: prove wall isolation for a native video upload.

For an actual `wall.post` workflow, a complete published+postponed snapshot remains mandatory. Its page totals and surface completeness are evidence, not assumptions; a truncated scan, invalid object, wrong owner, or exhausted configured limit blocks publication before mutation.

A delta reports exact created, changed, deleted, and surface-specific entries. Any non-clean upload-guard delta blocks `verified` and automatic continuation.

## Postponed publication

The default supported wall-write path is postponed publication through a separate immutable plan and journal.

A postponed operation binds:

- exact project/community/owner;
- attachment/video identity;
- rendered text and digest;
- timezone-aware future `publish_at` / exact `publish_date`;
- deterministic `guid`;
- source snapshot evidence;
- plan digest;
- published+postponed preflight evidence.

Preflight scans both surfaces for exact attachment duplicates and postponed schedule-slot collisions. Missing or incomplete surface coverage blocks before `wall.post`.

`wall.post` remains one ambiguous mutation attempt. A lost response, HTTP 429/5xx, transport error, or invalid response is never replayed blindly. Recovery captures a fresh two-surface snapshot and succeeds only when the exact one expected postponed post is the sole approved delta. A published object is not interchangeable.

## Immediate publication exception

Immediate wall publication is blocked by default. A permitted exception requires a different immutable per-post authorization with exact project/community/owner binding, explicit confirmation, before-snapshot, intent journal, one mutation attempt, and postflight verification.

No generic immediate-post command may treat the exception as a reusable project default.

## Cleanup boundary

Wave 4 contains no bulk deletion or automatic remediation. Issue #37 remains the only owner of its exact reviewed cleanup scope. Upload and publication recovery can classify unexpected posts but cannot delete them.

## Retry boundary

- ordinary snapshot reads are classified safe reads and may use the bounded retry policy;
- VK API code `9` (`Flood control`) is a distinct non-auto-retry condition: the exact account+method opens a durable local circuit after the first observed response, and later processes stop before network until that exact circuit is explicitly cleared; no universal recovery TTL is assumed;
- `wall.post`, `wall.edit`, `wall.delete`, upload reservation, upload-server POST, and all other mutations remain explicit ambiguous mutations;
- mutation transport loss, HTTP 429/5xx, and provider-transient responses are one attempt and externally non-retryable;
- `guid` is an additional duplicate guard, not a substitute for published+postponed preflight or postflight.

## Definition of done

Wave 4 is complete only when the contract is enforced by production code and regression tests, exact-head CI passes on Python 3.11/3.12/3.13, all supported call sites use the new signatures, the final diff contains no temporary workflow or provider artifact, living state is synchronized, and implementation/CI performed zero provider writes.
