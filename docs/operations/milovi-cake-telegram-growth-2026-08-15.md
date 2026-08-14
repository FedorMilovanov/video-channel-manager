# Milovi Cake — Telegram growth execution playbook

Date: 2026-08-15
Owning issue: #353
Project: `milovi-cake`
Telegram: `@MiloviCake`
Status: **provider-inert planning and onboarding**. This document does not authorize live publication, paid placement, direct messaging, admin changes, invite-link creation, or any Telegram/Dzen/VK provider mutation.

## 1. Objective

Build the first useful, relevant St Petersburg audience for Milovi Cake without turning Telegram into an extra mandatory step in the order funnel.

Primary commercial surfaces remain `https://milovicake.ru/` and the registered Milovi Cake VK community. Telegram is the owned-audience and retention layer: real finished works, useful buyer guidance, verified reviews, selected brand/person context and a small sourced pastry-culture layer from Milovi School.

Production/kitchen/BTS footage is currently unavailable as a reviewed editorial source. Its share is **0%** until the explicit Milovi asset contract is deliberately revised against real reviewed footage. Do not stage, imply or promise production access to satisfy a generic content template.

Working growth gates are 50, 150 and 300 relevant subscribers. They are decision gates, not promises or vanity targets. The quality test is whether subscribers read, forward, remain, message, visit Milovi surfaces and eventually contribute to attributable enquiries or sales.

## 2. Launch sequence — no empty-channel promotion

### Gate A — editorial readiness

The current editorial source of truth is the finished-work system under `content/telegram/milovi-cake/`:

- `media-source-map-2026-08.json` — 46 verified finished-work assets: 30 photos + 16 videos;
- `editorial-sequence-30-posts-2026-08.json` — exact 30-slot provider-inert launch sequence;
- `editorial-asset-contract-2026-08.md` — production BTS/kitchen share = 0%;
- `editorial-operating-plan-2026-08.md` — caption, first-screen, reuse and cadence rules;
- `school-source-shortlist-2026-08.json` — exact three-item School source binding.

The older `launch-pack-2026-08.md` remains useful draft material but is subordinate to the newer asset/operating contracts wherever wording conflicts. In particular, its old `детали и процесс` welcome wording is not publishable while the no-BTS contract is active.

Do not dump all posts at once. After an explicitly authorized and provider-verified canary, build a coherent native archive rather than a link dump. The first-screen sequence should already contain visually different finished works, buyer utility, a collection/poll, a verified trust signal and only a small educational share.

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

1. run the Milovi-only read-only discovery workflow from **current `main`**;
2. shared bot resolves exactly to the pinned id/username via `getMe`;
3. `@MiloviCake` resolves via `getChat` to one exact negative numeric `chat_id`;
4. numeric `getChat(chat_id)` round-trips to the same username and type `channel`;
5. exact shared-bot membership is queried with `getChatMember(chat_id, user_id=<proved bot id>)`;
6. the returned member identity must resolve to the same bot, status must be `administrator` or `creator`, and `can_post_messages` must be true;
7. all discovery provider calls remain read-only: `getMe`, `getChat`, `getChatMember`;
8. the proof is converted into an immutable target-binding candidate tied to the same profile digest;
9. binding is human-reviewed and committed in a separate change;
10. cross-project tests prove Milovi release/profile/binding cannot target Lordchrist or Svodka and vice versa;
11. first provider mutation is exactly one reviewed canary post tied to the exact candidate review identity, exact target binding and exact materialized media digest;
12. canary outcome is provider-verified before any second post, pin, scheduling or rollout.

The previous discovery failure on `getChatAdministrators` was repaired in PR #356. Do **not** reintroduce broad administrator enumeration merely for target proof; the exact bot member is the only subject that must be proved.

No username-only publishing path is acceptable after onboarding.

### Gate D — media readiness

Editorially valid media is not automatically transport-ready.

The first canary preparation in PR #360 deliberately uses one exact photo candidate (`p18`) and remains blocked until exact source bytes are materialized, decoded, dimension-checked and SHA-256-frozen.

The 16 canonical Milovi videos are WebM editorial sources. PR #361 freezes their exact source identities/sizes and defines a deterministic MP4/H.264 readiness lane, but accepted native-video outputs remain **0 / 16**. Do not silently send a WebM or failed MP4 as `sendDocument` merely to make a post succeed.

### Gate E — owned distribution

Only after the channel is worth subscribing to and the exact canary path is verified should source-attributed entry points be activated on owned surfaces. Never replace the primary order path with Telegram.

Recommended order of attack:

1. existing customers / post-purchase material;
2. packaging/card QR;
3. `milovicake.ru` contextual links;
4. VK posts/clips where Telegram genuinely continues the content;
5. YouTube descriptions/pinned comments where appropriate;
6. Dzen secondary distribution;
7. local partnerships;
8. paid Telegram placements only after attribution and retention review are operational.

