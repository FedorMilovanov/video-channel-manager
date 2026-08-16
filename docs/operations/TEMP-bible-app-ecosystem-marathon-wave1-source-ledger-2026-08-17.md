# TEMP — Bible App Ecosystem Marathon · Wave 1 Source & Surface Ledger

> **TEMPORARY ANNEX — DELETE TOGETHER WITH THE MARATHON LEDGER AT FINAL CLOSURE.**
>
> Owning issue: `#422`  
> Owning foundation PR: `#423`  
> Primary recovery ledger: `docs/operations/TEMP-bible-app-ecosystem-marathon-2026-08-17.md`
>
> Purpose: preserve the exact external-source review and current-code inventory used to make implementation decisions. This file is not a provider-write authorization and must not survive the final marathon cleanup.

## 1. Wave 1 checkpoint

Status: **RESEARCH MINIMUM MET; IMPLEMENTATION INVENTORY ACTIVE**.

### Current statistics

| Metric | Value |
|---|---:|
| Official/primary documentation pages opened and reviewed | 37 |
| Minimum required by marathon | 35 |
| Telegram primary docs reviewed | 16 |
| YouTube Help pages successfully opened in this batch | 1 |
| Google Search Central pages reviewed | 5 |
| web.dev performance pages reviewed | 7 |
| W3C/WAI pages reviewed | 4 |
| Astro current docs reviewed | 3 |
| Internal repositories inventoried | 3 / 3 |
| Provider writes performed | 0 |

Additional first-party/near-first-party VK research was found, but the public landing page is poorly parseable by the reader used here. VK implementation decisions must therefore continue to be grounded primarily in the repository's existing VK provider semantics plus live/manual provider review before rollout; do not promote a search snippet to normative API truth.

## 2. External source ledger

All rows below were opened/read, not merely copied from a search-result title. `Implication` is a project decision derived from the source, not a verbatim quote.

### Telegram — primary documentation

| ID | Source | Authority | Key rule / constraint | Implementation consequence |
|---|---|---|---|---|
| TG-01 | `https://core.telegram.org/bots/webapps` | Telegram official | Main Mini App can expose a prominent profile launch action; direct `?startapp=` passes a start parameter; menu button is a supported launch path; mobile-first/accessibility/safe-area guidance applies | Keep Main Mini App + menu as permanent entry points; deep links are canonical; app UI must remain mobile-first |
| TG-02 | `https://core.telegram.org/api/bots/webapps` | Telegram official | Native Telegram client model for Mini Apps and launch contexts | Do not invent unsupported launch semantics |
| TG-03 | `https://core.telegram.org/api/links` | Telegram official | `t.me` deep links are the supported public routing layer, including Mini App launch parameters/modes | Build stable human-auditable launch URLs rather than provider-specific hacks |
| TG-04 | `https://core.telegram.org/api/bots/menu` | Telegram official | Bot menu button is a first-class Mini App launcher | Existing menu entry is a durable high-value entry surface |
| TG-05 | `https://core.telegram.org/bots/api` | Telegram official | `web_app` inline button semantics differ by chat context; URL buttons are broadly supported | Channel posts should use reviewed URL links/buttons to the Main Mini App, not a private-chat-only Web App button assumption |
| TG-06 | `https://core.telegram.org/api/bots` | Telegram official | Bot API/MTProto bot capability boundary | Keep provider implementation within supported bot surfaces |
| TG-07 | `https://core.telegram.org/bots/features` | Telegram official | Current bot feature set and profile/product surfaces | Treat bot profile as product surface, not only command shell |
| TG-08 | `https://core.telegram.org/bots/faq` | Telegram official | General bot constraints and operational expectations | Avoid UX assumptions not supported across clients |
| TG-09 | `https://core.telegram.org/bots/tutorial` | Telegram official | BotFather/configuration flow is official management path | BotFather-only settings are provider configuration, not source-code state |
| TG-10 | `https://core.telegram.org/api/bots/attach` | Telegram official | Attachment-menu launch is a distinct optional surface | Do not expand scope to attachment menu without a separate product reason |
| TG-11 | `https://core.telegram.org/method/messages.requestAppWebView` | Telegram official | Direct Mini App deep link carries `start_param`; compact/fullscreen are explicit modes | Preserve start-param routing and test mode-independent behavior |
| TG-12 | `https://core.telegram.org/method/messages.requestMainWebView` | Telegram official | Main Mini App request supports `start_param` and fullscreen/compact flags | Main app routing contract can safely depend on Telegram start param |
| TG-13 | `https://core.telegram.org/method/bots.addPreviewMedia` | Telegram official | Main Mini App owners can add preview media | Profile screenshots/video are a high-value future permanent product surface |
| TG-14 | `https://core.telegram.org/method/bots.getPreviewMedias` | Telegram official | Preview media can be enumerated/read | Rollout can verify current preview state before mutation |
| TG-15 | `https://core.telegram.org/type/BotPreviewMedia` | Telegram official | Preview media is a defined Telegram object | Treat previews as provider state with exact verification, not chat memory |
| TG-16 | `https://core.telegram.org/constructor/keyboardButtonUrl` | Telegram official | URL button is a native Telegram keyboard primitive | URL-based navigation remains a safe fallback/appropriate channel CTA surface |

