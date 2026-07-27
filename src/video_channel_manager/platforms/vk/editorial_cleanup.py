from __future__ import annotations

import re
import unicodedata
from typing import Any

from video_channel_manager.platforms.vk.text_writer import canonical_vk_text

_ZERO_WIDTH = frozenset({"\ufeff", "\u200b", "\u2060", "\u2068", "\u2069"})
_URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
_PLAYLIST_RE = re.compile(
    r"https?://(?:www\.)?youtube\.com/playlist\?list=([A-Za-z0-9_-]+)(?:[^\s]*)?",
    re.IGNORECASE,
)
_YOUTUBE_VIDEO_RE = re.compile(
    r"https?://(?:www\.)?youtube\.com/(?:watch\?v=|shorts/)([A-Za-z0-9_-]{6,})(?:[^\s]*)?"
    r"|https?://youtu\.be/([A-Za-z0-9_-]{6,})(?:[^\s]*)?",
    re.IGNORECASE,
)
_FOOTER_LABEL_RE = re.compile(
    r"\b(?:VK|ВК|Telegram|Телеграм|RUTUBE|RuTube|Рутуб|YouTube|Ютуб)\s*:\s*",
    re.IGNORECASE,
)
_LEGACY_BRAND_RE = re.compile(
    r"The Legendary Poet\s*[-—]\s*"
    r"(?:поэзия, история, AI-музыка, голосовые эксперименты и визуальные реконструкции|"
    r"поэзия, музыка и литературные материалы)\.?",
    re.IGNORECASE,
)
FOOTER_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^\s*\*?(?:VK|ВК)\*?\s*:\s*https?://(?:www\.)?vk\.com/thelegendarypoet/?\s*$",
        r"^\s*\*?(?:Telegram|Телеграм|Канал в Телеграм с MP3)\*?\s*:\s*https?://t\.me/thelegendarypoet/?\s*$",
        r"^\s*\*?(?:RUTUBE|RuTube|Рутуб)\*?\s*:\s*https?://rutube\.ru/channel/74579453/?\s*$",
        r"^\s*\*?(?:YouTube|Ютуб|Полное собрание всех видео пока только на YOuTube)\*?\s*:\s*"
        r"https?://(?:www\.)?youtube\.com/@TheLegendaryPoet(?:/playlists)?/?\s*$",
        r"^\s*(?:🌐\s*)?(?:Сайт(?: The Legendary Poet)?\s*:\s*)?"
        r"https?://thelegendarypoet(?:\.ru)?/?\s*$",
        r"^\s*🎧\s*The Legendary Poet\s*[-—]\s*"
        r"русская поэзия, музыка и литературные материалы\.?\s*$",
        r"^\s*The Legendary Poet\s*[-—]\s*поэзия, история, AI-музыка, "
        r"голосовые эксперименты и визуальные реконструкции\.?\s*$",
        r"^\s*🎧\s*(?:T|The)?\s*$",
    )
)


def clean_vk_title(value: str, override: str | None = None) -> str:
    if override is not None:
        return canonical_vk_text(override)
    text = unicodedata.normalize("NFC", str(value or ""))
    text = "".join(character for character in text if character not in _ZERO_WIDTH)
    for pattern in (
        r"\s*[@#]TheLegendaryPoet\b",
        r"\s*@LegendaryPoet\b",
        r"\s*#TheEpicPoet\b",
        r"\s*#Shorts\b",
    ):
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\bFull Version\s*([1-9]\d*)\b",
        lambda match: f"ПОЛНАЯ ВЕРСИЯ {match.group(1)}",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bVersion\s*([1-9]\d*)\b",
        lambda match: f"ВЕРСИЯ {match.group(1)}",
        text,
        flags=re.IGNORECASE,
    )
    text = text.replace("Михал Лермонтов", "Михаил Лермонтов")
    text = re.sub(r"\bЧерный\b", "Чёрный", text)
    text = re.sub(r"\bDj\b", "DJ", text)
    text = re.sub(r"\b4к\b", "4K", text, flags=re.IGNORECASE)
    text = text.replace(" — ", " - ").replace(" – ", " - ")
    return canonical_vk_text(re.sub(r"\s{2,}", " ", text).strip(" -"))


def _outside_urls(value: str, transform: Any) -> str:
    result: list[str] = []
    cursor = 0
    for match in _URL_RE.finditer(value):
        result.extend((transform(value[cursor : match.start()]), match.group(0)))
        cursor = match.end()
    result.append(transform(value[cursor:]))
    return "".join(result)


def _replace_urls(value: str, policy: dict[str, Any]) -> str:
    playlists = {
        str(key): str(url)
        for key, url in dict(policy.get("playlist_replacements") or {}).items()
    }
    videos = {
        str(key): str(url)
        for key, url in dict(policy.get("youtube_video_replacements") or {}).items()
    }
    value = _PLAYLIST_RE.sub(
        lambda match: playlists.get(match.group(1), match.group(0)),
        value,
    )
    value = re.sub(
        r"https?://(?:www\.)?youtube\.com/(?:watch\?v=|shorts/)"
        r"([A-Za-z0-9_-]{6,})(?:[^\s]*)?",
        lambda match: videos.get(match.group(1), match.group(0)),
        value,
        flags=re.IGNORECASE,
    )
    return re.sub(
        r"https?://youtu\.be/([A-Za-z0-9_-]{6,})(?:[^\s]*)?",
        lambda match: videos.get(match.group(1), match.group(0)),
        value,
        flags=re.IGNORECASE,
    )