The machine-readable source registry is `docs/operations/milovi-cake-telegram-acquisition-registry-2026-08-15.json`. The evidence ledger is `docs/operations/milovi-cake-telegram-acquisition-experiments-2026-08-15.json`.

## 3. Attribution control plane

The old prose-only source table is replaced by the machine-readable registry. Fixed source IDs include:

- `tg-site-gallery` — contextual gallery → Telegram;
- `tg-site-footer` — site-wide social/footer discovery;
- `tg-vk-organic` — VK content with genuine Telegram continuation;
- `tg-youtube-organic` — YouTube continuation where useful;
- `tg-dzen-organic` — low-cost Dzen contribution;
- `tg-box` — packaging/insert QR;
- `tg-client` — natural post-purchase/existing-customer follow-up only.

Dynamic namespaces are reserved for exact named experiments:

- `tg-partner-<slug>`;
- `tg-placement-<slug>-<yyyymm>`.

### Source-link rules

When live acquisition is separately authorized:

- one measured source = one source-specific invite link;
- never recycle a paid-placement link for another channel or later buy;
- preserve source identity/evidence after closure or revocation;
- QR for a measured source points to that source-specific route, not the generic public username;
- the generic public route may remain an unmeasured profile/social link;
- no join-request friction by default unless abuse becomes a measured problem;
- no paid-subscription invite links for this project.

### Admin-rights boundary

Invite-link creation is **not** part of the posting bot's current publishing permission merely because source attribution is desirable.

Do not grant `@preaching_mp3_bot` broader rights such as `can_invite_users` only to automate analytics. The preferred default is manual source-link creation by a channel admin unless a separate exact provider mutation and permission change is reviewed and authorized.

The registry therefore keeps every `invite_url` null, every provider state `not_created`, and `invite_link_creation_authorized=false` until a real activation step exists.

## 4. Measurement model

The evidence ledger starts **empty**. Do not populate remembered/approximate metrics just to create a baseline. Capture a dated, evidence-backed baseline when the first experiment is actually activated.

### Acquisition

For each experiment record:

- immutable experiment ID;
- exact source ID;
- declared measurement method;
- start/end time;
- spend if applicable;
- attributed joins only when the declared method supports them;
- 7-day/30-day retained counts only if actually measurable;
- attributable enquiries/order signals only where evidence supports attribution;
- exact evidence references;
- explicit decision: `keep`, `iterate`, `stop` or `inconclusive`.

Missing evidence is `null`, not zero. Timing coincidence is not attribution.

Raw join count alone is not success.

### Content

Track views/reach over a consistent window, forwards, reactions, replies/channel DMs, clicks to Milovi-owned surfaces, and the reviewed content pillar. Current editorial pillars are more precise than the old generic tags: finished showcase, finished detail/design, collection/poll, social proof/buyer guidance, Milovi School and factual commercial.

For external placement evaluation, current channel/account evidence and third-party analytics may be used only as supporting evidence. Seller-reported subscriber count alone is insufficient.

### Commercial signal

The commercial funnel remains human and low-friction:

`Telegram source → site/VK/channel DM → qualified enquiry → order`.

Do not force customers through a bot for attribution. Prefer source-specific links and optional human attribution such as “где нас нашли?” only where useful.

## 5. Owned-surface implementations

### `milovicake.ru`

The site remains a conversion surface. A site implementation should preserve the order path and use contextual Telegram entry points near gallery/editorial/trust content rather than replacing primary order actions.

Candidate copy while the no-BTS contract is active:

- gallery: **“Новые работы и подборки — в Telegram”**;
- reviews/post-purchase area: **“Следить за новыми работами”**;
- footer/social area: a source-attributed Telegram link;
- no modal, interstitial or forced subscribe gate.

Do not use “процесс”, “закулисье” or similar production-access promises until reviewed production footage actually exists.

### Packaging / client insert

Keep Telegram growth and review collection as distinct actions:

- `tg-box`: **“Новые работы и идеи Milovi Cake”**;
- separate official review action: **“Поделиться впечатлением”** where appropriate.

The Telegram QR is a retention/inspiration route, not a review quid pro quo and not a required part of collecting the order.

### VK

Do not use verbatim cross-posting as the growth mechanic. Bridge examples while BTS is unavailable:

- VK clip shows a finished cake → Telegram has an extended finished-work selection, close-up/details or a real poll;
- VK post shows one work → Telegram has a thematic collection or comparison;
- VK educational teaser → exact School/TG continuation when the topic genuinely fits.

A bridge must add genuine value; “подпишитесь ещё и там” is not a strategy.

