# @lordchrist agent entrypoint

This file is the first stop for any agent asked to research, draft, revise, format, or hand off Telegram content for `@lordchrist` / «Господь Бог — Сила Моя».

## Read order

Before writing a rich/explanatory/theological post, read these files in order:

1. `README.md` — scope, evidence/presentation split, and provider boundary.
2. `RICH_EDITORIAL_STANDARD.md` — canonical prose, title, exegesis, length, and formatting contract.
3. `QUOTE_ATTRIBUTION_STANDARD.md` — exact quotation layout and spacing rules.
4. `DIRECT_COPY_TO_TELEGRAM.md` — Android rich-copy transport and `U+2060` spacer behavior for lane L1.
5. `RICH_EDITOR_ARTICLE_STANDARD.md` — long articles in the Telegram rich editor «Статья» (lane L2, up to 32 768): headings, list blocks, quote markup and air rules.
6. The task-specific research/evidence file, if one exists.

For short quote-lane production, follow `README.md` and `presentation-policy.json`; do not force the rich-article layout onto the short quote lane.

## Precedence

For reader-facing rich posts, presentation authority is:

1. the user's current explicit instruction;
2. `RICH_EDITORIAL_STANDARD.md`;
3. `RICH_EDITOR_ARTICLE_STANDARD.md` when the target is the rich editor «Статья» (lane L2);
4. `QUOTE_ATTRIBUTION_STANDARD.md`;
5. `DIRECT_COPY_TO_TELEGRAM.md` when the target is one ordinary message (lane L1);
6. task-specific research/evidence;
7. old drafts/examples/chat history. Attribution placement is lane-dependent: inside the quote block for L2, outside it for L1.

Research drafts are evidence inputs, **not presentation authority**. If an old draft shows an English work title, an attribution placement that conflicts with the target lane, collapsed spacing, slogan-like prose, or another layout that conflicts with the current standards, re-render it under the current standards instead of copying the old layout.

## Non-negotiable rich-post rules

- Reader-facing title: **bold, ALL CAPS, one concise line**.
- Body: continuous Russian prose, normally multi-sentence paragraphs; no AI slogan ladder.
- Prefer **positive contextualization over reflexive self-defense**. Do not clutter the reader-facing post with meta-disclaimers such as `Paul is not speaking about Judas here`, `this does not mean...`, or `we are not claiming...` merely to demonstrate caution. When applying a passage beyond its immediate setting, briefly establish the passage's own context and then make the warranted application directly. Use an explicit caveat only when it prevents a real exegetical or doctrinal misunderstanding that cannot be handled naturally in positive prose.
- Rich emphasis is part of the final presentation, not optional decoration. Use real **bold** for several short doctrinal/key phrases and *italic* for attribution plus occasional secondary contrast where it genuinely helps reading. Do not return an almost-plain article when the user asked for the rich-post format, and do not over-format every sentence.
- When the user asks for the final paste-ready Telegram post, return the exact reader-facing post in **one dedicated copyable/writing block** when the host interface supports such a block. The block must contain only the post itself—no verification notes, source discussion, character-count commentary, repository status, instructions, or other surrounding prose. Keep all such commentary outside the block. Do not bury the final copy target inside a normal mixed response: the user should be able to select/copy the entire post in one action.
- Preserve useful content. If the complete reviewed post fits Telegram, **do not shorten it merely to make it look more compact**. Remove repetition or weak wording, not evidence, exegesis, or useful context.
- State the lane before drafting: **L1** — one ordinary message, `sendMessage`, **1–4096 characters after entities parsing** (`https://core.telegram.org/bots/api#sendmessage`); **L2** — rich editor «Статья», up to **32 768 UTF-8 characters / 500 blocks / 16 nesting levels / 50 media**; **L3** — provider `sendRichMessage`, same limits as L2. Run the hard-length preflight on the exact pasted text, counting line breaks and every invisible `U+2060` spacer (L1 only). Keep a small margin rather than targeting the boundary exactly. Lane definitions: `RICH_EDITOR_ARTICLE_STANDARD.md`.
- Historical quotations: primary-source verified; editorial Russian translations must retain an exact original/English anchor in evidence.
- Quote entity: quoted words only.
- Attribution (lane **L1**, one ordinary message): immediately below the quote, outside the quote entity, in *italic*, and beginning with Unicode em dash plus one normal space (`— `); reader-facing work titles in Russian. Apply the same `— ` prefix to Scripture references. The dash is part of the attribution line, never part of the quote. In lane **L2** the attribution moves inside the quote as its last line — see the L2 layout rule below and `RICH_EDITOR_ARTICLE_STANDARD.md` §5.
- **Default: air before quotations.** Put one `U+2060` spacer line before a quote after a normal/substantial paragraph.
- Narrow exception only: a genuinely short one-sentence connector that exists solely to introduce the next quote (for example, `Об окончательно отпавших Иоанн говорит иначе:`) stays attached to the quote with no spacer. Do not generalize this exception.
- After quote attribution, restore the normal article gap before the next independent paragraph.
- **L1 only.** If the exact final post still has safe room, add a compact hashtag footer. Default rich-post footer is **4–6 genuinely topical hashtags on one line**. Each tag begins with a capital letter; multiword tags use readable CamelCase, e.g. `#ДжонОуэн #ДуховнаяБорьба`. Do not add generic or duplicate tags merely to fill space.
- Separate the hashtag line from the concluding prose by **two visual blank lines**. In the Android manual-copy representation, use two standalone `U+2060` spacer lines for this intentional footer break. Hashtags, line breaks and both spacer characters count toward the 4096-character preflight.
- Hashtags are lower priority than the article. If the post is close to the limit, reduce or omit hashtags before cutting useful exegesis, evidence, qualifications or the conclusion.
- **L2 (rich editor «Статья») has no hashtag footer.** A long article ends with its last paragraph: tags do not work as navigation there. Do not silently keep the L1 hashtag block when switching lanes.
- Manual Android paste: rendered ChatGPT text → Copy → Telegram composer → long-press → system **Paste / «Вставить»**. Never use the keyboard clipboard/history panel for rich posts.
- **L2 (`«Статья»`) layout:** real headings (`#` title in ALL CAPS, `##` sections in normal case; a single leading emoji marker per section is allowed only in articles with large, sparse sections — ≥ 3 000 characters per H2 on average — and never in numbered `1. 2. 3.` sequences; no emoji in the title or body), **air only before headings — never after**; every list item is its own paragraph starting with `•` or `1.`; no `U+2060` and no `U+200B` anywhere; quote attribution is the **last line inside the `>` block** (`> *— Author, «Work»*`), italic, prefixed with `— `, so that no block gap opens between the quote and the attribution; no hashtag footer.
- Never paste L2 Markdown into the ordinary composer: it renders literal `**` and `#`. Never select rendered Arena chat text as a copy source; produce one Markdown block or an HTML copy page instead.
- Before sending, visually inspect both formatting and paragraph spacing in the Telegram composer.

## Provider boundary

Editorial approval, repository changes, green CI, or a reviewed post do **not** authorize a Telegram provider write. Provider execution remains a separate exact-target operation requiring explicit authorization under the repository-wide `AGENTS.md` safety contract.
