# Milovi Telegram recovery: audio-free v12

Owner: issue #809. Distinct from Milovi VK #792, Milovi Instagram #790,
and all LordChrist Telegram publisher streams. This is a provider-inert
preview, not a release authorization.

## Issue 1: corrupt Cyrillic in first candidate

The first frozen publication ID milovi-feed-20261107-001 contains
literal question-mark characters replacing Russian lettering, due to an
unreviewed Windows console-codepage conversion. Old validation only checked
the SHA of already-damaged text, not its readability. It has never been
published. It is now in the immutable retired-publication denylist, which
fails closed before state-init or publish. Preserve it as evidence; never
rewrite the old release or recycle the ID.

## Issue 2: uncertain soundtrack permission

The legacy accepted v12 MP4 has an audible AAC soundtrack. Business
ownership does not establish licence to distribute this audio. The distinct
v12-muted MP4 was produced by dropping audio using FFmpeg stream-copy.
Compressed H.264 video essence remained identical:

- Video stream SHA-256 before/after:
  b521332dd0f153dd097753fe44f5a5af7cfe735f5b04a78adb256f2b4061cc82
- H.264, 720x1282, yuv420p, 299 frames, zero audio streams.
- New artifact 2,195,289 bytes, SHA256
  3b680fe94b5007daea9860eeaf16159abf17712887fa3b1714511b48b84143d7
- Protected evidence ref: agent/milovi-video-muted-v12-3b680fe94b50
- Immutable commit: 686223b41c01ce365853f2e2bf22c20240a1df01
- Git blob: 832d7632cac63a2302f045b8bec0fc1b41344328
- Derivation proof JSON SHA256:
  9657c47381b923394cee72d7dd832174f69de8293e648b0ae68876a58f8309be

The original accepted reservoir of 16 MP4s, ref, blobs and releases are
unchanged. The new transport is governed by a separate exact November
manifest and a new versioned video binding, pinned to a full Git commit.
Materialize-video rechecks both SHA256 and Git blob before any use.

## One exact new draft

- Publication ID: milovi-feed-20261107-002, NOT old 001.
- Target: @MiloviCake via existing permanent Telegram single-writer.
- Proposed 2026-11-07 at 11:00 Europe/Moscow: not scheduled or armed.
- Content: 10-second wedding cake with raspberries, no music/audio.
- Russian caption stored via escaped Unicode JSON and roundtrip verified.
- Candidate and three exact release/authority/transport JSONs are
  provider-inert. release_authorized=false, execution_authorized=false,
  provider_mutation_allowed=false.
- Public duplicate study: four native videos at message IDs 13,16,19,20,
  duration 48/59/28/21 seconds. New v12 is about 10 seconds and distinct,
  though a public study cannot prove status of inaccessible posts.

## Hard gates for actual publication

1. Human review of caption and visual source rights; removing audio does not
   establish rights to the cake footage. Accepted variant manifest retains
   explicit content_approved=false and rights_verified=false.
2. Separate exact human authorization for publication ID 002, reviewed caption,
   bytes and Moscow slot. This technical PR grants none.
3. Fresh main, full durable state, duplicate ledger and target preflight,
   through sole milovi-telegram-feed-publisher.yml control plane.
4. Durable intent before one provider send, no silent retry, exact message
   postflight and durable receipt.
5. Close #809 only after exact native Telegram message ID/URL verified.

No VK, Instagram, YouTube, quote, Charnock or Jude changes were made.


## Owner authorization, 6 November 2026

The current owner explicitly confirms that the original v12 wedding cake
footage belongs to MILOVI CAKE and requests upload. The exact video is
a 299-frame muted H.264 transport, so this declaration applies to source
video rights, **not** unlicensed music or other older videos.

The owner request binds the one already fully proofed Nov 7 candidate,
`milovi-feed-20261107-002`, its Russian caption, SHA256 and exact proposed
11:00 Europe/Moscow slot. The user requested actual uploading, so distinct
signed release and execution authority are now recorded for this exact
publication. The original source candidate file remains deliberately
provider-inert (data provenance, not permission). The reviewer/source
attestation is in
`content/telegram/milovi-cake/releases/milovi-feed-20261107-002-owner-attestation.json`.

Publishing still must happen only when the precise due window opens, through
the existing GitHub Actions single-writer workflow after fresh checks of
protected state and current main, with durable intent and one attempt.
**Merge and validate are not Telegram publication**.


## Fifteen audio-free video candidates, 8-22 November (provider-inert)

All remaining 15 of original 16 transports were individually verified by
exact source SHA256, unchanged H.264 video stream and zero audio streams.
Signed Nov 7 v12-muted stays unchanged.

- Permanent ref agent/milovi-video-muted15-80ee7f9fea.
- Immutable artifact commit 9331af0c6015404bfda0cd2c6392066b78dc68b3.
- Frozen media provenance SHA256 c62a03c876dfee047f39890d8837056a95f96d2f2a34062db7e5fa5f83ef31ba.
- Binary files stored on ref under artifacts/milovi-telegram/video-muted15/.
- Additive variant registry accepted-video-variants-2026-11.json maps each
  media ID to its distinct SHA256, Git blob, original parent SHA, zero-audio
  proof and immutable evidence commit.
- Fifteen exact provider-inert candidate, runtime/video and execution-authority
  bundles prepared for November 8-22 at 19:00 Moscow, one per day.
- Caption integrity verified as proper Unicode. No rewritten legacy video.
- Explicit rights proof for other fifteen and exact historical native-video
  duplicate reconciliation are not complete; older Telegram post #19 was
  inaccessible on public archive contact sheet.
- All fifteen: release_authorized=false, execution_authorized=false,
  provider_mutation_allowed=false, scheduling_active=false and zero provider sends.
- Proposed dates are not activated server-side Telegram schedules or GitHub
  cron triggers. The separate previously blocked scheduler is NOT bypassed.


## Owner-authorized fifteen follow-on releases (not yet scheduled)

Following the owner's explicit request on 2026-11-06 to upload the
MILOVI CAKE videos in deferred order, all fifteen audio-free videos
were individually authorized for **one exact future publication each**,
with their own Pydantic-reviewed candidate digest, release SHA,
individual human execution authority and frozen file SHA. The source
candidate bytes remain provider-inert; no old production history
is modified.

Exact collective provenance is recorded at
content/telegram/milovi-cake/releases/milovi-muted15-owner-authorization-20261106.json.
The owner's direction is not represented as an independent external
license certificate. All music has been removed. Public old video
lengths 21, 28, 48, 59 seconds are not byte-identical to these 10-second
sources. Source-clip semantic overlap cannot be proven absent.

These fifteen now pass the exact release and execution gate, but **no
protected state ledger is initialized and no scheduling trigger is
active** until a separate state-initialization transaction and
daily due-dispatch workflow are completed. The existing Nov 7 v12
release remains intact. This approval does not authorize a burst
upload or blind retries.
