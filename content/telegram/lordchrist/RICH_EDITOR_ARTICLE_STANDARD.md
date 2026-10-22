# @lordchrist rich-editor article standard (lane L2)

Status: canonical presentation contract for **long articles** published manually through the Telegram rich editor **«Статья»** (up to 32 768 characters). It complements `RICH_EDITORIAL_STANDARD.md` and does not replace the short quote lane.

Read after `RICH_EDITORIAL_STANDARD.md` and `QUOTE_ATTRIBUTION_STANDARD.md`. Precedence is defined in `AGENTS.md`.

## 1. Three publication lanes

| | L1 — сообщение | L2 — «Статья» | L3 — bot rich message |
|---|---|---|---|
| Limit | 1–4096 chars after entities parsing | 32 768 UTF-8 chars, 500 blocks, 16 nesting levels, 50 media, 20 table columns | same as L2 |
| Transport | Telegram composer, long-press → system Paste | 📎 → «Статья» → paste Markdown or rich HTML | `sendRichMessage` with `blocks` / `html` / `markdown` |
| Paragraph air | invisible `U+2060` spacer line between paragraphs | real blocks; **no invisible spacers at all** | block structure |
| Section markers | bold line with emoji (`🏛 Жан Кальвин`) | real heading `##` | `heading` block |
| Quotes | blockquote entity + italic attribution below | `>` blockquote + plain attribution line | `blockquote` block with `credit` |
| Hashtags | 4–6 tags, two blank lines above | **none** — a long article needs no hashtag footer | footer block |

Never mix the transports. `U+2060` in an L2 article is a defect: the editor already creates paragraph gaps, and an extra invisible line becomes a stray empty block. Conversely, L2 headings or Markdown lists pasted into the ordinary composer show up as literal `#` and `**`.

## 2. Length preflight

Count the exact reader-facing text:

- every visible character, including hashtags and table labels;
- every line break;
- no invisible spacers (there must be none).

Limits for L2: **≤ 32 768 UTF-8 characters**, **≤ 500 blocks**, **≤ 16 levels** of nesting, **≤ 50 media**, **≤ 20 table columns**. Keep a soft target of **≤ 32 300 characters**: that leaves roughly 470 characters of room, so any late edit still has to be paid for by a cut somewhere else. The closing bibliographic note (§5) takes about 700 characters of this budget and is counted by the preflight.

Block estimate: paragraphs + headings + list items + quote blocks (+ attribution paragraphs) + table rows. A typical 25 000–27 000-character article uses 110–140 blocks — well inside the limit.

If a reviewed article is over the limit: remove repetition and weak wording first (`RICH_EDITORIAL_STANDARD.md` §3), never exegesis or evidence. Only if it still does not fit, split at section boundaries into two L2 articles; do not degrade the prose into slogans. There is no hashtag footer to drop in L2 — the budget is spent on text only.

The 4096 limit and the `U+2060` rules in `DIRECT_COPY_TO_TELEGRAM.md` apply to **L1 only**. `telegram_research.py::validate_public_copy` (≤4096, plain text, no Markdown) is the bot plain-text lane and does not accept L2 Markdown.

## 3. Structure and headings

- **H1 — title.** Exactly one, first block, ALL CAPS, one line, ≤ 120 characters, plain (no `**`): `# ЖАЛКИЕ УТЕШИТЕЛИ: 10 СОВЕТОВ…`. The heading itself already renders large; wrapping it in bold only adds `**` to the pasted source.
- **H2 — sections.** Normal case, bold by heading rendering, ≤ 80 characters, no ALL CAPS, no clickbait. A single leading emoji marker is permitted only under the marker rule below.
- H3 only when a section genuinely has two levels; more than two heading levels is a defect.
- One H2 per **1 500–4 000 characters** of body. A 25 000+ character article normally has 10–16 sections.
- A heading never ends a message or a part; two headings never stand in a row.
- **Emoji marker rule.** In L2 an emoji is a normal part of the layout, not an exception: one marker leading an H2 line. Use it by default where a section is made of full paragraphs. Two cases take no marker: (1) a section inside a numbered ladder (`## 1. …`, `## 2. …`, `## 3. …`) — the number already marks position, and a pictogram next to it is noise; (2) a short rubric — a section under ~600 characters, meaning one or two sentences, a single item, or a brief insert — where the marker only distracts. No emoji in the H1 and no emoji in body paragraphs in any case; never more than one emoji per heading, always the first character of the line. The 600-character threshold is evaluated per section, not as an average over the article.
- **No bold and no italic in the body.** Neither `**…**` nor `*…*` appears in an L2 article: not for key phrases, not for Latin terms, not for the attribution line, not for sections of the argument. Emphasis is carried by word order and by a sentence of its own. Bold survives only as heading rendering, which the editor applies to `#` / `##` by itself.

