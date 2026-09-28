# LordChrist Rich — reader-first editorial standard

Status: canonical editorial contract for new `@lordchrist` research / history / explanatory Telegram posts.

This standard does **not** replace the live short quote lane. It defines the larger article format and the exact presentation conventions agents must follow when preparing a manually copyable rich post.

## 1. Core editorial rule

A rich post is a compact article for a real reader, not a Telegram formatting demonstration and not an AI-looking wall of slogans.

The prose must read as a continuous argument. Normal explanatory/theological paragraphs should usually contain **2–5 complete sentences**. Do not split one thought into a ladder of tiny one-line declarations merely for drama.

Avoid characteristic AI cadence such as:

- `Не в X.`
- `Не в Y.`
- `А в Z.`
- `Он падает.`
- `Он встаёт.`
- repeated slogan-like conclusions separated into single lines.

If several neighbouring sentences form one thought, keep them in one grammatical paragraph. One or two memorable short sentences may be used when genuinely warranted; they must not become the dominant rhythm.

## 2. Title rule

For the `@lordchrist` rich-article lane, the reader-facing post title is normally:

- **BOLD**;
- **ALL CAPS**;
- one concise line;
- concrete rather than clickbait.

Example:

**ВРЕМЕННО ВЕРУЮЩИЕ**

This is the explicit exception to the anti-all-caps rule. **Do not use all caps as body-text emphasis.** Body prose remains normally cased and uses restrained bold only where it helps hierarchy or comprehension.

## 3. Default article shape

Prefer this order when the subject allows it:

1. **Bold all-caps title**.
2. Primary biblical text / thesis quotation when it genuinely governs the article.
3. Lead and immediate context.
4. Continuous explanatory argument in normal multi-sentence paragraphs.
5. Two to four strong primary-source witnesses rather than many tiny quotations.
6. Canonical cross-references and doctrinal synthesis.
7. Restrained conclusion that follows from the exegesis rather than functioning as a slogan.

The post must fit the actual Telegram message limit with safety margin after rendering. Do not solve an overlong draft by turning it into fragments or deleting source context arbitrarily.

## 4. Paragraph spacing for manual Android posts

A manually copied rich article must preserve visible air between independent paragraphs. Telegram/Android can collapse genuinely empty rich-text lines, so the manual-copy representation uses a standalone invisible Unicode **WORD JOINER `U+2060`** spacer line where a paragraph gap must survive paste.

The reader must not see any placeholder character. Never substitute visible bars, dots, Markdown markers or fake quote symbols for spacing.

Use one invisible spacer between independent article paragraphs. Do not create multiple blank spacer rows unless there is an intentional major section break.

The transport details live in `DIRECT_COPY_TO_TELEGRAM.md`.

## 5. Quotations — exact presentation contract

`QUOTE_ATTRIBUTION_STANDARD.md` is authoritative for quote layout.

The key rules are:

- the Telegram quote block contains **only quoted words**;
- author/work or Scripture reference sits **outside** the quote block on the next line in *italic*;
- reader-facing historical work titles are in Russian;
- English/original titles and exact source anchors stay in the research/evidence layer;
- paraphrases never appear in quotation marks.

### Air before quotations

**Default: keep air before a quotation.** If a normal explanatory paragraph or substantial multi-sentence paragraph introduces a quotation, place one `U+2060` spacer line before the quote block.

Only one narrow exception exists: a very short one-sentence connector that exists solely to attach the immediately following quotation, for example:

`Об окончательно отпавших Иоанн говорит иначе:`

In that case the quote follows immediately, with no spacer between connector and quote, because they form one visual/semantic block.

Do **not** generalize this exception. Most quotes retain air before them. A colon by itself is not a reason to remove spacing. Do not manufacture tiny lead-in sentences merely to make a compact quote block.

After the quote, attribution stays attached immediately below it. Then use the normal paragraph gap before the next independent paragraph.

## 6. Primary-source discipline

Use a direct quotation only when exact wording adds value. Historical theologians, confessions and church fathers should be verified from primary texts or reliable critical/public-domain reproductions.

A named historical quotation must have in the evidence layer:

