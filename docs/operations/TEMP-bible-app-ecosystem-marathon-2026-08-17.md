# TEMP — Bible App Ecosystem Marathon Ledger

> **TEMPORARY EXECUTION/AUDIT FILE — MUST BE DELETED AT FINAL CLOSURE.**
>
> This file is the recoverable source of truth for the cross-repository marathon that integrates the Bible Mini App into the public ecosystem of **«Господь Бог — Сила Моя»** without turning every publication into advertising.
>
> It exists so that a new agent/session can resume after interruption without guessing from chat history. It is intentionally operational and temporary. Durable architecture/policy belongs in the appropriate repository contracts; durable historical evidence belongs in issues/PRs/audits. When the marathon is complete and durable state has been transferred, **delete this file entirely**.

## 0. Recovery protocol — read this first after any interruption

If a session/agent restarts:

1. Read this file from the latest branch/PR that owns the current wave.
2. Re-read the current `AGENTS.md` in every repository that the next wave will mutate.
3. Resolve **fresh current `main` SHA** for each affected repository. The SHAs in §2 are the start snapshot only, not standing authority.
4. Inspect active PRs/branches that can overlap the next bounded scope. Do not resume a stale/closed/superseded branch merely because this file names it.
5. Read the **Last verified checkpoint** in §15 and start from the first item whose postcondition is not proven.
6. Preserve completed child work. Never replay provider mutations or already-verified remote operations.
7. Update this ledger immediately after a meaningful recoverable checkpoint: branch/PR opened, review result, exact-head tests, merge, production witness, or a blocking decision.
8. Do not mark a row `DONE` from intent, code existence, an old green run, a screenshot, or chat memory. Record evidence.

**Stop condition:** if current `main`, provider state, or an overlapping lane materially differs from this ledger, stop implementation, reconcile read-only, then update this file before proceeding.

---

## 1. Owner directive / requested outcome

Build a premium, non-spammy ecosystem around the already-enabled Telegram Main Mini App `@milovanovaibot`:

- the Bible trainer should be discoverable from the places where a permanent product entry is natural;
- normal editorial posts must **not** carry the same CTA by default;
- contextual deep links should appear only when the content genuinely maps to a course/chapter/topic;
- `gospod-bog.ru` gets a dedicated premium application page and carefully chosen contextual entry points;
- Telegram channel/profile/pinned surfaces get durable navigation-level access;
- YouTube/VK receive stable profile/navigation links plus contextual links where the platform surface and topic justify them;
- `video-channel-manager` becomes the canonical policy/rendering layer for cross-platform CTA behavior rather than ad-hoc copy/paste;
- `bible-bot` gains/retains deterministic deep-link handling and measurable source attribution where appropriate;
- implementation is audited, source-led, mobile-first, accessible, performance-conscious, and recoverable;
- live provider writes remain separately gated by exact reviewed operations even when repository implementation is ready.

### Product-language rule

Public UX should prefer **«Библейский тренажёр»**, **«Приложение»**, **«Проверить знания»**, **«Закрепить прочитанное»** over repeated technical wording **«бот»**. `Telegram` is a launch environment, not the product identity.

---

## 2. Marathon start snapshot — 2026-08-17 02:03 +03:00

These are rollback/start anchors only. Re-resolve before every new wave.

| Repository | Start `main` SHA | Role |
|---|---|---|
| `FedorMilovanov/video-channel-manager` | `48fb0e8faf1bb0cce3932019fbaf473208d4765b` | cross-platform editorial/Telegram/YouTube/VK policy and preview/execution architecture |
| `FedorMilovanov/gb-is-my-strength` | `c729f799a7922c3e2641c14b8637c2a94f5e3f9d` | `gospod-bog.ru`, premium landing page, contextual site entry points |
| `FedorMilovanov/bible-bot` | `cba75e90d3717e0f6aebd5ffda08ba3db3ff4b84` | Telegram Mini App, deep links, source attribution, in-app return paths |

Known public/application state at marathon start:

- Telegram Main Mini App is already enabled for `@milovanovaibot`.
- Bot profile already exposes the large **Open App** action.
- Bot chat menu already exposes an **Open application** Mini App entry.
- Current Mini App URL in BotFather: `https://bible-bot-qrg1.onrender.com/app`.
- Current mode observed: `Fullsize`.
- `gospod-bog.ru` is the production custom domain for `gb-is-my-strength`.
- `video-channel-manager` already has a `lord-god-strength` / `@lordchrist` Telegram profile, with generic provider writes not standing-authorized.

Do not infer future provider authority from these observations.

---

## 3. Non-spam UX doctrine — mandatory

### 3.1 CTA intensity model

Every content item or surface must resolve to exactly one CTA level:

- `none` — default for ordinary editorial content;
- `contextual` — one restrained application link when the material maps to a useful test/course/topic;
- `strong` — only durable navigation/product surfaces or intentionally application-led launches.

**Default = `none`.**

Target editorial mix is a design heuristic, not an automated quota:

- roughly 80% of ordinary content: no app CTA;
- roughly 15%: contextual CTA where it adds reader value;
- roughly 5%: strong CTA for launch/pinned/navigation/application-focused material.

No implementation may automatically append the app CTA to every Telegram post, article, video, Clip, Short, or description.

### 3.2 Permanent/high-value entry surfaces

Strong or permanent entry is appropriate for:

- Telegram bot profile / Main Mini App;
- Telegram bot menu button;
- one curated `@lordchrist` navigation/pinned post;
- `@lordchrist` description/about when length and hierarchy permit;
- dedicated `gospod-bog.ru/app/` landing page;
- one tasteful home-page application card/entry;
- YouTube channel profile links;
- VK community navigation/pinned surface where supported and editorially appropriate.

### 3.3 Contextual entry surfaces

Use only when the content maps to a meaningful app destination:

- end-of-article continuation after reading/completion;
- local website quiz result/completion state;
- article/series about 1 Peter or another course actually present in the app;
- long-form YouTube/VK material with a matching trainer module;
- selected Telegram posts explicitly teaching the same chapter/topic.

### 3.4 Forbidden/avoid surfaces

Do not add repetitive app promotion:

- to unrelated quotations/devotional posts;
- in the middle of long-form reading where it interrupts comprehension;
- as intrusive modal/interstitial takeover;
- to every Short/Clip description merely because a link exists;
- as duplicate CTA when a nearby permanent navigation link already serves the same action;
- as generic `Подписывайтесь / переходите в бота` marketing copy.

---

## 4. Canonical destination model

### 4.1 Canonical public product route

Preferred canonical site landing route:

`https://gospod-bog.ru/app/`

Reason: the existing website already contains local quizzes/learning UI. `/app/` cleanly communicates that the Telegram trainer is a separate interactive product, while `/quiz/` can be misleadingly conflated with on-site quizzes.

Decision before implementation:

- [ ] confirm `/app/` as canonical route;
- [ ] decide whether `/quiz/` should be absent, redirect to `/app/`, or remain unused. Do not create duplicate indexable landing pages.

### 4.2 Canonical Telegram launch

Base Main Mini App link:

`https://t.me/milovanovaibot?startapp`

Deep-link source/topic parameters must be stable, human-auditable, and bounded.

Initial taxonomy proposal:

| Param | Intended source/destination |
|---|---|
| `tg_pin` | pinned/navigation post in `@lordchrist` |
| `tg_profile` | permanent Telegram profile/about entry where controllable |
| `site_app` | main CTA on `gospod-bog.ru/app/` |
| `site_home` | home-page application card |
| `site_1peter_ch1` … `site_1peter_ch5` | contextual site chapter entries |
| `yt_profile` | YouTube channel profile link |
| `yt_1peter_chN` | contextual long-form YouTube description/comment |
| `vk_pin` | VK navigation/pinned surface |
| `vk_1peter_chN` | contextual VK long-form material |

