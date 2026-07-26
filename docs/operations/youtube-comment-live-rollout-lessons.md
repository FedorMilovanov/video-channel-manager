# YouTube comment live rollout: incidents, lessons, and permanent rules

This document records operational knowledge gained while rolling sourced top-level comments across the public videos of **The Legendary Poet**. It is intentionally separate from the command-oriented runbook: the goal here is to preserve the failure modes, design decisions, and evidence behind the safeguards.

## Rollout context

The first complete audit covered 127 public videos and classified them as:

- 82 `foreign_only` — comments existed, but none was authored by the channel;
- 11 `missing` — no top-level comments existed;
- 34 `owned_present` — exactly one or more channel-authored top-level comments existed.

The rollout was deliberately split into reviewed waves rather than one blind generation pass:

1. a 15-video update batch for already reviewed comments;
2. Classic Wave 1 with 25 guarded creates;
3. Classic Wave 2 with 25 guarded creates;
4. a final create-only wave prepared from a fresh audit for the remaining live tail.

A wave is considered successful only when every planned write is verified by a post-write read and the apply journal reaches `completed`. The final channel state must be established by a new channel-wide audit, not by arithmetic alone.

## Incident 1: editorial standard and validator disagreed on the VK label

### Symptom

Wave 2 stopped at validation before any YouTube write:

```text
VK link label must be exactly *Сообщество проекта VK:*
```

The current editorial standard and reviewed records already used the more natural viewer-facing form:

```text
*Сообщество проекта в VK:*
```

### Root cause

The wording existed independently in several layers:

- editorial documentation;
- schema-v2 validator;
- YouTube renderer;
- plan-builder compatibility replacement;
- package-specific seed scripts.

One layer was updated while another still enforced the historical string.

### Permanent rule

There is one canonical viewer-facing label:

```text
*Сообщество проекта в VK:*
```

The historical label remains accepted as stored input so old approved records do not require a risky mass rewrite. Rendering always normalizes either accepted form to the canonical output. New records and examples must use only the canonical form.

### Why compatibility matters

A wording-only migration must not invalidate already reviewed facts, source bindings, review timestamps, or target IDs. Compatibility belongs in the renderer/validator contract, not in disposable wave scripts.

## Incident 2: a successful API write may not be immediately visible everywhere

### Symptom

A created or updated comment can be returned successfully by the write endpoint but remain absent from list results for several seconds.

### Root cause

YouTube comment indexing is not guaranteed to be instantaneous across:

- `commentThreads.list`;
- `comments.list`;
- moderation views;
- public UI rendering.

### Permanent rule

Verification is eventual but bounded:

1. retain the successful write response;
2. retry exact reads with increasing delays;
3. verify comment ID, ownership, target, and canonicalized text;
4. allow the write response only as a temporary fallback;
5. require the complete final postflight to observe every planned operation as applied.

Never issue a second create merely because the first result is not immediately indexed.

## Incident 3: published-only reads can hide channel comments

### Symptom

A comment owned by the authenticated channel may be absent from the default published thread listing while visible under another moderation state.

### Root cause

Channel-authored comments may temporarily appear under `heldForReview` or `likelySpam`, and API support for moderation filters can vary by request context.

### Permanent rule

The live reader must:

- read `published` comments;
- attempt `heldForReview` and `likelySpam` views;
- deduplicate by comment ID;
- treat failure of the published view as fatal;
- tolerate unsupported non-published moderation views;
- retain moderation state in the audit and journal when available.

## Incident 4: direct comment resources may lack enough target context

### Symptom

An exact `comments.list` response can contain the comment ID and text but omit fields needed to reconstruct the target video/channel reliably in every observed response shape.

### Permanent rule

Exact reads used during a guarded operation must carry reviewed context:

- expected video ID;
- expected channel ID;
- expected comment ID.

The system may reconstruct the snapshot using that context, but it must still verify ownership and exact text. A direct lookup is not allowed to silently retarget a write.

## Incident 5: update preflight must inspect the target video's owned comments

### Symptom

Relying only on a direct comment lookup made update classification vulnerable to incomplete metadata and target ambiguity.

### Permanent rule

Update preflight finds the exact expected comment among channel-owned top-level comments read from the reviewed target video. It then verifies:

- exact comment ID;
- exact reviewed-before text;
- exact target video;
- exact channel ownership.

A manually edited comment becomes a conflict. The bot must never overwrite it merely because the new text is approved.

## Incident 6: one audit is not a write lock

### Symptom

The live state can change after a plan is built or after the first preflight.

### Permanent rule

Every execution uses three state checks:

1. channel-wide audit bound to the signed snapshot;
2. complete live preflight before confirmation;
3. the same complete preflight repeated under the channel writer lock.

