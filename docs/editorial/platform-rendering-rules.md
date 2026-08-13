# Platform Rendering Rules

## Shared rules

All renderers receive the same validated canonical record. They preserve factual content, source mapping, variation key, question, and semantic link kinds. Renderers may change markup, spacing, link selection, and compactness; they may not invent facts or silently replace the editorial angle.

Every canonical record belongs to exactly one project profile:

- `lord-god-strength` — Господь Бог — Сила Моя;
- `legendary-poet` — The Legendary Poet — Легендарный Поэт.

Project identity is selected by explicit `project_key` and checked against the registered provider IDs. A record cannot use project links from another profile.

## Chat/operator handoff

Chat presentation is not provider markup.

When the user asks only for a finished YouTube description or pinned comment, present the exact copy inside one fenced `text` code block. The fence is transport-only and is never included in provider payload bytes.

Do not add prose before or after that block unless the user asked for explanation. Do not backslash-escape visible `*` or `_` characters.

## YouTube

### Video description

`YouTubeDescriptionRenderer` produces plain-text copy/paste payload.

It MUST NOT use Markdown-like emphasis markers (`**...**`, `*...*`, `_..._`, `__...__`) as a substitute for YouTube Studio rich text. Studio formatting is a UI operation and is not encoded by these markers in generated description copy.

Use paragraph order, short headings, capitalization, restrained emojis, and whitespace to create hierarchy.

The renderer must also reject:

- Markdown links instead of visible URLs;
- unresolved template placeholders;
- operator/admin URLs in public copy;
- project-link identity mismatches;
- platform length violations.

Relevant playlist links require exact known URLs and relevance to the current video. Do not dump every available playlist into every description.

### Comment / pinned comment

`YouTubeCommentRenderer` is a separate surface. YouTube comments support text tags such as:

```text
*bold text*
_italic text_
-strikethrough text-
```

Those comment tags MUST NOT be generalized to video descriptions. `**...**` is not the canonical bold syntax for comments.

A comment renderer may use restrained emphasis, one substantial factual paragraph, one concrete question, and a compact relevant link set.

## VK

VK video descriptions, posts, and comments are treated as plain text. Markdown emphasis, Markdown links, zero-width characters, and unsupported HTML must not leak into executable plans.

`VKVideoDescriptionRenderer` and `VKPostRenderer` keep each link label and URL on one line. They reject missing project routes where required and warn when a link line is likely to wrap badly on mobile.

Correct:

```text
Сообщество проекта в VK: https://vk.ru/the_lord_god_is_my_strength
```

or, for the separate poet project:

```text
Сообщество проекта в VK: https://vk.ru/thelegendarypoet
```

The literary or theological hierarchy is preserved through paragraph order, concise labels, and contextual markers rather than platform-incompatible markup.

`VKCommentRenderer` intentionally keeps at most two relevant links and warns when it compacts a larger link set.

## Project link enforcement

- `site` and `vk` link kinds must belong to `record.project_key`.
- A URL registered to another project is rejected even if it appears in a source ledger.
- Source-backed primary texts, articles, originals, full versions, and playlist links remain allowed when they are not another project's project links.
- Unknown project links fail closed.
- Cross-project promotion requires a separately reviewed operation.

## Layout and publishability diagnostics

The common preview/preflight layer checks for:

- orphan or dangling labels;
- label separated from its URL;
- malformed or unsupported platform markup;
- unresolved template placeholders;
- platform length violations;
- duplicate rendered output in a batch;
- project/channel identity mismatches;
- links from another project profile;
- operator/admin links in public output.

Provider-specific formatting rules must be sourced from current platform documentation rather than copied from another surface.
