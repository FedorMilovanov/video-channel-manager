# YouTube top-level comment editorial standard

## Purpose

A top-level channel comment must add something that is not already obvious from the title or description: a documented fact about the text, publication, manuscript, structure, performance, sermon, translation, or adaptation, followed by a precise invitation to respond.

It is not a second description, an advertising dump, a generic engagement prompt, or a place for unsupported claims.

## Project identity

Every record belongs to exactly one project:

- `lord-god-strength` — Господь Бог — Сила Моя;
- `legendary-poet` — The Legendary Poet — Легендарный Поэт.

Canonical records should declare `project_key`. The validator also checks the exact registered YouTube channel ID. A site or VK link from the other project is a blocking error.

See [`operations/project-identity-registry.md`](operations/project-identity-registry.md) for the authoritative identities and link profiles.

## Non-negotiable rules

1. Facts are written only after checking a primary text, authoritative edition, archive, scholarly note, catalogue record, original sermon source, transcript, or another named reliable source.
2. Every publishable record maps the exact factual paragraph to one or more `source_ids`.
3. A fact must be concrete. Prefer dates, first publication, manuscript history, textual variants, cycle structure, documented circumstances, source-sermon context, or the relationship between an adaptation and its original.
4. Do not approve a paragraph that could be pasted under unrelated material by changing only a name and title.
5. Interpretations are explicitly framed as readings or questions, not facts.
6. Do not call poets prophets and do not describe poems as prophecies.
7. Do not claim that an author predicted a revolution, war, death, or political event unless this is a direct sourced quotation whose context supports the statement.
8. Avoid generic phrases such as “great eternal masterpiece”, “incredible journey”, “speaks to all of us”, “more relevant than ever”, or “one of the greatest works”.
9. Avoid false certainty around ambiguous symbols, addressees, religious images, biographical motives, translations, and theological conclusions.
10. Do not use invented quotations, reconstructed speech, unsourced dates, or viral anecdotes.
11. Do not copy one identical comment across unrelated videos.
12. A comment marked `approved` is immutable editorial input. Any later text edit requires a new plan.
13. Never mix links from the two projects.

## Structured schema v2

New records contain separate editorial blocks rather than a hand-built advertising template:

- `project_key` — exact project identity;
- `profile` — content type;
- `variation_key` — a unique editorial variation identifier;
- `fact` — heading, factual paragraph, fact type, and exact evidence sources;
- `question` — optional emphasized lead and one specific question;
- `links` — compact inline links from the selected project profile or named sources.

The bot renders these blocks into the final YouTube comment, validates the layout, rejects duplicated `variation_key` values, and places the exact rendered text into the signed plan.

The bot does **not** decide whether a historical or theological claim is true. Truth is established during source review; the bot verifies that the approved claim is mapped to named evidence and has not changed afterward.

## Deep-fact requirement

An approved fact must belong to one of the supported evidence families, including:

- `composition_history`;
- `first_publication`;
- `manuscript_history`;
- `textual_structure`;
- `archival_provenance`;
- `documented_context`;
- `adaptation_history`;
- `performance_history`.

A publishable fact paragraph normally contains 100–900 characters. Length alone is not depth: it must name a verifiable detail that materially improves the viewer’s understanding.

## Visual style

The style is compact and readable on desktop and mobile.

### Allowed

- one contextual marker in the factual heading;
- `📌` for a registered project site;
- `🎧` for a relevant playlist;
- `📚` for a primary text or source;
- restrained `*bold*` and `_italic_` emphasis;
- one blank line between the fact, the question, and the compact link block;
- no blank lines inside the link block.

### Forbidden

- coloured circle bullets;
- emoji-only lines;
- more than four decorative markers in one comment;
- half a paragraph in bold or italics;
- empty labels followed by a URL on the next line;
- rows of decorative symbols;
- a site, VK, Telegram, Rutube, or playlist route copied from the other project.

## Required compact link layout

Each label and URL stay on the same line.

### Господь Бог — Сила Моя example

```text
📌 *Господь Бог — Сила Моя:* https://gospod-bog.ru/
🎧 *[relevant playlist]:* [exact reviewed playlist URL]
*Сообщество проекта в VK:* https://vk.ru/the_lord_god_is_my_strength
📚 _Источник или полный материал:_ [source-backed URL]
```

### The Legendary Poet example

```text
📌 *The Legendary Poet:* https://thelegendarypoet.ru/
🎧 *Сергей Есенин — плейлист:* https://www.youtube.com/playlist?list=...
*Сообщество проекта в VK:* https://vk.com/thelegendarypoet
📚 _Полный текст:_ [source-backed URL]
```

The poet website remains in the legacy profile for compatibility but must be confirmed operationally before a new mass rollout. Do not substitute the theological website into poet records.

Rules:

- the site label uses `📌` and restrained bold;
- a playlist label uses `🎧` and names the actual author, speaker, series, or category;
- the canonical VK label is `*Сообщество проекта в VK:*`;
- a primary-source label uses `📚` and restrained emphasis;
- use only links relevant to the exact video;
- two or three links are preferred; four are allowed when a primary source genuinely adds value;
- never invent a playlist URL;
- project link kinds must resolve through `record.project_key`.

## Variable composition, not templates

Comments must share standards, not sentences. Variation comes from a different fact family, a work-specific or sermon-specific heading, sentence rhythm, a precise question, and links appropriate to the exact target.

Do not mechanically begin every comment with “Интересный факт”.

## Content profiles

### Full poetry or cycle

Use composition history, first publication, manuscript history, or a demonstrable structural fact. Ask about a specific line, image, transition, refrain, or part of the cycle.

Typical links: registered project route, relevant playlist, VK, and optionally a primary text.

### Sermon, lecture, or theological material

Use a source-backed fact about the original sermon, biblical passage, speaker, series, translation, or publication context. Distinguish the source's statement from the editor's application.

Typical links: exact full material or series playlist, registered theological project route, and VK when useful.

### Historical or literary essay

Use one documented detail and one precise question about the presented material. Add the article or primary source when it improves verification.

### Cover or musical reinterpretation

Name the original accurately and state the documented relationship of the new version to it. Do not imply authorship of the original.

### Foreign-language adaptation

Explain the relationship to the original-language work without claiming that every nuance has a definitive equivalent. Link the original version when available.

### Shorts

Keep the factual note short but still specific. Prefer a link to the exact full version. Do not copy the full-length comment into the Short.

## Stable project links

The authoritative registry is `docs/operations/project-identity-registry.md`.

### `lord-god-strength`

- Site: https://gospod-bog.ru/
- VK: https://vk.ru/the_lord_god_is_my_strength
- VK Video: https://vkvideo.ru/@the_lord_god_is_my_strength
- Telegram: https://t.me/lordchrist
- Rutube: https://rutube.ru/channel/1876662/

### `legendary-poet`

- VK: https://vk.com/thelegendarypoet
- Telegram: https://t.me/thelegendarypoet
- Rutube: https://rutube.ru/channel/74579453/
- Site: `https://thelegendarypoet.ru/` remains a legacy registered value pending a fresh operational check.

## Existing comments

- No channel comment: an approved `create` operation may be planned.
- Identical channel comment: already applied; skip.
- One different channel comment: review it before deciding whether to update.
- Multiple channel comments: never choose automatically.
- Viewer comments only: the channel may still create one approved top-level comment.
- Comments disabled: no workaround or browser automation.

## Review status

Only `status=approved` is publishable.

Suggested non-publishable statuses:

- `needs-research`;
- `draft`;
- `fact-check`;
- `link-check`;
- `rejected`.