### YouTube

Use `tg-youtube-organic` only when a specific video has a sensible Telegram continuation. Do not blanket every description/pinned comment with an identical cross-platform CTA solely to inflate link frequency.

### Dzen

Use Dzen as secondary reach, not a dependency. Default to low-cost reuse/synchronization plus occasional adapted School long-form when the format warrants it.

Do not duplicate a separate editorial calendar unless measured results earn that effort.

## 6. Dzen stop/go experiment

Set the review point before launch; do not judge from one post. Track impressions, reads/views, completion where available, subscribers, outbound traffic, assisted enquiries and manual editorial time.

Decision:

- **GO / expand** only if there is meaningful incremental reach or qualified traffic relative to time cost;
- **KEEP CHEAP** if reuse provides some free reach but manual adaptation is not justified;
- **STOP MANUAL WORK** if repeated adapted posts produce negligible qualified reach/traffic.

Do not claim Dzen backlinks automatically improve `milovicake.ru` SEO.

## 7. Local partner loop

Potential St Petersburg categories include event/wedding photographers, decorators/florists, wedding/event organizers, children's studios/party organizers, presenters/small venues, and local family/lifestyle creators with credible geography.

A category is not a recommendation to buy. Each actual partner is a separate reviewed experiment with its own `tg-partner-<slug>` source, explicit value exchange and evidence. Avoid generic engagement swaps.

## 8. Paid Telegram placement checklist

Do not buy a placement until the channel has content depth, an exact source-specific route and a declared measurement method.

For each candidate record exact channel, geography, recent subscriber dynamics, recent and average reach, forwards/mentions, ad frequency, suspicious spikes, format/duration, price, current legal/marking handling, source ID, test-spend ceiling and post-campaign retention where measurable.

Start with small relevant local tests rather than scale. Measure retained relevant subscribers and enquiry quality, not raw joins.

## 9. Working milestone decisions

### Tiny launch cohort → 50 relevant subscribers

No paid scale. Build native archive depth and use owned/post-purchase sources. Look for non-family subscribers who actually read and remain.

### 50 → 150

Keep owned loops; begin measured local collaborations. Small paid placements only if archive, attribution and legal handling are ready.

### 150 → 300

Compare sources by retained relevant subscriber and enquiry quality. Increase only sources that survive the comparison. Telegram Ads or larger seeding may be considered only if they solve a measured acquisition problem better than owned/local sources.

### 300+

Do not scale automatically. Establish a repeatable cohort model: source → retention → reach → enquiry → order where measurable.

## 10. Platform features worth using — and not overusing

- source-specific Telegram invite links for acquisition attribution;
- descriptive natural-language first lines that help humans and public discovery understand the post;
- channel Direct Messages as a low-friction human contact path where useful;
- native polls only when there is a real editorial question/follow-up;
- Yandex Business review/trust work as a separate post-purchase loop;
- VK paid/organic growth tools only when they support a measured objective;
- finished-work video variants as a cross-surface test hypothesis, not a universal rule.

Do not expect platform discovery alone to replace acquisition at tiny scale.

## 11. Hard prohibitions

- fake/bought subscribers;
- engagement pods;
- spam DMs;
- invented reviews/customer stories;
- unapproved first-person Victoria voice;
- invented availability or “last slots” scarcity;
- stale prices;
- staged/fake BTS or production-access copy while no reviewed production footage exists;
- another project's Telegram binding/state/release;
- username-only destination after exact binding exists;
- broad administrator enumeration when exact `getChatMember` proof is sufficient;
- automatic posting-bot permission expansion merely to create invite links;
- blind retry after ambiguous provider effect;
- live mutation merely because a planning/registry document exists.

## 12. Exact current technical state and next dependency

Merged provider-inert foundation:

- #354 — initial Milovi onboarding/research/growth artifacts;
- #356 — exact-bot discovery repair (`getChatMember`, not administrator-list enumeration);
- #358 — 46-item finished-work source map + 30-slot no-BTS editorial system;
- #360 — exact blocked photo canary candidate + media readiness + Git-blob review lock;
- #361 — exact 16-WebM source manifest + deterministic native-video MP4 readiness lane, accepted outputs 0 / 16.

The live path is currently blocked on one fresh read-only action: manually run `.github/workflows/telegram-milovi-target-discovery.yml` from **current `main`**. Do not rerun the historical failed workflow run, because a rerun executes its original old SHA.

Review the resulting exact proof/binding candidate. Only then may a separate PR commit the exact Milovi target binding with cross-project guards. The existing photo canary remains blocked until the selected source bytes are materialized/verified and one exact mutation is explicitly authorized.

The acquisition registry and experiment ledger remain provider-inert until the channel canary and archive are verified; no invite links are created by this playbook.
