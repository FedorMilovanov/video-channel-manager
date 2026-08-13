from __future__ import annotations

import re

from video_channel_manager.editorial.youtube_copy import CopyFinding, CopyFix

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_MARKDOWN_LINK_RE = re.compile(r"\[[^\]\n]+\]\(https?://[^)\s]+\)", re.IGNORECASE)
_DOUBLE_STAR_RE = re.compile(r"(?<!\*)\*\*([^*\n]+)\*\*(?!\*)")
_SINGLE_STAR_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_DOUBLE_UNDERSCORE_RE = re.compile(r"(?<!_)__([^_\n]+)__(?!_)")
_SINGLE_UNDERSCORE_RE = re.compile(r"(?<![\w_])_([^_\n]+)_(?![\w_])")
_PLACEHOLDER_RE = re.compile(r"\[\[[^\]\n]+\]\]")
_MULTI_BLANK_RE = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)+")
_LITERAL_TRIPLE_STAR_RE = re.compile(r"(?<!\*)\*{3}(?!\*)")


def _mask_safe_literals(text: str) -> tuple[str, list[tuple[str, str]]]:
    replacements: list[tuple[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        token = f"\ue000{len(replacements)}\ue001"
        replacements.append((token, match.group(0)))
        return token

    masked = _URL_RE.sub(replace, text)
    masked = _LITERAL_TRIPLE_STAR_RE.sub(replace, masked)
    return masked, replacements


def _restore(text: str, replacements: list[tuple[str, str]]) -> str:
    for token, original in replacements:
        text = text.replace(token, original)
    return text


def _contains_emphasis(text: str) -> bool:
    masked, _ = _mask_safe_literals(text)
    return any(
        pattern.search(masked)
        for pattern in (_DOUBLE_STAR_RE, _DOUBLE_UNDERSCORE_RE, _SINGLE_STAR_RE, _SINGLE_UNDERSCORE_RE)
    )


def validate_youtube_description(description: str) -> list[CopyFinding]:
    findings: list[CopyFinding] = []
    if not description.strip():
        return [CopyFinding("empty_description", "error", "Описание пустое.")]

    if _contains_emphasis(description):
        findings.append(
            CopyFinding(
                "markdown_emphasis_in_description",
                "error",
                "Описание видео должно быть plain text: rich-text оформление применяется в YouTube Studio.",
            )
        )

    for match in _MARKDOWN_LINK_RE.finditer(description):
        findings.append(
            CopyFinding(
                "hidden_markdown_link",
                "error",
                "YouTube-описание должно содержать открытый URL, а не Markdown-ссылку.",
                excerpt=match.group(0),
            )
        )

    if "<" in description or ">" in description:
        findings.append(
            CopyFinding(
                "invalid_angle_bracket",
                "error",
                "В описании обнаружены угловые скобки; удалите неразрешённый placeholder или недопустимый символ.",
            )
        )

    placeholder = _PLACEHOLDER_RE.search(description)
    if placeholder is not None:
        findings.append(
            CopyFinding(
                "unresolved_template_placeholder",
                "error",
                "В описании остался неразрешённый шаблонный placeholder.",
                excerpt=placeholder.group(0),
            )
        )

    if _MULTI_BLANK_RE.search(description):
        findings.append(
            CopyFinding(
                "multiple_blank_lines",
                "warning",
                "Обнаружено больше одной пустой строки между смысловыми блоками.",
            )
        )

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", description.strip()) if part.strip()]
    for index, paragraph in enumerate(paragraphs, start=1):
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        verse_like = len(lines) >= 6 and max((len(line) for line in lines), default=0) <= 180
        if len(paragraph) > 700 and not verse_like:
            findings.append(
                CopyFinding(
                    "long_paragraph",
                    "warning",
                    "Плотный прозаический абзац длиннее 700 символов и требует ручной проверки переносов.",
                    paragraph_index=index,
                )
            )

    return findings


def autofix_youtube_description(description: str) -> tuple[str, list[CopyFix]]:
    masked, replacements = _mask_safe_literals(description)
    fixes: list[CopyFix] = []

    def strip(pattern: re.Pattern[str], text: str) -> str:
        def replace(match: re.Match[str]) -> str:
            before = match.group(0)
            after = match.group(1)
            fixes.append(CopyFix("markdown_emphasis_removed", before, after))
            return after

        return pattern.sub(replace, text)

    for pattern in (_DOUBLE_STAR_RE, _DOUBLE_UNDERSCORE_RE, _SINGLE_STAR_RE, _SINGLE_UNDERSCORE_RE):
        masked = strip(pattern, masked)
    updated = _restore(masked, replacements)

    def normalize(match: re.Match[str]) -> str:
        fixes.append(CopyFix("multiple_blank_lines", match.group(0), "\n\n"))
        return "\n\n"

    updated = _MULTI_BLANK_RE.sub(normalize, updated)
    return updated, fixes


__all__ = ["CopyFinding", "CopyFix", "autofix_youtube_description", "validate_youtube_description"]
