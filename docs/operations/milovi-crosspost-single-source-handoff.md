# Milovi Cake — single-source, six-platform handoff

Scope: **Milovi Cake only**, YouTube channel `UCMDnxfGZiBqcDzgUV1zjFpw`. This handoff does **not** create another publisher, authorize an API POST, change a Windows task, move the Instagram 19:00 Moscow slots, or add a cloud service.

## One video, separate provider effects

A frozen Instagram v5 source index is the media/intake input, not cross-platform publication approval. Run the provider-inert inspector from a clean, reviewed main runtime as:

```powershell
video-manager milovi crosspost-plan `
  --index 'C:\Users\Fedor\Projects\video-channel-manager\operator-output\milovi-cake-instagram\2026-11-05\meta-verified\milovi-ig-original-audio-handoff-v5-daily-20261110-28.json' `
  --start '2026-11-23' --end '2026-11-28' `
  --output 'H:\VCM-MILOVI-CROSSPOST-OUTBOX-20261123-28.json'
```

The result is six unique sources and 36 distinct destination logical identities. The CLI rehashes the entire original index and each selected MP4, its manifest, caption, exact owner acknowledgement and account binding. A drifted input fails before writing the output. Existing output bytes must match exactly; the CLI will not overwrite different bytes. The report is owner-local and may include local source filenames and captions; do not commit that report.

## Why all six destinations are not simply marked ready

| Destination | Owner/identity binding | Current safety boundary |
|---|---|---|
| YouTube Shorts | `UCMDnxfGZiBqcDzgUV1zjFpw` | Already the source; do not reupload the same six Shorts |
| Instagram Reels | `17841407843933779` / `@milovi_cake` | Sole existing Windows 19:00 publisher; confirm each provider media ID and durable ledger, no second writer |
| VK native Clips | `68859909` / owner `-68859909` | Issue #323: 12 historical native clips uploaded. Fresh Creator published/postponed/draft/private/processing reconciliation and separate write authority before any missing source |
| Telegram | `@MiloviCake`, chat `-1002215328390` | `state/milovi-cake-telegram` and one workflow `milovi-telegram-feed-publisher.yml`; past windows never backfilled; each new item requires new source-specific release, review, state and execution gates |
| RUTUBE | Exact account/channel ID **unverified** | Native Studio supports scheduled videos; PartnerAPI requires separately issued partner credentials; do not guess an account or use unapproved endpoints |
| Threads | Exact Threads account ID **unverified** | Official Threads API uses separate OAuth and publicly fetchable video URL; Instagram Graph credentials are not a Threads publication permission |

No route with missing target/auth/complete duplicate coverage is dispatchable. An acknowledgement of repost risk is **not** independent proof of music licensing or of new-platform editorial approval.

## Outbox semantics

The `milovi-crosspost-handoff-v1` artifact is an **operator-side source map**, never a queue with executable timers. It holds exact source video files, hashes, captions, proposed Moscow slots (for matching existing Instagram schedule only), stable per-platform keys without date in the logical identity, and explicit non-dispatch statuses. Every destination remains `may_dispatch=false`, `provider_receipt_verified=false` until its independent connector and ledger establish a new fact. A successful build cannot convert `hold_` to a provider receipt.

Do not edit the status JSON by hand to claim readiness. Attach provider-created IDs and actual source/target state through each platform's canonical writer and readback, in its own durable ledger. For media with unverified cross-platform music rights, preserve the rights HOLD on new routes.

## Provider rollout sequence (not performed by this package)

1. Reconcile all target identities and exact existing media before any new upload. Do not treat historical 12 VK native clips as a zero-content state.
2. Continue the existing Instagram task, with the PC and v2rayN online at 19:00 Moscow. Confirm the exact next Reel in Graph and the local SQLite ledger.
3. For each missing new-platform candidate, obtain reviewed source/rights/caption + exact target/schedule and install only one canonical platform writer, with durable intent and no blind retry.
4. RUTUBE: native Studio scheduled uploads, or documented partner interface if a **valid, separately authorized partner account** actually exists. Threads: Threads OAuth and an approved HTTPS media source first.
5. Never send 6*6 API writes simply because the handoff has 36 route entries. The YouTube six are source-only and the Instagram six already belong to another scheduler.

Current operator checkpoint: 23 November 2026, **zero** new provider posts and **zero** new schedulers created by this feature.
