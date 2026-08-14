# Milovi Cake — Telegram growth execution playbook

Date: 2026-08-15
Owning issue: #353
Project: `milovi-cake`
Telegram: `@MiloviCake`
Status: **provider-inert planning and onboarding**. This document does not authorize live publication, paid placement, direct messaging, or any Telegram/Dzen/VK provider mutation.

## 1. Objective

Build the first useful, relevant St Petersburg audience for Milovi Cake without turning Telegram into an extra mandatory step in the order funnel.

Primary commercial surfaces remain `https://milovicake.ru/` and the registered Milovi Cake VK community. Telegram is the owned-audience and retention layer: real works, Victoria/brand presence, useful buyer guidance, pastry culture, verified reviews, and occasional factual offers.

Working growth gates are 50, 150 and 300 relevant subscribers. They are decision gates, not promises or vanity targets. The quality test is whether subscribers read, forward, return, message, visit Milovi surfaces and eventually contribute to attributable enquiries or sales.

## 2. Launch sequence — no empty-channel promotion

### Gate A — editorial readiness

Before meaningful promotion, the channel should have enough useful depth that a new visitor can scroll and understand the proposition. Use the reviewed 30-post launch pack in `content/telegram/milovi-cake/launch-pack-2026-08.md`.

Do not dump all posts at once. The initial archive should be built as a coherent sequence: positioning → real work → utility → person/trust → real work → School story → social proof, with discovery posts interleaved rather than clustered.

### Gate B — exact target readiness

Before the first automated/live post:

1. selected Milovi profile is valid and `provider_writes_authorized=false`;
2. shared bot resolves exactly to bot id `8716602202`, username `@preaching_mp3_bot`;
3. `@MiloviCake` resolves to one exact negative numeric `chat_id`;
4. numeric `getChat(chat_id)` round-trips to the same username and type `channel`;
5. shared bot is present as channel administrator and has `can_post_messages`;
6. the read-only proof is converted to a target-binding candidate;
7. binding is reviewed and committed separately;
8. cross-project tests prove Milovi profile/release cannot target Lordchrist or Svodka;
9. first provider mutation is exactly one reviewed canary post;
10. canary outcome is verified before any second post or scheduling.

No username-only publishing path is acceptable after onboarding.

### Gate C — owned distribution

Only after the channel looks worth subscribing to, activate source-attributed entry points on owned surfaces. Do not replace order CTAs with Telegram CTAs.

Order of attack:

1. existing Milovi customers / post-purchase material;
2. `milovicake.ru` contextual links;
3. VK posts/clips where Telegram genuinely continues the story;
4. YouTube descriptions/pinned comments where appropriate;
5. packaging/card QR;
6. Dzen secondary distribution;
7. local partnerships;
8. paid Telegram placements only after retention can be measured.

## 3. Invite-link attribution contract

Do not use the same `t.me/MiloviCake` URL everywhere when Telegram invite links are available. Create one invite link per meaningful source so acquisition is attributable inside Telegram.

Canonical source IDs:

| Source ID | Placement | Purpose |
|---|---|---|
| `tg-site` | `milovicake.ru` | owned web → Telegram |
| `tg-vk` | VK community/posts/clips | VK → Telegram |
| `tg-youtube` | YouTube descriptions/comments | YouTube → Telegram |
| `tg-dzen` | Dzen bio/posts where appropriate | Dzen → Telegram |
| `tg-box` | cake box / insert QR | post-purchase retention |
| `tg-client` | manual existing-client follow-up | attributable client base |
| `tg-partner-<slug>` | photographer/decorator/studio partner | collaboration attribution |
| `tg-placement-<slug>-<yyyymm>` | each paid placement | media-buy attribution |

Rules:

- one source = one invite link;
- title the invite link with the exact source ID;
- never recycle a paid-placement link for another channel;
- preserve source ID in the experiment ledger even if the Telegram link is later revoked;
- QR codes point to the source-specific invite link, not the generic public username;
- do not introduce join-request approval friction for normal acquisition unless abuse becomes a measured problem;
- do not use paid subscription invite links for this project.

## 4. Measurement model

### Acquisition

For each source/experiment record:

- source ID;
- start/end date;
- spend if any;
- joins attributed to the invite link;
- observed unsubscribes / retained audience where measurable;
- cost per join;
- cost per retained relevant subscriber for paid sources.

Raw join count alone is not a success metric.

### Content

Track at minimum:

- views/reach by post and over a consistent time window;
- forwards;
- reactions;
- replies/Direct Messages attributable to content where known;
- clicks to `milovicake.ru`, Milovi School or registered Milovi VK surfaces;
- format/topic tag: `work`, `victoria`, `utility`, `school`, `review`, `commercial`, `poll`.

For external placement evaluation, TGStat may be used for recent subscriber dynamics, average post reach, ERR/ER, ad reach, forwards and post-level stats. Never accept a seller's subscriber count as sufficient evidence of audience quality.

### Commercial signal

The commercial funnel remains human and low-friction. Track when technically/operationally possible:

`Telegram source → site/VK/DM → qualified enquiry → order`.

Do not force customers into a bot merely to obtain cleaner attribution. If source attribution becomes commercially important, use source-specific links and a lightweight optional question such as “где нас нашли?”, not a mandatory automation wall.

## 5. Owned-surface implementations

### `milovicake.ru`

The site already has analytics hooks for `t.me` clicks. Any future site change should preserve the purchase path and use contextual Telegram entry points, for example near gallery/editorial/trust content rather than replacing primary order actions.

