from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from video_channel_manager.editorial._project_profiles import LEGENDARY_POET, LORD_GOD_STRENGTH, PROJECT_KEYS
from video_channel_manager.platforms.vk.text import VkDescriptionRender, render_vk_video_description

VK_PUBLICATION_POLICY_VERSION = "vk-publication-project-profile-v3"


@dataclass(frozen=True, slots=True)
class VkPublicationProfile:
    project_key: str
    site_url: str
    brand_line: str
    title_suffix: str


@dataclass(frozen=True, slots=True)
class VkPublicationText:
    project_key: str
    title: str
    description: str
    policy_version: str
    description_sha256: str
    render: VkDescriptionRender


VK_PUBLICATION_PROFILES: Mapping[str, VkPublicationProfile] = MappingProxyType(
    {
        LORD_GOD_STRENGTH: VkPublicationProfile(
            project_key=LORD_GOD_STRENGTH,
            site_url="https://gospod-bog.ru/",
            brand_line="† Господь Бог — Сила Моя † — Писание, богословие, проповеди и христианские материалы.",
            title_suffix="",
        ),
        LEGENDARY_POET: VkPublicationProfile(
            project_key=LEGENDARY_POET,
            site_url="https://thelegendarypoet.ru/",
            brand_line="🎧 The Legendary Poet — русская поэзия, музыка и литературные материалы.",
            title_suffix="⚡",
        ),
    }
)


def _sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _publication_profile(project_key: str | None) -> VkPublicationProfile:
    normalized = str(project_key or "").strip()
    if normalized not in PROJECT_KEYS:
        raise ValueError("VK publication requires an explicit registered project_key")
    return VK_PUBLICATION_PROFILES[normalized]


def render_vk_publication_title(source_title: str, *, project_key: str | None = None) -> str:
    """Apply only the selected project's reviewed VK title convention."""

    profile = _publication_profile(project_key)
    title = " ".join(str(source_title or "").split())
    if not title:
        raise ValueError("VK video title cannot be blank")
    if not profile.title_suffix:
        return title
    if profile.title_suffix in title:
        return title
    if "🔥" in title:
        return title.replace("🔥", profile.title_suffix, 1)
    return f"{title} {profile.title_suffix}"


def render_vk_publication_description(
    source_description: str,
    *,
    project_key: str | None = None,
) -> VkDescriptionRender:
    """Render publication text from one explicit project profile and fail closed."""

    profile = _publication_profile(project_key)
    rendered = render_vk_video_description(
        source_description,
        site_url=profile.site_url,
        brand_line=profile.brand_line,
    )
    if rendered.issues:
        findings = ", ".join(f"{issue.severity}:{issue.code}" for issue in rendered.issues)
        raise ValueError(f"VK description requires editorial review before publication: {findings}")
    return rendered


def render_vk_publication(
    source_title: str,
    source_description: str,
    *,
    project_key: str | None = None,
) -> VkPublicationText:
    profile = _publication_profile(project_key)
    rendered = render_vk_publication_description(source_description, project_key=profile.project_key)
    return VkPublicationText(
        project_key=profile.project_key,
        title=render_vk_publication_title(source_title, project_key=profile.project_key),
        description=rendered.text,
        policy_version=VK_PUBLICATION_POLICY_VERSION,
        description_sha256=_sha256_text(rendered.text),
        render=rendered,
    )


__all__ = [
    "VK_PUBLICATION_POLICY_VERSION",
    "VK_PUBLICATION_PROFILES",
    "VkPublicationProfile",
    "VkPublicationText",
    "render_vk_publication",
    "render_vk_publication_description",
    "render_vk_publication_title",
]
