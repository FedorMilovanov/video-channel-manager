# YouTube top-level comment editorial standard

## Purpose

A top-level channel comment must add something that is not already obvious from the title or description: a documented fact about the text, publication, manuscript, structure, performance, sermon, translation, or adaptation, with a self-contained, substantive conclusion. No response invitation or closing question is required.

It is not a second description, an advertising dump, a generic engagement prompt, or a place for unsupported claims. Do not append invented questions, two-choice polls, "what do you think?", "leave a comment", "write Amen", like/subscribe appeals, or other engagement bait. Preserve intentional paragraph breaks and the owner's edits.

Questions belong only where they are the actual subject (a quiz, a documented interpretive dispute) or the owner expressly requests one; never generate a question merely to finish a public comment.

**Маршрутизация Lord God:** перед составлением или редакцией авторских комментариев канала `UCeSJsC6go2c9pdJCuUI1BYA` прочитать [матрицу YouTube-поверхностей](operations/lord-god-youtube-agent-decision-contract.md). Для комментариев **нет** правила двух чистых строк SHARE (оно относится к Description), зато для каждой подписи URL действует `*Подпись:* URL` на **одной строке**; конечный знак выделенной фразы — **до** закрывающего `*` / `_`, если входит в выделяемую фразу. Не переносить пунктуацию без смысловой проверки. Прежде чем создавать новый комментарий, читать текущие авторские top-level comments и pin-state.

## Exact upload identity and pin state for historical interviews

For a manually uploaded full-length conversation, **re-resolve the active YouTube video ID immediately before every metadata or comment action**. The previous video's URL, upload file name, title, description, or cached receipt is not proof that it is still the current provider object. A deleted/absent ID and a newly uploaded same-named video require separate read-only checks of the exact owner channel, file details, duration, visibility, description, and existing author comments. A stale plan must not be silently retargeted; build and approve an exact-ID plan for the replacement.

**Posting and pinning are different effects.** The YouTube Data API can create and verify a top-level channel comment but does not provide a pin operation. Report `COMMENT_POSTED` only after comment readback; report `PINNED_CONFIRMED` only after the owner-side UI shows that exact comment pinned on that exact video. Do not create several author comments to imitate a pin.

Historical and theological comments should add independently sourced particulars (such as a first meeting, an early book endorsement, or a later recollection), each dated to its own source rather than presented as dialogue from the older recording. For a familiar church audience, name the people and substance directly; avoid formulaic introductions and compulsory engagement questions. Media rights, comment approval, publication visibility, and pin authorization remain separate gates.

## Manual pinned comments for The Legendary Poet packages

When the user requests a **manual five-block YouTube package** for `legendary-poet`, the owner's [`youtube-metadata-package-master-v3.1.md`](youtube-metadata-package-master-v3.1.md) governs the **copy-only pinned-comment format** (500–900 characters, bold title line, 1–2 italic lines, a documented interpretive or historical insight and two verified playlist links). The present document still governs **fact accuracy, project identity and source-backed claims**. Its structured v2 schema and provider comment executor are **not** silently changed by the manual v3.1 template. The manual text is a draft, not an approved `create` or `update` action. A full poem in a pin requires the owner's explicit separate request and exact text verification. For the owner's **quote-Shorts exception** (compact Shorts text, first full-edition pin candidate, second independent history comment), use [`youtube-metadata-package-master-v3.1.md` §5a](youtube-metadata-package-master-v3.1.md). A second reply/comment must not be mistaken for a second pin. A pinned label is not proof that the owner comment was pinned; independently verify exact IDs and Studio state after separate approval.

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
- `question` — optional and normally omitted; only a genuine content-driven or expressly requested question, never a default engagement ending;
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

### Дополнение 2026-11-14: осмысленный закреп и единая типографика ссылок

