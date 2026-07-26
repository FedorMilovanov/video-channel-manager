# YouTube comment live rollout: incidents, lessons, and permanent rules

This document preserves the operational knowledge gained while rolling sourced top-level comments across the public videos of **The Legendary Poet**. It complements the command-oriented runbooks: the purpose here is to record failure modes, root causes, and the safeguards that followed from them.

## Rollout context

The first complete audit covered 127 public videos:

- 82 `foreign_only` — comments existed, but none was authored by the channel;
- 11 `missing` — no top-level comments existed;
- 34 `owned_present` — a channel-authored top-level comment existed.

The rollout was split into reviewed waves rather than one blind generation pass:

1. a 15-video update batch;
2. Classic Wave 1 with 25 guarded creates;
3. Classic Wave 2 with 25 guarded creates;
4. a final create-only wave derived from a fresh live audit.

A wave succeeds only when every planned operation is verified and its journal reaches `completed`. Complete channel coverage is established by a new channel-wide audit, never by arithmetic alone.

## 1. Editorial standard and validator disagreed on the VK label

Wave 2 stopped safely before any write because the validator still required:

```text
*Сообщество проекта VK:*
```

while the approved standard and records used:

```text
*Сообщество проекта в VK:*
```

The wording had been duplicated in documentation, the schema-v2 validator, renderer, plan workaround, and package seed scripts.

### Permanent rule

There is one canonical viewer-facing label:

```text
*Сообщество проекта в VK:*
```

The historical form remains accepted only as stored migration input. Every renderer, preview, and signed plan emits the canonical wording. A wording migration must not invalidate reviewed facts, source bindings, timestamps, or target IDs; compatibility belongs in the renderer/validator contract, not in disposable wave scripts.

## 2. Successful writes may not be immediately visible

YouTube can accept a create or update before the comment appears consistently in `commentThreads.list`, `comments.list`, moderation views, or the public UI.

### Permanent rule

Verification is eventual but bounded:

1. retain the successful write response;
2. retry exact reads with increasing delays;
3. verify comment ID, owner, target, and canonicalized text;
4. use the write response only as a temporary safe fallback;
5. require the final postflight to observe every planned operation as applied.

Never issue a second create merely because the first result is not immediately indexed.

## 3. Published-only reads can hide channel comments

A channel-authored comment may temporarily appear under `heldForReview` or `likelySpam`. Non-published moderation filters may also be unsupported in some request contexts.

### Permanent rule

The live reader:

- reads `published` comments;
- attempts `heldForReview` and `likelySpam`;
- deduplicates by exact comment ID;
- treats failure of `published` as fatal;
- tolerates unsupported non-published views;
- preserves moderation state when available.

## 4. Direct comment resources can omit target context

An exact `comments.list` response may contain the ID and text without enough fields to reconstruct the video and channel in every observed response shape.

### Permanent rule

Exact reads inside a guarded operation carry reviewed context:

- expected comment ID;
- expected video ID;
- expected channel ID.

Returned target fields, when present, must match that context. Ownership and exact text are still verified. A direct read can never silently retarget a mutation.

## 5. Update preflight must inspect the reviewed target video

A direct lookup alone was not sufficient for safe update classification because of incomplete metadata and target ambiguity.

### Permanent rule

Update preflight finds the exact expected comment among channel-owned top-level comments read from the reviewed video and verifies:

- exact comment ID;
- exact reviewed-before text;
- exact target video;
- exact channel owner.

A manual edit creates a conflict. Approved new text never authorizes overwriting an unknown live state.

## 6. One audit is not a write lock

Live state can change after plan construction or after the operator's first preflight.

### Permanent rule

Execution uses three checks:

1. channel-wide audit bound to the signed snapshot;
2. complete live preflight before confirmation;
3. the same complete preflight repeated under the channel writer lock.

The locked ready set must match the confirmed ready set exactly. Any new comment, deletion, edit, ownership change, disabled-comments state, or inaccessible target aborts the batch.

## 7. Plan success is not channel closure

A signed plan can complete perfectly while unplanned `missing` or `foreign_only` videos remain elsewhere.

### Permanent rule

Two success conditions are reported separately:

- **plan success:** every signed operation is verified;
- **channel closure:** a fresh channel-wide postflight reports `missing + foreign_only == 0`.