The operation set under the lock must match the confirmed ready set exactly. Any new comment, deletion, edit, ownership change, disabled-comment state, or inaccessible video aborts all remaining writes.

## Incident 7: planned-operation verification is not channel closure

### Symptom

A plan can complete perfectly while unplanned `missing` or `foreign_only` videos remain elsewhere on the channel.

### Permanent rule

There are two different success conditions:

- **plan success:** every operation in the signed plan is verified;
- **channel closure:** a fresh channel-wide postflight reports `missing + foreign_only == 0`.

The plan builder supports fail-closed complete-coverage checks, and the refresh workflow supports a channel-wide postflight plus a zero-tail requirement.

Comments-disabled and API-error states are reported separately. They are blockers requiring investigation, not successful coverage and not silently counted as actionable creates.

## Incident 8: total inventory and public inventory are different numbers

A scan can report more videos than the comment audit reads. This is not automatically a bug:

- the export can contain private, unlisted, scheduled, or otherwise non-public videos;
- the comment workflow intentionally hashes and audits the exact public-video set.

Always compare:

- total videos in the snapshot;
- public videos selected for the comment inventory;
- the public-video set SHA-256;
- the exact audit coverage set.

Never infer missing audit pages from the total export count alone.

## Incident 9: human-readable output is useful but not authoritative data

The refresh wrapper currently extracts preflight counts from stable human-readable lines. This worked during the rollout, but machine-readable reports are safer for long-term automation.

Until a JSON preflight sidecar is added:

- parsing must fail closed when any expected count is absent;
- `ready + already_applied + blockers` must equal `planned`;
- the parsed planned count must equal the signed plan operation count;
- exact channel, snapshot, ready count, and plan SHA-256 remain mandatory execution confirmations.

## Incident 10: CI steps with `continue-on-error` can look green while their outcome failed

The workflow uploads Ruff, mypy, audit, and pytest logs even when a gate fails. GitHub can display an individual continued step with a successful-looking conclusion while `steps.<id>.outcome` remains `failure`. The final `Enforce quality gates` step intentionally converts any such outcome into a failed job.

Operational response:

1. inspect the artifact/log for the original continued step;
2. do not assume the final gate itself is defective;
3. fix the underlying Ruff, format, mypy, audit, or pytest failure;
4. confirm a completely green matrix on every supported Python version.

## Incident 11: create-missing is not the same as create-only

### Symptom

A workflow that merely enables missing-comment creation can still include reviewed updates when its content directory also contains records for already covered videos.

### Permanent rule

Final channel-closing waves use both:

```text
--create-missing --creates-only
```

Create-only mode omits update planning and then verifies the signed operation list contains no action other than `create`. It is an independent safety boundary, not a convention about which records happen to be present in a folder.

## Editorial scaling lesson: research dossiers, not title-based invention

Repeated musical versions of the same work should share a researched dossier, but not identical comments.

A dossier may provide several verified angles:

- composition history;
- first publication;
- manuscript or edition history;
- textual structure;
- archival provenance;
- adaptation or performance history.

Each target video still requires:

- a unique `variation_key`;
- a distinct heading or factual angle;
- a question tied to that specific angle or arrangement;
- only relevant links;
- exact source IDs covering the factual paragraph.

This approach scales research without producing copy-paste comments or inventing facts from video titles.

## Journal and recovery rules

The apply journal is part of the safety model, not disposable logging.

- It is written before each remote mutation.
- Every attempt records action, video ID, timestamps, result IDs, and verified text hash.
- A partial or ambiguous failure is resumed with the same signed plan and journal.
- Journals must never be deleted to force a rerun.
- A new plan SHA-256 always receives a different journal.
- Reruns classify completed operations as already applied rather than duplicating them.

## Recommended final-wave command shape

A channel-closing pass should use the repository workflow rather than a one-off package wrapper:

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

The workflow must stop before writes when coverage is incomplete. If all planned writes verify but the channel-wide postflight still finds an actionable tail, it must report that distinction explicitly; completed remote writes are not rolled back or hidden.

## Completed hardening and remaining engineering debt

The moderation-state reads, context-aware exact comment reads, and bounded delayed verification discovered during live operation now live in the core `YouTubeCommentWriter`. The historical `apply_youtube_comment_plan_compat.py` path remains as a thin UTF-8 wrapper so saved Windows commands, signed-wave launchers, and recovery instructions continue to work without maintaining a second implementation.

The principal remaining debt is a machine-readable preflight sidecar that replaces regex extraction from console output while preserving the same exact confirmation and writer-lock model. Once operational callers have migrated, the compatibility filename may be deprecated separately; it must not be removed as part of an unrelated cleanup.
