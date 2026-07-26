# YouTube comment recovery design

## Completion is evidence, not terminal wording

A channel-wide comment wave is complete only when all of the following artifacts agree:

1. the original signed plan is valid;
2. the original apply journal contains one completed attempt for every plan operation;
3. verify-only recovery confirms the planned live state without a create or update call;
4. a fresh channel snapshot is produced after recovery;
5. a fresh audit accounts for every public video exactly once;
6. every public video has exactly one channel-authored top-level comment;
7. a coverage certificate binds the plan, journal, snapshot, and audit by SHA-256.

A successful-looking terminal line is never accepted as evidence by itself.

## Import boundary

Low-level YouTube and VK packages must not eagerly import editorial renderers. Operational scripts import comment writers before they need rendering code, while renderers depend on editorial records. Eager package re-exports can therefore create an import cycle that appears only in a clean interpreter and remains invisible when a test process has imported modules in a different order.

Renderer and preview re-exports are lazy. CI launches operational imports in separate Python interpreters to preserve the production import order.

## Fail-closed audit arithmetic

The recovery certificate rejects:

- missing or non-object `counts`;
- boolean, negative, or non-integer count values;
- unknown statuses;
- duplicate video IDs;
- a mismatch between declared counts and per-video statuses;
- a mismatch between the video list and inventory size;
- zero or multiple channel-authored comments on any public video;
- any `missing`, `foreign_only`, `comments_disabled`, or `error` target.

This prevents absent JSON data from being coerced into false zeroes by a shell.

## Next hardening layer

The apply executor should use a completed journal attempt's exact `comment_id` as a no-write verification fallback when YouTube's list endpoint temporarily omits a newly created comment. The exact lookup must verify comment ID, target video, owner channel, and planned text. A completed journal entry must never be reclassified as a safe new create solely because a list response is temporarily incomplete.

After coverage closure, a separate content-integrity audit should distinguish:

- exact approved text;
- approved but outdated text;
- unmanaged channel text;
- duplicate channel comments;
- missing comments;
- API or moderation blockers.

Coverage and content integrity are different claims and should produce different certificates.
