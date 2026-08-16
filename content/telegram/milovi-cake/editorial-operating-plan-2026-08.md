# Milovi Cake Telegram — editorial operating plan

Status: **provider-inert / review only**  
Owning issue: #353  
Project: `milovi-cake`  
Current source constraint: production/kitchen/BTS footage is unavailable and its editorial share is **0%**.

## 1. What the channel is trying to become

Telegram should not duplicate the Milovi Cake website and should not become an extra step required to place an order. The strongest commercial surfaces remain VK and `milovicake.ru`. Telegram earns a subscription by becoming a compact visual media channel people can keep even when they do not need a cake today.

The launch promise is:

- real finished Milovi Cake work;
- useful ideas a person may save for a future celebration;
- clear, non-invented guidance about formats, design references and ordering;
- verified customer trust signals;
- later, occasional separately labelled educational reading when it is genuinely interesting.

The channel does **not** promise kitchen access, decorating footage, a studio tour, a daily diary, or staged stories about how an individual cake was made.

## 2. Milovi Cake and Milovi School are separate editorial identities

Milovi Cake is the cake/dessert product brand. Milovi School is a separate educational/editorial/SEO content project. School articles can create useful reading, discovery and brand interest, but they are not evidence of Milovi Cake recipes, production techniques, kitchen identity, staff training, product origin or culinary lineage.

Therefore:

- never call Milovi Cake a French-cuisine/French-pastry business merely because School publishes French pastry history;
- never say or imply that a School article explains how a Milovi Cake product was made;
- never infer that Milovi Cake uses a School recipe or technique;
- any direct product/production relationship between Cake and School requires its own exact source;
- the first ten launch posts contain **zero School items**;
- later School material must be clearly framed as separate educational reading, not product/process evidence.

The hard rule is `editorial-brand-boundary-2026-08.md`.

## 3. Current asset truth

The canonical Milovi Cake gallery declares 46 finished-work assets: 30 photographs and 16 videos. The local machine-readable mirror for editorial selection is `media-source-map-2026-08.json`, tied to source blob `e20e60c07479e8b20c1db700f1a40364b81eb669` in `FedorMilovanov/Milovi_Cake/js/gallery/data.js`.

It covers sculptural/3D cakes, children's themes, sports themes, bento, wedding work, cupcakes, meringue roll, Pavlova and gift-dessert formats. This is enough variety for a strong native launch without manufacturing fake BTS.

## 4. Long-horizon mix while BTS is unavailable

`editorial-sequence-30-posts-2026-08.json` remains a planning aid, not an execution queue. Its long-horizon categories may include a small educational lane, but the current first-screen release overrides older sequencing assumptions:

- first ten: **0 School**;
- finished Milovi work is the visual majority;
- useful format/design guidance should keep the feed from becoming repetitive “вот ещё торт” cards;
- exact social proof is allowed only from exact published review sources;
- educational School material can be considered only after the first screen and only under the separate-content rule above.

## 5. How one finished work becomes several legitimate posts

Reusing one real work is allowed only when each publication has a distinct editorial job. Do not repost the same image with cosmetic wording changes.

A real work may support:

1. **Hero/showcase** — the complete finished work with one clear identifying idea.
2. **Visible detail/design** — commentary on shape, colour, focal figure, texture, typography or contrast actually visible/documented.
3. **Collection/comparison** — several exact real works grouped under one theme, occasion, palette or format.
4. **Buyer-guidance illustration** — a neutral finished work accompanies factual guidance without inventing a customer story.

Never turn reuse into an invented production narrative. A final-cake video remains final-cake media; do not call it “процесс”, “как это создавалось” or “закулисье” without exact reviewed production footage.

## 6. Caption architecture

Default finished-work structure:

**Line 1 — searchable human title.** Name what is actually visible.

**Body — one useful observation.** Explain one visible/documented idea rather than stacking adjectives.

**Optional final line — one useful action.** Save the reference, compare a format, or use one relevant destination. A link is not mandatory.

Avoid:

- hashtag walls;
- generic adjective stacks without substance;
- invented emotional reactions/customer histories;
- invented ingredients/fillings;
- unverified availability/prices/delivery promises;
- fake scarcity;
- production claims inferred from a finished image;
- Cake↔School production claims;
- first-person Victoria voice without exact quotation or explicit reviewed approval.

## 7. First-screen quality standard