- author;
- exact work;
- chapter/section/paragraph when recoverable;
- primary/public-domain source URL;
- exact original-language or English anchor when the Telegram post uses an editorial Russian translation;
- translation status: published Russian translation vs editorial translation.

Never put quotation marks around a paraphrase. When translating a source editorially, preserve its logical force and use a short contiguous excerpt. Ellipses must represent real omissions and must not stitch unrelated clauses into a statement the author never made.

For a normal one-message theological article, **2–4 substantial historical quotations** are generally stronger than many tiny fragments. Scripture may be quoted more freely when it directly drives the exegesis.

## 7. Exegesis standard

When the article turns on a biblical phrase:

- establish the immediate literary context first;
- use parallel passages where they genuinely illuminate the text;
- distinguish lexical observation from theological inference;
- do not make a Greek tense, lemma or preposition prove more than it proves;
- distinguish final apostasy from serious falls of a true believer where Scripture requires it;
- when Scripture gives both divine causation and human means, state both. Example: `1 Pet. 1:5` speaks of believers guarded by **God's power through faith**.

A doctrinal conclusion should arise from Scripture and canonical cross-references, then be confirmed by historical witnesses—not imposed on the text by the witnesses.

## 8. Tone

Prefer calm, serious, well-read Russian that a normal reader can follow.

Avoid:

- clickbait (`шок`, `вы не поверите`, `невероятная история`);
- artificial suspense;
- bureaucratic prose;
- repetitive AI cadence;
- slogan ladders;
- body-text all caps;
- excessive bolding;
- sentimental conclusions unsupported by the argument;
- rankings of ministers by fame, archive size or surviving media.

Theological firmness is compatible with measured prose. Explain rather than hammer.

## 9. Rich-format restraint

Use bold for title, hierarchy and genuinely important phrases—not every second sentence. Use italics for attribution, work titles where appropriate, foreign terms or secondary emphasis.

Use block quotes only for genuine quotations. Do not use quote formatting merely to decorate the author's own prose.

Use lists only for genuinely parallel items. Tables are justified only when the reader is comparing the same attributes across several subjects.

## 10. Visual standard

Images are explanatory evidence, not decoration. A normal rich historical article may use **1–3 images** if each serves a distinct function: portrait, manuscript/source, archive object, period photograph, place, map, timeline or comparison graphic.

Do not repeat near-identical portraits. Do not use generic generated religious scenery as fake historical evidence. Every external image must retain reviewed provenance and rights/licence metadata.

## 11. Direct ChatGPT → Telegram drafting mode

When the user asks for a manually copyable Telegram article, the assistant should return **one clean rendered rich-text article**, not raw Markdown, raw HTML or a code block.

Required reader-facing representation:

- **bold all-caps title**;
- real rendered **bold** and *italic*;
- real blockquote entities;
- normal multi-sentence paragraphs;
- `U+2060` invisible spacer lines where Telegram must preserve paragraph air;
- quote attribution outside the quote block in italics;
- no literal `>`, `**`, HTML tags or other visible transport syntax.

Canonical Android insertion path:

**Rendered ChatGPT text → Copy → Telegram composer → long-press → system Paste.**

Do not insert rich posts via the keyboard clipboard/history panel; that route can flatten the clipboard to plain text.

## 12. Production review checklist

Before considering a rich article finished:

- [ ] title is one concise **bold all-caps** line;
- [ ] article has one clear argument/narrative spine;
- [ ] body paragraphs are real paragraphs, not a slogan ladder;
- [ ] independent paragraphs have preserved visual air;
- [ ] most quotations have air before them;
- [ ] only a genuinely short connector is attached directly to its quote;
- [ ] quotation blocks contain quoted words only;
- [ ] author/work or Scripture reference is italic and outside the quote block;
- [ ] reader-facing historical work titles are Russian;
- [ ] every historical quotation has a primary-source anchor in the evidence layer;
- [ ] editorial translations are identified as such in evidence;
- [ ] paraphrases are not presented as quotations;
- [ ] bold/italic formatting is restrained and purposeful;
- [ ] doctrinal conclusion follows from the biblical argument;
- [ ] manual Android paste is tested through long-press → system Paste, not keyboard clipboard insertion;
- [ ] Telegram composer is visually inspected before sending;
- [ ] provider execution, if used, remains a separate explicitly authorized action.