Topic-opening params already supported by the app must not be accidentally broken. If source attribution and destination routing need both dimensions, define a versioned encoding contract rather than overloading one string informally.

---

## 5. Measurement / attribution requirements

The marathon is not complete if entry links are impossible to distinguish.

Minimum desired event model, subject to current `bible-bot` architecture review:

- `launch_source` / normalized `start_param`;
- resolved destination/course/chapter;
- first app open vs returning open when safely measurable;
- quiz/course start after external entry;
- quiz/course completion after external entry;
- no client-authoritative score or identity fields;
- no sensitive raw Telegram payload logging;
- bounded retention consistent with existing application data policy.

Preferred principle: store normalized attribution in server-authoritative application state or an existing analytics-safe event mechanism; do not make `localStorage` the durable source of truth.

Metrics for final audit:

- launches by source surface;
- conversion launch → course start;
- conversion course start → completion;
- contextual chapter deep-link success rate;
- 404/dead-link rate;
- site CTA click-through by placement if a privacy-compatible site metric already exists or is intentionally added.

Do not add third-party analytics merely to satisfy this marathon without an explicit privacy/architecture decision.

---

## 6. Cross-platform presentation policy target

`video-channel-manager` should eventually own a canonical, provider-inert CTA object rather than literal duplicated copy.

Conceptual model (exact schema TBD after code audit):

```text
ecosystem_links:
  website
  bible_app
  telegram_channel
  discussion
  youtube
  vk

app_cta:
  level: none | contextual | strong
  destination: <stable destination key>
  source_surface: <stable source key>
  copy_variant: <reviewed variant key>
```

Renderer responsibility:

- Telegram channel: URL button/link appropriate for channel posts, never a private-chat-only Web App button;
- YouTube: profile link or restrained description/comment block where supported;
- VK: native text/link treatment appropriate to the target surface;
- website: native design-system component, not copied provider markup;
- Mini App: native internal navigation/outbound library links.

The existing `@lordchrist` legacy live path must not be casually refactored merely to add a new CTA class. Build preview/provider-inert capability first and preserve cross-track safety.

---

## 7. Website design brief — `gospod-bog.ru/app/`

Quality bar: editorial-premium, part of the existing library, not a SaaS template and not a Telegram-blue advertisement.

### 7.1 Visual language

Reuse the site's current design system/tokens and typography contracts. Current palette direction includes deep graphite, warm ivory text and muted gold accents. Telegram blue, if used, is a minor affordance accent only.

Avoid:

- generic phone mockup + blue gradient hero;
- fake testimonials/review counters;
- oversized marketing claims not backed by product capability;
- duplicate CSS/runtime systems;
- intrusive auto-playing video;
- decorative complexity that harms LCP/CLS/INP.

### 7.2 Proposed information architecture

1. **Hero** — `БИБЛЕЙСКИЙ ТРЕНАЖЁР` / `Читайте. Проверяйте. Запоминайте.`
2. One primary CTA — `Открыть тренажёр` → `?startapp=site_app`.
3. Real product preview, not invented UI.
4. `Как это работает`: read → check → learn from mistakes → continue.
5. Real course/topic availability from current app inventory.
6. Progress/statistics/challenge benefits only if current product supports them.
7. Relationship to the website library: trainer complements deep reading.
8. Compact FAQ: Telegram requirement, privacy/account behavior, free/access status only if verified.
9. Final CTA.

Desktop may include a QR launch aid; mobile should prefer one-tap launch and hide redundant QR UI.

### 7.3 Site placement doctrine

Candidate permanent placements:

- one home-page card in the existing entry/navigation system;
- dedicated `/app/` page;
- possibly footer/resource navigation if current hierarchy supports it.

Candidate contextual placements:

- after local `Проверь себя` completion;
- at the end of matching 1 Peter chapter/article pages;
- at a series completion/continue-learning point.

No blanket injection into every article template unless the component itself evaluates a reviewed context rule and defaults to hidden.

---

## 8. Telegram `@lordchrist` target presentation