## 4. Spacing

L2 has two representations, and they control spacing differently.

**L2-MD — Markdown source (what the agent writes).** Telegram's rich editor builds paragraph and heading blocks itself. A blank line in Markdown is a block separator, not an empty paragraph; an empty paragraph cannot be expressed in Markdown at all. Therefore the Markdown source never simulates air: it uses exactly one blank line between blocks, and the editor supplies the normal paragraph and heading gaps. No invisible characters are allowed in the source.

**L2-HTML — copy page (the publication artifact).** Air is one explicit empty block, `<p>&#160;</p>` (a no-break space, `U+00A0`). It stands **before every `h2`** and **above and below every block quote** — nowhere else. The first block of the article is the `h1` and takes no air; there is no air after a heading; two consecutive blocks never get two empty blocks between them.

The character matters. A zero-width space (`U+200B`) looks like the obvious choice, and it is the wrong one: the editor «Статья» treats a paragraph with no visible character as empty text and drops it on paste, so the air silently disappears and the article arrives as a solid wall of text with headings glued to the paragraph above. A no-break space survives HTML parsing, renders as exactly one blank line and no glyph. This is the only permitted invisible character in the whole pipeline, it lives in the artifact, and the reader never sees it as text.

Air exists **only in the HTML artifact**. The Markdown paste has no way to express it: a blank line there is a block separator, not an empty paragraph. If the air before headings is missing in a published post, the post was pasted as Markdown, not from the copy page.

Spacing matrix for the rendered artifact:

| Transition | Rendered artifact |
|---|---|
| paragraph → paragraph | ordinary paragraph gap |
| paragraph → H2 | **air before** — exactly one empty block (`U+00A0`) |
| H1 → next block | no air: the title stands alone |
| H2 → first paragraph | **no air after**; text follows immediately |
| paragraph → block quote | **air above** — one empty block (`U+00A0`) |
| short connector → block quote | no air: the connector exists to hold the quote tight (§5) |
| block quote → paragraph | **air below** — one empty block (`U+00A0`) |
| block quote → H2 | one empty block, not two: the heading's own air is that block |
| block quote → block quote | one empty block between them |
| quote → attribution | **same block**: attribution is the last line inside the quote, no gap possible (§5) |
| list item → list item | ordinary paragraph gap; each item is its own block (§6) |
| anywhere else | ordinary paragraph gap |

Air appears in exactly two places: **before headings** and **around quotations** — one empty block each time, never two in a row. Air after a heading is a defect: it doubles the gap the editor already adds. Air between ordinary paragraphs is a defect too: the editor already separates them, and empty blocks there turn a long article into a ladder of gaps. A copy page that puts empty blocks anywhere else fails review.

Why quotations are isolated: a quote is the only block whose boundary the reader must see without being told. Two air lines make it a figure on the page instead of a sentence that drifted out of the paragraph; in a 30 000-character article the eye needs that boundary at a glance. Headings and quotations are the article's two load-bearing structures, and air marks exactly those.

A plain Markdown paste without the renderer is acceptable when headings already look right in the current client; the renderer exists to make the result deterministic across clients.

## 5. Quotations in L2

Exact Markdown shape:

```text
Абзац, который вводит цитату и объясняет, зачем она здесь.

> «Точный текст цитаты»
> — Автор, «Название труда»
```

Rules:

- the quoted words occupy the opening lines of the block; the last line of the same block is the attribution — plain text, starting with Unicode em dash `—` and one space; no `*` around it;
- the attribution is **inside the quote block, as its last line**, never a separate paragraph under it. A paragraph that follows `<blockquote>` always inherits the editor's block spacing, and that is exactly the stray gap readers complain about; inside the block the attribution sits directly under the quoted words with no gap at all. This is a transport decision, not an attribution rule: the words still belong to the author, not to the quoted text, and `QUOTE_ATTRIBUTION_STANDARD.md` governs names and titles;
- the quoted words never carry the author, the reference or the work title;
- Scripture uses the same shape: `> — Иов 16:2` as the last line;
- the quote block is surrounded by one empty block above and one below (§4): the boundary between the author's words and the channel's commentary must be visible without being announced;
- air before the quote is the default. The only exception is a genuinely short connector that exists only to introduce the quote:

```text
Об окончательно отпавших Иоанн говорит иначе:
> «Цитата»
> — 1 Ин. 2:19
```

The connector is one short line ending with a colon (≤ 120 characters) that has no independent argument of its own. A colon alone is not a reason to remove air; do not manufacture one-sentence lead-ins.

- A quote block may be large. The normal range is 300–1 500 characters of quoted words; a key passage may run to 4 000 characters when the author's argument is continuous there. The attribution line does not count towards the limit. Size is decided by the argument, not by the layout: do not cut a passage that holds the proof in order to keep the block short, and do not splice two distant passages into one block — an omission inside a block is marked by `…` only where the author really skips text.
- No nested quotes and no second level of `>`.
- No translation note under a quote: neither «перевод мой» nor any similar mark. A Russian rendering of an English author is the channel's own translation by definition, and the credit line the reader sees in the author field carries only `— Автор, «Труд»`.
- Ellipses mark real omissions; paraphrases never stand inside quotation marks.
- Inline Scripture inside a running argument stays plain text inside the quotation marks — no bold, no italic. The blockquote shape is for quotations that stand as evidence on their own; do not convert every reference into a block.

### Lane split for the attribution

The placement of the attribution depends on the lane, and the two rules must not be mixed:

| Lane | Transport | Attribution |
|---|---|---|
| **L2** — rich editor «Статья», up to 32 768 characters | Markdown → «Статья» → paste, or HTML copy page | **inside** the quote block, last line, plain: `> — Автор, «Труд»` |
| **L1** — one ordinary message, up to 4 096 characters | plain rich composer | **outside** the quote block, separate paragraph: `*— Автор, «Труд»*` (`QUOTE_ATTRIBUTION_STANDARD.md`) |

Why the difference: in a long article the quote is one block among hundreds, and any block boundary under it produces a visible gap the editor controls, so the attribution is pulled inside. In a short post the attribution is its own line of the layout, and the older L1 rule stands.

HTML markup: the attribution line is rendered as `<cite>` inside the same `<blockquote>` — `<blockquote>…<br><cite>— Автор, «Труд»</cite></blockquote>`. `cite` is the element Telegram itself reads as the quote's author: Android turns its contents into `pageBlockBlockquote.caption` and shows that line in the author field of the block; Desktop does not know the tag, so the text simply stays inside the quote after a line break. Without `cite` the author stays empty and Android draws its placeholder label `Author` under the quote. Do not use `<br><i>` for the attribution, and do not put it in a separate `<p>` — a paragraph after the quote takes block spacing and gives the stray gap.

Known client behaviour, not a defect: a long quote renders collapsed behind a `Collapse` control, and the author line sits in the author field of the block. That is the intended shape — do not move the attribution outside the block and do not strip the `cite` tag to "fix" the collapse.

### Bibliographic note at the end

Every article ends with the source note: one paragraph, plain text, no heading. It starts straight with the substance — no «Откуда цитаты», no label of any kind — and the only decoration is one emoji at the very beginning:

```text
📖 Цитаты Чарнока — из книги «Беседы о существовании и атрибутах Бога» (Discourses upon the Existence and
Attributes of God), изданной посмертно в 1682 году; взяты из первой беседы — «О существовании Бога», по
словам псалма XIV:1. Текст — по изданию Robert Carter & Brothers, 1853 года, где оба тома напечатаны
вместе; оно оцифровано Project Gutenberg: eBook #53527, https://www.gutenberg.org/ebooks/53527.
```

Why it exists: the credit line under a quote may only carry the author and the work, and a reader who wants to check the source should not have to hunt through 43 quotes to find out which book he is reading. One block, once, at the end.

Rules:

- it is the **last** block of the article, after the final section;
- it begins with the words «Цитаты Чарнока — из книги…» — the reader learns the source from the first line, without a service label;
- exactly **one** emoji, the first character, as a marker of the note (📖 for a book source; the copyright sign if the rights are the point). This is the only place in the article where an emoji may stand in a paragraph — everywhere else it belongs to a heading;
- it names the book, the edition and the source URL; the URL is allowed here and only here;
- it carries no bold, no italic and no heading, and it does not talk about the translation or its literalness: that is the channel's business, not the reader's.

The Russian title of the book is «Беседы о существовании и атрибутах Бога». «Атрибуты» is the term Russian theology actually uses here, so the title keeps it; do not replace it with «свойства».

`scripts/lordchrist_article_preflight.py` fails an article without the note, without the URL in it, or with more than one emoji.

