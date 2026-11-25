# Господь Бог — Сила Моя: Instagram-карусели, 16–21.11.2026

**Состояние:** editorial assets frozen; cloud schedule activates only after PR merge and successful read-only GitHub preflight. Do not infer a published post from successful CI.

## Editorial contract

Not a stream of unattributed aphorisms. These six carousels answer bounded questions, distinguish the original text from interpretation, and point to actual published articles of [gospod-bog.ru](https://gospod-bog.ru/). No direct verbatim Bible verses or invented words attributed to a preacher enter artwork.

| Date (MSK) | ID | Theme | Article |
| --- | --- | --- | --- |
| 2026-11-16 | 01-heart | The biblical heart is not merely emotion | https://gospod-bog.ru/articles/chto-bibliya-nazyvaet-serdcem/ |
| 2026-11-17 | 02-congresses | Two distinct Russian evangelical meetings in 1884 | https://gospod-bog.ru/baptisty-rossii/dva-sezda-1884/ |
| 2026-11-18 | 03-peter4 | What 1 Peter 4:6 does and does not establish | https://gospod-bog.ru/hard-texts/blagovestie-mertvym-1-petra-4-5-6/ |
| 2026-11-19 | 04-christ | Christ at the center of 1 Peter 3:18–22 | https://gospod-bog.ru/hard-texts/duhi-v-temnice-noi-kreshchenie-pobeda/ |
| 2026-11-20 | 05-jude | Jude 6–7: explicit text vs contextual inference | https://gospod-bog.ru/hard-texts/angely-pod-mrakom-iuda-6-7-2-petra-2/ |
| 2026-11-21 | 06-spirits | Three confidence levels for spirits in prison | https://gospod-bog.ru/hard-texts/duhi-v-temnice-noi-kreshchenie-pobeda/ |

## Immutable input artifacts

- Editorial plan (six captions, 30 exact slide texts, source revision IDs): `content/instagram/lord-god-strength-carousel-wave-20261116.json`.
- Image registry (all SHA-256, byte lengths, dimensions, parent post bindings): `content/instagram/lord-god-strength-carousel-wave-20261116-assets.json`.
- Public media host: [GitHub Release: lord-god-instagram-carousels-20261116-21](https://github.com/FedorMilovanov/video-channel-manager/releases/tag/lord-god-instagram-carousels-20261116-21). All 30 JPEGs 1080×1350, 4:5, 2–10 slides per carousel (we use 5).
- Asset generation script and provider-staging test kept **outside the repository** at `E:\VideoChannelManager\Instagram\LordGod\20261116-carousel-wave\`. They do not mutate GitHub or Instagram posts by themselves.

## Cloud publishing gates

- Target IG Professional ID `17841433845016161`, linked FB Page `1457892317403899`; username `thelordgodismystrength`.
- Secret `LORD_GOD_INSTAGRAM_PAGE_TOKEN` must remain in repository Actions Secrets; never print, copy into source or expose in logs.
- Separate GitHub Workflow: `.github/workflows/lord-god-instagram-carousel-cloud-20261116.yml`.
- Primary schedule **09:45 UTC / 12:45 MSK**, backup **10:10 UTC / 13:10 MSK**, strictly 16–21 November 2026.
- Manual `workflow_dispatch` is **read-only**: asset URL and SHA checks, Meta account identity and published caption readback. It must never call a provider POST.
- Scheduled event verifies the exact date and 12:45–14:00 Moscow clock window before provider writes.
- Each carousel: five child containers (`is_carousel_item=true`), one parent (`media_type=CAROUSEL` and five child IDs), exactly one `media_publish`, readback of `media_id`, `media_type=CAROUSEL_ALBUM`, exact caption and permalink.
- No blind retries after an uncertain provider response; failed or missing scheduled jobs are *not* proof of publication.
- Never edit the existing 12–15 November quote workflow, local disabled Windows quote jobs, or 19:00 MSK Reels tasks as part of this release.

## Verified before merge

- 30/30 uploaded media SHA-256 matched the frozen local originals via public HTTPS redirects.
- One one-time, **non-publishing** Meta Graph provider proof built **five child containers** and a parent carousel with `status_code=FINISHED`. The test script has no `media_publish` call.
- Before marking a date `published`, require matching Meta post ID/permalink plus an exact `PUBLISHED_CONFIRMED` run log.
- After each date, check both scheduled GitHub runs. `ALREADY_PUBLISHED_SKIP` from backup is expected when the primary posted, not a second publication.

**Release scope:** six photo carousels only. Daily Reels remain separate, unchanged. GitHub schedule can be delayed; 13:10 backup is a reliability measure, not a minute-precision guarantee.