### Permanent surfaces

- concise profile/about line for the trainer if current hierarchy/length allows it;
- one pinned/navigation post for the whole ecosystem;
- app link should sit alongside website/video/discussion destinations, not dominate every message.

### Pinned/navigation post concept

`ГОСПОДЬ БОГ — СИЛА МОЯ`

- Читать исследования → website
- Проверять и закреплять знания → Bible trainer
- Смотреть материалы → video surfaces
- Обсуждать → community/chat

Provider implementation must use supported URL buttons/links for a channel context and be previewed exactly before any live write.

### Ordinary post policy

`app_cta=none` unless a reviewed content-to-course mapping exists.

Contextual copy examples to test, not yet canonical:

- `Закрепить прочитанное → пройти вопросы по 1 Петра 2`
- `Проверить, что запомнилось → открыть тренажёр`
- `Продолжить изучение в тренажёре →`

Avoid promotional boilerplate and emoji overload.

---

## 9. YouTube / VK target policy

### YouTube

Permanent:

- channel profile links: website first, Bible trainer second unless later evidence justifies another hierarchy.

Contextual:

- long-form descriptions on matching topics;
- selected pinned/top-level comment only when it adds a useful next step and does not duplicate nearby copy.

Avoid:

- raw app URL spam in Shorts descriptions/comments where the platform experience makes it low-value;
- changing unrelated published metadata in bulk without an exact reviewed plan.

### VK

Permanent:

- community navigation/pinned entry where current platform/community configuration supports it.

Contextual:

- matching long-form post/video copy;
- Clips should normally lead to a related full internal video/content path before pushing users out to Telegram, when that creates a better native journey.

All provider changes require separate exact reviewed rollout authorization.

---

## 10. Wave plan and status dashboard

Status vocabulary:

- `TODO` — not started;
- `ACTIVE` — bounded current work exists;
- `BLOCKED` — cannot safely proceed; reason must be recorded;
- `REVIEW` — implementation exists, exact review/checks pending;
- `DONE-REPO` — repository implementation merged and exact-head green;
- `DONE-LIVE` — provider/site live postcondition verified where live rollout is part of that wave;
- `N/A` — deliberately not required, with reason.

### Aggregate start statistics

| Metric | Start | Current |
|---|---:|---:|
| Waves fully complete | 0 / 10 | 0 / 10 |
| Repositories with marathon implementation merged | 0 / 3 | 0 / 3 |
| Dedicated site landing route live | 0 / 1 | 0 / 1 |
| Cross-platform CTA policy implemented | 0 / 1 | 0 / 1 |
| Source-attribution/deep-link contract verified | 0 / 1 | 0 / 1 |
| Permanent public entry surfaces reviewed | 0 / target TBD | 0 |
| Contextual placements reviewed | 0 / target TBD | 0 |
| Official/reliable research sources reviewed | 0 / ≥35 | 0 |
| Provider writes executed by this marathon | 0 | 0 |
| Temporary marathon files remaining | 1 | 1 |

### Wave table

| Wave | Scope | Repository/surface | Status | Completion evidence |
|---:|---|---|---|---|
| 0 | Recoverable audit/ledger foundation | `video-channel-manager` | `ACTIVE` | this file committed on bounded branch |
| 1 | 35+ source research + current-surface inventory | all/public docs | `TODO` | source ledger + current implementation map |
| 2 | Canonical CTA/deep-link/attribution contract | `video-channel-manager` + `bible-bot` | `TODO` | reviewed schemas/contracts/tests |
| 3 | Provider-inert Telegram/YouTube/VK CTA preview support | `video-channel-manager` | `TODO` | exact previews + tests, no provider write |
| 4 | Premium `/app/` landing page | `gb-is-my-strength` | `TODO` | route/registry/SEO/visual/browser checks |
| 5 | Site home/contextual entry integration | `gb-is-my-strength` | `TODO` | bounded placements + no blanket spam |
| 6 | Mini App launch-source handling + useful return-to-library paths | `bible-bot` | `TODO` | server/UI tests, no trusted client state |
| 7 | Cross-repo UX/performance/accessibility/security audit | all 3 | `TODO` | exact-head evidence + regression matrix |
| 8 | Exact provider rollout plans/previews for permanent surfaces | Telegram/YouTube/VK | `TODO` | reviewed immutable plan(s), still no write unless authorized |
| 9 | Authorized live rollout + postflight + temporary-ledger deletion | selected providers + all repos | `TODO` | verified live postconditions; this file deleted |