## 6. Lists in L2

- Lists only for genuinely parallel items (`RICH_EDITORIAL_STANDARD.md` §10).
- **Every item is a separate paragraph block**, separated by a paragraph break. A Markdown `-` list renders as a tight list block with no air between items and is therefore forbidden in L2.
- Allowed item shapes: `• **Грех.** Дальше объяснение.` and `1. **Они ставили диагноз.** Дальше объяснение.`
- One item: 1–3 sentences. If an item grows past that, it is a paragraph, not a list item.
- Blank line before the first item and after the last item; the introducing paragraph ends with a colon and is separated from the list by a paragraph break.

## 7. Hashtags

**L2 articles have no hashtag footer.** In a long article tags do not work as navigation, are not used by the channel's readers, and only add clutter after the conclusion. The article ends with its last paragraph.

Hashtags stay where they belong: the L1 short-post lane (quote cards), 4–6 topical tags, one line, two blank lines above (`AGENTS.md`).

If a particular long article is published in a context where tags are genuinely required, that is a user instruction and overrides this section; the renderer and preflight then take `--allow-hashtags`.

## 8. Transport: Arena → Telegram

Two supported paths.

**A. Markdown → «Статья» (preferred for Arena sessions).** The assistant returns the article as one copyable Markdown block; the editor parses it into headings, bold, italic, quotes and paragraphs.

1. Copy the block.
2. Telegram → channel → 📎 → **«Статья»**.
3. Long-press inside the editor → system **Paste / «Вставить»** (not the keyboard clipboard panel).
4. Inspect headings, quote attribution and air before sending.

**B. Rich HTML copy page (deterministic).** A self-contained page rendered from the L2-MD source by `render_l2_copy_page.py`: headings, bold/italic, block quotes, separate item blocks and air before headings are materialised in HTML, and one button writes `text/html` through `navigator.clipboard.write(new ClipboardItem(...))`, with a `text/plain` fallback and a "select the article" fallback. Paste with the same long-press → system Paste. Use this path when the current client does not parse Markdown reliably, or when spacing must be identical across devices.

Forbidden paths:

- selecting rendered assistant text in an Arena chat (selection grabs the whole conversation or returns plain text);
- pasting L2 Markdown into the ordinary composer — it shows literal `**` and `#`;
- keyboard clipboard/history panel for rich payloads.

Desktop: Telegram Desktop 7.1+ also parses Markdown when pasting into the rich editor; ordinary Ctrl+V is acceptable there, verify the result.

## 9. Arena session output contract

When the user asks for a paste-ready long article:

1. Return the **whole article** in one copyable Markdown block, with no commentary inside it.
2. Outside the block, report the preflight: characters, blocks (estimate), headings, quotes, lane = L2.
3. If the session can write files, also produce the copy page (path B) or the `.md` file; never rely on the chat selection.
4. Never claim provider authorization; L2 is a manual publication lane.

## 10. Review checklist

- [ ] lane stated explicitly (L2) and the limit checked against 32 768 / 500 blocks;
- [ ] exactly one H1, ALL CAPS, plain (no `**`), ≤ 120 characters;
- [ ] H2 in normal case, one section per 1 500–4 000 characters; a leading emoji marker under the §3 rule (single, leading, allowed in paragraph-sized named sections, never in numbered `1. 2. 3.` sequences, never on rubrics under ~600 characters);
- [ ] artifact: exactly one empty block before every H2 and above/below every quote, none after a heading, none between ordinary paragraphs, never two in a row, and that block is `U+00A0`, not `U+200B`;
- [ ] every list item is its own paragraph with `•` or `1.`, none rendered as a tight Markdown list;
- [ ] quotes: quoted words only inside `>`; attribution on the next line, italic, `— ` prefix;
- [ ] air before quotations by default; connector exception used only where justified;
- [ ] no hashtag footer (L2); no emoji in the H1 or in body text, heading markers only where the §3 rule permits them;
- [ ] no `U+2060`, no `U+200B`, no visible transport characters (the only invisible character allowed in the artifact is the air block's no-break space);
- [ ] no slogan ladder; paragraphs are multi-sentence;
- [ ] evidence rules from `RICH_EDITORIAL_STANDARD.md` satisfied;
- [ ] the article ends with the bibliographic note: one emoji, «Цитаты Чарнока — из книги…», book, edition, source URL, no heading, no bold, no italic, no talk about the translation;
- [ ] composer inspected after paste: typography, quote blocks, spacing.
