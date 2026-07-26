from __future__ import annotations

import hashlib
from dataclasses import dataclass

from video_channel_manager.platforms.vk.text import VkDescriptionRender, render_vk_video_description

VK_PUBLICATION_POLICY_VERSION = "vk-publication-safe-v2"


@dataclass(frozen=True, slots=True)
class VkPublicationText:
    title: str
    description: str
    policy_version: str
    description_sha256: str
    render: VkDescriptionRender


def _sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def render_vk_publication_title(source_title: str) -> str:
    """Apply the conservative The Legendary Poet title convention for VK."""

    title = " ".join(str(source_title or "").split())
    if not title:
        raise ValueError("VK video title cannot be blank")
    if "⚡" in title:
        return title
    if "🔥" in title:
        return title.replace("🔥", "⚡", 1)
    return f"{title} ⚡"


def render_vk_publication_description(source_description: str) -> VkDescriptionRender:
    """Render publication text and fail closed on every unresolved finding."""

    rendered = render_vk_video_description(source_description)
    if rendered.issues:
        findings = ", ".join(f"{issue.severity}:{issue.code}" for issue in rendered.issues)
        raise ValueError(f"VK description requires editorial review before publication: {findings}")
    return rendered


def render_vk_publication(source_title: str, source_description: str) -> VkPublicationText:
    rendered = render_vk_publication_description(source_description)
    return VkPublicationText(
        title=render_vk_publication_title(source_title),
        description=rendered.text,
        policy_version=VK_PUBLICATION_POLICY_VERSION,
        description_sha256=_sha256_text(rendered.text),
        render=rendered,
    )


__all__ = [
    "VK_PUBLICATION_POLICY_VERSION",
    "VkPublicationText",
    "render_vk_publication",
    "render_vk_publication_description",
    "render_vk_publication_title",
]
