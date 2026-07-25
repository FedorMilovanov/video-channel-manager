# YouTube top-level comment editorial standard

## Purpose

A top-level channel comment must add something that is not already obvious from the title or description: a documented fact about the text, publication, manuscript, structure, performance, or adaptation, followed by a precise invitation to respond.

It is not a second description, an advertising dump, a generic engagement prompt, or a place for unsupported literary claims.

## Non-negotiable rules

1. Facts are written only after checking a primary text, authoritative edition, archive, scholarly note, catalogue record, or another named reliable source.
2. Every publishable record maps the exact factual paragraph to one or more `source_ids`.
3. A fact must be concrete. Prefer dates, first publication, manuscript history, textual variants, cycle structure, documented circumstances, or the relationship between an adaptation and its original.
4. Do not approve a paragraph that could be pasted under an unrelated poem by changing only the author and title.
5. Interpretations are explicitly framed as readings or questions, not facts.
6. Do not call poets prophets and do not describe poems as prophecies.
7. Do not claim that an author predicted a revolution, war, death, or political event unless this is a direct sourced quotation whose context supports the statement.
8. Avoid generic phrases such as “great eternal masterpiece”, “incredible journey”, “speaks to all of us”, “more relevant than ever”, or “one of the greatest works”.
9. Avoid false certainty around ambiguous symbols, addressees, religious images, and biographical motives.
10. Do not use invented quotations, reconstructed speech, unsourced dates, or viral anecdotes.
11. Do not copy one identical comment across unrelated videos.
12. A comment marked `approved` is immutable editorial input. Any later text edit requires a new plan.

## Structured schema v2

New records use `schema_version=2` and contain separate editorial blocks rather than a hand-built advertising template:

- `profile` — content type;
- `variation_key` — a unique editorial variation identifier;
- `fact` — heading, factual paragraph, fact type, and exact evidence sources;
- `question` — optional emphasized lead and one specific question;
- `links` — two to four compact inline links.

The bot renders these blocks into the final YouTube comment, validates the layout, rejects duplicated `variation_key` values, and places the exact rendered text into the signed plan.

The bot does **not** decide whether a historical claim is true. Truth is established during source review; the bot verifies that the approved claim is mapped to named evidence and has not changed afterward.

## Deep-fact requirement

An approved v2 fact must belong to one of these families:

- `composition_history` — documented writing date or circumstances;
- `first_publication` — first known publication and edition context;
- `manuscript_history` — drafts, copies, revisions, or textual variants;
- `textual_structure` — cycle, stanza, refrain, syntax, or another demonstrable structural feature;
- `archival_provenance` — archive, autograph, catalogue, or surviving document;
- `documented_context` — a factual historical or literary context directly tied to the work;
- `adaptation_history` — documented relationship between the current adaptation and the original;
- `performance_history` — documented premiere, recording, broadcast, or performance history.

A publishable fact paragraph normally contains 100–900 characters. Length alone is not depth: it must name a verifiable detail that materially improves the viewer’s understanding.

## Visual style

The style is compact, literary, and readable on desktop and mobile.

### Allowed

- one contextual marker in the factual heading, for example `📖`, `❄️`, `⚔️`, `🌊`, `🎭`, `📝`, `🎼`, or `🕯️`;
- `📌` for the project site;
- `🎧` for a playlist;
- `📚` for the primary text;
- restrained `*bold*` and `_italic_` emphasis;
- one blank line between the fact, the question, and the compact link block;
- no blank lines inside the link block.

### Forbidden

- coloured circle bullets such as `🔵`, `🔴`, `🟢`, `🟡`, `🟠`, `🟣`, `⚫`, `⚪`, or `🟤`;
- emoji-only lines;
- more than four decorative markers in one comment;
- half a paragraph in bold or italics;
- empty labels followed by a URL on the next line;
- rows of decorative symbols.

## Required compact link layout

Each label and URL stay on the **same line**. This avoids the orphaned `VK:` label and unnecessary empty vertical space.

Recommended rendering:

```text
📌 *The Legendary Poet:* https://thelegendarypoet.ru/
🎧 *Сергей Есенин — плейлист:* https://www.youtube.com/playlist?list=...
*Сообщество проекта VK:* https://vk.com/thelegendarypoet
📚 _Полный текст:_ https://...
```

Rules:

- the site label uses `📌` and restrained bold;
- a playlist label uses `🎧` and names the actual author, series, or category;
- the VK label is exactly `*Сообщество проекта VK:*`;
- a primary-text label uses `📚` and restrained emphasis;
- use only links relevant to the exact video;
- two or three links are preferred; four are allowed when the primary text genuinely adds value;
- never invent a playlist URL.

## Variable composition, not templates

Comments must share standards, not sentences.

Variation comes from:

- a different fact family;
- a work-specific factual heading;
- a different sentence rhythm;
- a question tied to a precise image, structural turn, textual variant, or documented context;
- a link block appropriate to the specific work.

Do not mechanically begin every comment with “Интересный факт”. Suitable headings include, when accurate:

- `📖 *История публикации*`
- `📝 *След рукописи*`
- `🕯️ *Дата и контекст*`
- `🎼 *Как текст стал песней*`
- `⚔️ *Структура цикла*`
- `❄️ *Первая публикация*`

These are examples, not mandatory templates.

## Recommended full-length shape

```text
[contextual marker] *[work-specific factual heading]*

[one substantial, sourced factual paragraph]

_[short lead if useful]:_ [one specific question]?

📌 *The Legendary Poet:* https://thelegendarypoet.ru/
🎧 *[relevant playlist label]:* [playlist URL]
*Сообщество проекта VK:* https://vk.com/thelegendarypoet
[optional primary-text line]
```

## Content profiles

### Full poetry or cycle

Use composition history, first publication, manuscript history, or a demonstrable structural fact. Ask about a specific line, image, transition, refrain, or part of the cycle.

Required link kinds: site, relevant playlist, VK. A primary-text link is optional.

### Historical or literary essay

Use one documented historical detail and one precise question about the presented material. Add the article or primary source when it improves verification.

Required link kinds: site and VK. A primary-text or article link is usually appropriate.

### Cover or musical reinterpretation

Name the original accurately and state the documented relationship of the new version to it. Do not imply authorship of the original.

Required link kinds: site, relevant playlist, VK. The original work link is optional.

### Foreign-language adaptation

Explain the relationship to the original-language work without claiming that every nuance has a definitive equivalent. Link the original version when available.

Required link kinds: site, relevant playlist, VK.

### Shorts

Keep the factual note short but still specific. Prefer a link to the exact full version. Do not copy the full-length comment into the Short.

Required link kinds: site, VK, and full version.

## Stable project links

- Site: https://thelegendarypoet.ru/
- VK: https://vk.com/thelegendarypoet
- Telegram: https://t.me/thelegendarypoet
- RUTUBE: https://rutube.ru/channel/74579453/

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

- `needs-research`
- `draft`
- `fact-check`
- `link-check`
- `rejected`
