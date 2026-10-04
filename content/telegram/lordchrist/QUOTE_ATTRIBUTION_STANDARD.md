# @lordchrist quotation attribution standard

Status: canonical presentation rule for quotations in rich/editorial Telegram posts.

## Core rule

A Telegram blockquote contains **only the quoted words**. Author, work title, Scripture reference, section number and other source metadata are never part of the quotation entity.

Immediately after the quote block, place the attribution on its own line in *italic*, outside the blockquote. Every reader-facing attribution line begins with a Unicode em dash `—` (`U+2014`) followed by one normal space:

> «Точный текст цитаты»

*— Автор, «Название труда»*

For Scripture use the same hierarchy and the same em-dash prefix:

> «Текст библейской цитаты»

*— Лк. 8:13*

The em dash belongs to the attribution line, **not** to the quotation entity. Do not substitute a hyphen `-`, en dash `–`, bullet, copyright sign or other prefix. This keeps the source visually connected to the quotation while making it unmistakably separate from the quoted words.

The reader-facing line is the **reviewed attribution of the card, verbatim**. The pipeline must never re-derive it from the normalized evidence identity: re-deriving used to merge the chapter reference into the quoted work title and, where the reviewed line already contains a quoted title, produced nested or unclosed quotation marks such as `«проповедь «Божественный суверенитет», 1856»`, `«Святость, «Цена»»` or `«курс «The God Who Is There`. Quotation marks inside a reviewed attribution must stay balanced and must never nest; the runtime contract rejects both.

## Reader-facing language

Reader-facing Telegram attribution uses Russian forms:

- accepted Russian form of the author's name;
- Russian title of the work;
- chapter/section number only when it materially helps verification;
- no English work title merely to demonstrate research.

The exact English/original title, original-language anchor, public-domain source URL and translation status remain in the research/evidence layer. They do not clutter the Telegram article.

## Spacing before quotations

The default is **air before a quote**. If a normal explanatory paragraph or a substantial multi-sentence paragraph introduces the quotation, insert one visible paragraph gap before the quote block. In the Android manual-copy path this gap is preserved by a standalone invisible `U+2060 WORD JOINER` spacer line.

Canonical substantial-intro shape:

```text
Explanatory paragraph of normal article length.

[U+2060 spacer line]

> «Quotation»

*— Attribution*
```

There is one narrow exception: when a **very short one-sentence connector** exists only to attach the immediately following quotation—for example, `Об окончательно отпавших Иоанн говорит иначе:`—the quote follows that connector directly, with **no spacer between the connector and quotation**. The connector and quote should read as one semantic block.

```text
Об окончательно отпавших Иоанн говорит иначе:
> «Quotation»

*— Attribution*
```

Do not generalize this exception. **Most quotations should still have air before them.** Do not remove spacing merely because the preceding paragraph happens to end with a colon. The criterion is semantic and visual: only a genuinely short connector/label is kept attached to its quote.

Also do not manufacture tiny one-sentence lead-ins merely to avoid spacing. If the thought belongs to a larger paragraph, write the larger paragraph and keep the normal air before the quotation.

## Spacing after quotations

Attribution is visually attached to its quotation and therefore receives no extra spacer between quote and attribution. The required `— ` prefix does not change this spacing rule. After the italic attribution, use one normal article gap (`U+2060` in the Android manual-copy path) before the next independent paragraph.

So the preferred hierarchy is:

```text
substantial paragraph
[air]
quotation block
italic attribution beginning with —
[air]
next paragraph
```

and only for the narrow connector case:

```text
short connector:
quotation block
italic attribution beginning with —
[air]
next paragraph
```

## Primary-source discipline

Attribution styling does not relax evidence requirements. Historical quotations must be exact primary-source quotations or clearly identified editorial translations from a verified primary/public-domain text. Paraphrases must not be placed inside quotation marks.

For an editorial Russian translation, keep an exact original-language or English anchor in the evidence record. Ellipses must represent real omissions and must not stitch separate passages into a sentence the author never wrote.

## Android manual-paste rule

When manually copying from ChatGPT on Android, preserve visual gaps with an invisible `U+2060 WORD JOINER` on its own separator line. It must remain invisible and never appear inside quotation wording.

The canonical insertion path is:

**Rendered ChatGPT text → Copy → Telegram composer → long-press → system Paste.**

Do not insert rich posts from the keyboard clipboard/history panel; that path can flatten rich text to plain text.
