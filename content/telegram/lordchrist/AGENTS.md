# @lordchrist agent entrypoint

This file is the first stop for any agent asked to research, draft, revise, format, or hand off Telegram content for `@lordchrist` / «Господь Бог — Сила Моя».

## Read order

Before writing a rich/explanatory/theological post, read these files in order:

1. `README.md` — scope, evidence/presentation split, and provider boundary.
2. `RICH_EDITORIAL_STANDARD.md` — canonical prose, title, exegesis, length, and formatting contract.
3. `QUOTE_ATTRIBUTION_STANDARD.md` — exact quotation layout and spacing rules.
4. `DIRECT_COPY_TO_TELEGRAM.md` — Android rich-copy transport and `U+2060` spacer behavior.
5. The task-specific research/evidence file, if one exists.

For short quote-lane production, follow `README.md` and `presentation-policy.json`; do not force the rich-article layout onto the short quote lane.

## Precedence

For reader-facing rich posts, presentation authority is:

1. the user's current explicit instruction;
2. `RICH_EDITORIAL_STANDARD.md`;
3. `QUOTE_ATTRIBUTION_STANDARD.md`;
4. `DIRECT_COPY_TO_TELEGRAM.md`;
5. task-specific research/evidence;
6. old drafts/examples/chat history.

Research drafts are evidence inputs, **not presentation authority**. If an old draft shows an English work title, attribution inside a quote block, collapsed spacing, slogan-like prose, or another layout that conflicts with the current standards, re-render it under the current standards instead of copying the old layout.

## Non-negotiable rich-post rules

- Reader-facing title: **bold, ALL CAPS, one concise line**.
- Body: continuous Russian prose, normally multi-sentence paragraphs; no AI slogan ladder.
- Preserve useful content. If the complete reviewed post fits Telegram, **do not shorten it merely to make it look more compact**. Remove repetition or weak wording, not evidence, exegesis, or useful context.
- Telegram hard-length preflight must be run on the exact pasted text. Count line breaks and invisible `U+2060` spacer characters too. Prefer a small safety margin below the platform limit.
- Historical quotations: primary-source verified; editorial Russian translations must retain an exact original/English anchor in evidence.
- Quote entity: quoted words only.
- Attribution: immediately below the quote, outside the quote entity, in *italic*; reader-facing work titles in Russian.
- **Default: air before quotations.** Put one `U+2060` spacer line before a quote after a normal/substantial paragraph.
- Narrow exception only: a genuinely short one-sentence connector that exists solely to introduce the next quote (for example, `Об окончательно отпавших Иоанн говорит иначе:`) stays attached to the quote with no spacer. Do not generalize this exception.
- After quote attribution, restore the normal article gap before the next independent paragraph.
- Manual Android paste: rendered ChatGPT text → Copy → Telegram composer → long-press → system **Paste / «Вставить»**. Never use the keyboard clipboard/history panel for rich posts.
- Before sending, visually inspect both formatting and paragraph spacing in the Telegram composer.

## Provider boundary

Editorial approval, repository changes, green CI, or a reviewed post do **not** authorize a Telegram provider write. Provider execution remains a separate exact-target operation requiring explicit authorization under the repository-wide `AGENTS.md` safety contract.
