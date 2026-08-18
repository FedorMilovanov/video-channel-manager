# Milovi Cake Telegram

Owning issue: #353.

This directory is the canonical Milovi Cake Telegram editorial/readiness area. Editorial approval, transport readiness and provider execution authority are separate gates.

## Current truth

- Exact Telegram target: `@MiloviCake`, chat id `-1002215328390`.
- Exact shared publisher bot: `8716602202 / @preaching_mp3_bot`.
- The bot is proved as a channel administrator with `can_post_messages=true`.
- Historical message `25` was an exact provider-verified `sendPhoto` canary; the channel owner later deleted it because its caption used misleading Milovi School/French-culture framing. Its retained dispatch remains evidence only and that exact payload must not be republished.
- Fresh live canary `milovi-canary-20260818-002` was provider-verified as Telegram message `26` on 2026-08-18. The provider execution used one durable intent, one mutation attempt and zero blind retries. The channel owner then manually replaced the weak service-style caption in Telegram with improved public copy; therefore the historical provider payload digest remains execution evidence but is not the canonical future editorial wording.
- Future Milovi Cake captions follow the portfolio-first standard in `editorial-copy-style-2026-08.md`: brand authorship is implicit, visible work is described directly, service/catalogue phrases such as `реальная работа` and `хороший референс` are not default public copy, and public resources come from the centralized footer.
- Ordinary provider mutations remain limited to the inclusive `09:00–21:00 Europe/Moscow` audience window. Do not backfill after hours.
- Nine first-screen photo sources are exact-byte/materialization verified and have deterministic JPEG transport SHA-256 values. This readiness still does not authorize publication.

## Cake vs School: hard editorial boundary

**Milovi Cake is the cake and dessert business. Milovi School is a separate educational/editorial/SEO content project.**

Milovi School is not evidence of how Milovi Cake products are made. Do not infer or claim from School content that Milovi Cake uses a School recipe or technique, operates a French kitchen, has French culinary lineage, trains production through School, or derives a product from a School article.

The first-screen Cake continuation contains **zero Milovi School items**. Later School material may be adapted only as separately labelled educational reading and must not imply a production/product relationship without a separate exact source.

Canonical rule: `editorial-brand-boundary-2026-08.md`.

## Current artifacts

- `editorial-brand-boundary-2026-08.md` — hard Cake/School editorial separation and do-not-republish rule for the bad historical canary wording;
- `publishing-window-2026-08.json` — hard audience-local quiet-hours policy;
- `live/operator-correction-2026-08-16.json` — owner-reported deletion/correction for historical message 25 without rewriting the historical dispatch receipt;
- `editorial-copy-style-2026-08.md` — canonical portfolio-first public-copy rules for future Cake posts;
- `editorial-public-footer-2026-08.json` — centralized exact public-resource footer and banned service-language guardrails;
- `first-screen-continuation-copy-2026-08.json` — revised provider-inert continuation copy under new publication identities; it does not mutate historical bootstrap payloads;
- `next-publication-candidate-2026-08-19.json` — exact provider-inert candidate for the next daylight post; a fresh release/execution authorization is still required before provider access;
- `bootstrap-first-screen-candidates-2026-08.json` — historical/reviewed first-screen candidate corpus. Its remaining old caption payloads must not be used as future public copy once superseded by the portfolio-first continuation;
- `bootstrap-photo-source-readiness-2026-08.json` — 9/9 exact source-byte and deterministic JPEG readiness;
- `bootstrap-photo-transport-proof-2026-08.json` — exact source SHA-256, dimensions and JPEG transport SHA-256/byte sizes for all nine first-screen photos;
- `launch-pack-2026-08.md` — historical/provider-inert editorial corpus. It contains superseded examples and is **not an executable publication source**;
- `editorial-asset-contract-2026-08.md` — current source-availability constraint; production/kitchen/BTS footage remains 0% until separately reviewed source footage exists;
- `media-source-map-2026-08.json` — verified 46-item finished-work source map (30 photos + 16 videos);
- `school-source-shortlist-2026-08.json` — source evidence for optional future educational reading only; it does not prove a Cake production relationship;
- `editorial-sequence-30-posts-2026-08.json` — long-horizon provider-inert editorial planning, not an execution queue;
- `editorial-operating-plan-2026-08.md` — current channel-quality, reuse, cadence and acquisition rules;
- `video-source-readiness-2026-08.json`, `video-conversion-contract-2026-08.json`, `video-output-records-2026-08.json`, `video-conversion-readiness-2026-08.md` — native-video lane; accepted MP4 outputs remain 0/16 until exact conversion evidence exists.

The exact historical canary/release/dispatch artifacts must remain immutable enough to explain what was actually sent. Do not “fix” an old caption in place and thereby falsify retained SHA-256 evidence. Correct future copy through a new candidate/release/publication identity.

## Finished-work source policy

The current reviewed visual source is finished Milovi Cake work. Production/kitchen/BTS content remains 0% until separate reviewed footage exists. A final-cake photo/video may support showcase, visible-detail analysis, comparison, collection or buyer guidance, but must never be captioned as production footage or as evidence of an unseen process.

## Public-copy policy

A post published by Milovi Cake already carries Milovi Cake authorship. Future Cake captions should therefore lead with the visual, design, occasion or useful selection context rather than proving that an image is a “real work”. The default shape is: human title → visible/useful observation → optional selection/personalisation context → centralized public-resource footer → zero to four topical hashtags.

Registered public resources are website `https://milovicake.ru/`, VK `https://vk.ru/milovi_cake`, YouTube `https://www.youtube.com/@milovi_cake` and Dzen `https://dzen.ru/milovicake.ru`. Telegram does not need a self-link in every Telegram caption.

## Live execution boundary

Verified messages `25` and `26` prove target/sendPhoto capability under their exact historical operations; they are not standing authority for a batch or for a different publication identity.

Any future provider operation must separately bind:

1. exact current `main` and owning issue;
2. exact target/bot identity and fresh administrator/posting-right proof;
3. exact selected publication id;
4. exact caption digest and canonical editorial standard;
5. exact materialized JPEG transport SHA-256 value where media is present;
6. hard `09:00–21:00 Europe/Moscow` execution window before provider access and before durable intent;
7. one durable intent/barrier before `sendPhoto`/`sendMessage`;
8. zero blind mutation retries;
9. exact returned `message_id`/chat verification before considering the operation successful;
10. fail-closed handling of unknown outcomes.

Do not convert the historical launch pack, bootstrap payloads, media map, editorial sequence, School shortlist, canary files or readiness records into a live queue merely because they exist.
