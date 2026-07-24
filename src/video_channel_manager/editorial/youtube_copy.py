from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Literal

Severity = Literal["error", "warning"]

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]\n]+\]\(https?://[^)\s]+\)", re.IGNORECASE)
MULTI_BLANK_RE = re.compile(r"\n{3,}")
PUNCT_OUTSIDE_RE = re.compile(r"(?:\*[^*\n]+\*|(?<!\w)_[^_\n]+_(?!\w))[,.:;!?…]")
BOLD_SPAN_RE = re.compile(r"\*([^*\n]*)\*")
ITALIC_SPAN_RE = re.compile(r"(?<!\w)_([^_\n]+)_(?!\w)")

_METADATA_PREFIXES = (
    "*the legendary poet*",
    "🎧 *the legendary poet*",
    "*плейлист ",
    "*vk:*",
    "*telegram:*",
    "*rutube:*",
    "#",
)


@dataclass(frozen=True)
class CopyFinding:
    code: str
    severity: Severity
    message: str
    paragraph_index: int | None = None
    excerpt: str | None = None


def _paragraphs(description: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", description.strip()) if part.strip()]


def _excerpt(value: str, limit: int = 140) -> str:
    single_line = " ".join(value.split())
    return single_line if len(single_line) <= limit else f"{single_line[: limit - 1]}…"


def _is_emoji(character: str) -> bool:
    """Recognize leading emoji without treating box-drawing separators as emoji."""

    if not character:
        return False
    codepoint = ord(character)
    return (
        0x1F000 <= codepoint <= 0x1FAFF
        or 0x2600 <= codepoint <= 0x27BF
        or 0x2300 <= codepoint <= 0x23FF
        or 0x2B00 <= codepoint <= 0x2BFF
    )


def _leading_emoji(paragraph: str) -> str | None:
    stripped = paragraph.lstrip()
    return stripped[0] if stripped and _is_emoji(stripped[0]) else None


def _is_metadata_paragraph(paragraph: str) -> bool:
    lowered = paragraph.casefold().lstrip()
    return any(lowered.startswith(prefix) for prefix in _METADATA_PREFIXES)


def _is_long_prose_paragraph(paragraph: str) -> bool:
    """Flag dense prose, not verse blocks or hashtag-only metadata."""

    if len(paragraph) <= 700 or _is_metadata_paragraph(paragraph):
        return False
    lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
    if len(lines) >= 6 and max((len(line) for line in lines), default=0) <= 180:
        return False
    return True


def _italic_marker_positions(text: str) -> list[int]:
    positions: list[int] = []
    for index, character in enumerate(text):
        if character != "_":
            continue
        previous = text[index - 1] if index else ""
        following = text[index + 1] if index + 1 < len(text) else ""
        opening = (not previous or not previous.isalnum()) and bool(following and not following.isspace())
        closing = bool(previous and not previous.isspace()) and (not following or not following.isalnum())
        if opening or closing:
            positions.append(index)
    return positions


def validate_youtube_description(description: str) -> list[CopyFinding]:
    findings: list[CopyFinding] = []
    paragraphs = _paragraphs(description)

    if not description.strip():
        return [CopyFinding("empty_description", "error", "Описание пустое.")]

    first = paragraphs[0] if paragraphs else ""
    first_without_urls = URL_RE.sub("", first)
    if "*" in first_without_urls or "_" in first_without_urls:
        findings.append(
            CopyFinding(
                "first_paragraph_formatting",
                "error",
                "Первый абзац содержит * или _ вне URL. По стандарту превью он должен быть без форматирования.",
                paragraph_index=1,
                excerpt=_excerpt(first),
            )
        )

    text_without_urls = URL_RE.sub("", description)
    if text_without_urls.count("*") % 2:
        findings.append(CopyFinding("unbalanced_bold", "error", "Нечётное число маркеров *: жирная обёртка не закрыта."))
    if len(_italic_marker_positions(text_without_urls)) % 2:
        findings.append(
            CopyFinding("unbalanced_italic", "error", "Обнаружена незакрытая или одиночная курсивная обёртка _.")
        )

    for match in BOLD_SPAN_RE.finditer(description):
        inner = match.group(1)
        if inner != inner.strip():
            findings.append(
                CopyFinding(
                    "bold_edge_space",
                    "error",
                    "Внутри края жирной обёртки есть пробел.",
                    excerpt=_excerpt(match.group(0)),
                )
            )

    for match in ITALIC_SPAN_RE.finditer(text_without_urls):
        inner = match.group(1)
        if inner != inner.strip():
            findings.append(
                CopyFinding(
                    "italic_edge_space",
                    "error",
                    "Внутри края курсивной обёртки есть пробел.",
                    excerpt=_excerpt(match.group(0)),
                )
            )

    for match in PUNCT_OUTSIDE_RE.finditer(text_without_urls):
        findings.append(
            CopyFinding(
                "punctuation_outside_emphasis",
                "error",
                "Знак сразу после закрывающего * или _. Если он завершает выделенную фразу, перенесите его внутрь; внешнюю синтаксическую пунктуацию оставьте снаружи.",
                excerpt=_excerpt(match.group(0)),
            )
        )

    for match in MARKDOWN_LINK_RE.finditer(description):
        findings.append(
            CopyFinding(
                "hidden_markdown_link",
                "error",
                "YouTube-описание должно содержать открытый URL, а не Markdown-ссылку.",
                excerpt=_excerpt(match.group(0)),
            )
        )

    if MULTI_BLANK_RE.search(description):
        findings.append(
            CopyFinding(
                "multiple_blank_lines",
                "warning",
                "Обнаружены три или более перевода строки подряд.",
            )
        )

    for index, paragraph in enumerate(paragraphs, start=1):
        if _is_long_prose_paragraph(paragraph):
            findings.append(
                CopyFinding(
                    "long_paragraph",
                    "warning",
                    "Плотный прозаический абзац длиннее 700 символов и требует ручной проверки переносов.",
                    paragraph_index=index,
                    excerpt=_excerpt(paragraph),
                )
            )

    body_paragraphs = [paragraph for paragraph in paragraphs if not _is_metadata_paragraph(paragraph)]
    leading = [_leading_emoji(paragraph) for paragraph in body_paragraphs]
    leading_emojis = [emoji for emoji in leading if emoji is not None]

    if len(body_paragraphs) >= 4 and len(leading_emojis) == len(body_paragraphs):
        findings.append(
            CopyFinding(
                "emoji_every_paragraph",
                "warning",
                "Каждый смысловой абзац начинается с эмодзи. Проверьте, не стало ли оформление механическим.",
            )
        )
    elif len(body_paragraphs) >= 5 and len(leading_emojis) / len(body_paragraphs) >= 0.8:
        findings.append(
            CopyFinding(
                "emoji_density_high",
                "warning",
                "Эмодзи стоят перед 80% или более смысловых абзацев. Нужна редакционная проверка плотности.",
            )
        )

    repeated = Counter(leading_emojis)
    if repeated and repeated.most_common(1)[0][1] >= 3:
        emoji, count = repeated.most_common(1)[0]
        findings.append(
            CopyFinding(
                "emoji_repeated_mechanically",
                "warning",
                f"Один и тот же начальный эмодзи {emoji} повторён {count} раз(а).",
            )
        )

    return findings
