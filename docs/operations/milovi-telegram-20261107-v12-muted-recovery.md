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


## One-time GitHub due dispatch (after explicit owner approval)

The account already has the maximum 5 ChatGPT scheduled tasks; do not
delete or displace unrelated agents' automations. Use normal repository
infrastructure for this *single* exact release instead.

- Workflow: .github/workflows/milovi-telegram-exact-due-20261107.yml
- Cron trigger: 2026-11-07 08:07 UTC = 11:07 Europe/Moscow.
- GitHub cron may be delayed; the dispatcher checks real UTC time and
  refuses every invocation outside [08:00, 10:00) UTC on that date.
- The workflow also rejects a stale main, changed release/digest, missing
  owner approval or absent/inconsistent durable release ledger/index.
- Manual workflow_dispatch runs are permanent **read-only dry-runs**.
- On the exact date only, a pending/impossible record with zero intent
  permits dispatch of milovi-telegram-feed-publisher.yml with
  PUBLISH:@MiloviCake:milovi-feed-20261107-002.
- This dispatcher never handles a Telegram bot token or calls Telegram.
  The existing writer has the real bot/target proof, concurrency control,
  one durable intent/attempt, terminal outcome, and verified message id.
- Already-published verified records are skipped; unknown, dispatching,
  failed, or unverified states halt. **Never blindly retry**.
- After 2026-11-07 this schedule becomes inert even if GitHub triggers it
  in later years; remove only after preserving audit evidence.
