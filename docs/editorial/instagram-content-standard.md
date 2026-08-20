# Instagram Content Standard

Status: provider-inert editorial policy  
Owner issue: #492  
Last researched: 2026-08-20

## Purpose

Instagram is a discovery and retention surface for the existing `legendary-poet` and
`lord-god-strength` projects. It is not a place to copy YouTube/VK descriptions
verbatim and it is not an excuse to weaken the repository's evidence boundary.

The Instagram layer owns presentation: a concise topic line, mobile-readable caption,
relevant discovery terms, restrained hashtags, one clear CTA, media suitability and
AI-media disclosure. It never invents a fact, quotation, date, biographical detail,
theological conclusion or literary interpretation.

This document is content policy only. It authorizes no Meta/Instagram provider write.
Public handles supplied by the owner are discovery hints until exact Professional
account IDs are proved and bound to project keys in a separate provider-facing scope.

## Current Meta facts that constrain the policy

The following are source facts, not growth folklore:

1. Instagram recommendations can surface eligible public-account content in Reels,
   Explore, Feed recommendations, Search and Suggested Accounts. Professional accounts
   can inspect recommendation eligibility in Account Status. Eligibility is not a
   promise of distribution.
2. Suggested-post systems use signals that include a viewer's activity and connections,
   information about the post and recent interactions with the account. We therefore
   optimize for useful, specific content rather than a guessed hashtag formula.
3. Meta has explicitly increased the share of original content in Instagram
   recommendations; its creator guidance also distinguishes original work from
   low-value reposting. Our Instagram masters should therefore be project-owned exports,
   not downloads with another platform's watermark.
4. The official Instagram API supports publishing for Professional Business/Creator
   accounts. Current official Reels publishing guidance recommends 9:16 and accepts
   MOV/MP4, H.264 or HEVC video, AAC 48 kHz audio, 23–60 fps, up to 1 GB and 3 seconds
   to 15 minutes. Exact API eligibility must be re-read immediately before executor
   implementation because provider contracts can change.
5. Meta requires disclosure when organic content contains photorealistic video or
   realistic-sounding audio that was digitally created or altered. The Legendary Poet
   musical masters created with generative music technology therefore carry an
   explicit AI-audio disclosure requirement in our editorial record; the disclosure
   describes the *musical interpretation*, never the canonical poem as AI-generated.

### Official research ledger

- Recommendation eligibility:
  https://www.facebook.com/help/instagram/653964212890722
- Suggested-post signals:
  https://www.facebook.com/help/381638392275939/
- Instagram creator Best Practices announcement:
  https://about.fb.com/news/2024/10/best-practices-for-creators-to-optimize-their-content-on-instagram/
- Meta 2026 original-content update:
  https://about.fb.com/news/2026/01/2026-ai-drives-performance/
- Instagram API / Reels publishing (official Meta Postman workspace):
  https://www.postman.com/meta/instagram/collection/6yqw8pt/instagram-api
- AI-generated/altered media labeling policy:
  https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/

Do not encode undocumented claims such as “N hashtags is optimal”, “post exactly N
minutes apart”, “the first 30 minutes decide the Reel”, or “daily posting is required”.
Those may be experiments later, never policy facts.

## Shared Instagram editorial contract

### 1. One post, one discoverable subject

The first caption line must name the actual subject in natural language. Examples:

- `Сергей Есенин — «Я усталым таким ещё не был». Музыкальная интерпретация.`
- `Что Библия называет сердцем?`
- `1 Петра 4:5–6: кому было благовествовано?`

Do not start with generic hooks such as `Вы не поверите`, `Это изменит вашу жизнь`,
`Шокирующая правда` or decorative emoji blocks.

### 2. Search terms are prose, not stuffing

Put author/work, biblical passage, historical person/event or theological topic in the
natural caption where it belongs. Hashtags are a secondary classification aid, not the
caption's semantic core.

Internal default: 3–6 tightly relevant hashtags. This is a house readability rule, not
an algorithm claim. More requires an editorial reason. Reject repeated keyword lists,
unrelated trending tags and duplicate tags that add no new classification value.

### 3. Mobile caption shape

Default Reel caption:

1. exact topic line;
2. one compact explanatory paragraph;
3. optional provenance/disclosure line;
4. one CTA at most;
5. restrained hashtags.

Paragraphs should be short enough to scan on a phone. A long source article is linked
or adapted into a carousel; it is not pasted into the Reel caption.

### 4. CTA policy

One post gets at most one primary intent:

- `Слушать полную версию — ссылка в профиле.`
- `Полный разбор — на сайте по ссылке в профиле.`
- `Сохраните, если хотите вернуться к разбору.` only when saving genuinely helps.

Do not use coercive engagement bait. In particular, `lord-god-strength` must not use
`напиши «Аминь»`, `поставь лайк, если веришь`, spiritual threats, promised blessings for
engagement, manufactured urgency, or claims that an interaction demonstrates faith.

### 5. Originality and cross-platform reuse

Cross-platform reuse is allowed when the project owns the underlying media, but the
Instagram export must be a clean master:

