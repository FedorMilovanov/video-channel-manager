# VK upload and wall safety contract

Updated: 2026-08-04  
Owner: Wave 4 / issue #36

## Invariant

A VK video upload and a VK wall publication are separate remote mutations. The supported upload path never authorizes a wall mutation implicitly.

Every upload plan or runtime contract must therefore bind:

- `project_key`;
- exact VK `community_id` and negative `owner_id`;
- `wall_mutation_authorized: false`;
- a read-only published+postponed wall snapshot identity and digest captured before execution;
- an exact postflight wall snapshot and delta after any upload request may have reached VK.

Missing, true, coerced, wrong-project, wrong-community, or wrong-owner wall authorization fails before provider configuration, tokens, or network.

## Upload reservation

Every supported `video.save` reservation sends `wallpost=0` explicitly.

No safety claim is derived from `repeat`; that parameter describes playback looping in the available SDK schemas. `auto_publish` is not treated as verified current primary-contract evidence and is not required blindly.

The wall firewall is the combination of:

1. explicit `wallpost=0`;
2. `wall_mutation_authorized=false` bound to the upload operation;
3. published+postponed before-snapshot digest;
4. mandatory postflight snapshot/delta;
5. terminal reconciliation when any unexpected wall delta appears.

Upload recovery never auto-deletes an unexpected post.

## Snapshot scope

A wall snapshot covers both surfaces for one exact VK owner:

- published posts;
- postponed posts.

Each normalized entry binds at least:

- owner ID;
- post ID;
- published/postponed surface;
- publication timestamp;
- normalized text digest;
- normalized attachment identities;
- deterministic `guid` evidence when available;
- canonical URL evidence when available.

The snapshot digest is calculated over a canonical, stable ordering. A delta reports exact created, changed, deleted, and surface-moved entries. Any non-empty delta during an upload operation is unexpected and blocks automatic continuation.

## Postponed publication

The default supported wall-write path is postponed publication through a separate immutable plan and journal.

A postponed operation binds:

- exact project/community/owner;
- attachment/video identity;
- rendered text and digest;
- timezone-aware future `publish_at`;
- deterministic `guid`;
- source snapshot evidence;
- plan digest;
- locked re-preflight evidence.

Preflight scans published and postponed posts for exact attachment, canonical URL, deterministic `guid`, reviewed text identity, exact slot collisions, and configured near-slot collisions.

Intent is durably recorded before `wall.post`. A lost response is one ambiguous mutation attempt and becomes an unknown reconciliation state. It is never replayed blindly. Success requires verification of the exact postponed object; a published object is not interchangeable.

## Immediate publication exception

Immediate wall publication is blocked by default. A permitted exception requires a separate immutable per-post authorization with exact project/community/owner binding, explicit confirmation, before-snapshot, intent journal, one mutation attempt, and postflight verification.

No generic immediate-post command may treat the exception as a reusable project default.

## Cleanup boundary

Wave 4 contains no bulk deletion or automatic remediation. Issue #37 remains the only owner of its exact reviewed cleanup scope. Upload and publication recovery can classify unexpected posts but cannot delete them.

## Retry boundary

- snapshot reads are classified safe reads and may use the Wave 3 bounded retry policy;
- `wall.post`, `wall.edit`, `wall.delete`, upload reservation, upload-server POST, and all other mutations remain explicit ambiguous mutations;
- mutation transport loss, HTTP 429/5xx, and provider-transient responses are one attempt and externally non-retryable;
- `guid` is an additional duplicate guard, not a substitute for published+postponed preflight or postflight.

## Definition of done

Wave 4 is complete only when the contract is enforced by production code and regression tests, exact-head CI passes on Python 3.11/3.12/3.13, the final diff contains no temporary workflow or provider artifact, and implementation/CI performed zero provider writes.
