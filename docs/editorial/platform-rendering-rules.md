# Platform Rendering Rules

## Shared rules

All renderers receive the same validated canonical record. They preserve the factual paragraph, source mapping, variation key, question, and semantic link kinds. Renderers may change markup, spacing, link selection, and compactness; they may not invent facts or silently replace the editorial angle.

Every renderer reports character count, link count, layout warnings, orphan labels, and platform errors. Preview is mutation-free.

`rendering_metadata.preferred_link_order` may be either one shared list or a mapping with `platform.surface`, platform, and `default` keys. It changes presentation order only; it cannot make an unsuitable link eligible for a platform or bypass required-link validation.

## YouTube

### Comment

`YouTubeCommentRenderer` produces:

1. a contextual heading with restrained `*bold*` or `_italic_` emphasis;
2. one substantial factual paragraph;
3. one concrete question;
4. two to four `label + URL` lines.

Long-form poetry, covers, and adaptations require a relevant playlist. Short-form records require a full-version route. Site and VK project routes remain required by the current comment standard. More than four decorative markers is rejected.

The canonical VK community line is:

```text
*Сообщество проекта в VK:* https://vk.com/thelegendarypoet
```

The historical stored label `*Сообщество проекта VK:*` remains accepted only as migration input. YouTube rendering always normalizes it to the canonical wording. New records, examples, previews, and signed plans must use the canonical output.

### Description

`YouTubeDescriptionRenderer` uses the same content blocks with the YouTube emphasis style and a 5,000-character project limit. It is suitable for reviewed description-improvement plans, not automatic replacement of complete existing descriptions.

## VK

VK video descriptions, posts, and comments are treated as plain text. `*`, `_`, Markdown links, zero-width characters, and unsupported HTML must not leak into an executable plan.

`VKVideoDescriptionRenderer` and `VKPostRenderer` keep every link label and URL on one line. They reject missing site/community routes where those routes are required and warn when a link line is likely to wrap badly on mobile.

Correct:

```text
Сообщество проекта в VK: https://vk.com/thelegendarypoet
```

Incorrect:

```text
VK:
https://vk.com/thelegendarypoet
```

The VK renderer strips paired YouTube emphasis and converts Markdown links when that transformation is deterministic. If HTML tags, unresolved asterisks, or paired underscores remain after fallback conversion, the renderer emits a blocking error rather than allowing literal markup into a VK catalog plan.

The literary hierarchy is preserved through paragraph order, concise labels, and contextual emoji markers. The renderer does not create large blank gaps or decorative-only lines.

`VKCommentRenderer` intentionally keeps at most two relevant links. It emits a warning when it compacts a larger link set.

## Layout diagnostics

The common preview layer detects:

- orphan or dangling labels;
- a label separated from its URL;
- unusually long URL lines that may wrap badly;
- forbidden colored circles;
- unresolved platform markup;
- platform length violations;
- duplicate rendered output in a batch.
