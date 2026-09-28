# LordChrist Rich — reader-first editorial standard

Status: editorial contract for new `@lordchrist` research / history / explanatory successor releases.

This standard does **not** replace the live short quote lane. It defines the larger article format that should alternate with short verified quotations so the channel does not become a sequence of visually identical quote cards.

## Core rule

A rich post is a compact article for a real reader, not a Telegram formatting demonstration and not an AI-looking wall of headings.

Every paragraph, heading, image, list, quote or optional details block must earn its place by improving understanding, evidence, historical context or emotional clarity.

The prose must read as continuous argument, not as a stack of slogans. Do **not** manufacture rhythm by breaking one ordinary thought into a run of one-line paragraphs. Short isolated lines are reserved for rare conclusions that genuinely need emphasis; they are not the default cadence.

## Default article shape

Prefer this order when the subject allows it:

1. **Title** — concrete and informative, not clickbait.
2. **Lead** — 2–4 sentences explaining why the subject matters.
3. **Context** — enough history or textual background to understand the question.
4. **Two to four sections** — one idea per section, short Telegram paragraphs.
5. **Evidence / primary-source boundary** — make clear what is documented, estimated or interpreted.
6. **Christian takeaway** — restrained and textually connected to the material; no forced moral appended to unrelated history.
7. **Sources/details** when useful — compact, not a bibliography wall in the main reading flow.

For explanatory/theological posts, normal body paragraphs should usually contain **2–5 complete sentences**. Single-sentence paragraphs may be used when the sentence genuinely changes direction or carries unusual weight, but repeated slogan-like one-liners are a quality defect.

## Anti-slogan rule

Avoid the characteristic AI cadence of repeated standalone declarations, especially chains such as:

- `Не в X.`
- `Не в Y.`
- `А в Z.`
- `Он падает.`
- `Он встаёт.`
- `Есть вера...`

If several neighbouring lines belong to one argument, combine them into one grammatical paragraph. Prefer explanation over rhetorical hammering. A post may have one or two memorable sentences; it should not be built from them.

Do not use all-caps as a substitute for argument. Full-cap emphasis is exceptional and should normally be avoided in rich articles.

## Quotations and primary-source discipline

Use direct quotations only when the exact wording adds value. Do not manufacture dialogue or devotional quotes.

For historical theologians, confessions and church fathers, prefer **primary texts** over summaries. A named historical quotation must have:

- author;
- exact work;
- section/chapter/paragraph when recoverable;
- a primary-text or reliable critical/public-domain source URL in the evidence record;
- the original-language anchor or exact English anchor when the published post uses a Russian translation;
- a translation status indicating whether the Russian wording is an existing published translation or an editorial translation.

Never put quotation marks around a paraphrase. If a source is being summarized, write it as prose and say what the author argues rather than presenting an invented Russian sentence as a quotation.

When translating a primary source for Telegram, preserve the claim and logical force of the source. Prefer a short contiguous excerpt over a stitched quotation. Ellipses must represent actual omissions and must not fuse separate passages into a sentence the author never wrote.

For a normal one-post theological article, **2–4 substantial historical quotations** are usually stronger than many tiny quote fragments. Scripture quotations remain primary and may be used more freely when central to the exegesis.

Long quotation blocks should not dominate an explanatory article. Prefer short exact excerpts surrounded by original explanation and source context.

Where a historical teacher is discussed, Scripture and Christ remain the final norm; historical influence is not spiritual authority by itself.

## Exegesis standard

When a post turns on a biblical phrase:

- establish the immediate literary context first;
- use parallel passages where they genuinely illuminate the text;
- distinguish lexical observation from theological inference;
- do not claim that a Greek tense, lemma or preposition proves more than it actually proves;
- distinguish final apostasy from the serious falls of a true believer when the text requires that distinction;
- state both divine causation and human means when Scripture states both (for example, `1 Pet. 1:5`: guarded by God's power **through faith**).

A doctrinal conclusion should arise from the text and its canonical cross-references, then be confirmed by historical witnesses—not the other way round.

## Visual standard

Images are explanatory evidence, not decoration.

A normal rich historical article may use **1–3 images**. More are allowed only when the sequence itself teaches something.

Useful roles include:

- a historically appropriate portrait when the person is central;
- a manuscript, printed page, sermon volume, archive object or period photograph that directly supports the story;
- a church, city, pulpit or institution when place explains the history;
- a timeline, comparison graphic or map when prose would be harder to scan;
- two or three contrasting images when the article compares people, eras or preservation media.

Do not repeat essentially the same portrait several times. Do not use generic generated religious scenery as fake historical evidence.

Every external image must retain reviewed provenance and rights/licence metadata. Caption the image with what it actually shows and attribute it where required.

## Calvin / Spurgeon / MacArthur series

The prepared `research-posts-v3` corpus should be treated as article copy, not collapsed back to one quote plus attribution.

Examples of useful visual structures:

- **«Перо, стенографист и магнитная лента»**: Calvin manuscript/sermon record → Spurgeon printed sermon/volume → MacArthur recording/archive medium.
- **«Учиться у тех, кто жил до нас»**: restrained portraits or documentary artifacts for the historical links actually discussed.
- **«Один текст — разные способы проповедовать»**: one meaningful visual per preacher, or a compact three-column comparison graphic if it is clearer than three decorative portraits.
- **«Невидимая дисциплина»**: study/preparation/archive evidence rather than generic pulpit glamour.

Do not rank ministers by fame, archive size, sermon count or surviving media. Counts must always keep their denominator and uncertainty: preached, recorded, surviving and published are different quantities.

## Tone

Prefer calm, serious curiosity and warmth.

Avoid:

- `невероятная история`, `шок`, `вы не поверите`;
- artificial suspense;
- bureaucratic phrases such as `в рамках данного материала`;
- repetitive AI cadence and identical paragraph lengths;
- slogan chains and repeated one-line emphatic paragraphs;
- excessive all-caps or bolding;
- rankings of servants of God;
- claims that surviving archives measure final faithfulness;
- sentimental conclusions unsupported by the body.

The ideal voice is well-read, understandable Russian that can explain evidence without sounding academic for its own sake.

## Rich-format restraint

Use bold for hierarchy or genuinely important phrases, not every second sentence. Use italic sparingly for titles, foreign terms or secondary emphasis.

Use block quotes for genuine quotations only. Do not use block quotes as decoration for the author's own prose.

Use lists only for parallel items. Use a table only when the reader compares the same attributes across several subjects. Use details/source blocks only for optional depth.

A rich block is removed if ordinary prose is clearer.

## Direct ChatGPT → Telegram drafting mode

Some `@lordchrist` posts are composed interactively in ChatGPT and then posted manually from a phone. For this mode, the assistant output should be a **single ordinary rendered rich-text response**, not a code block and not raw Markdown source.

The intended manual-copy representation is:

- real rendered **bold**;
- real rendered *italic*;
- real rendered block quotes;
- normal paragraph spacing;
- no literal `>`, `**`, `*` or HTML tags in the reader-facing copy.

The user should select the rendered article text directly when the client preserves rich clipboard data. The ChatGPT/message `Copy` action must not be assumed to preserve rich formatting; some clients copy Markdown/plain text instead.

Because Android/browser clipboard handling can regress or vary by browser build, direct-copy eligibility must be checked with a small formatting canary before relying on it for a long post. The operational troubleshooting and canary are documented in `DIRECT_COPY_TO_TELEGRAM.md`.

Do not change the article itself merely to work around a clipboard bug. Transport problems belong in the copy workflow, not in visible editorial punctuation or fake quote markers.

## Evidence and freshness

Every factual claim must remain bound to accepted source evidence from the owning research queue/registry. Preserve certainty labels and measurement scope.

Historical facts may be evergreen; modern biographical/status facts must be refreshed before a new release if they could have changed since the evidence pass.

A retired provider release is immutable historical evidence. Copy may be adapted into a **new** successor release, but old provider intent/digests must never be reused to obtain a second mutation.

## Production review checklist

Before a new rich article becomes eligible for a provider canary:

- [ ] title and lead make sense to a first-time reader;
- [ ] article has one clear question or narrative spine;
- [ ] body paragraphs are real paragraphs, not a slogan ladder;
- [ ] isolated one-line emphasis is rare and justified;
- [ ] every material factual claim maps to accepted evidence;
- [ ] historical quotations are exact primary-source quotations or explicitly labelled paraphrases;
- [ ] translated quotations retain an original-language/English anchor in the evidence record;
- [ ] estimates/ranges are not rewritten as exact facts;
- [ ] images are relevant, non-duplicative and provenance/rights-reviewed;
- [ ] captions identify what the image actually shows;
- [ ] formatting improves reading rather than demonstrating features;
- [ ] theological conclusion follows from the article rather than being pasted on;
- [ ] visible plain text and reviewed canonical copy agree;
- [ ] provider execution has a new exact successor identity and does not reuse a retired release;
- [ ] provider write remains separately authorized and one-shot, with durable intent and no blind retry.