Для The Legendary Poet подписи ссылок **обязательно жирные**: `*Плейлист «Александр Блок»:* https://...`, `*VK:* https://...`, `📌 *The Legendary Poet:* https://...`. Адреса не выделяются; двоеточие входит внутрь звёздочек. Это применимо к закрепу и к дополнительному авторскому комментарию.

Закреп — самостоятельная содержательная миниатюра (обычно 500–1400 символов), а не уменьшенная копия Description. При подготовке двух вариантов каждый должен опираться на **разный проверенный фактический узел** (например, воспоминание современника против места текста в структуре поэтического цикла), а не повторять одну идею другими словами. Не добавлять обязательный вопрос с двумя ответами, шаблонные приглашения подписаться или ненужные эмодзи. Если нужен второй развёрнутый авторский комментарий под одним видео, он остаётся **незакреплённым**: одновременно закрепить два нельзя.

### 2026-11-18 — YouTube-native punctuation regression

YouTube uses `*bold*` and `_italic_` (not Markdown double asterisks). A comma, period or link-label colon that **belongs to the emphasized phrase** goes **before** the closing marker: `*важное слово,*`, `_греческий текст сохранился,_`, `*Источник:*` and `_мысль._`. Reject `*важное слово*,`, `_греческий текст сохранился_,`, `*Источник*:` and `_мысль_.` before a YouTube comment POST or PUT.

The incident was reproduced on two Lord God Q&A №54 owner comments: the malformed `_греческий текст сохранился_,` and `_не оправдывать себя_,` passed the older length/encoding-only comment validator. This is a **preflight rejection**, not an instruction to silently rewrite the punctuation in an arbitrary phrase; preserve exact meaning and review punctuation before submitting new copy. External connectors such as `*Джон МакАртур* — богослов` remain outside the emphasis. Existing public comments are not a reason for unrelated bulk edits.

## Visual style

The style is compact and readable on desktop and mobile.

### Allowed

- one contextual marker in the factual heading;
- `📌` for a registered project site;
- `🎧` for a relevant playlist;
- `📚` for a primary text or source;
- restrained `*bold*` and `_italic_` emphasis;
- one blank line between meaningful paragraphs and the compact link block (and around any genuinely needed question);
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
*Сообщество проекта в VK:* https://vk.ru/thelegendarypoet
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

Comments must share standards, not sentences. Variation comes from a different fact family, a work-specific or sermon-specific heading, sentence rhythm, an independently useful conclusion, and links appropriate to the exact target.

Do not mechanically begin every comment with “Интересный факт”.

## Content profiles

### Full poetry or cycle

Use composition history, first publication, manuscript history, or a demonstrable structural fact. Explain a specific line, image, transition, refrain, or part of the cycle, with attribution where interpretation is contested.

Typical links: registered project route, relevant playlist, VK, and optionally a primary text.

### Sermon, lecture, or theological material

Use a source-backed fact about the original sermon, biblical passage, speaker, series, translation, or publication context. Distinguish the source's statement from the editor's application.

Typical links: exact full material or series playlist, registered theological project route, and VK when useful.

### Historical or literary essay

Use one documented detail and a precise source-backed insight about the presented material. Add the article or primary source when it improves verification.

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

- VK: https://vk.ru/thelegendarypoet
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

## 2026-11-08: приёмка существующего закрепа после редакции

Проверка парных `*...` / `_...` в исходнике не равна проверке их публичного отображения. После утверждённого изменения **того же owner comment** прочитать новый текст, затем проверить публичный owner comment и меню `Unpin`. Не считать слово `Pinned` или наличие комментария доказательством авторства и успешной редакции. При расхождении текста/пиннинга — `not_verified`, без слепого повторного создания, удаления или закрепления. Длинный полный текст стихотворения разрешён лишь при явном запросе владельца, сверке с достоверным изданием и соблюдении ограничений площадки. Для новых пакетов v3.1 сохраняется отдельный краткий формат по умолчанию; старые согласованные полные комментарии автоматически не сокращать.
