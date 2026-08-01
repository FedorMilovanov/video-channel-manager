# Platform Rendering Rules

## Shared rules

All renderers receive the same validated canonical record. They preserve the factual paragraph, source mapping, variation key, question, and semantic link kinds. Renderers may change markup, spacing, link selection, and compactness; they may not invent facts or silently replace the editorial angle.

Every canonical record belongs to exactly one project profile:

- `lord-god-strength` — Господь Бог — Сила Моя;
- `legendary-poet` — The Legendary Poet — Легендарный Поэт.

The project is selected by explicit `project_key` and checked against the registered YouTube channel ID. A record cannot use a site or VK link from the other project. Account aliases never determine the project.

Every renderer reports character count, link count, layout warnings, orphan labels, and platform errors. Preview is mutation-free.

`rendering_metadata.preferred_link_order` may be either one shared list or a mapping with `platform.surface`, platform, and `default` keys. It changes presentation order only; it cannot make an unsuitable link eligible for a platform or bypass required-link validation.

The canonical identity and link profiles are documented in [`../operations/project-identity-registry.md`](../operations/project-identity-registry.md).

## YouTube

### Comment

`YouTubeCommentRenderer` produces:

1. a contextual heading with restrained `*bold*` or `_italic_` emphasis;
2. one substantial factual paragraph;
3. one concrete question;
4. two to four `label + URL` lines.

Long-form poetry, covers, and adaptations require a relevant playlist. Short-form records require a full-version route. Site and VK project routes remain required where the selected content profile requires them. More than four decorative markers is rejected.

The canonical VK label is project-neutral:

```text
*Сообщество проекта в VK:* [registered VK URL for record.project_key]
```

The historical stored label `*Сообщество проекта VK:*` remains accepted only as migration input. YouTube rendering always normalizes it to the canonical wording. New records, examples, previews, and signed plans must use the canonical output.

Examples:

```text
*Сообщество проекта в VK:* https://vk.ru/the_lord_god_is_my_strength
```

```text
*Сообщество проекта в VK:* https://vk.com/thelegendarypoet
```

A single rendered record may contain only one of those project profiles.

### Description

`YouTubeDescriptionRenderer` uses the same content blocks with the YouTube emphasis style and a 5,000-character project limit. It is suitable for reviewed description-improvement plans, not automatic replacement of complete existing descriptions.

A project footer is assembled only from the selected project's registered links. Relevant playlist links still require exact source or snapshot evidence; they are not guessed from titles.

## VK

VK video descriptions, posts, and comments are treated as plain text. `*`, `_`, Markdown links, zero-width characters, and unsupported HTML must not leak into an executable plan.

`VKVideoDescriptionRenderer` and `VKPostRenderer` keep every link label and URL on one line. They reject missing project routes where those routes are required and warn when a link line is likely to wrap badly on mobile.

Correct:

```text
Сообщество проекта в VK: https://vk.ru/the_lord_god_is_my_strength
```

or, for the separate poet project:

```text
Сообщество проекта в VK: https://vk.com/thelegendarypoet
```

Incorrect:

```text
VK:
https://vk.ru/the_lord_god_is_my_strength
```

The VK renderer strips paired YouTube emphasis and converts Markdown links when that transformation is deterministic. If HTML tags, unresolved asterisks, or paired underscores remain after fallback conversion, the renderer emits a blocking error rather than allowing literal markup into a VK catalog plan.

The literary or theological hierarchy is preserved through paragraph order, concise labels, and contextual markers. The renderer does not create large blank gaps or decorative-only lines.

`VKCommentRenderer` intentionally keeps at most two relevant links. It emits a warning when it compacts a larger link set.

## Project link enforcement

- `site` and `vk` link kinds must belong to `record.project_key`.
- A URL registered to the other project is rejected even when it is also placed in the source ledger.
- Source-backed primary texts, articles, originals, full versions, and playlist links remain allowed when they are not registered as another project's project link.
- Unknown project links fail closed.
- Cross-project promotion requires a separately reviewed operation and is not enabled by the default canonical schema.

## Layout diagnostics

The common preview layer detects:

- orphan or dangling labels;
- a label separated from its URL;
- unusually long URL lines that may wrap badly;
- forbidden colored circles;
- unresolved platform markup;
- platform length violations;
- duplicate rendered output in a batch;
- project/channel identity mismatches;
- links that belong to another project profile.
