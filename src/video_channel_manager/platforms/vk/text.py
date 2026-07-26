from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

Severity = Literal["warning", "error"]

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_MARKDOWN_LINK_RE = re.compile(r"\[(?P<label>[^\]\n]+)\]\((?P<url>https?://[^)\s]+)\)", re.IGNORECASE)
_DOUBLE_STAR_RE = re.compile(r"(?<!\*)\*\*(?![\s*])(?P<body>[^*\n]*?\S)\*\*(?!\*)")
_SINGLE_STAR_RE = re.compile(r"(?<!\*)\*(?![\s*])(?P<body>[^*\n]*?\S)\*(?!\*)")
_DOUBLE_UNDERSCORE_RE = re.compile(r"(?<![\w_])__(?![\s_])(?P<body>[^_\n]*?\S)__(?![\w_])")
_SINGLE_UNDERSCORE_RE = re.compile(r"(?<![\w_])_(?![\s_])(?P<body>[^_\n]*?\S)_(?![\w_])")
_STRIKETHROUGH_RE = re.compile(r"(?<!~)~~(?![\s~])(?P<body>[^~\n]*?\S)~~(?!~)")
_MULTI_BLANK_RE = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)+")
_HTML_TAG_RE = re.compile(r"</?[A-Za-z][^>\n]*>")
_ZERO_WIDTH = {"\ufeff", "\u200b", "\u2060"}
_LITERAL_TRIPLE_STAR_RE = re.compile(r"(?<!\*)\*{3}(?!\*)")
_DEFAULT_SITE_URL = "https://thelegendarypoet.ru/"
_DEFAULT_BRAND_LINE = "🎧 The Legendary Poet — русская поэзия, музыка и литературные материалы."
_EMPHASIS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("**", _DOUBLE_STAR_RE),
    ("__", _DOUBLE_UNDERSCORE_RE),
    ("~~", _STRIKETHROUGH_RE),
    ("*", _SINGLE_STAR_RE),
    ("_", _SINGLE_UNDERSCORE_RE),
)


@dataclass(frozen=True, slots=True)
class VkTextIssue:
    code: str
    severity: Severity
    message: str
    excerpt: str | None = None


@dataclass(frozen=True, slots=True)
class VkDescriptionRender:
    text: str
    source_sha256: str
    rendered_sha256: str
    removed_emphasis_pairs: int
    converted_markdown_links: int
    removed_zero_width_characters: int
    collapsed_blank_runs: int
    footer_added: bool
    issues: tuple[VkTextIssue, ...]

    @property
    def changed(self) -> bool:
        return self.source_sha256 != self.rendered_sha256

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)


@dataclass(frozen=True, slots=True)
class VkTextCapabilities:
    surface: str
    supports_markdown: bool
    supports_html: bool
    supports_inline_bold: bool
    supports_inline_italic: bool
    supports_plain_urls: bool
    supports_hashtags: bool
    notes: str


VK_VIDEO_DESCRIPTION_CAPABILITIES = VkTextCapabilities(
    surface="vk_video_description",
    supports_markdown=False,
    supports_html=False,
    supports_inline_bold=False,
    supports_inline_italic=False,
    supports_plain_urls=True,
    supports_hashtags=True,
    notes=(
        "VK Video descriptions are treated as plain text. YouTube emphasis markers such as *...* and _..._ "
        "must be removed before publication; visible URLs and hashtags should remain literal."
    ),
)


def _sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _excerpt(value: str, limit: int = 160) -> str:
    compact = " ".join(value.split())
    return compact if len(compact) <= limit else f"{compact[: limit - 1]}…"


def _closing_emphasis_suffix(text: str, match: re.Match[str]) -> str:
    """Return a URL suffix that belongs to an enclosing emphasis span.

    ``https?://\\S+`` deliberately accepts URL underscores and punctuation. It
    can therefore also consume the closing ``*``/``_``/``~~`` of a span such as
    ``*https://example.test/path*``. We only unmask a suffix when the complete
    same-line text proves that a matching emphasis span ends exactly there.
    """

    raw = match.group(0)
    line_start = text.rfind("\n", 0, match.start()) + 1
    candidate = text[line_start : match.end()]
    relative_url_start = match.start() - line_start
    for marker, pattern in _EMPHASIS_PATTERNS:
        if not raw.endswith(marker):
            continue
        for emphasis_match in pattern.finditer(candidate):
            if emphasis_match.end() == len(candidate) and emphasis_match.start() < relative_url_start:
                return marker
    return ""


