# One-time VK Shorts reset approval — 2026-08-01

Project: `lord-god-strength`
Community ID: `60805374`
Owner ID: `-60805374`

## Scope

This file records parameters approved only for the current Shorts cleanup and reupload operation.

It is not a general project rule, not a default deletion threshold, and not precedent for future VK cleanup work. Future operations require their own reviewed criteria and immutable plan.

## Owner-approved parameters for this operation

- Preserve wall post `wall-60805374_12400` and every earlier post.
- Consider only wall posts with `post_id > 12400` that live inspection proves are automatic Shorts/Clip posts.
- For the current candidate batch only, an old VK clip may be considered for replacement when its final live view count is strictly below 20.
- A clip with 20 or more views is excluded from this specific batch.
- The below-20 value is a one-time operational filter chosen because the owner may have opened some clips a few times while checking them.

## Identity requirements

A candidate old clip must also:

1. belong to owner `-60805374`;
2. have final live `type=short_video`;
3. map by exact VK ID to one canonical YouTube Short in the reviewed Shorts ledger;
4. have no ambiguous source match;
5. be fully processed and readable through the authoritative endpoint;
6. have no remaining published or postponed wall reference after the approved wall cleanup;
7. have a complete backup and exact before-state record.

## Replacement order

For every candidate:

1. create a 16:9 ordinary-video source that preserves the complete vertical picture without cropping;
2. upload with `wallpost=0`, `auto_publish=0`, `repeat=0`, and no playlist mutation;
3. verify the new object is fully processed and has final `type=video`;
4. verify no unexpected wall post appeared;
5. only then delete the old `short_video` object;
6. journal both remote IDs and never repeat a mutation whose outcome is accepted or unknown.

A single canary must pass before the remaining batch is attempted.

## Wall cleanup

Deleting wall posts and deleting video objects are separate phases.

A wall post after boundary `12400` is eligible only when live hydration confirms that it is a simple automatic post containing the relevant own-community `short_video` and no mixed attachments or copied-post content.

Wall-post view counts do not control this owner-approved boundary cleanup. The view-count filter above applies only to replacement of the underlying clip objects in this specific batch.

## Required confirmations

The executable plan must bind:

- project key `lord-god-strength`;
- community ID `60805374`;
- owner ID `-60805374`;
- preserved boundary post ID `12400`;
- the operation-specific candidate filter recorded in this file;
- exact candidate counts;
- exact manifest SHA-256 values;
- destructive-operation environment gate and explicit execute confirmation.

No other cleanup operation may reuse these parameters automatically.