`comments_disabled` and API `error` states are separate blockers. They are neither successful coverage nor silent create targets.

## 8. Total inventory and public inventory are different

A scan can export more videos than the comment audit reads because private, unlisted, scheduled, or otherwise non-public items can exist in the snapshot.

Always compare:

- total snapshot videos;
- selected public videos;
- public-video set SHA-256;
- exact audit coverage IDs.

Never infer an incomplete audit from the total export count alone.

## 9. Human-readable output is not an automation contract

The first refresh wrapper extracted confirmation counts from stable console lines. That worked during rollout, but terminal wording is not authoritative data.

### Permanent rule

`preflight_youtube_comment_plan.py` now emits schema `video-manager.youtube-comment-preflight` version 1. The refresh workflow binds this report to the signed plan by exact:

- channel ID;
- source snapshot;
- plan SHA-256;
- operation count.

It also requires:

```text
ready + already_applied + blockers == planned
```

The human-readable summary remains for operators, while automation consumes JSON. This report does not replace the executor's own preflight or the locked re-preflight.

## 10. CI steps with `continue-on-error` can look green

Ruff, mypy, audit, and pytest logs are uploaded even when a gate fails. A continued step can appear successful in the UI while `steps.<id>.outcome` is `failure`; the final `Enforce quality gates` step then correctly fails the job.

### Permanent rule

1. inspect the original step artifact;
2. do not disable the final gate;
3. fix the underlying Ruff, format, mypy, audit, or pytest failure;
4. require a green matrix on every supported Python version.

During this hardening pass the strict gate exposed stale VK expectations, an obsolete workaround test, formatting drift, and a final Ruff F541. The causes were fixed; the gate was preserved.

## 11. `create-missing` is not the same as `create-only`

Enabling creates can still allow reviewed updates when the content directory also contains records for already covered videos.

### Permanent rule

Final channel-closing waves use both:

```text
--create-missing --creates-only
```

Create-only mode omits update planning and then verifies every signed operation has action `create`. This is an independent safety boundary, not an assumption about folder contents.

## Editorial scaling: research dossiers, not title-based invention

Repeated musical versions of one work should share a researched dossier, but not identical comments. A dossier may supply verified angles such as:

- composition history;
- first publication;
- manuscript or edition history;
- textual structure;
- archival provenance;
- adaptation or performance history.

Every target still requires:

- a unique `variation_key`;
- a distinct heading or factual angle;
- a question tied to that angle or arrangement;
- only relevant links;
- exact source IDs supporting the factual paragraph.

This scales research without copy-paste comments or facts invented from titles.

## Journal and recovery rules

The apply journal is part of the safety model:

- it is written before every remote mutation;
- every attempt records action, video ID, timestamps, result IDs, and verified text hash;
- partial or ambiguous failures resume with the same signed plan and journal;
- journals are never deleted to force a rerun;
- a new plan SHA-256 receives a distinct journal;
- completed operations become `already_applied` on rerun rather than duplicates.

## Recommended final-wave command

```powershell
python -X utf8 .\scripts\refresh_youtube_comments.py `
  --account legendary-poet `
  --channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --content-dir <approved-wave-directory> `
  --create-missing `
  --creates-only `
  --require-complete-coverage `
  --require-no-review-only `
  --postflight-audit `
  --require-zero-tail `
  --execute `
  --confirm-channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --write-delay 3
```

The workflow stops before writes when coverage is incomplete. When verified writes succeed but the channel-wide postflight still finds an actionable tail, it reports that distinction explicitly; completed remote writes are not rolled back or hidden.

## Current implementation state

The live-proven behavior now lives in the core repository:

- moderation-state reads and deduplication are in `YouTubeCommentWriter`;
- exact direct reads carry target context;
- creates and updates use bounded delayed verification;
- the historical compatibility executor is a thin UTF-8 entrypoint rather than a second monkeypatched implementation;
- complete-coverage, no-review-only, strict create-only, postflight, and zero-tail modes are first-class workflow options;
- preflight confirmation values come from a signed-plan-bound JSON artifact.

The compatibility filename remains available so saved Windows commands, wave launchers, and recovery instructions do not break. Its eventual deprecation must be a separate migration, never an unrelated cleanup.
