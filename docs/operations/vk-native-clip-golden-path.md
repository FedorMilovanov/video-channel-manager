# VK native Clip golden path

Status: canonical architecture contract for future VK native-Clip work. This document is provider-inert and grants no mutation authority.

## Why this exists

The Legendary Poet lineage accumulated practical batch/resume/native-Clip experience. Milovi Issue #323 added stronger exact identity, temporal wall-incarnation, replay and mutation-governance rules. The reusable result is not a copy of one historical script and not another project-specific executor. It is one small production kernel with project-specific policies layered around it.

A future project must begin with a delta against this contract. Anything classified `SAME` is reused rather than reimplemented.

## Canonical kernel

The reusable native-Clip kernel owns these semantics exactly once:

1. exact project/community/owner binding before provider mutation;
2. bounded reviewed source manifest and immutable source identity;
3. exact media QC and digest binding;
4. exact existing-Clip reconciliation before new dispatch;
5. one reservation lifecycle;
6. one binary-transfer lifecycle;
7. durable dispatch evidence before ambiguous mutations;
8. no blind replay after a provider effect may have occurred;
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
