# Milovi Cake Telegram — editorial operating plan

Status: **provider-inert / review only**  
Owning issue: #353  
Project: `milovi-cake`  
Current source constraint: production/kitchen/BTS footage is unavailable and its editorial share is **0%**.

## 1. What the channel is trying to become

Telegram should not duplicate the Milovi Cake website and should not become an extra step required to place an order. The strongest commercial surfaces remain VK and `milovicake.ru`. Telegram earns a subscription by becoming a compact visual media channel people can keep even when they do not need a cake today.

The launch promise is therefore:

- real finished Milovi Cake work;
- useful ideas a person may save for a future celebration;
- clear, non-invented guidance about ordering;
- verified customer trust signals;
- a small amount of genuinely interesting pastry-culture material from Milovi School.

The channel does **not** promise kitchen access, decorating footage, a studio tour, a daily diary, or staged stories about how an individual cake was made.

## 2. Current asset truth

The canonical Milovi Cake gallery declares 46 finished-work assets: 30 photographs and 16 videos. The local machine-readable mirror for editorial selection is `media-source-map-2026-08.json`, tied to source blob `e20e60c07479e8b20c1db700f1a40364b81eb669` in `FedorMilovanov/Milovi_Cake/js/gallery/data.js`.

This is already enough variety for a serious launch archive. It covers, among other things:

- sculptural / 3D cakes;
- children's themes and characters;
- sports themes;
- bento cakes;
- wedding work;
- black-and-gold / gold-texture visual styles;
- cupcakes;
- meringue roll;
- Pavlova;
- gift dessert sets.

Do not invent a new content class merely because a generic social-media template says every brand needs BTS.

## 3. Launch mix while BTS is unavailable

For a 30-post launch cycle, use the exact working allocation encoded in `editorial-sequence-30-posts-2026-08.json`:

- 14 finished-work showcases;
- 6 finished-work detail/design posts;
- 3 collections or native polls;
- 3 verified social-proof / buyer-guidance posts;
- 3 Milovi School mini-stories;
- 1 factual commercial post.

That gives finished-work media the majority of the feed without making every publication a repetitive "вот ещё один торт" card.

## 4. How one finished work becomes several legitimate posts

Reusing one real work is allowed only when each publication has a distinct editorial job. Do not repost the same image with cosmetic wording changes.

A strong work may support, for example:

1. **Hero/showcase** — the whole finished cake or final video, with one clear identifying idea.
2. **Detail** — one visible compositional element: shape, colour, focal figure, texture, typography or contrast. Commentary must stay inside what is actually visible or documented.
3. **Collection** — the same work appears next to several other real works under one theme, occasion, palette or format.
4. **Poll** — the work becomes one option in a real visual preference question.
5. **Buyer guidance illustration** — a neutral real work accompanies factual guidance about briefing, format selection or ordering without pretending that the photographed cake belongs to the described hypothetical customer.

Never turn reuse into an invented production narrative. A final-cake video is still final-cake media; do not caption it as "показываем процесс", "как это создавалось", "за кадром" or equivalent unless an exact reviewed production asset exists.

## 5. Caption architecture

For finished-work posts, default to a compact structure:

**Line 1 — searchable human title.** Name what a person is actually looking at: `3D-торт с лисёнком`, `свадебный торт с сердцем`, `бенто`, `меренговый рулет`, `торт в стиле Minecraft`.

**Body — one useful observation.** Explain one visible/documented idea rather than stacking adjectives. Examples: the main character controls the composition; the palette is deliberately restrained; the form carries the theme; the visual weight sits in one accent.

**Optional final line — one destination.** Gallery, the closest product page, a Milovi School article, or no link when the post works better natively.

Avoid:

- hashtag walls;
- generic "невероятный / волшебный / роскошный" copy without substance;
- invented emotional reactions from customers;
- invented ingredients or filling descriptions;
- claims that a design was requested for a specific person unless the source actually records that;
- fake scarcity or "последние места";
- unverified availability.

## 6. First-screen quality standard

A cold visitor should understand the channel in the first 8-10 visible publications without opening external links.

The first screen should contain at least:

- several clearly different finished works;
- one practical post worth saving;
- one collection/poll or comparison idea;
- one trust signal;
- at most one Milovi School item in a short initial cluster;
- no run of several sales posts;
- no run of several external-link posts;
- no weak filler used just to increase post count.