---

## 11. Repository lane map

### Lane A — `video-channel-manager`

**Mode:** substantial integration; one focused `agent/...` branch and PR per independently mergeable scope.

Initial foundation branch:

`agent/bible-app-ecosystem-marathon-foundation`

Allowed foundation scope:

- this temporary ledger;
- exact owning issue/PR metadata for the marathon foundation;
- research/source ledger additions inside this file until a durable contract is justified.

Forbidden in foundation commit:

- provider writes;
- legacy writer behavior changes;
- credentials/settings mutation;
- unrelated YouTube/VK/Telegram hardening.

### Lane B — `gb-is-my-strength`

Before mutation:

- re-resolve current `main`/rollback SHA;
- read `AGENTS.md`, `docs/WORK_MODES.md`, relevant `AGENTS-REFERENCE.md` route/UI/SEO/accessibility sections;
- declare exact route/registry/shared-component scope;
- because route registry/migration/shared surfaces may be touched, choose the mode required by current contracts rather than treating the landing page as a trivial file drop.

Expected bounded product work:

- canonical `/app/` Astro route;
- route ownership/profile/search/sitemap/RSS integration as required by current architecture;
- native premium components using existing design system;
- home-card/contextual CTA components only after inventory proves the correct shared surface;
- OG/meta and real product preview assets;
- targeted browser/visual/accessibility/performance checks.

### Lane C — `bible-bot`

Before mutation:

- re-resolve current `main`/rollback SHA;
- inspect current Mini App start-param parsing and server state model;
- preserve `telegram_production.py` as production composition root;
- preserve Mongo/server authority for durable quiz/result state;
- do not expose answer/score/trusted fields to client;
- add attribution only through bounded, source-traceable state/events.

Expected bounded product work:

- deterministic start-param/source parsing contract;
- source/destination mapping tests;
- optional app → library contextual links where UX benefit is proven;
- product-profile/splash assets only if repository/deployment contracts make them code-managed; BotFather-only settings remain provider/UI operations.

---

## 12. Research/source ledger requirements

Wave 1 target: review **at least 35 distinct reliable sources**, biased to primary/official documentation.

Required source groups:

- Telegram Mini Apps / Main Mini App / deep links / menu buttons / inline URL buttons;
- Telegram bot/channel limitations relevant to Web App vs URL buttons;
- YouTube channel links, description/comment/Short link behavior;
- VK community/video/Clip linking/navigation capabilities;
- Google Search page experience / intrusive interstitial / metadata / image/OG guidance;
- Web performance Core Web Vitals;
- WCAG 2.2 target size, focus, keyboard and contrast guidance;
- Astro/static-site practices only where current repository implementation needs an external normative reference;
- current first-party product/platform docs over marketing blogs.

For each source, record:

```text
ID | platform/topic | URL | authority | key rule/constraint | implementation consequence | reviewed date
```

Do not treat a search-result snippet as evidence. Open/read the relevant documentation before adopting a rule.

---

## 13. Verification matrix

### `video-channel-manager`

Repository implementation evidence must include the exact checks required by the files changed. For CTA/provider-adjacent work, expected categories include:

- unit/model/schema validation;
- deterministic renderer/preview tests;
- provider-free dry-run/preview;
- exact identity/binding checks where applicable;
- no weakening of existing Telegram cross-track/state safety;
- exact-current-head CI before merge.

No live mutation test is implied.

### `gb-is-my-strength`

Expected categories, selected per current `WORK_MODES` and touched surfaces:

- route registry/profile consistency;
- Astro type/build checks;
- static publication validation;
- search/sitemap/RSS/SEO contracts when route membership changes;
- targeted desktop/mobile browser checks;
- visual regression for the new premium surface and home/contextual integration;
- accessibility checks: keyboard/focus/target size/contrast/reduced-motion behavior;
- performance budget: no avoidable hero LCP regression, layout shift, or heavy duplicate runtime;
- production witness only after merge/deploy when a live claim is made.

### `bible-bot`

Expected exact-head gates per repository contract:

- Python compile/lint/workflow validation;
- full relevant pytest suite;
- Mini App JS syntax/unit tests;
- security/secret guards;
- Docker production import/smoke where required;
- CodeQL/Security Audit per current PR admission;
- deployment/live Render witness only after merge when production is claimed.

---

## 14. Provider mutation boundary

This marathon separates **repository implementation**, **artifact/preview readiness**, and **live provider rollout**.

Repository work and provider-inert previews may proceed under the user's marathon request.

Before any live mutation to Telegram/YouTube/VK:

1. identify the exact provider target and exact fields/messages to change;
2. re-read current operational state and exact target binding;
3. freeze/review the exact payload;
4. obtain/record the exact execution authority required by the repository contract;
5. persist intent before dispatch where the executor contract requires it;
6. perform zero blind mutation retries;
7. read back and verify the provider-visible postcondition;
8. write the result into durable provider state/evidence, not only this temporary file.

This file never grants standing provider-write authority.

---

## 15. Last verified checkpoint

Update this section after every meaningful recoverable milestone.

**Checkpoint ID:** `M0-foundation-start`

**Verified at:** `2026-08-17 02:03 +03:00`

**Current wave:** `0 — recoverable audit/ledger foundation`

**Current owner branch:** `FedorMilovanov/video-channel-manager:agent/bible-app-ecosystem-marathon-foundation`

**Verified facts:**

- current repository contracts were read before mutation;
- start `main` SHAs for all three repositories were resolved;
- no overlapping branch named for this Bible ecosystem marathon was found in `video-channel-manager` or `gb-is-my-strength` searches;
- the foundation branch was created from exact `video-channel-manager` start `main`;
- no provider mutation has been performed by this marathon.

**Next safe action:**

1. commit this ledger on the foundation branch;
2. open a bounded owning issue/PR for the foundation;
3. execute Wave 1 research/inventory;
4. update this file with the source ledger and refined wave counts before product-code mutation.

**Known blockers:** none at foundation start.

---

## 16. Final deletion gate — this file must disappear

This temporary file may be deleted only when all applicable conditions are proven:

- [ ] all three repository implementation lanes are merged or explicitly dispositioned `N/A` with rationale;
- [ ] final exact-head checks are green for every merged lane;
- [ ] `gospod-bog.ru/app/` and chosen site placements have production witness if production is claimed;
- [ ] Mini App deep-link/source behavior has production witness if production is claimed;
- [ ] permanent Telegram/YouTube/VK surfaces are either verified live or explicitly left as a separately owned future rollout with durable issue/state evidence outside this file;
- [ ] no unresolved `BLOCKED`, `ACTIVE`, or `REVIEW` rows remain in §10;
- [ ] durable architecture/policy that must survive has been moved into normal repository contracts/tests;
- [ ] durable historical evidence has been moved to issues/PRs/audit records where required;
- [ ] temporary branches/fixtures/previews introduced only for the marathon are removed or aligned/closed per repository policy;
- [ ] a final cross-repo postflight confirms there is no blanket CTA spam and no dead deep link;
- [ ] aggregate statistics are copied to the final closure issue/PR comment;
- [ ] **delete `docs/operations/TEMP-bible-app-ecosystem-marathon-2026-08-17.md` itself** in the final cleanup change.

If the only remaining work is a deliberately unauthorized future provider rollout, move that obligation to a durable exact provider issue/state record first; do not keep this temporary ledger forever.
