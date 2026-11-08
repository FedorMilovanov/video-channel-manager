# VK native Clip golden path

Status: canonical architecture contract for future VK native-Clip work. This document is provider-inert and grants no mutation authority.

## Why this exists

The Legendary Poet lineage accumulated practical batch/resume/native-Clip experience. Milovi Issue #323 added stronger exact identity, temporal wall-incarnation, replay and mutation-governance rules. The reusable result is not a copy of one historical script and not another project-specific executor. It is one small production kernel with project-specific policies layered around it.

A future project must begin with a delta against this contract. Anything classified `SAME` is reused rather than reimplemented.

## Creator UI surfaces: Clip is not an ordinary Video (Issue #774, 2026-11-08)

Owner-verified incident: the same native Clip `-235216998_456239259` appeared in
ordinary video analytics and in the Creator Clips surface. An ordinary Video
editor could retain video metadata, but its postponed action called
`video.publish` and returned `Invalid request`; reopening the exact editor
proved that its date was still blank. **Do not retry that action, or infer
native-Clip schedule from ordinary Video editor fields.** The owner scheduled
the *existing* native Clip from Creator Clips; a separate read-only opening
confirmed `Отложен` with the owner-selected slot on 2026-11-10 at 16:25 MSK.

For any explicit, authorized Creator UI operation, use this contract:

1. Resolve the exact canonical `project_key`, community, `owner_id`,
   YouTube source ID, VK video ID, and **provider media type**. A vertical
   aspect ratio, duration, familiar title, or successful upload alone does
   not prove `type=short_video`; verify the native Clips object/surface.
2. Before uploading a source, reconcile **published, scheduled, draft,
   private, processing, and exact previously reserved IDs**. A missing
   list row is not proof of a missing remote object. Never dispatch a
   second upload for an accepted, processing, unknown, or scheduled item.
3. Native Clip scheduling belongs to the **native Clips editor**, not the
   ordinary Video editor or an ad-hoc `video.publish` call. Freeze the
   owner-selected local date/time and an independently justified timezone;
   do not substitute a proposed slot for the user's actual saved slot.
   Disable separate wall-post creation unless it has its own approved
   intent and exact attachment duplicate check.
4. The native Clip **caption/description field** is authoritative for
   that surface. Text seen in ordinary Video analytics is not a substitute.
   Read the exact native caption and schedule on a **fresh editor opening**
   after saving; the original source URL and project site URL must remain.
5. Preserve text semantically and structurally. If the provider removes
   hashtags, blank lines, or other text, record the **exact before/after
   diff** and classify unapproved loss as `conflict`. The presence of the
   site and original URL alone does **not** prove full caption fidelity.
   Do not call a normalized or truncated caption `exact_verified`
   unless a separately reviewed provider-normalization policy accepts
   the precise change.
6. A click, modal closing, HTTP 200, or success-looking toast is not
   `verified`: only exact-ID, exact-type, exact scheduled-slot and
   native-caption readback establishes the claimed state. Failed or
   ambiguous writes remain `may_exist` until read-only reconciliation.
   Do not retry `video.publish` or reselect the MP4 to resolve ambiguity.
7. Browser writes must use the existing **community-scoped single-writer
   lock and durable provider-effect journal**. A standalone Playwright
   script with per-file local logs does not automatically satisfy that
   contract. If these safeguards cannot be proven, use owner interaction
   or read-only diagnosis rather than another browser mutation.

This is an operational safeguard, not a new second VK Clip uploader, an API
authorization, or a direction to retroactively edit existing content.

## Owner-wide absence gate for NEW ordinary VK Video uploads (Issue #774)

The ordinary VK Video Wave previously checked `video.get` immediately before
`video.save`. This is **public ordinary Video only**, not proof that the
same original is absent from Creator's drafts, postponed queue, private or
processing ordinary media, or native Clips. As demonstrated by Issue #774,
a private original can coexist with an already-public or deferred *different
VK ID* for the same YouTube source.

**Effective guard:** every **new reservation** in
`vk-native-video-wave-v2` requires both:

