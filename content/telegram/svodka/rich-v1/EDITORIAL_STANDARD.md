# Svodka Rich Articles — reader-first editorial standard

Status: editorial contract for `content/telegram/svodka/rich-v1/`.

The target reader is an intelligent non-specialist encountering the subject for the first time. The writing must be simple enough to follow without prior coursework, but never patronising and never simplified into a false scientific claim.

## Core rule

A Rich Message is an article, not a Telegram feature demo.

Every heading, quote, image, list, table, formula, details block, collage or slideshow must earn its place by making the subject easier to understand. If removing a block does not make the explanation worse, the block should normally be removed.

## Explanation order

For a technical idea, prefer this order:

1. **Question or intuitive problem.** What are we trying to understand?
2. **Plain-language mechanism.** Explain what physically/biologically happens before naming it.
3. **Term.** Introduce the scientific word only after the reader has a mental model.
4. **Number or measurement.** Say what was measured, with what comparison or scale makes it meaningful.
5. **Boundary.** State what the experiment/result does *not* prove.
6. **Takeaway.** One sentence the reader can repeat without distorting the science.

Not every article needs six explicit sections, but the logic should be visible.

## Terms

- Define a technical term at first use in ordinary Russian.
- Never use terminology merely to sound scientific.
- Prefer a short concrete analogy when it preserves the underlying mechanism.
- Mark analogies as analogies; do not let them quietly become factual claims.

## Numbers

A number without context is often decoration. Whenever useful, answer at least one of:

- Compared with what?
- Is this large or small on a familiar scale?
- Is this a local measurement, a total quantity, a rate, a duration or a probability?
- What exactly did the instrument/experiment measure?

Do not add unsupported precision.

## Formulas

A formula is allowed only when the reader already understands the idea in words and the formula makes the idea clearer or more compact.

A formula must never be inserted just because Telegram Rich Messages can render mathematics.

If a formula is used:

- explain every symbol relevant to the reader;
- explain the direction of the relationship in words;
- give the reader a plain-language conclusion immediately before or after it;
- remove it if the article remains equally understandable without it.

The successful native-rich canary of 2026-08-11 deliberately exercised mathematical-expression and table capabilities. That canary was a capability proof, **not** the editorial template for production posts.

## Tables, lists, details, collage and slideshow

- Use a **list** when items are genuinely parallel and scanning is easier than prose.
- Use a **table** only when the reader is comparing the same attributes across multiple items.
- Use **details** for sources, definitions or optional depth that should not interrupt the main explanation.
- Use **collage/slideshow** only when several images jointly explain a process, timeline, comparison or sequence.
- Do not duplicate the same information in prose and a table just to demonstrate both blocks.

## Images

Images are explanatory assets, not decoration.

Good roles include:

- exact map for a geographic question;
- diagram for a mechanism that is hard to picture in prose;
- timeline for deep-time comparisons;
- photograph of the actual organism/instrument/place being discussed;
- before/after or sequential panels when order matters.

Every image must retain reviewed provenance/licence metadata.

## Scientific boundaries

- Stay within the claims supported by the article's registered sources.
- Clearly separate observation, measurement, interpretation and analogy.
- Do not turn correlation, convenience or a plausible function into an evolutionary explanation.
- Do not turn recognition into detailed recollection, survival into normal life, lineage age into unchanged species, or a local peak temperature into total energy.
- If a source did not test a claim, say so rather than filling the gap with folklore.

## Tone

Prefer calm curiosity over hype.

Avoid:

- `учёные доказали невероятное`;
- `шокирующий факт`;
- fake rhetorical suspense;
- treating an animal or researcher as a ranking object;
- repeated canned phrases such as `на деле всё интереснее`;
- talking down to the reader.

The ideal tone is: **"I did not know this either; here is how the experiment or mechanism actually works."**

## Production review checklist

Before an article may move out of `editorial_draft_review_required`, review it for:

- [ ] first-time reader can explain the main mechanism back in one or two sentences;
- [ ] technical terms are defined at first use;
- [ ] numbers have context;
- [ ] every rich block improves comprehension;
- [ ] no formula/table exists only as a capability demonstration;
- [ ] source-supported claim boundary is explicit;
- [ ] media provenance is complete;
- [ ] Markdown reading copy and canonical JSON say the same thing;
- [ ] provider writes remain separately authorised and are never implied by editorial approval.