Best candidates for a later reviewed site PR:

- gallery: “Новые работы и процесс — в Telegram”;
- reviews/post-purchase area: “Следить за новыми работами”;
- footer/social area: source-attributed Telegram link;
- no modal, interstitial or forced subscribe gate.

### Packaging / client insert

Use two independent QR actions rather than one overloaded code:

- `tg-box`: “Новые работы и закулисье Milovi Cake”;
- official Yandex Business review QR: “Поделиться впечатлением”.

Never offer a discount/reward specifically for a positive Yandex review and never script the review text.

### VK

Do not repost Telegram verbatim as the growth mechanic. Use bridge content:

- VK clip shows the finished cake → Telegram has the process/detail/choice story;
- VK post shows one work → Telegram poll decides the next close-up;
- VK educational teaser → exact School/TG continuation.

A bridge must contain real incremental value; “подпишитесь ещё и там” without value is not a strategy.

### Dzen

Use Dzen as secondary reach, not a dependency. The low-cost default is official Telegram-to-Dzen synchronization plus occasional adapted School long-form when the format warrants it.

Do not duplicate a separate manual editorial calendar unless the experiment earns it.

## 6. Dzen stop/go experiment

Evaluation window: use enough published material to avoid judging from one post; record a fixed review point before starting the experiment.

Track:

- impressions;
- opens/reads;
- completion where available;
- subscribers gained;
- outbound traffic to Milovi-owned surfaces;
- assisted enquiries if identifiable;
- manual editorial time spent.

Decision:

- **GO / expand** only if Dzen produces meaningful incremental reach or qualified traffic relative to the time cost;
- **KEEP CHEAP** if sync produces some free reach but manual adaptation is not justified;
- **STOP MANUAL WORK** if repeated adapted posts produce negligible qualified reach/traffic. Automatic low-cost sync may remain if it causes no operational burden.

Do not claim Dzen backlinks automatically improve `milovicake.ru` SEO.

## 7. Local partner loop

Priority partner categories in St Petersburg:

- event/wedding photographers;
- decorators and florists;
- wedding/event organizers;
- children's studios and party organizers;
- presenters / small event venues;
- local family/lifestyle creators where audience geography is credible.

A collaboration should have a source-specific invite link and a clear value exchange. Avoid generic engagement swaps and channels whose only value is a large unexplained subscriber count.

## 8. Paid Telegram placement checklist

Do not buy a placement until the channel has enough content depth and a source-specific invite link.

For every candidate channel record:

- exact public channel username/link;
- geography and relevance to SPb / specific districts/suburbs;
- recent subscriber dynamics;
- average post reach and recent post-level reach;
- ERR/ER where available;
- forwards/mentions/citation pattern;
- recent ad frequency;
- suspicious spikes or abrupt audience changes;
- expected placement format and duration;
- quoted cost;
- Russian internet-ad classification/marking handling for this exact format;
- experiment source ID `tg-placement-...`;
- maximum acceptable test spend before launch;
- post-campaign retained-subscriber result.

Start with small, relevant local channels. One successful micro-placement is more useful than a large generic audience that never needs a cake in St Petersburg.

## 9. Working milestone decisions

### 7 → 50

No paid scale. Build channel depth and use owned/post-purchase sources. Look for signs that non-family subscribers actually read and remain.

### 50 → 150

Keep owned loops, start measured local collaborations. Test only small paid placements if the channel archive and attribution are ready.

### 150 → 300

Compare sources by retained relevant subscriber and enquiry quality. Increase only the sources that survive this comparison. Telegram Ads / broader media may be considered only if they solve a measured acquisition problem better than local seeding.

### 300+

Do not automatically scale spend. Establish a repeatable acquisition cohort model first: source → retention → reach → enquiry → order where measurable.

## 10. Golden features worth using — and not overusing

- **Telegram source-specific invite links:** core attribution primitive.
- **Telegram public post search:** reason to use descriptive natural-language first lines rather than hashtag spam.
- **Similar/recommended public channels:** reason to keep the channel public and topically coherent; not a substitute for acquisition at tiny scale.
- **Channel Direct Messages:** useful low-friction contact path; avoid an unnecessary customer-facing order bot.
- **Native polls:** useful when there is a real follow-up action; do not create empty engagement bait.
- **Yandex Business review QR:** post-purchase trust loop.
- **Yandex live rating badge:** later trust test near reviews, not in the protected primary order hero by default.
- **Yandex Actions:** free distribution for a genuine current special offer, never fake scarcity.
- **VK channel-promotion object:** later measurable growth option for VK/Dzen; not a reason to divert the first Telegram budget.
- **VK AdBlogger:** candidate source for measured local creator/community placements, with legal/marking workflow checked per placement.

## 11. Hard prohibitions

- fake/bought subscribers;
- engagement pods;
- spam DMs;
- invented client stories/reviews;
- invented availability or “last slots” scarcity;
- publishing stale prices without source recheck;
- using another project's Telegram binding, state branch or release;
- username-only destination after exact binding exists;
- blind retry after ambiguous Telegram provider effect;
- live provider mutation merely because this planning document exists.

## 12. Exact next technical step

After this playbook and launch pack are reviewed on the branch, run **read-only target discovery** through the repository's generic profile-driven Telegram runtime. Persist the proof artifact, review the resulting numeric `chat_id`, then create a Milovi-specific immutable target binding in a separate reviewed change.

Only after the binding and cross-project guards are green should #353 be amended with one exact canary payload and explicit provider-write authorization for that single operation.
