# VK upload and wall safety contract

Updated: 2026-09-11  
Owner: Wave 4 / issue #36

## Invariant

A VK video upload and a VK wall publication are separate remote mutations. The supported upload path never authorizes a wall mutation implicitly.

Every ordinary native-video upload binds:

- `project_key`;
- exact VK `community_id` and negative `owner_id`;
- `wall_mutation_authorized: false`;
- explicit `video.save` wall-publication flags.

Ordinary native-video upload does not read `wall.get` before or after the video mutation. Wall availability is therefore not an upload prerequisite. Missing, true, coerced, wrong-project, wrong-community, wrong-owner, or digest-tampered wall authorization still fails before provider dispatch.

## Upload reservation

Primary VK API schema 5.199 confirms all three relevant `video.save` parameters. Every supported reservation therefore sends explicitly:

- `wallpost=0`;
- `auto_publish=0`;
- `repeat=0` for the generic upload path.

`repeat` controls playback looping rather than wall publication, but the generic upload contract still fixes it to zero so behavior is not inherited from an implicit provider default. Any future loop exception requires a separate reviewed policy type; it cannot be inferred from a loose mapping or truthy value.

The ordinary upload wall boundary is intentionally small:

1. all three explicit zero-valued `video.save` switches;
2. versioned, self-digested `wall_mutation_authorized=false` bound to operation identity;
3. upload and wall publication remain separate commands/workflows.

The upload lifecycle still journals reservation intent before `video.save`, persists the exact returned owner/video identity, forbids blind retransmission after an ambiguous dispatch, and verifies the exact VK video ID. Wall reads are not part of that success condition.

## Optional wall evidence

The shared upload state machine still accepts a bounded upload-wall guard for specialized workflows that explicitly require wall-state evidence. When such a guard is supplied, the existing before/after comparison and fail-closed wall reconciliation semantics remain available.

The ordinary `VkNativeVideoUploadAdapter` does not supply that guard. It performs no `wall.get` preflight or postflight and records success from exact video readiness instead. This removes the accidental availability dependency `wall.get -> video.save` while preserving the separate wall-publication workflow below.

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

- wall snapshot reads, when a wall workflow actually needs them, are classified safe reads and may use the bounded retry policy;
- VK API code `9` (`Flood control`) is a distinct non-auto-retry condition for methods that are called; native-video upload no longer calls `wall.get` merely to prove that wall publishing was disabled;
- `wall.post`, `wall.edit`, `wall.delete`, upload reservation, upload-server POST, and all other mutations remain explicit ambiguous mutations;
- mutation transport loss, HTTP 429/5xx, and provider-transient responses are one attempt and externally non-retryable;
- `guid` is an additional duplicate guard, not a substitute for published+postponed preflight or postflight.

## Definition of done

Wave 4 is complete only when the contract is enforced by production code and regression tests, exact-head CI passes on Python 3.11/3.12/3.13, all supported call sites use the new signatures, the final diff contains no temporary workflow or provider artifact, living state is synchronized, and implementation/CI performed zero provider writes.
