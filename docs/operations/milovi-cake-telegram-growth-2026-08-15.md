# Milovi Cake — Telegram growth execution playbook

Date: 2026-08-15
Owning issue: #353
Project: `milovi-cake`
Telegram: `@MiloviCake`
Status: **provider-inert planning and onboarding**. This document does not authorize live publication, paid placement, direct messaging, admin changes, invite-link creation, or any Telegram/Dzen/VK provider mutation.

## 1. Objective

Build the first useful, relevant St Petersburg audience for Milovi Cake without turning Telegram into an extra mandatory step in the order funnel.

Primary commercial surfaces remain `https://milovicake.ru/` and the registered Milovi Cake VK community. Telegram is the owned-audience and retention layer: real works, brand/person presence, useful buyer guidance, pastry culture, verified reviews and occasional factual offers.

Working growth gates are 50, 150 and 300 relevant subscribers. They are decision gates, not promises or vanity targets. The quality test is whether subscribers read, forward, remain, message, visit Milovi surfaces and eventually contribute to attributable enquiries or sales.

## 2. Launch sequence — no empty-channel promotion

### Gate A — editorial readiness

Use the reviewed 30-post launch pack in `content/telegram/milovi-cake/launch-pack-2026-08.md`.

Do not dump all posts at once. Build a coherent archive: positioning → real work → utility → person/trust → real work → School story → verified social proof. Discovery posts are interleaved rather than clustered.

Every customer quote must be exact from the current published Milovi review source. First-person Victoria copy requires explicit approval or an exact sourced quotation.

### Gate B — discovery identity

Exact target discovery needs an immutable identity contract before a numeric target can be proved. Therefore a **provisional discovery profile** may exist before the numeric `chat_id`, but only under these constraints:

1. exact project key is `milovi-cake`;
2. exact public username is `@MiloviCake`;
3. shared bot expectation is pinned to id `8716602202`, username `@preaching_mp3_bot`;
4. `provider_writes_authorized=false` is mandatory;
5. profile existence is not publication authorization;
6. no target binding is committed until read-only provider proof succeeds.

This profile-first step is not a username-only publishing path. It creates the digest that the provider proof and eventual binding must match.

### Gate C — exact target readiness

Before the first automated/live post:

1. run the Milovi-only read-only discovery workflow from current `main`;
2. shared bot resolves exactly to the pinned id/username;
3. `@MiloviCake` resolves to one exact negative numeric `chat_id`;
4. numeric `getChat(chat_id)` round-trips to the same username and type `channel`;
5. shared bot appears as channel administrator and has `can_post_messages`;
6. all provider calls used for discovery are read-only (`getMe`, `getChat`, `getChatAdministrators`);
7. the proof is converted into an immutable target-binding candidate tied to the same profile digest;
8. binding is human-reviewed and committed in a separate change;
9. cross-project tests prove Milovi release/profile/binding cannot target Lordchrist or Svodka and vice versa;
10. first provider mutation is exactly one reviewed canary post;
11. canary outcome is verified before any second post or scheduling.

No username-only publishing path is acceptable after onboarding.

### Gate D — owned distribution

Only after the channel is worth subscribing to, activate source-attributed entry points on owned surfaces. Never replace the primary order path with Telegram.

Order of attack:

1. existing customers / post-purchase material;
2. `milovicake.ru` contextual links;
3. VK posts/clips where Telegram genuinely continues the story;
4. YouTube descriptions/pinned comments where appropriate;
5. packaging/card QR;
6. Dzen secondary distribution;
7. local partnerships;
8. paid Telegram placements only after retention can be measured.

## 3. Invite-link attribution contract

When live acquisition is authorized, use one Telegram invite link per meaningful source rather than one generic URL everywhere.

| Source ID | Placement | Purpose |
|---|---|---|
| `tg-site` | `milovicake.ru` | owned web → Telegram |
| `tg-vk` | VK community/posts/clips | VK → Telegram |
| `tg-youtube` | YouTube descriptions/comments | YouTube → Telegram |
| `tg-dzen` | Dzen bio/posts where appropriate | Dzen → Telegram |
| `tg-box` | cake box / insert QR | post-purchase retention |
| `tg-client` | existing-client follow-up | attributable client base |
| `tg-partner-<slug>` | photographer/decorator/studio partner | collaboration attribution |
| `tg-placement-<slug>-<yyyymm>` | each paid placement | media-buy attribution |

Rules:

- one source = one invite link;
- title link with exact source ID;
- never recycle a paid-placement link for another channel;
- preserve source ID in the experiment ledger even after revocation;
- QR points to the source-specific invite link, not the generic public username;
- no join-request friction unless abuse becomes a measured problem;
- no paid subscription invite links for this project.

## 4. Measurement model

### Acquisition

Record source ID, date range, spend if any, attributed joins, retention/unsubscribes where measurable, cost per join and cost per retained relevant subscriber for paid sources.

Raw join count alone is not success.

### Content

Track views/reach over a consistent window, forwards, reactions, replies/channel DMs, clicks to Milovi-owned surfaces, and a topic tag (`work`, `victoria`, `utility`, `school`, `review`, `commercial`, `poll`).

