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
| Quotes | blockquote entity + italic attribution below | `>` blockquote + italic attribution line | `blockquote` block with `credit` |
| Hashtags | 4–6 tags, two blank lines above | **none** — a long article needs no hashtag footer | footer block |

Never mix the transports. `U+2060` in an L2 article is a defect: the editor already creates paragraph gaps, and an extra invisible line becomes a stray empty block. Conversely, L2 headings or Markdown lists pasted into the ordinary composer show up as literal `#` and `**`.

## 2. Length preflight

Count the exact reader-facing text:

- every visible character, including hashtags and table labels;
- every line break;
- no invisible spacers (there must be none).

Limits for L2: **≤ 32 768 UTF-8 characters**, **≤ 500 blocks**, **≤ 16 levels** of nesting, **≤ 50 media**, **≤ 20 table columns**. Keep a soft target of **≤ 30 000 characters** so late edits do not cross the boundary.

Block estimate: paragraphs + headings + list items + quote blocks (+ attribution paragraphs) + table rows. A typical 25 000–27 000-character article uses 110–140 blocks — well inside the limit.

If a reviewed article is over the limit: remove repetition and weak wording first (`RICH_EDITORIAL_STANDARD.md` §3), never exegesis or evidence. Only if it still does not fit, split at section boundaries into two L2 articles; do not degrade the prose into slogans. There is no hashtag footer to drop in L2 — the budget is spent on text only.

The 4096 limit and the `U+2060` rules in `DIRECT_COPY_TO_TELEGRAM.md` apply to **L1 only**. `telegram_research.py::validate_public_copy` (≤4096, plain text, no Markdown) is the bot plain-text lane and does not accept L2 Markdown.

## 3. Structure and headings

- **H1 — title.** Exactly one, first block, ALL CAPS, one line, ≤ 120 characters, bold: `# **ЖАЛКИЕ УТЕШИТЕЛИ: 10 СОВЕТОВ…**`.
- **H2 — sections.** Normal case, bold by heading rendering, ≤ 80 characters, no ALL CAPS, no clickbait. A single leading emoji marker is permitted only under the marker rule below.
- H3 only when a section genuinely has two levels; more than two heading levels is a defect.
- One H2 per **1 500–4 000 characters** of body. A 25 000+ character article normally has 10–16 sections.
- A heading never ends a message or a part; two headings never stand in a row.
- **Emoji marker rule.** In L2 an emoji is a normal part of the layout, not an exception: one marker leading an H2 line. Use it by default where a section is made of full paragraphs. Two cases take no marker: (1) a section inside a numbered ladder (`## 1. …`, `## 2. …`, `## 3. …`) — the number already marks position, and a pictogram next to it is noise; (2) a short rubric — a section under ~600 characters, meaning one or two sentences, a single item, or a brief insert — where the marker only distracts. No emoji in the H1 and no emoji in body paragraphs in any case; never more than one emoji per heading, always the first character of the line. The 600-character threshold is evaluated per section, not as an average over the article.
- Body bold: short key phrases only (normally ≤ 7 words). Do not bold whole sentences or alternate every paragraph.
- Italic: attribution, foreign terms, occasional secondary contrast. Not decoration.

## 4. Spacing

L2 has two representations, and they control spacing differently.

**L2-MD — Markdown source (what the agent writes).** Telegram's rich editor builds paragraph and heading blocks itself. A blank line in Markdown is a block separator, not an empty paragraph; an empty paragraph cannot be expressed in Markdown at all. Therefore the Markdown source never simulates air: it uses exactly one blank line between blocks, and the editor supplies the normal paragraph and heading gaps. No invisible characters are allowed in the source.

**L2-HTML — copy page (the publication artifact).** When the house style requires air **before** headings, the renderer emits one explicit empty block — `<p>&#8203;</p>` (a zero-width space) — immediately before each `h1`/`h2` and nowhere else. This is the only permitted invisible character in the whole pipeline, it lives in the artifact, and it is never visible to the reader.

Spacing matrix for the rendered artifact:

| Transition | Rendered artifact |
|---|---|
| paragraph → paragraph | ordinary paragraph gap |
| paragraph → H1 / H2 | **air before** — exactly one empty block |
| H2 → first paragraph | **no air after**; text follows immediately |
| paragraph → block quote | air before (default) |
| short connector → block quote | no extra air (narrow exception, §5) |
| quote → attribution | **same block**: attribution is the last line inside the quote, no gap possible (§5) |
| attribution → next paragraph | ordinary paragraph gap |
| list item → list item | ordinary paragraph gap; each item is its own block (§6) |
| anywhere else | ordinary paragraph gap |