### YouTube — official help successfully opened

| ID | Source | Authority | Key rule / constraint | Implementation consequence |
|---|---|---|---|---|
| YT-01 | `https://support.google.com/youtube/answer/6388789?hl=en-GB` | YouTube Help | End screens should be relevant; external website element depends on YouTube Partner Programme; metrics exist | Do not make end screens a baseline requirement for the trainer; prefer profile/description surfaces unless current channel eligibility and relevance are proven |

Notes from a separate YouTube Help search result were not counted toward the 37-page opened minimum because repeated direct opens hit provider rate limits. Before final YouTube rollout, re-open current YouTube Help pages for channel profile links, clickable long-form URLs, Shorts link behavior and related-video behavior; do not rely on this annex as permanent platform truth.

### Google Search Central — official

| ID | Source | Authority | Key rule / constraint | Implementation consequence |
|---|---|---|---|---|
| GSC-01 | `https://developers.google.com/search/docs/appearance/avoid-intrusive-interstitials` | Google Search Central | Promotional/app-install interstitials should not obstruct primary content; small non-intrusive banners are preferable | No full-page app takeover on articles; contextual CTA belongs after/around content, not over it |
| GSC-02 | `https://developers.google.com/search/docs/appearance/snippet` | Google Search Central | Useful page-specific meta descriptions improve snippet quality | `/app/` needs unique product-specific description, not copied home metadata |
| GSC-03 | `https://developers.google.com/search/docs/appearance/title-link` | Google Search Central | Descriptive concise titles/headings and metadata influence title-link generation | `/app/` must have one clear product title and aligned heading/meta semantics |
| GSC-04 | `https://developers.google.com/search/docs/appearance/google-images` | Google Search Central | Relevant representative quality imagery and image metadata matter | Use real trainer/product preview and intentional OG image, not generic Telegram logo art |
| GSC-05 | `https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls` | Google Search Central | Duplicate public URLs should consolidate to a canonical URL | Prefer one canonical `/app/`; do not create separately indexable duplicate `/quiz/` landing content |

### Performance — web.dev / Chrome team

| ID | Source | Authority | Key rule / constraint | Implementation consequence |
|---|---|---|---|---|
| PERF-01 | `https://web.dev/articles/vitals` | web.dev / Chrome | Core Web Vitals: LCP, INP, CLS; recommended good thresholds are LCP ≤2.5s, INP ≤200ms, CLS ≤0.1 at the 75th percentile | New landing page/CTA must not buy visual polish with avoidable LCP/INP/CLS regression |
| PERF-02 | `https://web.dev/articles/lcp` | web.dev / Chrome | LCP is the principal loading metric | Hero preview asset must be sized/loaded intentionally |
| PERF-03 | `https://web.dev/articles/inp` | web.dev / Chrome | INP measures interaction responsiveness | Avoid large duplicated client runtime just for CTA/preview effects |
| PERF-04 | `https://web.dev/articles/cls` | web.dev / Chrome | CLS measures unexpected layout movement | Reserve media dimensions and avoid late expanding promo UI |
| PERF-05 | `https://web.dev/articles/optimize-cls` | web.dev / Chrome | Preventable layout shifts should be designed out | Product-preview and QR containers need stable dimensions |
| PERF-06 | `https://web.dev/articles/optimize-inp` | web.dev / Chrome | Long main-thread work harms responsiveness | Keep landing interaction simple/static-first |
| PERF-07 | `https://web.dev/articles/defining-core-web-vitals-thresholds` | web.dev / Chrome | Threshold methodology targets broad user experience, not one lab trace | Use both repo regression evidence and production/field evidence where available |

### Accessibility — W3C/WAI

| ID | Source | Authority | Key rule / constraint | Implementation consequence |
|---|---|---|---|---|
| A11Y-01 | `https://www.w3.org/TR/WCAG22/` | W3C Recommendation | WCAG 2.2 includes focus-not-obscured and target-size minimum criteria | App CTA/navigation must be keyboard/touch auditable |
| A11Y-02 | `https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html` | W3C/WAI | AA target-size minimum is 24×24 CSS px with defined exceptions; larger controls are preferred for important actions | Primary app CTA should comfortably exceed the bare minimum |
| A11Y-03 | `https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum` | W3C/WAI | Focused controls must not be entirely hidden by author-created overlays/sticky UI | Test CTA keyboard traversal with current site chrome/sticky controls |
| A11Y-04 | `https://www.w3.org/WAI/WCAG22/Understanding/focus-visible` | W3C/WAI | Keyboard-operable UI requires a visible focus indicator | Do not remove focus outline for premium appearance |
| A11Y-05 | `https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum` | W3C/WAI | AA text contrast is 4.5:1 for normal text, 3:1 for large text | Gold/muted copy must be contrast-checked against both light/dark site surfaces |

