# Milovi Cake unresolved-source visual evidence

This runbook is the provider-inert follow-up to Issue #257 after the exact public Clips UI and the published-wall native Clip inventory reconciled to the same 106 exact remote IDs.

## Scope

The reader is deliberately limited to the 25 YouTube rows that remained unresolved after metadata-only review and are themselves in the accepted confectionery scope:

- cakes and bento cakes;
- pastries/cupcakes where represented by the reviewed candidate set;
- desserts, trifles, meringue rolls, eclairs and other clear confectionery.

Personal/family material, non-confectionery content, packaging-only material and process/masterclass-only material are outside this pass.

This is **not** an upload queue.

## Accepted input

The command accepts exactly the operator reconciliation ZIP created from:

1. successful `vk-clips-browser-ui-read-v1` evidence for exact `milovi-cake / 68859909 / -68859909`; and
2. the earlier immutable wall evidence handoff.

Before any network read, the module checks the input SHA-256 bindings, exact project identity, read-only flags, 106 unique exact UI Clip IDs, the known Shrek control Clip, and exact equality between the public UI set and the 106 wall-proven nested `type=short_video` IDs.

A mismatch fails closed.

## Read transport

Transport is `internal_web_read` over public image resources only. The reader downloads:

- YouTube-generated `0.jpg`, `1.jpg`, `2.jpg`, and `3.jpg` thumbnails for each of the 25 exact YouTube IDs;
- one highest-resolution available VK first-frame/poster image from the already captured wall object for each of the 106 exact Clips.

Only HTTPS image hosts under the explicit allowlist are admitted: YouTube image hosts plus VK/OK image CDN hosts already present in captured evidence. Query strings are not persisted in result metadata. No cookie, authorization header, browser profile or provider credential is required or saved.

## Visual evidence semantics

Each accepted image is SHA-256 hashed and assigned a 64-bit difference hash. The tool combines visual proximity with title-token, duration and publication-date support to rank up to five VK candidates for each unresolved YouTube row.

These ranks are **supporting evidence only**:

- a thumbnail/preview similarity is not an exact-media identity proof;
- a non-match is not proof that a provider object is absent;
- `same_media_claim=false` remains explicit;
- `missing_native_clip_claim=false` remains explicit.

The evidence is intended to identify obvious metadata misses and prioritize the next review step without manufacturing a migration decision.

## IP and transfer gates

The reviewed IP policy remains blocking even when the content itself is a cake or dessert:

- `IP_HOLD_HIDE` -> `IP_HOLD_DO_NOT_TRANSFER`;
- `VISUAL_REVIEW` -> `VISUAL_REVIEW_REQUIRED`;
- `TRADEMARK_REVIEW` -> `TRADEMARK_REVIEW_REQUIRED`;
- ordinary low-risk rows remain `MEDIA_RECONCILIATION_REQUIRED` until source identity is sufficiently proved.

No result authorizes upload, hide, delete, wall publication or scheduling.

## Operator output

The current-main command writes a deterministic directory and ZIP under the canonical Windows outbox:

```text
C:\Users\Fedor\Projects\video-channel-manager\operator-output\milovi-cake-gap-thumbnail-evidence\
C:\Users\Fedor\Projects\video-channel-manager\operator-output\milovi-cake-gap-thumbnail-evidence.zip
```

The ZIP contains:

- `00-manifest.json` with exact hashes and provider-inert safety state;
- `01-gap-thumbnail-reconciliation.json` with the 25 ranked candidate rows;
- downloaded public image evidence under `media/youtube/` and `media/vk/`.

Provider writes are always `0`. A partial public-image download is reported as `partial_network_evidence`; it does not silently become a missing-content conclusion.
