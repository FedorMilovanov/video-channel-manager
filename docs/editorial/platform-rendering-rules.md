# Platform Rendering Rules

## Shared rules

All renderers receive the same validated canonical record. They preserve the factual paragraph, source mapping, variation key, question, and semantic link kinds. Renderers may change markup, spacing, link selection, and compactness; they may not invent facts or silently replace the editorial angle.

Every renderer reports character count, link count, layout warnings, orphan labels, and platform errors. Preview is mutation-free.

## YouTube

### Comment

`YouTubeCommentRenderer` produces:

1. a contextual heading with restrained `*bold*` or `_italic_` emphasis;
2. one substantial factual paragraph;
3. one concrete question;
4. two to four `label + URL` lines.

Long-form poetry, covers, and adaptations require a relevant playlist. Short-form records require a full-version route. Site and VK project routes remain required by the current comment standard. More than four decorative markers is rejected.

### Description

`YouTubeDescriptionRenderer` uses the same content blocks with the YouTube emphasis style and a 5,000-character project limit. It is suitable for reviewed description-improvement plans, not automatic replacement of complete existing descriptions.

## VK

VK video descriptions, posts, and comments are treated as plain text. `*`, `_`, Markdown links, zero-width characters, and unsupported HTML must not leak into the final field.

`VKVideoDescriptionRenderer` and `VKPostRenderer` keep every link label and URL on one line. They reject missing site/community routes where those routes are required and warn when a link line is likely to wrap badly on mobile.

Correct:

```text
Сообщество проекта VK: https://vk.com/thelegendarypoet
```

Incorrect:

```text
VK:
https://vk.com/thelegendarypoet
```

The VK renderer strips YouTube emphasis while preserving the literary hierarchy through paragraph order, concise labels, and contextual emoji markers. It does not create large blank gaps or decorative-only lines.

`VKCommentRenderer` intentionally keeps at most two relevant links. It emits a warning when it compacts a larger link set.

## Layout diagnostics

The common preview layer detects:

- orphan or dangling labels;
- a label separated from its URL;
- unusually long URL lines that may wrap badly;
- forbidden colored circles;
- platform length violations;
- duplicate rendered output in a batch.
