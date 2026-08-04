# Legendary Poet VK Clips attempt timeline

**Scope:** the sequence of attempts used to move YouTube Shorts into native VK Clips on 2026-08-03/04.

**Purpose:** learn from concrete failures and make the next workflow faster, safer, and available through one supported command. This is not a request for permanent global channel auditing.

## 01 — Initial exact sync V1

**Intent:** automatically classify Shorts, download missing media, upload through VK API, require a canary, and continue only when the result became `short_video`.

**Observed design:** fixed matrix `59 Shorts / 40 pairs / 19 missing / 1 extra vertical object`; snapshot identity was package-bound.

**Failure pattern:** the package treated an earlier classification and snapshot as operational truth. When current source inventory differed, the workflow could not distinguish stale evidence from a real channel change.

**Permanent rule:** counts are outputs, never hard-coded success criteria. Acquire the smallest fresh preflight required by the current operation.

## 02 — Fresh-audit sync V2

**Intent:** repair V1 by generating fresh YouTube/VK audits and using a guarded `yt-dlp` fallback for a source ID temporarily absent from the YouTube audit.

**Observed design:** fresh snapshot IDs, but the same `59/40/19/1` classification remained.

**Failure pattern:** refreshing inputs did not fix an incorrect classification model. The later reviewed set was `56/41/15`.

**Permanent rule:** do not confuse fresh data with correct interpretation. Exact reviewed mappings outrank fuzzy count matrices.

## 03 — Reviewed-map sync V3

**Intent:** replace automated classification with 56 exact YouTube IDs, 41 reviewed pairs, 15 missing sources, and separate short/long canaries.

**Observed result:** the long canary was returned by VK as a playable vertical ordinary `video`, not `short_video`; the group stopped.

**Failure pattern:** the workflow assumed the public upload route could reliably produce native Clips for long Shorts.

**Permanent rule:** provider capability and user-visible goal are separate. A successful upload is not success when the required final surface/type is different.

## 04 — Long-video fallback V4

**Intent:** resume from the V3 journal and accept a long playable vertical ordinary video as a fallback.

**Observed result:** safer reconciliation, but the acceptance rule drifted away from the user's real goal: native VK Clips.

**Failure pattern:** solving the technical blocker by weakening the product requirement.

**Permanent rule:** fail closed when the adapter cannot guarantee the requested surface. Do not silently redefine “Clip” as “vertical video.”

## 05 — Native Clips republish package

**Intent:** prepare 48 controlled MP4 files and upload them through the native Clips interface.

**Observed result:** local preparation worked; browser automation depended on a brittle UI path and did not provide a durable supported workflow. Manual upload succeeded.

**Failure pattern:** selectors and visible button text were treated as a stable provider contract.

**Permanent rule:** browser automation must be an explicit adapter with resilient discovery, screenshots/evidence, and a manual handoff fallback. It must never be the only source of truth.

## 06 — Checker V1

**Intent:** scan likely new VK IDs and match them to the 48-source queue.

**Observed result:** nonexistent IDs/placeholders contaminated counts; matching relied on `title`, while native Clips returned `title=None` and useful text in `description`.

**Permanent rules:**

- count only fully validated remote objects;
- `owner_id`, `id`, `type`, and positive duration are required;
- normalize and inspect both `title` and `description`;
- absence is not an object with unknown fields.

## 07 — Checker V2

**Intent:** filter real `short_video` objects, use exact markers, frame hashes, and unique durations.

**Observed result:** it correctly found 30 real clips, but local media existed for only one source, so complete visual matching was impossible. Eight pairs were auto-matched by unique duration and the rest required description review.

**Failure pattern:** a report could appear to be a visual checker even when the required local media was missing.

**Permanent rule:** verification dimensions are independent: identity, type, processing, duration, text mapping, playability, and media fingerprint must each have their own status.

## 08 — “Remaining 18” selector

**Intent:** copy the 18 apparently missing files into a separate folder for a second upload.

**Observed result:** the file selection itself was deterministic, but the conclusion that VK had a hard 30-file limit was premature. Additional objects appeared after processing delay.

**Failure pattern:** eventual consistency was interpreted as a permanent provider limit.

**Permanent rule:** wait and poll safe reads before classifying files as missing or retrying an upload. Never retransmit accepted/processing/unknown objects.

## 09 — Final checker

**Intent:** confirm all new native Clips.

**Observed result:** it found 48 real `short_video` objects in the exact contiguous range `456239167–456239214`, but automatically matched only 41. Seven descriptions were obvious to a human. It also printed impossible comparisons such as `62→178s` because expected durations were manually hard-coded, and reported fake ID gaps because gaps were calculated from the matched subset rather than the complete remote set.

**Permanent rules:**

- obtain expected duration from `ffprobe`;
- never hand-code media facts already available from source files;
- calculate ID continuity over the complete validated remote set;
- calculate content mapping separately;
- fuzzy matching failure does not imply remote absence.

## 10 — Expanded postflight tool

**Intent:** prove every possible dimension after the operation.

**Observed design:** clips, local media, visual hashes, walls, memberships, retained ordinary videos, and documentation state were combined into one large postflight.

**Failure pattern:** correction overshot into a broad, expensive audit that was no longer aligned with the practical task.

**Permanent rule:** use two scopes:

- **Quick operation scope:** just-in-time preflight, exact manifest, execution/resume, and postflight for the requested items;
- **Full incident scope:** only when a failure, ambiguous mutation, or explicit audit request justifies it.

## Desired end state

One supported command should:

1. validate the requested local files;
2. derive facts through `ffprobe` and SHA-256;
3. take a minimal fresh preflight for the selected target;
4. build one immutable manifest;
5. execute through one reviewed adapter or produce a clear manual handoff;
6. journal accepted, processing, rejected, and unknown outcomes;
7. never resend accepted/processing/unknown items;
8. perform a bounded postflight only for the manifest scope;
9. print one concise result and exact next action.