Air **only before** headings. Air after a heading is a defect: it doubles the gap the editor already adds. A copy page that inserts empty blocks anywhere except before headings fails review.

A plain Markdown paste without the renderer is acceptable when headings already look right in the current client; the renderer exists to make the result deterministic across clients.

## 5. Quotations in L2

Exact Markdown shape:

```text
Абзац, который вводит цитату и объясняет, зачем она здесь.

> «Точный текст цитаты»
> *— Автор, «Название труда»*
```

Rules:

- the quoted words occupy the **opening lines** of the block; the **last line of the same block** is the attribution — italic, starting with Unicode em dash `—` and one space;
- the attribution is **inside the quote block, as its last line**, never a separate paragraph under it. A paragraph that follows `<blockquote>` always inherits the editor's block spacing, and that is exactly the stray gap readers complain about; inside the block the attribution sits directly under the quoted words with no gap at all. This is a transport decision, not an attribution rule: the words still belong to the author, not to the quoted text, and `QUOTE_ATTRIBUTION_STANDARD.md` governs names and titles;
- the quoted words never carry the author, the reference or the work title;
- Scripture uses the same shape: `> *— Иов 16:2*` as the last line;
- after the quote block — ordinary paragraph break, no extra air;
- air before the quote is the default. The only exception is a genuinely short connector that exists only to introduce the quote:

```text
Об окончательно отпавших Иоанн говорит иначе:
> «Цитата»
> *— 1 Ин. 2:19*
```

The connector is one short line ending with a colon (≤ 120 characters) that has no independent argument of its own. A colon alone is not a reason to remove air; do not manufacture one-sentence lead-ins.

- One quote block ≤ ~600 characters of quoted words; the attribution line does not count towards the limit. A longer passage is split by the author's own narration, not by `…`.
- No nested quotes and no second level of `>`.
- Ellipses mark real omissions; paraphrases never stand inside quotation marks.
- Inline Scripture inside a running argument stays inline bold (as in the current articles). The blockquote shape is for quotations that stand as evidence on their own; do not convert every reference into a block.

### Lane split for the attribution

The placement of the attribution depends on the lane, and the two rules must not be mixed:

| Lane | Transport | Attribution |
|---|---|---|
| **L2** — rich editor «Статья», up to 32 768 characters | Markdown → «Статья» → paste, or HTML copy page | **inside** the quote block, last line: `> *— Автор, «Труд»*` |
| **L1** — one ordinary message, up to 4 096 characters | plain rich composer | **outside** the quote block, separate paragraph: `*— Автор, «Труд»*` (`QUOTE_ATTRIBUTION_STANDARD.md`) |

Why the difference: in a long article the quote is one block among hundreds, and any block boundary under it produces a visible gap the editor controls, so the attribution is pulled inside. In a short post the attribution is its own line of the layout, and the older L1 rule stands.

HTML markup: the attribution line is rendered as `<cite>` inside the same `<blockquote>` — `<blockquote>…<br><cite>— Автор, «Труд»</cite></blockquote>`. `cite` is the element Telegram itself reads as the quote's author: Android turns its contents into `pageBlockBlockquote.caption` and shows that line in the author field of the block; Desktop does not know the tag, so the text simply stays inside the quote after a line break. Without `cite` the author stays empty and Android draws its placeholder label `Author` under the quote. Do not use `<br><i>` for the attribution, and do not put it in a separate `<p>` — a paragraph after the quote takes block spacing and gives the stray gap.

Known client behaviour, not a defect: a long quote renders collapsed behind a `Collapse` control, and the author line sits in the author field of the block. That is the intended shape — do not move the attribution outside the block and do not strip the `cite` tag to "fix" the collapse.

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
- [ ] exactly one H1, ALL CAPS, bold, ≤ 120 characters;
- [ ] H2 in normal case, one section per 1 500–4 000 characters; a leading emoji marker under the §3 rule (single, leading, allowed in paragraph-sized named sections, never in numbered `1. 2. 3.` sequences, never on rubrics under ~600 characters);
- [ ] artifact: air **before** every heading, none after (empty block only there);
- [ ] every list item is its own paragraph with `•` or `1.`, none rendered as a tight Markdown list;
- [ ] quotes: quoted words only inside `>`; attribution on the next line, italic, `— ` prefix;
- [ ] air before quotations by default; connector exception used only where justified;
- [ ] no hashtag footer (L2); no emoji in the H1 or in body text, heading markers only where the §3 rule permits them;
- [ ] no `U+2060`, no `U+200B`, no visible transport characters;
- [ ] no slogan ladder; paragraphs are multi-sentence;
- [ ] evidence rules from `RICH_EDITORIAL_STANDARD.md` satisfied;
- [ ] composer inspected after paste: typography, quote blocks, spacing.
