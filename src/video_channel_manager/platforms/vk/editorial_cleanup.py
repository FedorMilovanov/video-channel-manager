from __future__ import annotations

import re
import unicodedata
from typing import Any

from video_channel_manager.platforms.vk.text_writer import canonical_vk_text

_ZERO_WIDTH = frozenset({"\ufeff", "\u200b", "\u2060", "\u2068", "\u2069"})
_URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
FOOTER_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^\s*\*?(?:VK|ВК)\*?\s*:\s*https?://(?:www\.)?vk\.com/thelegendarypoet/?\s*$",
        r"^\s*\*?(?:Telegram|Телеграм|Канал в Телеграм с MP3)\*?\s*:\s*https?://t\.me/thelegendarypoet/?\s*$",
        r"^\s*\*?(?:RUTUBE|RuTube|Рутуб)\*?\s*:\s*https?://rutube\.ru/channel/74579453/?\s*$",
        r"^\s*\*?(?:YouTube|Ютуб|Полное собрание всех видео пока только на YOuTube)\*?\s*:\s*https?://(?:www\.)?youtube\.com/@TheLegendaryPoet(?:/playlists)?/?\s*$",
        r"^\s*(?:🌐\s*)?(?:Сайт(?: The Legendary Poet)?\s*:\s*)?https?://thelegendarypoet(?:\.ru)?/?\s*$",
        r"^\s*🎧\s*The Legendary Poet\s*[-—]\s*русская поэзия, музыка и литературные материалы\.?\s*$",
        r"^\s*The Legendary Poet\s*[-—]\s*поэзия, история, AI-музыка, голосовые эксперименты и визуальные реконструкции\.?\s*$",
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
    playlists = {str(key): str(url) for key, url in dict(policy.get("playlist_replacements") or {}).items()}
    videos = {str(key): str(url) for key, url in dict(policy.get("youtube_video_replacements") or {}).items()}
    value = re.sub(
        r"https?://(?:www\.)?youtube\.com/playlist\?list=([A-Za-z0-9_-]+)(?:[^\s]*)?",
        lambda match: playlists.get(match.group(1), match.group(0)),
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"https?://(?:www\.)?youtube\.com/(?:watch\?v=|shorts/)([A-Za-z0-9_-]{6,})(?:[^\s]*)?",
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


def clean_vk_description(value: str, policy: dict[str, Any]) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    text = "".join(character for character in text if character not in _ZERO_WIDTH)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("https://thelegendarypoet\n", "https://thelegendarypoet.ru/\n")
    text = text.replace("https://thelegendarypoet ", "https://thelegendarypoet.ru/ ")
    text = _replace_urls(text, policy)
    text = _outside_urls(text, lambda part: part.replace("*", "").replace("`", "").replace("_", ""))
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


__all__ = ["clean_vk_description", "clean_vk_title"]
