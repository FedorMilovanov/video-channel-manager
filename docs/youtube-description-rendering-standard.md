# YouTube description rendering standard

Project: `legendary-poet` / The Legendary Poet

This document separates three different surfaces that must never share one formatting grammar:

1. Chat/operator handoff.
2. YouTube video descriptions.
3. YouTube comments and pinned comments.

## 1. Video descriptions are generated as plain text

A generated YouTube video-description payload MUST NOT use Markdown-like emphasis markers as formatting.

Forbidden as description formatting:

```text
**bold**
*bold*
_italic_
__bold__
```

They can survive as literal characters in YouTube Studio and therefore are a copy/paste defect.

YouTube Studio supports bold, italic, and strikethrough through its own description editor controls. If rich text is required, the operator applies it in Studio. The generated copy stays plain text.

Correct generated payload:

```text
🕯 О РОМАНЕ
Лишь в 1833 году «Евгений Онегин» впервые появился единым изданием.

🎼 Текст: Александр Сергеевич Пушкин
```

Incorrect generated payload:

```text
🕯 *О РОМАНЕ*
Лишь в **1833 году** «Евгений Онегин» впервые появился единым изданием.

🎼 *Текст:* Александр Сергеевич Пушкин
```

Use short headings, capitalization, emojis when appropriate, paragraph order, and whitespace for hierarchy.

## 2. Chat/operator copy transport

When the user asks only for a finished YouTube description or pinned comment, return the finished copy inside one fenced code block tagged `text`.

The fence exists only so ChatGPT does not consume visible formatting characters and so line breaks copy exactly. The opening and closing fence are never part of the YouTube payload.

Do not backslash-escape `*` or `_`.

If several variants are requested, use one separate `text` block per variant.

## 3. Comments are a separate surface

YouTube comments/pinned comments have their own supported text tags:

```text
*bold text*
_italic text_
-strikethrough text-
```

These rules apply only to comments. Never generalize comment syntax to video descriptions. Never use `**text**` as a universal YouTube bold syntax.

## 4. First paragraph

The first description paragraph should:

- be plain text;
- describe the exact work/video immediately;
- normally contain 2–4 sentences;
- contain no link dump;
- contain no internal placeholders;
- avoid generic openings such as «Это не просто...» unless editorially justified.

## 5. Links

- Keep URLs as visible plain URLs.
- Do not use Markdown links.
- Keep label and URL on one line.
- Include only playlists relevant to the specific video.
- Never invent a playlist or project URL.
- Never mix links from another project profile.
- Never publish operator/admin dashboard URLs.

## 6. Placeholder guard

Publishable copy must contain no unresolved template markers, including angle-bracket placeholders or double-square-bracket placeholders.

Internal drafts may use structured placeholders, but the final copy/paste payload must resolve or remove them before it is called ready.

## 7. The Legendary Poet footer

Baseline public links:

```text
Сайт проекта: https://thelegendarypoet.ru/
VK: https://vk.ru/thelegendarypoet
Telegram: https://t.me/thelegendarypoet
RUTUBE: https://rutube.ru/channel/74579453/
```

Add relevant playlists above this block only when their exact URL is known and they relate to the current video.

## 8. Final preflight for video descriptions

Before returning or publishing final description copy, verify the exact final bytes:

1. No Markdown emphasis markers are being used as description formatting.
2. No Markdown links.
3. No unresolved template placeholders.
4. No cross-project or operator-only links.
5. Playlist links are known and relevant.
6. The first paragraph is concrete and readable.
7. Paragraph spacing is intentional.
8. The copy fits YouTube's current description limit.
9. If this is a ChatGPT handoff, the response uses the required `text` fence, while the fence itself is not part of the payload.

## 9. Platform evidence rule

Do not infer formatting rules from Markdown, old screenshots, or another YouTube surface.

Before changing this contract, check current official YouTube Help. At the time this standard was corrected:

- video-description rich text is applied through Studio editor formatting controls;
- comments support `*bold*`, `_italic_`, and `-strikethrough-` text tags.

If YouTube changes these rules, update this contract first and then update examples/renderers.