For external placement evaluation, TGStat may be used for recent subscriber dynamics, average reach, ERR/ER, ad reach, forwards and post-level stats. Seller-reported subscriber count alone is insufficient evidence.

### Commercial signal

The commercial funnel remains human and low-friction:

`Telegram source → site/VK/channel DM → qualified enquiry → order`.

Do not force customers through a bot for attribution. Prefer source-specific links and an optional “где нас нашли?” when useful.

## 5. Owned-surface implementations

### `milovicake.ru`

The site already has analytics hooks for Telegram clicks. A later site PR should preserve the purchase path and use contextual Telegram entry points near gallery/editorial/trust content, not replace primary order actions.

Candidates:

- gallery: “Новые работы и процесс — в Telegram”;
- reviews/post-purchase area: “Следить за новыми работами”;
- footer/social area: source-attributed Telegram link;
- no modal, interstitial or forced subscribe gate.

### Packaging / client insert

Use two independent QR actions:

- `tg-box`: “Новые работы и закулисье Milovi Cake”;
- official Yandex Business review QR: “Поделиться впечатлением”.

Never offer a reward for a positive Yandex review and never dictate review wording.

### VK

Do not use verbatim cross-posting as the growth mechanic. Bridge examples:

- VK clip shows the finished cake → Telegram has process/detail/choice context;
- VK post shows one work → Telegram has a real follow-up/poll/close-up;
- VK educational teaser → exact School/TG continuation.

A bridge must add genuine value; “подпишитесь ещё и там” is not a strategy.

### Dzen

Use Dzen as secondary reach, not a dependency. Default to low-cost Telegram-to-Dzen synchronization plus occasional adapted School long-form when the format warrants it.

Do not duplicate a separate editorial calendar unless measured results earn that effort.

## 6. Dzen stop/go experiment

Set the review point before launch; do not judge from one post. Track impressions, reads/views, completion where available, subscribers, outbound traffic, assisted enquiries and manual editorial time.

Decision:

- **GO / expand** only if there is meaningful incremental reach or qualified traffic relative to time cost;
- **KEEP CHEAP** if sync provides some free reach but manual adaptation is not justified;
- **STOP MANUAL WORK** if repeated adapted posts produce negligible qualified reach/traffic.

Do not claim Dzen backlinks automatically improve `milovicake.ru` SEO.

## 7. Local partner loop

Priority categories in St Petersburg: event/wedding photographers, decorators/florists, wedding/event organizers, children's studios/party organizers, presenters/small venues, and local family/lifestyle creators with credible geography.

Every collaboration needs a source-specific invite link and a clear value exchange. Avoid generic engagement swaps.

## 8. Paid Telegram placement checklist

Do not buy a placement until the channel has content depth and a source-specific invite link.

For each candidate record exact channel, geography, recent subscriber dynamics, recent and average reach, ERR/ER, forwards/mentions, ad frequency, suspicious spikes, format/duration, price, legal/marking handling, source ID, test-spend ceiling and post-campaign retention.

Start with small relevant local channels. Measure retained relevant subscribers and enquiry quality, not raw joins.

## 9. Working milestone decisions

### 7 → 50

No paid scale. Build depth and use owned/post-purchase sources. Look for non-family subscribers who actually read and remain.

### 50 → 150

Keep owned loops; begin measured local collaborations. Small paid placements only if archive and attribution are ready.

### 150 → 300

Compare sources by retained relevant subscriber and enquiry quality. Increase only sources that survive the comparison. Telegram Ads may be considered only if it solves a measured acquisition problem better than local seeding.

### 300+

Do not scale automatically. Establish a repeatable cohort model: source → retention → reach → enquiry → order where measurable.

## 10. Golden features worth using — and not overusing

- source-specific Telegram invite links for acquisition attribution;
- public post search: descriptive natural-language first lines, not hashtag spam;
- similar/recommended public channels: keep the channel public and coherent, but do not expect discovery to replace acquisition at tiny scale;
- channel Direct Messages as a low-friction human contact path;
- native polls only when there is a real follow-up;
- Yandex Business review QR as a post-purchase trust loop;
- Yandex live rating badge as a later trust test near reviews, not in the protected hero by default;
- Yandex Actions only for genuine current offers;
- VK channel-promotion object and AdBlogger as later measurable tools;
- short real-work video variants as a VK test hypothesis, not a universal rule.

## 11. Hard prohibitions

- fake/bought subscribers;
- engagement pods;
- spam DMs;
- invented reviews/customer stories;
- unapproved first-person Victoria voice;
- invented availability or “last slots” scarcity;
- stale prices;
- another project's Telegram binding/state/release;
- username-only destination after exact binding exists;
- blind retry after ambiguous provider effect;
- live mutation merely because this planning document exists.

## 12. Exact next technical step

After branch review/CI, merge the provider-inert onboarding artifacts. Then manually run `.github/workflows/telegram-milovi-target-discovery.yml` on current `main`.

Review the generated proof and binding candidate. Commit the exact Milovi binding separately with cross-project guards. Only after that should #353 receive one exact canary payload and explicit provider-write authorization for that single operation.
