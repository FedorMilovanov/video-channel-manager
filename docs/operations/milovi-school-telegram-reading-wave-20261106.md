# MILOVI CAKE Telegram — MILOVI SCHOOL editorial reading wave, 6 November 2026

Owning scope: Milovi Cake Telegram #353. Owner explicitly requested posts sharing interesting Milovi School articles, their existing images and source links; separate educational content rather than claims about the Milovi Cake kitchen.

## Exact publication plan

| Date | Time Moscow | Publication ID | School article |
| --- | --- | --- | --- |
| 17 Nov 2026 | 12:30 (GitHub 12:37) | `milovi-feed-20261117-002` | https://french.milovicake.ru/articles/paris-brest-race-dessert/ |
| 21 Nov 2026 | 12:30 (GitHub 12:37) | `milovi-feed-20261121-002` | https://french.milovicake.ru/articles/croissant-history/ |
| 25 Nov 2026 | 12:30 (GitHub 12:37) | `milovi-feed-20261125-001` | https://french.milovicake.ru/articles/stohrer-1730/ |

All three are native Telegram photos, not link-only previews: source WebP at 1280×800 (Paris-Brest, Stohrer) or 1280×796 (the superior visually inspected `body-croissant-golden-baked.webp` Croissant figure, rather than the ambiguous round `croissant-history.webp` hero) from the exact public `FedorMilovanov/Milovi_School` commit `f540e8d6fca89592a8394e0a707e6af0d85afc14`, converted deterministically to JPEG with Pillow 13.0.0 using the existing Milovi feed media contract. Provider-facing captions are fully written, <1024 chars, in Russian. Each story features a historical fact, a concise explanation and an educational article link. Future captions use Telegram rich HTML without an image credit in the public text. No product CTA or Cake production-lineage implication.

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

- `paris-brest-race-dessert`: 1891 founding of the Paris–Brest–Paris cycling race; Louis Durand's 1910 wheel-shaped pastry; later interpretation by Philippe Conticini.
- `croissant-history`: historical Austrian kipferl precursor, diffusion into Paris in the nineteenth century, later development of laminated dough; 1683 siege story explicitly treated as an unverified legend.
- `stohrer-1730`: Maison Stohrer on rue Montorgueil, 51, tracing its Paris establishment to 1730; earlier/modern recipes carefully distinguished.

School articles are editorially sourced, not proof of individual original product or factory production practice. Do not falsely reuse the deleted historical Milovi Cake/School canary, or reinterpret Site-generated images as actual Milovi Cake commissions.

## Completion and provider-state truth

A merged release and an initialized ledger mean **queued / pending**, not already published. For each exact date retain the canonical Telegram message ID, chat match, content proof and channel-visible link. If a precondition or exact scheduled window is missed, do not bulk backfill or bypass the first-screen guard.

## 6 November 2026: fresh owner-authorized early Paris-Brest publication

Owner explicitly overrode the delayed first-screen policy for ONE School story: «Да нормально, отправляй сейчас сегодня, разрешаю». Immediate native photo release 'milovi-feed-20261106-001' is source-, caption-, and JPEG-byte-equivalent to the Paris-Brest story originally scheduled Nov 17, with its own fresh authorization, exact 22:20 Moscow November 6 release time, and one-attempt canonical dispatch.

The original Nov17 release and protected pending ledger remain untouched as historical evidence. At the Nov17 due slot the School dispatcher verifies the early photo's actual published/verified protected receipt, positive message ID, exact bot/chat, identical caption, source digest and JPEG transport digest. It will suppress Nov17 if the Nov6 message has actually been sent. On Nov21 and Nov25, a verified early receipt may satisfy the Paris-Brest predecessor, but the first-ten real Cake videos remain an absolute prerequisite for those later two School posts. No blind retry is authorized after an uncertain provider outcome.

This explicit exception does not authorize sending the other two School photos early and does not affect any Milovi Cake video schedule. Real completion requires Telegram provider receipt and public message URL. Manual execution uses only existing canonical milovi-telegram-feed-publisher.yml, operation publish, exact publication ID and PUBLISH:@MiloviCake confirmation; do not use a second bot client.

## November 6: owner-requested polished Telegram reading style

School posts are informative historical miniatures, not product portfolio captions.

- Start with a verifiable name, date, technique or unexpected detail. No advertising slogans.
- One compact bold headline (native Telegram HTML b tag), at most one relevant lead emoji.
- One italic framing line; other italic text only for useful foreign culinary vocabulary.
- Two or three compact paragraphs with facts, names, dates, addresses and mechanisms.
- One clickable contextual article link using the native Telegram a href tag, with Milovi School as its visible reading destination.
- Up to two relevant hashtags. No naked long URL, image-credit line, boilerplate disclaimers, calls to buy or claims about what Milovi Cake produced.

Nov 6 published Paris-Brest message #27 is NOT auto-edited; the owner requested a revised ready-to-paste caption. The Nov17 duplicate remains suppressed on receipt. Only unattempted Nov21/25 entries are restyled to rich HTML photo v2, without changing the image bytes, schedules, or protected bot/channel identities.

The typed v2 payload records source HTML, expected visible plain text and UTF-16 Telegram formatting entities, including the exact article URL. A reply lacking those entities is treated as an ambiguous send, never blindly retried. All existing v1 photo releases keep their original schema and digest.

For the protected-state transition, main-CI bootstrap checks the exact pre-revision release digest, candidate digest, provider-payload digest and both ledgers/index rows. Only provider-impossible, never-attempted pending records may migrate. Both are validated before either is written. Other posts (especially published Nov6 message #27) remain unchanged. The operation is idempotent, provider-inert and uses the existing channel-wide writer lock.