1. a fresh independently reviewed complete owner Creator absence evidence
   file, bound by path and SHA-256 to the individual source operation; and
2. the existing fresh public `video.get` exact URL/title-duration guard
   under the same community writer lock, immediately before dispatch.

The owner-evidence gate is deliberately fail-closed when no valid file was
supplied. Preparation without it remains **provider-inert** and reports
`owner_creator_absence_evidence_attached=false`; it cannot initiate a
new provider reservation. Existing journaled reservations are reconciled
by their **exact known VK ID**, without fresh absence evidence and without
any new media upload. The proof is never a publication authorization.

The `--owner-absence-evidence` option of `wave video prepare` accepts a
reviewed JSON file containing the following contract; fields below are a
**schema illustration, not a fabricated or reusable owner snapshot**:

```json
{
  "schema_name": "video-manager.vk-owner-creator-absence-v1",
  "project_key": "legendary-poet",
  "community_id": 235216998,
  "owner_id": -235216998,
  "source_channel_id": "UC-78ys2S3cQ3lpqgXfo-SvQ",
  "source_video_id": "<EXACT_REVIEWED_YT_ID>",
  "capture_method": "owner_authenticated_creator_read_only",
  "read_only": true,
  "provider_effect": "safe_read_only",
  "verdict": "confirmed_absent",
  "observed_at": "<CURRENT_TIME_WITH_UTC_OFFSET>",
  "surfaces": {
    "ordinary_video": {
      "pagination_complete": true,
      "covered_states": ["published", "postponed", "draft", "private", "processing", "accepted"],
      "exact_source_matches": [],
      "unresolved_candidates": []
    },
    "native_clip": {
      "pagination_complete": true,
      "covered_states": ["published", "postponed", "draft", "private", "processing", "accepted"],
      "exact_source_matches": [],
      "unresolved_candidates": []
    }
  }
}
```

**The JSON is a reviewed owner/operator assertion, not cryptographically
authenticated VK evidence.** Never set `pagination_complete=true` or
`confirmed_absent` unless an authenticated owner session genuinely
inspected the entire relevant surface and all relevant statuses and
resolved every source/near-duplicate collision. Public APIs alone,
partially loaded Creator lists, duration-only matching, and experimental
`shortVideo.getOwnerVideos` are NOT sufficient. A known match or unknown
candidate must remain explicit and block the upload; never delete it from
the evidence to obtain a passing verdict. The proof expires after
**60 minutes** and is revalidated at provider dispatch after preparation.
If reliable complete owner observation is unavailable, the upload
remains blocked instead of falling back to public-only absence.

This additional gate is **not** retroactive approval to reupload Mavrin
`456239258`, Mayakovsky `456239259`, or any historical duplicate;
all belong to existing provider IDs. No new browser client, account,
secondary VK uploader, scheduled-wall action, or automatic retrial is
introduced.

## Canonical kernel

The reusable native-Clip kernel owns these semantics exactly once:

1. exact project/community/owner binding before provider mutation;
2. bounded reviewed source manifest and immutable source identity;
3. exact media QC and digest binding;
4. exact existing-Clip reconciliation before new dispatch;
5. one reservation lifecycle;
6. one binary-transfer lifecycle;
7. durable dispatch evidence before ambiguous mutations;
8. no blind replay after a provider effect may have occurred, while a definite no-effect provider rejection must not become an unrecoverable dead end;
9. native `short_video` verification using phase-appropriate readiness;
10. durable per-item completion before advancing the batch.

Direct provider reservation/transfer primitives remain centralized in the existing generic VK upload writer/lifecycle. New projects must not invent a second direct `video.save` or binary-transfer owner.

## Extensions

Extensions may add semantics after the core child is durably identified, but may not redefine core upload identity or replay rules.

### WallPolicy.DISABLED

Use when the project requires native Clips without a separate wall publication. Historical Legendary Poet native-Clip work is the nearest operational lineage for this mode.

### ScheduledWallExtension

Adds one logical scheduled mapping:

`source_id + clip_remote_id + frozen_publish_slot`

