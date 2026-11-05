# Milovi Cake Instagram — safe staged Reel transfer

Owner: Issue #790. Status: **provider-inert preparation only**.

## Exact identities and boundaries

- Project: `milovi-cake`
- Source: `UCMDnxfGZiBqcDzgUV1zjFpw` (`@milovi_cake`).
- Canonical product site: https://milovicake.ru/
- Destination Instagram Professional account: **not registered or verified as of 2026-11-05**.
- The existing Meta configuration for `the.legendary.poet` is not the Milovi Cake destination.
- No vidIQ budget is needed. Use read-only APIs and exact existing project media.
- `main` is the only supported code baseline. This command never runs provider writes.

## Provider-free candidate preview

The operator needs five exact inputs: a public YouTube source inventory,
verified per-video metadata, caption drafts, proposed slots, and the tracked
`content/instagram/milovi-cake-scope-holds-v1.json` review registry.

The operator artifacts are in:
`C:\Users\Fedor\Projects\video-channel-manager\operator-output\milovi-cake-instagram\2026-11-05\`

Run from the repository root:

```powershell
video-manager instagram milovi-cake-preview `
  "operator-output/milovi-cake-instagram/2026-11-05/source-review-inventory.json" `
  "operator-output/milovi-cake-instagram/2026-11-05/twelve-candidate-youtube-metadata.json" `
  "operator-output/milovi-cake-instagram/2026-11-05/caption-drafts-review-only.json" `
  "operator-output/milovi-cake-instagram/2026-11-05/twelve-slot-preview.json" `
  --output "operator-output/milovi-cake-instagram/2026-11-05/repo-generated-preview.json"
```

The result is deterministic for exact bytes and records each input's SHA-256.
Dates are **proposed** clock times, never scheduled provider operations.
Every valid preview has:
- `project_key=milovi-cake` and exact source channel, but no destination Instagram ID;
- `provider_effect=impossible`, `provider_writes_authorized=false`;
- `schedule_armed=false`, `publish_ready_count=0`;
- Tuesday/Thursday/Saturday 19:00 `Europe/Moscow` slots, >=48h apart;
- holds for Instagram presence, source rights, audio rights, clean master,
  compatibility, cover, and exact publication authority.

Unlike the Legendary Poet daily queue, this is a **three-per-week proposed
cadence**, not an executable queue. It cannot produce a live
`InstagramPublishManifest`.

## Source audit and safety

The public Shorts listing on 2026-11-05 contained 135 unique IDs; 12 shortlisted
videos had individually verified public metadata and 14–60 second durations.
This is not a fresh owner-only YouTube AuditPackage; owner OAuth refresh failed.

The stoplist contains 26 title-level triage entries: 16 franchise/character,
three brand/logo, and seven non-cake/personal. A flag is not a legal conclusion;
unflagged videos still require content, audio and rights review.

The 16 separate website gallery WebM (VP9) references are not clean Instagram
masters and are not automatically bound to the 12 video IDs. Their extracted
1080x1920 cover previews are not approved final covers.

## Preconditions before real scheduling

1. Verify an owner-bound Milovi Instagram Professional account ID and
   username/login/Page linkage through the official API.
2. Reconcile the complete current Instagram Reel inventory and durable account
   publication ledger; matching titles are insufficient evidence of absence.
3. Prove rights, audio, exact clean master bytes, Reel MP4 compatibility and
   exact source-bound cover for each genuinely missing item.
4. Freeze reviewed captions and a unique immutable provider publication manifest.
5. Use the **existing canonical** Instagram production publisher with one writer,
   durable intent, exact target preflight, one dispatch and no blind retry.
6. Arm a production scheduler only after the separate exact provider-write gate.
   No same-day bulk backfill; missed slots must not silently accumulate.

A green CI result, credential availability or this preview does not authorize
Meta publication. Never revive old publication keys or build a second writer.
