from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Literal

Severity = Literal["error", "warning"]

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
LITERAL_TRIPLE_STAR_RE = re.compile(r"(?<!\*)\*{3}(?!\*)")
NON_MARKER_RE = re.compile(r"https?://\S+|(?<!\*)\*{3}(?!\*)", re.IGNORECASE)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]\n]+\]\(https?://[^)\s]+\)", re.IGNORECASE)
MULTI_BLANK_RE = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)+")
FIRST_PARAGRAPH_RE = re.compile(r"\A(?P<first>.*?)(?P<separator>\n[ \t]*\n|\Z)", re.DOTALL)
PUNCT_OUTSIDE_RE = re.compile(
    r"(?P<span>\*[^*\n]+\*|(?<!\w)_[^_\n]+_(?!\w))(?P<punct>[,.:;!?…])"
)
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
_METADATA_LABELS = {
    "vk",
    "telegram",
    "телеграм",
    "rutube",
    "рутуб",
}
_TERMINAL_PUNCTUATION = ("?", "!", "…", "?»", "!»", "…»")


@dataclass(frozen=True)
class CopyFinding:
    code: str
    severity: Severity
    message: str
    paragraph_index: int | None = None
    excerpt: str | None = None


@dataclass(frozen=True)
class CopyFix:
    code: str
    before: str
    after: str