The provider `post_id` is incarnation-local evidence, not permanent logical identity. Before the frozen slot, a journaled postponed incarnation remains exact. After the slot, exact old-ID readback plus one uniquely proven published successor may represent the same mapping. Aggregate omission never proves exact-object absence by itself.

An unresolved `wall_intent`/`wall_may_exist` may adopt a uniquely bound published incarnation after the frozen slot; publication before the slot is a blocker. Recovery never blindly repeats the original wall mutation.

### PromotionExtension

Metadata promotion has a reviewed BEFORE/AFTER contract:

- exact reviewed legacy copy; or
- exact promoted copy.

Any third text state is conflict, even if it still contains a recognizable source URL or belongs to the correct remote object. Target identity does not grant overwrite authority.

Before the first promotion mutation, the whole bounded batch is read-only preflighted. Deterministic drift on a later item must be discovered before partial edits to earlier items.

Every ambiguous edit persists `dispatch_started` before the provider call, reconciles only from exact readback, and never blindly replays.

An explicit rejection that returned no ticket and no bytes is the one recoverable terminal state. Reopening it is a separate reviewed action, not an automatic retry: the caller must be a later, separately invoked Wave, the durable object identity must be unchanged, the rejected attempt must be archived under `known_rejections`, and current media must be re-verified before a new reservation. Any reservation, transfer or verification evidence keeps the journal non-replayable.

### CatalogExtension

Albums/catalog placement is a separate extension. It may consume a durably verified Clip but may not reopen upload authority.

## Concurrency contract

One VK community has one local mutation mutex, regardless of executor name or operation name. Lock identity is scoped to the exact `community_id`; operation-specific filenames are not independent authorization domains.

This prevents rollout, resume, finalizer, anomaly reconciliation, editorial maintenance, or future extensions from mutating the same community concurrently merely because they chose different lock filenames.

## Mutation contract

For every provider mutation:

`reviewed intent -> durable intent -> durable dispatch_started -> one provider dispatch -> exact reconciliation -> verified`

If a process restarts after durable dispatch evidence, it may reconcile or block. It may not reacquire blind replay authority.

Legacy durable intent created by code that did not persist a separate dispatch marker is conservatively treated as potentially dispatched unless exact evidence proves a terminal state.

Each destructive effect has one owning phase. Later phases consume durable outcome evidence rather than reacquiring delete/upload/edit authority.

## Readiness versus identity

Fresh/resumed upload readiness may depend on processing/playability/title/type fields needed to prove a newly uploaded object usable. A child already durably verified is not invalidated solely by a later weaker provider projection. Preservation/final phases use only the stable invariants authorized for that phase.

## New-project delta requirement

Before project-specific runtime code is written, record a short delta with these sections:

### SAME

Typical reusable items:

- reservation semantics;
- binary-transfer semantics;
- Clip logical identity;
- ambiguous-effect reconciliation;
- durable journal lifecycle;
- no-replay contract;
- community-scoped writer serialization.

### CHANGED

Typical configuration-only items:

- project/community/owner IDs;
- source manifest;
- copy factory;
- duration/media policy where explicitly reviewed.

### ADDED

Only genuinely new semantics belong here, for example:

- scheduled wall;
- promotion;
- catalog placement.

### FORBIDDEN

A new project must not introduce, without an explicit architecture migration:

- a project-specific direct `video.save` owner;
- a second binary-transfer lifecycle;
- duplicated existing-Clip reconciliation semantics;
- a different definition of ambiguous mutation replay;
- an operation-named lock that bypasses the community mutex;
- a phase that requires a postcondition only a later phase is authorized to establish.

## Migration rule

Do not refactor an in-progress provider rollout merely to make the architecture prettier. Preserve its durable identities and finish it through the current reviewed compatibility path first. After exact live completion, extract the stable shared kernel behind compatibility tests and migrate project adapters without replaying provider effects.

## Completion evidence

Repository implementation, CI success and live provider completion are separate facts. A project using this Golden Path is live-complete only when its own exact provider postflight proves the bounded target state. No document, merged PR or green test run substitutes for that readback.