- no TikTok/YouTube/VK watermark;
- no captured player controls;
- no foreign channel branding;
- no low-value border/speed-change-only “transformation” of another creator's media.

If the same project publishes the same master elsewhere first, retain source ownership
and exact media provenance. Do not download the social-platform copy and re-upload it.

### 6. Recommendation-risk check

Before approval, record:

- public/professional recommendation eligibility checked by the owner or a read-only
  provider preflight when that capability exists;
- no known Recommendation Guidelines blocker in the copy or media;
- no deceptive headline relative to the source;
- no purchased/fake engagement plan;
- no cross-project identity leakage.

A green eligibility state never proves the post will receive recommendations.

## The Legendary Poet policy

Source authority is the current The Legendary Poet project charter and exact edition
records. The canonical literary text and the musical/visual interpretation are separate
objects.

### Required wording boundary

- Quote only exact text from a bound canonical edition.
- Do not modernize, paraphrase or “improve” a quoted poem line for a hook.
- If an exact edition is not bound in the Instagram candidate, use the work title and
  author only; do not improvise the quote from memory.
- Describe generated music as `музыкальная интерпретация`, not as the poet “singing”.
- Do not imply that Pushkin, Yesenin, Blok or another historical author performed,
  approved or heard the generated track.

### AI-audio disclosure

For a Reel using a current music master whose source credits say it was created with
`генеративных музыкальных технологий`:

- `ai_audio_disclosure_required = true`;
- the publishing checklist must require Meta's available AI disclosure control when the
  audio is realistic-sounding synthetic audio;
- the caption may use the restrained provenance line
  `Музыкальная интерпретация создана с использованием генеративных музыкальных технологий.`
- the canonical poem itself must never be labeled as AI-written.

### Launch mix

The initial grid should establish three things before chasing volume:

1. real canonical poetry is the source;
2. music/visuals are modern interpretations;
3. the project has repeatable depth beyond a single viral clip.

Use a mixture of music Reels, source/interpretation carousels and one project-manifesto
piece. Do not publish nine near-identical waveform clips.

## Господь Бог — Сила Моя policy

Source authority is the current `gb-is-my-strength` published content and its source
apparatus. An article whose current source explicitly says `contentStatus: draft` is
not eligible for a launch candidate even if its frontmatter also contains `draft: false`.

### Theology and Scripture

- Name the biblical passage or subject exactly.
- Distinguish `текст говорит`, `грамматика позволяет`, `наиболее вероятное чтение`,
  `мы считаем` and `текст не сообщает` instead of flattening degrees of certainty.
- Quote Scripture only from the edition/source actually bound to the candidate.
- Never turn a disputed interpretation into `Библия однозначно доказала...`.
- Preserve source caveats when the article itself says a conclusion is probable rather
  than mathematically exclusive.

### Tone

Use calm, precise Russian. The account is not a fear/prophecy clickbait feed.
Reject:

- `скрытая тайна, которую от вас прятали`;
- `все богословы ошибаются`;
- end-times date predictions;
- invented revelations/dreams;
- engagement-as-faith tests;
- attacks on a person where the source discusses an argument or historical claim.

Strong hooks are still allowed when they are exact questions from the source, e.g.
`Кому было благовествовано в 1 Петра 4:6?`.

## Surface policy

### Reel

Primary discovery surface. Prefer one coherent claim or one musical/emotional movement
per Reel. The content pack may reference a longer source, but the Reel must make sense
without requiring the viewer to read a hidden essay first.

Provider-inert media QC target:

- portrait 9:16 master preferred;
- project-owned clean export;
- spoken/on-screen text remains readable without relying on the caption;
- subtitles/captions for spoken material where practical;
- no text or important face detail pushed against unsafe screen edges;
- exact API codec/duration/file-size checks belong in the future executor, not in copy.

### Carousel

Use for distinctions, source maps, timelines and `what the text says / does not say`
material that would become rushed or sensational in a short Reel. Every slide claim
must remain source-backed.

### Static feed post

Use selectively for durable artwork, exact quotations and release covers. Do not fill
an account with quote cards merely to make a 3x3 grid look complete.

## Candidate lifecycle

`candidate` → content is source-bound but not approved.  
`reviewed` → human has reviewed exact copy/media intent; still provider-inert.  
`approved-for-plan` → may enter a future exact-ID Instagram plan.  
`published-verified` → only after a separate provider executor returns and re-reads the
exact remote media ID.

No file in `content/instagram/` created under issue #492 is live-publication
authorization.

## Measurement contract

Do not optimize on likes alone. The future analytics layer should retain only metrics
actually exposed by the current official API and label unavailable metrics as unknown,
not zero.

Decision groups:

- discovery: reach / non-follower reach where exposed;
- consumption: plays/views and watch metrics where exposed;
- value: saves and shares;
- conversation: comments/replies;
- conversion: profile actions, follows and link actions where exposed;
- content identity: exact project, candidate ID, published media ID, publish timestamp,
  creative/version hash.

Compare formats inside the same project. Do not compare a theology carousel directly to
a poetry music Reel and call one “better” from raw views alone.