def _mask_urls(text: str) -> tuple[str, list[tuple[str, str]]]:
    replacements: list[tuple[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        suffix = _closing_emphasis_suffix(text, match)
        original = match.group(0)
        protected = original[: -len(suffix)] if suffix else original
        token = f"\ue100{len(replacements)}\ue101"
        replacements.append((token, protected))
        return f"{token}{suffix}"

    return _URL_RE.sub(replace, text), replacements


def _restore_masks(text: str, replacements: list[tuple[str, str]]) -> str:
    for token, original in replacements:
        text = text.replace(token, original)
    return text


def _strip_emphasis(text: str) -> tuple[str, int]:
    masked, replacements = _mask_urls(text)
    removed = 0

    def strip(match: re.Match[str]) -> str:
        nonlocal removed
        removed += 1
        return match.group("body")

    patterns = (
        _DOUBLE_STAR_RE,
        _DOUBLE_UNDERSCORE_RE,
        _SINGLE_STAR_RE,
        _SINGLE_UNDERSCORE_RE,
        _STRIKETHROUGH_RE,
    )
    for pattern in patterns:
        while True:
            updated, count = pattern.subn(strip, masked)
            masked = updated
            if count == 0:
                break
    return _restore_masks(masked, replacements), removed


def _convert_markdown_links(text: str) -> tuple[str, int]:
    def replace(match: re.Match[str]) -> str:
        label = match.group("label").strip()
        url = match.group("url")
        if not label:
            return url
        separator = " " if label.endswith((":", "：", "—", "–", "-")) else ": "
        return f"{label}{separator}{url}"

    return _MARKDOWN_LINK_RE.subn(replace, text)


def _remove_zero_width(text: str) -> tuple[str, int]:
    removed = sum(text.count(character) for character in _ZERO_WIDTH)
    return "".join(character for character in text if character not in _ZERO_WIDTH), removed


def _normalize_lines(text: str) -> tuple[str, int]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    collapsed = len(_MULTI_BLANK_RE.findall(text))
    text = _MULTI_BLANK_RE.sub("\n\n", text)
    return text.strip(), collapsed


def _remaining_marker_issues(text: str) -> list[VkTextIssue]:
    issues: list[VkTextIssue] = []
    masked, _ = _mask_urls(text)
    without_literal_titles = _LITERAL_TRIPLE_STAR_RE.sub("", masked)

    if "*" in without_literal_titles:
        issues.append(
            VkTextIssue(
                code="literal_asterisk_remaining",
                severity="warning",
                message=(
                    "После очистки остались символы *. VK покажет их буквально; проверьте, являются ли они частью "
                    "названия или незакрытой YouTube-разметкой."
                ),
                excerpt=_excerpt(without_literal_titles),
            )
        )
    if _SINGLE_UNDERSCORE_RE.search(without_literal_titles) or _DOUBLE_UNDERSCORE_RE.search(without_literal_titles):
        issues.append(
            VkTextIssue(
                code="paired_underscore_remaining",
                severity="warning",
                message="После очистки осталась похожая на курсив конструкция с _. VK покажет её буквально.",
                excerpt=_excerpt(without_literal_titles),
            )
        )
    html = _HTML_TAG_RE.search(text)
    if html is not None:
        issues.append(
            VkTextIssue(
                code="html_tag_not_supported",
                severity="warning",
                message="HTML-разметка в обычном описании VK Видео не должна использоваться.",
                excerpt=_excerpt(html.group(0)),
            )
        )
    return issues


def render_vk_video_description(
    source_description: str,
    *,
    site_url: str = _DEFAULT_SITE_URL,
    brand_line: str = _DEFAULT_BRAND_LINE,
) -> VkDescriptionRender:
    """Render a YouTube-oriented description as conservative VK plain text.

    The function preserves wording, paragraphs, visible URLs, hashtags, literal
    triple-star poem titles, and underscores inside URLs/identifiers. It removes
    only paired emphasis syntax that VK Video would otherwise display literally.
    """

    source = str(source_description or "")
    text = unicodedata.normalize("NFC", source)
    text, zero_width_removed = _remove_zero_width(text)
    text, converted_links = _convert_markdown_links(text)
    text, removed_emphasis = _strip_emphasis(text)
    text, collapsed_blank_runs = _normalize_lines(text)

    footer_added = False
    normalized_site = site_url.strip()
    normalized_brand = brand_line.strip()
    if normalized_site and normalized_site not in text:
        footer = "\n".join(part for part in (normalized_brand, f"🌐 {normalized_site}") if part)
        text = f"{text}\n\n{footer}" if text else footer
        footer_added = True

    issues = tuple(_remaining_marker_issues(text))
    return VkDescriptionRender(
        text=text,
        source_sha256=_sha256_text(source),
        rendered_sha256=_sha256_text(text),
        removed_emphasis_pairs=removed_emphasis,
        converted_markdown_links=converted_links,
        removed_zero_width_characters=zero_width_removed,
        collapsed_blank_runs=collapsed_blank_runs,
        footer_added=footer_added,
        issues=issues,
    )


def render_vk_clip_description(
    source_description: str,
    *,
    full_video_url: str | None = None,
    site_url: str = _DEFAULT_SITE_URL,
    max_characters: int = 4000,
) -> VkDescriptionRender:
    """Render plain text for VK Clips and add a full-video route when supplied."""

    if max_characters <= 0:
        raise ValueError("max_characters must be positive")
    base = render_vk_video_description(source_description, site_url=site_url)
    text = base.text
    normalized_full_url: str | None = None
    if full_video_url is not None:
        normalized_full_url = full_video_url.strip()
        parsed = urlsplit(normalized_full_url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            raise ValueError("full_video_url must be an absolute http(s) URL")
    if normalized_full_url and normalized_full_url not in text:
        route = f"▶ Полная версия: {normalized_full_url}"
        text = f"{text}\n\n{route}" if text else route
    issues = list(base.issues)
    if len(text) > max_characters:
        issues.append(
            VkTextIssue(
                code="clip_description_too_long",
                severity="error",
                message=f"Описание клипа содержит {len(text)} символов при лимите политики {max_characters}.",
            )
        )
    return VkDescriptionRender(
        text=text,
        source_sha256=base.source_sha256,
        rendered_sha256=_sha256_text(text),
        removed_emphasis_pairs=base.removed_emphasis_pairs,
        converted_markdown_links=base.converted_markdown_links,
        removed_zero_width_characters=base.removed_zero_width_characters,
        collapsed_blank_runs=base.collapsed_blank_runs,
        footer_added=base.footer_added,
        issues=tuple(issues),
    )


__all__ = [
    "VK_VIDEO_DESCRIPTION_CAPABILITIES",
    "VkDescriptionRender",
    "VkTextCapabilities",
    "VkTextIssue",
    "render_vk_clip_description",
    "render_vk_video_description",
]