def _paragraphs(description: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", description.strip()) if part.strip()]


def _excerpt(value: str, limit: int = 140) -> str:
    single_line = " ".join(value.split())
    return single_line if len(single_line) <= limit else f"{single_line[: limit - 1]}…"


def _without_non_markers(text: str) -> str:
    """Remove text fragments whose underscores or stars are not formatting markers."""

    without_urls = URL_RE.sub("", text)
    return LITERAL_TRIPLE_STAR_RE.sub("", without_urls)


def _mask_non_markers(text: str) -> tuple[str, list[tuple[str, str]]]:
    replacements: list[tuple[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        token = f"\ue000{len(replacements)}\ue001"
        replacements.append((token, match.group(0)))
        return token

    return NON_MARKER_RE.sub(replace, text), replacements


def _restore_masks(text: str, replacements: list[tuple[str, str]]) -> str:
    for token, original in replacements:
        text = text.replace(token, original)
    return text


def _contains_emphasis(text: str) -> bool:
    masked, _ = _mask_non_markers(text)
    return BOLD_SPAN_RE.search(masked) is not None or ITALIC_SPAN_RE.search(masked) is not None


def _strip_emphasis_markers(text: str) -> str:
    masked, replacements = _mask_non_markers(text)
    masked = BOLD_SPAN_RE.sub(lambda match: match.group(1), masked)
    masked = ITALIC_SPAN_RE.sub(lambda match: match.group(1), masked)
    return _restore_masks(masked, replacements)


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


def _emphasis_inner(span: str) -> str:
    return span[1:-1].strip()


def _is_metadata_label(inner: str) -> bool:
    lowered = inner.casefold().strip()
    return lowered.startswith("плейлист ") or lowered in _METADATA_LABELS


def _with_punctuation_inside(span: str, punctuation: str) -> str:
    return f"{span[:-1]}{punctuation}{span[-1]}"


def _punctuation_finding(match: re.Match[str]) -> CopyFinding:
    span = match.group("span")
    punctuation = match.group("punct")
    inner = _emphasis_inner(span)
    excerpt = _excerpt(match.group(0))

    if punctuation == ":":
        if _is_metadata_label(inner):
            return CopyFinding(
                "punctuation_outside_emphasis",
                "error",
                "Двоеточие является частью подписи ссылки и должно находиться внутри *...* или _..._.",
                excerpt=excerpt,
            )
        return CopyFinding(
            "colon_after_emphasis_review",
            "warning",
            "Двоеточие после выделения может быть внешней синтаксической связкой. Проверьте контекст вручную.",
            excerpt=excerpt,
        )

    if punctuation == "." and inner.endswith(_TERMINAL_PUNCTUATION):
        return CopyFinding(
            "duplicate_terminal_punctuation",
            "error",
            "После выделенной фразы уже есть ?/!/…; внешнюю точку нужно удалить, а не переносить внутрь.",
            excerpt=excerpt,
        )

    if inner.endswith(_TERMINAL_PUNCTUATION):
        return CopyFinding(
            "punctuation_after_terminal_review",
            "warning",
            "Выделенная фраза уже заканчивается ?/!/…. Внешний знак требует ручной синтаксической проверки.",
            excerpt=excerpt,
        )

    return CopyFinding(
        "punctuation_outside_emphasis",
        "error",
        (
            "Знак сразу после закрывающего * или _. Если он завершает выделенную фразу, "
            "перенесите его внутрь; внешнюю синтаксическую пунктуацию оставьте снаружи."
        ),
        excerpt=excerpt,
    )


def validate_youtube_description(description: str) -> list[CopyFinding]:
    findings: list[CopyFinding] = []
    paragraphs = _paragraphs(description)

    if not description.strip():
        return [CopyFinding("empty_description", "error", "Описание пустое.")]

    first = paragraphs[0] if paragraphs else ""
    if _contains_emphasis(first):
        findings.append(
            CopyFinding(
                "share_preview_emphasis",
                "error",
                (
                    "Первый абзац содержит *...* или _..._. На странице ролика это отображается, "
                    "но SHARE-превью показывает первый абзац без жирного и курсива. Уберите маркеры только здесь."
                ),
                paragraph_index=1,
                excerpt=_excerpt(first),
            )
        )

    text_without_non_markers = _without_non_markers(description)
    if text_without_non_markers.count("*") % 2:
        findings.append(
            CopyFinding("unbalanced_bold", "error", "Нечётное число маркеров *: жирная обёртка не закрыта.")
        )
    if len(_italic_marker_positions(text_without_non_markers)) % 2:
        findings.append(
            CopyFinding("unbalanced_italic", "error", "Обнаружена незакрытая или одиночная курсивная обёртка _.")
        )

    for match in BOLD_SPAN_RE.finditer(text_without_non_markers):
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

    for match in ITALIC_SPAN_RE.finditer(text_without_non_markers):
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

    findings.extend(
        _punctuation_finding(match) for match in PUNCT_OUTSIDE_RE.finditer(text_without_non_markers)
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
                "Обнаружено больше одной пустой строки между смысловыми блоками.",
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


def autofix_youtube_description(description: str) -> tuple[str, list[CopyFix]]:
    """Apply only deterministic copy fixes that preserve wording and editorial meaning."""

    updated = description
    fixes: list[CopyFix] = []

    first_match = FIRST_PARAGRAPH_RE.match(updated)
    if first_match is not None:
        first = first_match.group("first")
        separator = first_match.group("separator")
        clean_first = _strip_emphasis_markers(first)
        if clean_first != first:
            fixes.append(CopyFix("share_preview_emphasis", first, clean_first))
            updated = f"{clean_first}{separator}{updated[first_match.end():]}"

    def trim_bold(match: re.Match[str]) -> str:
        inner = match.group(1)
        if inner == inner.strip():
            return match.group(0)
        after = f"*{inner.strip()}*"
        fixes.append(CopyFix("bold_edge_space", match.group(0), after))
        return after

    def trim_italic(match: re.Match[str]) -> str:
        inner = match.group(1)
        if inner == inner.strip():
            return match.group(0)
        after = f"_{inner.strip()}_"
        fixes.append(CopyFix("italic_edge_space", match.group(0), after))
        return after

    masked, replacements = _mask_non_markers(updated)
    masked = BOLD_SPAN_RE.sub(trim_bold, masked)
    masked = ITALIC_SPAN_RE.sub(trim_italic, masked)
    updated = _restore_masks(masked, replacements)

    def fix_punctuation(match: re.Match[str]) -> str:
        span = match.group("span")
        punctuation = match.group("punct")
        inner = _emphasis_inner(span)
        before = match.group(0)

        if punctuation == ":":
            if not _is_metadata_label(inner):
                return before
            after = _with_punctuation_inside(span, punctuation)
        elif punctuation == "." and inner.endswith(_TERMINAL_PUNCTUATION):
            after = span
        elif inner.endswith(_TERMINAL_PUNCTUATION):
            return before
        else:
            after = _with_punctuation_inside(span, punctuation)

        if after != before:
            fixes.append(CopyFix("punctuation", before, after))
        return after

    updated = PUNCT_OUTSIDE_RE.sub(fix_punctuation, updated)

    def normalize_blank_lines(match: re.Match[str]) -> str:
        before = match.group(0)
        after = "\n\n"
        fixes.append(CopyFix("multiple_blank_lines", before, after))
        return after

    updated = MULTI_BLANK_RE.sub(normalize_blank_lines, updated)
    return updated, fixes
