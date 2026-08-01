# VK Shorts cleanup and ordinary-video reupload policy

Updated: 2026-08-01
Project: `lord-god-strength`
VK community ID: `60805374`
VK owner ID: `-60805374`
Credential alias: `legendary-poet`

## Owner-approved boundary

- Preserve wall post `wall-60805374_12400`.
- Preserve every wall post with `post_id <= 12400`.
- Wall posts with `post_id > 12400` may be removed only when live hydration proves that the post is an automatic Shorts/Clip post under the exact eligibility rules below.

## Wall-post deletion eligibility

A post is eligible only when all conditions are true:

1. `owner_id == -60805374`;
2. `post_id > 12400`;
3. the post contains exactly one relevant own-community video attachment;
4. the attached object is hydrated live and has final `type=short_video`;
5. the post has no mixed attachments, copied-post payload, poll, document, photo, external link, or ordinary-video attachment;
6. the post has not changed since the signed plan was built.

Wall-post views do not block deletion for this approved post-boundary cleanup.

## Clip-object deletion eligibility

Deleting the wall post and deleting the clip object are separate operations.

The actual VK video object may be deleted only when all conditions are true:

1. exact live object `type == short_video`;
2. exact owner `owner_id == -60805374`;
3. exact VK ID is linked to one canonical YouTube Short in the reviewed Shorts SQLite ledger/manifest;
4. no unresolved or ambiguous source match exists;
5. final live view count is strictly less than 20: `views < 20`;
6. `views == 20` or greater is not eligible;
7. the object is not processing, converting, missing, or reported through an incomplete endpoint;
8. backup captures the full object, source YouTube ID/URL, title, description, duration, dimensions, current type, views, wall references, and playlist memberships;
9. no other published or postponed wall post references the object after the approved wall-post cleanup;
10. the immutable plan records exact before-state revision/hash.

The `<20` threshold intentionally allows for a few owner test views.

## Reupload goal

Every deleted low-view clip is reuploaded as an ordinary VK-hosted video, not as a Clip and not as an external YouTube embed.

Required behavior:

- use the original/canonical Short source from the ledger;
- render it onto a 16:9 canvas without cropping the vertical content;
- preserve the complete source image inside the horizontal frame;
- use a reviewed background treatment, normally blurred or neutral side fill;
- preserve source audio and duration;
- explicitly send `wallpost=0`, `auto_publish=0`, and `repeat=0`;
- set `wall_mutation_authorized=false`;
- create no playlist membership during upload;
- upload one canary first;
- wait until processing completes;
- require final live `type=video` before continuing;
- abort after the canary if VK returns `short_video`, processing never settles, or any unexpected wall post appears.

## Required operation phases

1. Fresh read-only wall and video inventory.
2. Exact plan for wall-post cleanup after boundary 12400.
3. Exact plan for clip deletion with `views < 20`.
4. Backup and immutable SHA-256 manifests.
5. Dry-run with ready/already-absent/conflict classifications.
6. Apply wall-post deletions with journal and postflight.
7. Re-read clip objects and view counts after wall cleanup.
8. Apply eligible clip deletions with a separate journal.
9. Produce one 16:9 ordinary-video canary.
10. Reupload remaining eligible sources only after final canary `type=video` verification.
11. Re-read the wall and fail if any new post appeared.
12. Keep all reuploaded ordinary videos off the wall until a separate postponed publishing plan is approved.

## Exact confirmations required

Any destructive executor must require:

- project key `lord-god-strength`;
- community ID `60805374`;
- owner ID `-60805374`;
- preserved boundary post ID `12400`;
- strict view threshold `20` interpreted as `views < 20`;
- candidate wall-post count;
- candidate clip count;
- wall-plan SHA-256;
- clip-plan SHA-256;
- source/reupload manifest SHA-256;
- explicit execute flag and destructive-operations environment gate.

## Forbidden behavior

- Do not delete post 12400 or anything earlier.
- Do not delete a clip with 20 or more views.
- Do not infer a Short from title, duration, aspect ratio, or publication time alone.
- Do not delete ordinary `type=video` objects.
- Do not retransmit an accepted/unknown upload outcome.
- Do not publish reuploaded videos immediately.
- Do not combine wall cleanup, video deletion, playlist mutation, descriptions, and postponed publishing into one unreviewed mega-operation.