def _cap_hashtags(value: str, maximum: int) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for line in value.splitlines():
        output: list[str] = []
        for token in line.split():
            if token.startswith("#") and len(token) > 1:
                key = token.rstrip(".,;:").casefold()
                if key in seen or len(seen) >= maximum:
                    continue
                seen.add(key)
            output.append(token)
        lines.append(" ".join(output))
    return "\n".join(lines)


def _hashtag_count(value: str) -> int:
    return len(
        {
            token.rstrip(".,;:").casefold()
            for token in value.split()
            if token.startswith("#") and len(token) > 1
        }
    )


def clean_vk_description(value: str, policy: dict[str, Any]) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    text = "".join(character for character in text if character not in _ZERO_WIDTH)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("https://thelegendarypoet\n", "https://thelegendarypoet.ru/\n")
    text = text.replace("https://thelegendarypoet ", "https://thelegendarypoet.ru/ ")
    text = _replace_urls(text, policy)
    text = _outside_urls(
        text,
        lambda part: part.replace("*", "").replace("`", "").replace("_", ""),
    )
    text = re.sub(r"^[━─═—-]{15,}\s*$", "━━━━━━━━━━━━━━━", text, flags=re.MULTILINE)
    text = "\n".join(
        line.rstrip()
        for line in text.splitlines()
        if not any(pattern.match(line) for pattern in FOOTER_PATTERNS)
    )
    text = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text).strip()
    settings = dict(policy.get("description_policy") or {})
    text = _cap_hashtags(text, int(settings.get("max_hashtags", 10)))
    footer = canonical_vk_text(str(settings.get("canonical_footer") or ""))
    return canonical_vk_text(f"{text}\n\n{footer}" if text and footer else text or footer)


def description_semantic_body(value: str, policy: dict[str, Any]) -> str:
    """Return content-only text for fail-closed technical-cleanup comparison.

    URLs, hashtags, known legacy/canonical footer material, Markdown markers,
    decorative rules, whitespace, and zero-width characters are excluded. Any
    remaining word or punctuation change is considered editorial and must block
    the automatic description wave.
    """

    text = unicodedata.normalize("NFC", str(value or ""))
    text = "".join(character for character in text if character not in _ZERO_WIDTH)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    footer = canonical_vk_text(
        str(dict(policy.get("description_policy") or {}).get("canonical_footer") or "")
    )
    footer_lines = {line.strip() for line in footer.splitlines() if line.strip()}
    output: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in footer_lines or any(pattern.match(line) for pattern in FOOTER_PATTERNS):
            continue
        if re.fullmatch(r"[━─═—-]{10,}", stripped):
            continue
        body = _URL_RE.sub("", line)
        body = body.replace("*", "").replace("`", "").replace("_", "")
        body = _FOOTER_LABEL_RE.sub("", body)
        body = _LEGACY_BRAND_RE.sub("", body)
        tokens = [
            token
            for token in body.split()
            if not (token.startswith("#") and len(token) > 1)
        ]
        cleaned = " ".join(tokens).strip()
        if cleaned:
            output.append(cleaned)
    return re.sub(r"\s+", " ", " ".join(output)).strip()


def description_change_reasons(
    before: str,
    after: str,
    policy: dict[str, Any],
) -> list[str]:
    """Describe the deterministic, non-editorial changes in a description."""

    reasons: list[str] = []
    settings = dict(policy.get("description_policy") or {})
    mapped_video_ids = set(dict(policy.get("youtube_video_replacements") or {}))
    canonical_footer = canonical_vk_text(str(settings.get("canonical_footer") or ""))
    if any(character in before for character in _ZERO_WIDTH):
        reasons.append("remove_zero_width")
    if "\r" in before:
        reasons.append("normalize_line_endings")
    if "https://thelegendarypoet\n" in before or "https://thelegendarypoet " in before:
        reasons.append("repair_site_url")
    if _PLAYLIST_RE.search(before):
        reasons.append("replace_youtube_playlist")
    for match in _YOUTUBE_VIDEO_RE.finditer(before):
        video_id = match.group(1) or match.group(2)
        if video_id in mapped_video_ids:
            reasons.append("replace_own_youtube_video")
            break
    if any(marker in _URL_RE.sub("", before) for marker in ("*", "`", "_")):
        reasons.append("remove_markdown_markers")
    if any(any(pattern.match(line) for pattern in FOOTER_PATTERNS) for line in before.splitlines()):
        reasons.append("replace_legacy_footer")
    if _LEGACY_BRAND_RE.search(before):
        reasons.append("replace_legacy_brand_block")
    if _hashtag_count(before) > int(settings.get("max_hashtags", 10)):
        reasons.append("cap_hashtags")
    if re.search(r"^[━─═—-]{15,}\s*$", before, flags=re.MULTILINE):
        reasons.append("normalize_divider")
    if canonical_footer and canonical_footer not in canonical_vk_text(before):
        reasons.append("add_canonical_footer")
    if canonical_vk_text(before) != canonical_vk_text(after) and not reasons:
        reasons.append("normalize_whitespace")
    return sorted(set(reasons))


__all__ = [
    "clean_vk_description",
    "clean_vk_title",
    "description_change_reasons",
    "description_semantic_body",
]
