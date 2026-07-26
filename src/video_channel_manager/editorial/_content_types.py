from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

CANONICAL_SCHEMA_NAME = "video-manager.editorial-content"
CANONICAL_SCHEMA_VERSION = 1
LEGACY_YOUTUBE_SCHEMA_NAME = "video-manager.youtube-comment-content"
LEGACY_YOUTUBE_SCHEMA_VERSION = 2

APPROVED_PROJECT_URLS = frozenset(
    {
        "https://thelegendarypoet.ru/",
        "https://vk.com/thelegendarypoet",
        "https://t.me/thelegendarypoet",
        "https://rutube.ru/channel/74579453/",
        "https://www.youtube.com/@TheLegendaryPoet/playlists",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3uYdxFo5bxzXEUI8HYIo-sHb",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3uaxXMvilfZIYVXsf4fY18T8",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3uaI7EGOexBWQp7WX-KVabKM",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3uapKkid7HzfXHmSi3FR2y3Q",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3ubOdGfY8orpQzGNAAvkqul5",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3ua0FhqDhByHxyaBjVrk0-pE",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3ua3Q9BQe1Dhuzn7Knbz2djU",
        "https://www.youtube.com/playlist?list=PLKzLtO0ERdzg",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3uYTrhcN1TDMUeks46Y-TT_M",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3ua1QeVsZutwScsM0l-asll4",
        "https://www.youtube.com/playlist?list=PLy9lLJfoq3uZcrWY0F3Qux93xos6kIS7-",
    }
)

ALLOWED_STATUSES = frozenset({"approved", "needs-research", "draft", "fact-check", "link-check", "rejected"})
ALLOWED_FACT_TYPES = frozenset(
    {
        "composition_history",
        "first_publication",
        "manuscript_history",
        "textual_structure",
        "archival_provenance",
        "documented_context",
        "adaptation_history",
        "performance_history",
    }
)
ALLOWED_PROFILES = frozenset(
    {
        "long_form_poetry",
        "short_form",
        "short",
        "essay",
        "historical",
        "historical_or_essay",
        "music_cover",
        "cover_or_adaptation",
        "foreign_language_adaptation",
    }
)
ALLOWED_LINK_KINDS = frozenset(
    {
        "site",
        "playlist",
        "vk",
        "vk_album",
        "primary_text",
        "original_work",
        "full_version",
        "article",
    }
)
ALLOWED_SURFACES = {
    "youtube": frozenset({"comment", "description"}),
    "vk": frozenset({"video_description", "post", "comment"}),
}
BANNED_CIRCLE_MARKERS = frozenset({"🔵", "🔴", "🟢", "🟡", "🟠", "🟣", "⚫", "⚪", "🟤"})
DECORATIVE_MARKERS = ("📖", "📌", "🎧", "📚", "❄️", "⚔️", "🌊", "🎭", "📝", "🎼", "🕯️", "🗂️")
BANNED_GENERIC_PHRASES = (
    "великое вечное произведение",
    "актуально как никогда",
    "говорит с каждым из нас",
    "невероятное путешествие",
    "один из величайших шедевров",
    "пророческое произведение",
    "поэт предсказал",
    "поэт-пророк",
    "поэты-пророки",
    "шедевр на все времена",
)


@dataclass(frozen=True, slots=True)
class SourceLedgerEntry:
    source_id: str
    title: str
    url: str | None = None
    path: str | None = None


@dataclass(frozen=True, slots=True)
class FactBlock:
    heading: str
    text: str
    fact_type: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class QuestionBlock:
    text: str
    lead: str = ""


@dataclass(frozen=True, slots=True)
class LinkBlock:
    kind: str
    label: str
    url: str
    platforms: tuple[str, ...] = ()
    surfaces: tuple[str, ...] = ()

    def is_suitable(self, platform: str, surface: str) -> bool:
        return (not self.platforms or platform in self.platforms) and (not self.surfaces or surface in self.surfaces)


@dataclass(frozen=True, slots=True)
class EditorialContentRecord:
    schema_name: str
    schema_version: int
    origin_schema_name: str
    status: str
    profile: str
    variation_key: str
    content_id: str
    channel_id: str | None
    video_id: str | None
    video_title: str | None
    reviewed_at: str | None
    source_ids: tuple[str, ...]
    fact: FactBlock
    question: QuestionBlock
    links: tuple[LinkBlock, ...]
    sources: tuple[SourceLedgerEntry, ...]
    rendering_metadata: Mapping[str, Any]
    platform_suitability: Mapping[str, frozenset[str]]
    platform_targets: Mapping[str, str]

    def supports(self, platform: str, surface: str) -> bool:
        return surface in self.platform_suitability.get(platform, frozenset())

    def links_for(self, platform: str, surface: str) -> tuple[LinkBlock, ...]:
        return tuple(link for link in self.links if link.is_suitable(platform, surface))

    def target_for(self, platform: str, surface: str) -> str | None:
        exact = self.platform_targets.get(f"{platform}.{surface}")
        if exact:
            return exact
        return self.platform_targets.get(platform)
