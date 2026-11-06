# MILOVI CAKE Telegram — MILOVI SCHOOL editorial reading wave, 6 November 2026

Owning scope: Milovi Cake Telegram #353. Owner explicitly requested posts sharing interesting Milovi School articles, their existing images and source links; separate educational content rather than claims about the Milovi Cake kitchen.

## Exact publication plan

| Date | Time Moscow | Publication ID | School article |
| --- | --- | --- | --- |
| 17 Nov 2026 | 12:30 (GitHub 12:37) | `milovi-feed-20261117-002` | https://french.milovicake.ru/articles/paris-brest-race-dessert/ |
| 21 Nov 2026 | 12:30 (GitHub 12:37) | `milovi-feed-20261121-002` | https://french.milovicake.ru/articles/croissant-history/ |
| 25 Nov 2026 | 12:30 (GitHub 12:37) | `milovi-feed-20261125-001` | https://french.milovicake.ru/articles/stohrer-1730/ |

All three are native Telegram photos, not link-only previews: 1280×800 WebP from the exact public `FedorMilovanov/Milovi_School` commit `f540e8d6fca89592a8394e0a707e6af0d85afc14`, converted deterministically to JPEG with Pillow 13.0.0 using the existing Milovi feed media contract. Provider-facing captions are fully written, <1024 chars, in Russian. Each story features a specific historical fact, a short contextual explanation, an educational project link and an image-disclosure line. No product CTA or Cake production-lineage implication.

## Hard independent safety gates

- The School is a separate educational project. Its image is labelled `Иллюстрация — Milovi School.` The image does **not** represent a finished order at Milovi Cake.
- First-ten actual native Milovi Cake videos must be **published/verified**: Nov 7 `milovi-feed-20261107-002` and Nov 8–16 `milovi-feed-202611DD-001` (10 receipts in all). The protected index and each exact immutable ledger must both attest correct channel `-1002215328390`, bot `8716602202`, message ID and public URL. Missing/uncertain/skipped/failed video stops the School wave.
- Each new School post requires the preceding School publication's verified receipt. Any unresolved provider effect blocks the channel.
- Published + verified daily item count remains max 2. On Nov 17/21 the existing Cake video is due at 19:00; the School photo is a separate 12:30 slot. No overlap in code writer or time.
- One existing canonical `milovi-telegram-feed-publisher.yml` performs all mutations. `milovi-telegram-school-reading-due-20261117.yml` is **only** a date-specific verified-state dispatcher and bootstrapper; it reuses the shared `milovi-cake-telegram-publisher` concurrency mutex. It contains no Telegram client and no media copy fallback.
- Source/transport exact SHA-256 and Git blob pinned in three `-media.json` files. The source GitHub repository is public; access succeeds without an access token. The photo comes from an exact Git commit, not a mutable production path.
- State initialization is provider-inert, idempotent and resides only on `state/milovi-cake-telegram`. No Telegram message is sent by a CI event.
- Per-item release and per-item execution authority are bound to exact payload/digest and the owner's 2026-11-06 instruction. A future operation must still pass current-main quality, daylight audience window, current bot/channel preflight, durable single intent, no-replay and exact provider outcome.

## Source / narrative provenance

- `paris-brest-race-dessert`: 1910 Paris–Brest–Paris cycling race; Louis Durand's wheel-shaped pastry; later interpretation by Philippe Conticini.
- `croissant-history`: historical Austrian kipferl precursor, diffusion into Paris in the nineteenth century, later development of laminated dough; 1683 siege story explicitly treated as an unverified legend.
- `stohrer-1730`: Maison Stohrer on rue Montorgueil, 51, tracing its Paris establishment to 1730; earlier/modern recipes carefully distinguished.

School articles are editorially sourced, not proof of individual original product or factory production practice. Do not falsely reuse the deleted historical Milovi Cake/School canary, or reinterpret Site-generated images as actual Milovi Cake commissions.

## Completion and provider-state truth

A merged release and an initialized ledger mean **queued / pending**, not already published. For each exact date retain the canonical Telegram message ID, chat match, content proof and channel-visible link. If a precondition or exact scheduled window is missed, do not bulk backfill or bypass the first-screen guard.