`A11Y-05` was opened after the 37-page checkpoint; total successful source opens is therefore now **38**. Keep the aggregate as `≥38`, not a brittle fixed claim if more sources are added.

### Astro — current official docs

| ID | Source | Authority | Key rule / constraint | Implementation consequence |
|---|---|---|---|---|
| ASTRO-01 | `https://docs.astro.build/en/reference/configuration-reference/` | Astro official | Current configuration/static output/site URL behavior is documented centrally | Follow repository's existing Astro/static publication contract rather than legacy root HTML |
| ASTRO-02 | `https://docs.astro.build/en/basics/astro-pages/` | Astro official | File-based Astro page routing is native | `/app/` should be a native current route, registered through repository route governance |
| ASTRO-03 | `https://docs.astro.build/en/guides/view-transitions/` | Astro official | View transitions have accessibility/reduced-motion implications | Do not add decorative route animation without honoring current reduced-motion/a11y behavior |

### VK research disposition

Useful current first-party/near-first-party evidence found:

- `https://vk-video.production.vklanding.ru/` — search/indexed content describes creator editing and Clip↔full-video linking; the direct reader exposes almost no textual body.
- `https://vk.company.ru/ru/press/releases/12148/` — VK corporate press release on updated creator analytics/tools.
- `https://vk.company.ru/ru/press/releases/12296/` — VK corporate press release on mobile creator cabinet and traffic-source analytics.
- official VK Video/Clips Telegram channels also describe Clip↔full-video linking, but these are communication posts, not API contracts.

Disposition: do **not** build a new provider mutation solely from these pages. For Wave 3/8, use the repository's current VK provider contracts/runbooks as execution truth and fresh live/manual provider review for exact UI-only settings.

## 3. Current-code inventory

### 3.1 `bible-bot`

Current Mini App client:

- calls `Telegram.WebApp.ready()` and `expand()` at startup;
- sends Telegram `initData` to server in `X-Telegram-Init-Data`;
- treats server as authority for quiz/session state;
- restores durable active quiz before processing a fresh deep link;
- reads launch routing from `tgWebAppStartParam` or fallback `start` query parameter;
- resolves that one string directly as a course key, then tries `level_<param>` fallback;
- when a course resolves, opens its mode picker;
- currently has no explicit source-attribution dimension in that launch contract.

Current canonical course inventory includes:

- chapter groups 1–5 plus context;
- Mini App-visible Chapter 1 subcourses;
- `level_intro1`, `level_intro2`, `level_intro3`;
- `level_nero`;
- `level_geography`;
- `chapter2`, `chapter3`, `chapter4`, `chapter5`, subject to server-side availability policy.

**Wave 2 design consequence:** a raw source token such as `site_app` cannot simply replace the start param if we also need direct course routing. Define one deterministic, versioned `source + destination` grammar with a safe legacy fallback. Preserve existing links such as `?startapp=chapter2`.

Candidate grammar for design review, NOT YET CANONICAL:

```text
v1_<source>__<destination>
```

Examples:

```text
v1_site_app__home
v1_site_ch2__chapter2
v1_tg_pin__home
v1_tg_ch2__chapter2
v1_yt_ch2__chapter2
v1_vk_ch2__chapter2
```

Before adoption verify Telegram's current allowed `startapp` character/length contract and add parser tests. Do not store arbitrary unvalidated external strings.

### 3.2 `gb-is-my-strength`

Current production architecture:

- Astro 7/static production-like `dist/` is the current publication path;
- new public routes must go through `migration/page-ownership.json` + `data/route-profiles/*.json` and derived route matrix/policies;
- current `WORK_MODES.md` classifies migration/shared/global surfaces as SYSTEM and route-local feature work as LANE where boundaries allow;
- home route is native `src/pages/index.astro` and delegates to leaf components;
- home `HomeMain.astro` owns a refined light/dark editorial palette with graphite/ivory/gold plus restrained cyan accent, responsive section rhythm, focus states and native Astro component composition;
- `HomeMain` is already decomposed into leaf sections (`Directions`, `Publications`, `About`, etc.), so a home app entry should be a bounded leaf integration rather than a new parallel home tree;
- repository policy forbids casually adding a new shared CSS/JS runtime; route-local/native component styling is preferable unless a separately declared SYSTEM change is justified.