The first-screen test fails if the channel looks like a mirror of VK/YouTube links rather than a native Telegram destination.

## 7. Launch cadence

The 30 entries are an editorial sequence, not an instruction to publish 30 days in a row.

After a separately authorized and verified one-post canary:

- establish roughly 8-10 useful posts over the next 5-7 days;
- do not dump the whole archive in a single session;
- after the initial archive exists, move toward roughly 4-5 strong posts per week;
- change cadence only from actual channel response, not because the calendar demands a post.

At seven or a few dozen subscribers, posting frequency is not a substitute for acquisition. A small channel benefits more from a convincing archive plus targeted entry points than from mechanically publishing every day to almost nobody.

## 8. Acquisition loop the content must support

Every growth surface should send people to a channel that already explains why it deserves the subscription.

### VK → Telegram

Do not make Telegram a mandatory order hop. VK can keep selling. Use Telegram only when there is a real continuation value, for example a saved collection, an extended selection of finished works, a native poll, or a concise educational series.

### Website → Telegram

Use a tasteful secondary entry point after visual interest has already been established — gallery/footer/post-conversion areas are safer than interrupting the main order path. The site already has its own sales job.

### Existing customers / packaging

A packaging QR can be one of the highest-quality hypotheses because the recipient already knows the product. The value proposition should be about future inspiration and new finished works, not "subscribe to our channel" in the abstract.

### YouTube / Clips

Short-form video can point to Telegram when there is additional native value, but do not turn every caption into a cross-platform redirect.

### Paid/local placements

Paid seeding comes only after the channel has a credible archive and source-specific attribution. Each placement needs its own invite source. Judge it on retained relevant subscribers and eventual enquiries, not raw joins.

## 9. Discovery and search writing

Telegram has public-channel discovery/search surfaces, so titles should contain natural topic language that a real user might search or understand immediately. This does not mean keyword stuffing.

Good first lines are descriptive and specific:

- `3D-торт в стиле Minecraft`;
- `Свадебный торт с сердцем`;
- `Бенто на день рождения`;
- `Что написать кондитеру в первом сообщении`;
- `Почему Paris-Brest выглядит как колесо?`.

Avoid replacing meaningful language with generic hashtag stacks.

## 10. Editorial quality gates before a post may even become a canary candidate

A draft is not canary-ready unless all applicable checks pass:

1. the selected asset ID exists in `media-source-map-2026-08.json`;
2. the file path still matches the Milovi Cake source gallery;
3. the copy describes only what the source supports;
4. any quoted review is exact and currently published;
5. any price/address/delivery statement is freshness-checked against the current Milovi Cake fact source;
6. any Milovi School claim is checked against the exact article and its source trail;
7. any external link points to the intended current destination;
8. no BTS/kitchen/production promise is present while the asset contract says 0%;
9. no first-person Victoria voice is used without explicit approval or exact quotation;
10. no provider mutation is implied by editorial approval.

## 11. Known correction to the older launch corpus

`launch-pack-2026-08.md` predates the explicit no-BTS asset contract. Its pinned draft currently contains the phrase `детали и процесс`. While the current asset contract is active, that phrase is **not publishable as written** because readers could reasonably interpret it as production-process access.

The safe replacement is:

`Здесь — реальные работы Milovi Cake, красивые детали и подборки, полезные подсказки перед заказом и короткие истории французской кондитерской культуры из Milovi School.`

Any other older example using `process`, `backstage`, `закулисье`, `как мы делали` or similar language must be interpreted as superseded unless it refers unambiguously to the documented ordering/selection process.

## 12. What to collect later when production footage becomes available

BTS should be added only when there is material worth showing. A future source pack might contain:

- clean decorating close-ups;
- controlled final-assembly shots;
- short detail work with hands/tools;
- packaging/final check;
- a visually acceptable work surface;
- voiceover or caption context that does not expose private customer data.

When that material exists, revise the asset contract deliberately and re-balance the mix. Do not retroactively label old finished-work clips as BTS.

## 13. Completion boundary

This document, the media map and the 30-post sequence improve repository/editorial readiness only. They do not create a scheduler queue, invite link, post, pin, channel setting, ad placement or any other provider-side effect.

Live publication remains blocked until exact target discovery succeeds, immutable binding/cross-project guards are reviewed, and one exact canary is explicitly authorized and verified.