A cold visitor should understand the channel in the first ten visible publications without opening external links.

The current canonical set is `bootstrap-first-screen-candidates-2026-08.json`. It should provide:

- clearly different finished works;
- different editorial jobs: showcase, format/design reference, useful selection context;
- one exact trust signal;
- **zero Milovi School items**;
- no sales-post run;
- no external-link dump;
- no filler added just to increase count.

The first-screen test fails if the channel looks like a mirror of external platforms, a generic AI feed, or an educational School channel instead of Milovi Cake.

## 8. Publication cadence and quiet hours

Do not dump the archive in one session. Audience timing is part of product quality.

Canonical audience timezone: `Europe/Moscow` (Saint Petersburg/Moscow time).

- Ordinary Milovi Cake Telegram provider mutations may start only from **09:00 through 21:00 local time**.
- The gate runs before Telegram provider access and before durable dispatch intent.
- A release/authorization created during quiet hours does not override the window.
- A missed slot is not backfilled at night.
- Preferred rollout slots are `10:30`, `13:30`, `17:00`, `20:00` local.
- After the first-screen archive is established, move toward roughly 4–5 strong posts per week and adjust from actual audience response.

The machine-readable policy is `publishing-window-2026-08.json`.

## 9. Acquisition loop the content must support

Every growth surface should send people to a channel that already explains why it deserves the subscription.

- **VK → Telegram:** only when Telegram offers real continuation value; VK remains a sales surface.
- **Website → Telegram:** tasteful secondary entry points after visual interest, not interruption of the order path.
- **Existing customers/packaging:** future inspiration/new finished works is a better proposition than a generic “subscribe”.
- **YouTube/Clips:** link when there is additional native value, not on every item.
- **Paid/local placements:** only after a credible archive and source-specific attribution exist.

## 10. Discovery and search writing

Use natural descriptive topic language. Do not keyword-stuff. A title such as `3D-торт в стиле Minecraft`, `Светлый свадебный торт` or `Бенто с персональной надписью` is useful because it tells a human what they are seeing.

School/search content, when used later, must be introduced as an article/educational story. Search value never justifies implying a product/manufacturing relationship.

## 11. Editorial quality gates

A draft cannot enter an executable release unless all applicable checks pass:

1. exact asset id/path/source identity is known;
2. exact source bytes and accepted transport bytes are frozen for photo/video operations;
3. copy stays within visible/documented/source-backed facts;
4. quoted reviews are exact and source-bound;
5. current price/address/delivery claims are freshness-checked if used;
6. School material is separately labelled and passes Cake≠School boundary review;
7. external links are current and serve a real editorial purpose;
8. BTS/process language is absent while production footage remains 0%;
9. first-person Victoria voice has exact support/approval;
10. editorial approval is not confused with provider execution authority;
11. the selected release passes the daylight-window contract before provider access.

## 12. Historical canary correction

The exact historical canary `milovi-cake-canary-001` was successfully sent as Telegram message `25`, proving target identity, administrator/posting rights and JPEG `sendPhoto` capability. Its caption, however, included wording about “French pastry culture from Milovi School” that could imply an inappropriate direct relationship between Milovi Cake and School/French production identity.

The channel owner deleted that post. Preserve the exact historical dispatch/caption digest as evidence, but treat the payload as **superseded / do-not-republish**. See `live/operator-correction-2026-08-16.json`.

The older `launch-pack-2026-08.md` and historical canary files may contain other superseded examples. They are research/editorial history, not executable publication sources. The revised first-screen candidate set and brand-boundary rule govern future rollout copy.

## 13. Transport readiness

Nine first-screen photos now have exact pinned source byte identity, decoded dimensions and deterministic JPEG transport digests in `bootstrap-photo-transport-proof-2026-08.json`. This is transport readiness only. It does not authorize provider writes.

Current WebM gallery videos remain editorial sources, not native Telegram video payloads. Accepted MP4/H.264 outputs remain 0/16 until exact conversion/probe/output evidence exists. Never silently fall back to `sendDocument`.

## 14. Completion boundary

Repository/editorial readiness, transport artifact readiness and provider rollout are separate completion states.

The first-screen rollout is complete only when every selected item has its own durable intent, one zero-retry provider mutation, verified exact returned chat/message identity, persisted receipt, and no unresolved `may_exist` outcome. A historical successful canary does not grant standing batch authority.