**Wave 4 consequence:** `/app/` should be native Astro, static-first, route-governed, use current design language, real product preview and no generic Telegram-blue SaaS template.

**Wave 5 consequence:** home integration should be one intentional card/entry in the existing navigation/content composition, not a global banner. Contextual article CTA should be introduced only after the exact article/quiz completion owner is located and mapped.

### 3.3 `video-channel-manager`

Current architecture already contains the exact anti-spam principle needed for this marathon:

- Unified Editorial Standard says one canonical record should render per platform;
- links are semantic/relevant and **must not become a fixed spam footer**;
- platform suitability is an allow-list;
- approved project URLs are checked against a project link profile;
- `lord-god-strength` is already a registered project identity for YouTube/VK and has an approved project-link map;
- current `ALLOWED_LINK_KINDS` contains `site`, `playlist`, `vk`, `vk_album`, `primary_text`, `original_work`, `full_version`, `article` — no Bible-trainer kind yet;
- `LinkBlock` already supports per-platform and per-surface suitability;
- current project link profile for `lord-god-strength` includes the site, `@lordchrist`, VK/VK Video and other project destinations, but not yet `https://t.me/milovanovaibot?...`;
- generic `@lordchrist` Telegram profile remains `provider_writes_authorized=false`;
- current operational state explicitly warns not to mutate the legacy live Lordchrist path merely to activate another content class.

**Wave 2/3 consequence:** prefer an additive canonical link kind/profile policy and provider-inert rendering/preview path. Do not bolt the trainer URL into the legacy quote renderer or append it globally.

Potential minimal domain direction for review:

- add a semantic link kind such as `bible_trainer`;
- approve only canonical bounded trainer URLs for `lord-god-strength`;
- use existing `platforms`/`surfaces` suitability to make contextual inclusion explicit;
- if CTA intensity/copy variant needs stronger semantics than links alone, add a small additive policy object with default `none` rather than overloading every existing record;
- retain provider execution in existing guarded platform executors.

## 4. Main-drift observation

At marathon start the VCM main SHA was recorded as:

`48fb0e8faf1bb0cce3932019fbaf473208d4765b`

Before the foundation PR was opened, current `main` advanced to:

`f16cf4161a9e7c9a25f00bb3f813539d7d7ec110`

The new main is a merge of PR `#419` (`agent/milovi-ledger-init-handoff`) and has the original start SHA as one parent.

Disposition:

- this is a real concurrent-state change and is recorded, not hidden;
- the foundation PR remains docs/provider-inert;
- before merge/rebase, compare the foundation branch against fresh current `main` and rerun applicable docs/shared-file checks;
- before any VCM product-code Wave 2/3 branch is created, branch from the then-fresh `main`, not from the foundation branch's old base.

## 5. Wave 1 decisions now considered stable enough to implement

1. Canonical public site product route: **`/app/`** unless a current route collision is discovered in preflight.
2. `/quiz/` should not become a second indexable duplicate landing page. Redirect only if a real compatibility need appears.
3. Strong app promotion belongs on permanent product/navigation surfaces, not ordinary content.
4. Contextual app CTA defaults off and must require a content→destination mapping.
5. Telegram channel CTA uses a supported URL deep link to Main Mini App; do not assume a private-chat `web_app` button works as a channel primitive.
6. Existing legacy deep links (`chapter2`, `level_nero`, etc.) must remain valid.
7. Attribution must not steal the only destination token; Wave 2 defines a versioned composite grammar or equivalent server-authoritative mapping.
8. No third-party analytics is added solely for this marathon.
9. VCM canonical editorial/link policy is the right cross-platform policy layer; legacy Lordchrist live quote writer is not.
10. `/app/` visual direction follows current `gospod-bog.ru` editorial system and uses real app UI.

## 6. Wave transition

Wave 0: **REVIEW** — foundation ledger + Issue #422 + draft PR #423 exist; exact-current-main reconciliation/checks still required before merge.

Wave 1: **REVIEW** — external minimum exceeded and all three repo surfaces inventoried; remaining task is targeted provider/help refresh for YouTube/VK before any live rollout, not a blocker for provider-inert domain implementation.

Wave 2 may begin on fresh current-main branches only after:

- current `bible-bot/main` is re-resolved;
- current `video-channel-manager/main` is re-resolved;
- overlapping PRs are checked for the exact files selected;
- the deep-link grammar is validated against Telegram's documented start-param character/length constraints;
- exact tests to preserve legacy deep links are declared.

No live provider mutation is authorized by this transition.

## 7. Final cleanup obligation

Delete this annex together with:

`docs/operations/TEMP-bible-app-ecosystem-marathon-2026-08-17.md`

at final marathon closure, after durable architecture/tests and closure evidence have been transferred out of temporary files.