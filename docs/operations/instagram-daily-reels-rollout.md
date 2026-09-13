# Instagram daily Reels rollout — Legendary Poet

Status: provider-inert queue and preparation pipeline. Automatic Meta writes are deliberately disabled.

## Queue contract

- Source: current YouTube Shorts surface for `UC-78ys2S3cQ3lpqgXfo-SvQ`.
- Snapshot: 62 Shorts, all portrait 1080×1920 and 9–180 seconds.
- Already published to Instagram: 2 Shorts (`T6WIgGaZm74`, `0C1-2tk9aQg`).
- Rights/editorial review hold: 6 Shorts.
- Ready daily schedule: 54 Shorts, one slot per day.
- First scheduled slot: 2026-09-14 19:00 Europe/Moscow.
- Queue SHA-256: `sha256:56f71f2ec0c593448f4560bec4df3a413c5175fb676ead9246f37434a41b303a`.

The queue artifact is provider-inert. CI or Scheduled Task execution cannot publish to Meta by itself.

## Ranking and SEO policy

The rollout favors actual source performance without publishing the same poet repeatedly when an alternative is available. Captions use a searchable first line, natural poet/work keywords, a short contextual sentence, one save/share CTA, and no more than five focused hashtags. Generic hashtag stuffing such as `#fyp`, `#viral`, or thirty-tag blocks is intentionally rejected.

Primary optimization signals are watch time/retention, sends/shares, saves, and content clarity. Global timing studies disagree materially, so 19:00 Moscow is only the initial controlled slot; once enough Instagram Insights exist, timing should be adapted to the account's own audience data instead of global averages.

## Media preparation contract

1. Download H.264 MP4 video plus M4A/AAC audio from the exact YouTube Short.
2. Remux without re-encoding using `-use_editlist 0 -movflags +faststart`.
3. Perform a complete SHA-256 read and size-stability check before structural probing.
4. Run strict local Instagram validation: MP4, moov-before-mdat, no edit lists, H.264/HEVC, yuv420p, progressive, accepted frame rate, AAC, and closed-GOP proof.
5. Upload the content-addressed `<sha256>.mp4` to GitHub Release `instagram-staging`.
6. Validate the public object end-to-end. Redirects are allowed only through explicit HTTPS allowlisted hosts. Current approved path is `github.com -> release-assets.githubusercontent.com`.
7. Build an immutable publication manifest and plan it in the durable Instagram ledger.

Meta write operations are not part of this operator.

## Durable safety rules

- `VCM_INSTAGRAM_WRITES_ENABLED=false` is forced by the daily operator.
- A publication key with durable status `published` is skipped.
- `planned` is safe to prepare idempotently.
- Any non-final/non-planned status blocks the queue and requires reconciliation before advancing.
- No blind retries of provider writes.
- Publication keys are immutable.

## Research basis reviewed

The policy above was checked against more than twenty current references and platform/operator sources:

1. Meta for Developers — Instagram Content Publishing: https://developers.facebook.com/docs/instagram-platform/content-publishing/
2. Meta for Developers — Graph API rate limiting: https://developers.facebook.com/docs/graph-api/overview/rate-limiting/
3. Meta for Business — Reels ads / 9:16 guidance: https://www.facebook.com/business/ads/facebook-instagram-reels-ads
4. Buffer — Best time to post on Instagram, 2026 data: https://buffer.com/resources/when-is-the-best-time-to-post-on-instagram/
5. Adobe Express — Best times to post Instagram Reels in 2026: https://www.adobe.com/express/learn/blog/best-times-to-post-instagram-reels
6. Hootsuite — Best time to post on Instagram, 2026 data: https://blog.hootsuite.com/best-time-to-post-on-instagram/
7. Sprout Social — Best times to post on social media / Instagram: https://sproutsocial.com/insights/best-times-to-post-on-social-media/
8. Later — Best time to post on Instagram: https://later.com/blog/best-time-to-post-on-instagram/
9. Later — How to create Instagram Reels: https://later.com/blog/create-instagram-reels/
10. SocialPilot — Best time to post Reels in 2026: https://www.socialpilot.co/insights/best-time-to-post-reels-on-instagram
11. Sendible — Best time to upload Reels: https://www.sendible.com/insights/best-time-to-upload-reels-on-instagram
12. Hopper HQ — Instagram posting frequency 2026: https://www.hopperhq.com/blog/instagram-posting-frequency-2026/
13. Dash Social — How often to post on Instagram in 2026: https://www.dashsocial.com/blog/how-often-should-you-post-on-instagram
14. MeetEdgar — Best time to post on Instagram 2026: https://meetedgar.com/blog/best-time-to-post-on-instagram
15. ManyChat — Instagram hashtag strategy 2026: https://manychat.com/blog/instagram-hashtag-strategy/
16. Sked Social — Instagram hashtags in 2026: https://skedsocial.com/blog/how-to-use-hashtags-on-instagram-in-2026-hashtag-tips-to-up-your-insta-game
17. Toptal Creator — Instagram SEO in 2026: https://www.toptal.com/creator/post/instagram-seo
18. Lamplight Creatives — Captions vs hashtags in 2026: https://lamplightcreatives.com/captions-vs-hashtags-instagram-2026/
19. Dive Media — Social SEO keywords vs hashtags: https://www.divemedia.com.au/marketing-tips-and-insights/social-seo-keywords-vs-hashtags
20. Cyndi Zaweski — Instagram captions in 2026: https://www.cyndizaweski.com/articles/how-to-write-instagram-captions
21. CreatorFlow — Instagram algorithm 2026: https://creatorflow.so/blog/instagram-algorithm-2026/
22. Zeely — Best time to post Reels in 2026: https://zeely.ai/blog/best-time-to-post-reels-in-2026/
23. Loopex Digital — Instagram Reels statistics 2026: https://www.loopexdigital.com/blog/instagram-reels-statistics
24. MicroPoster — How often to post on Instagram: https://microposter.so/blog/how-often-should-you-post-on-instagram
25. Shannon McKinstrie — 2026 Instagram strategy: https://shannonmckinstrie.com/2026-instagram-strategy/

Timing and hashtag recommendations from third-party studies are treated as directional evidence, not platform guarantees. The durable technical publication contract remains authoritative for execution.
