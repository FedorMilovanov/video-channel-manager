from __future__ import annotations

from video_channel_manager.editorial.content import EditorialContentRecord, LinkBlock, contains_banned_circle
from video_channel_manager.editorial.linking import ordered_links
from video_channel_manager.editorial.rendering import (
    ContentSurface,
    PlatformName,
    RenderIssue,
    RenderedContent,
    count_urls,
    layout_issues,
)
from video_channel_manager.editorial.youtube_description_plaintext import (
    autofix_youtube_description,
    validate_youtube_description,
)
from video_channel_manager.platforms.youtube.comments import validate_comment_text
from video_channel_manager.platforms.youtube.labels import (
    CANONICAL_VK_COMMUNITY_LABEL,
    canonicalize_youtube_link_label,
)

_DECORATIVE_MARKERS = ("📖", "📌", "🎧", "📚", "❄️", "⚔️", "🌊", "🎭", "📝", "🎼", "🕯️", "🗂️")


def _links(record: EditorialContentRecord, *, surface: str) -> tuple[LinkBlock, ...]:
    return ordered_links(record, platform="youtube", surface=surface)


def _comment_heading(value: str) -> str:
    if "*" in value or "_" in value:
        return value
    for marker in _DECORATIVE_MARKERS:
        prefix = f"{marker} "
        if value.startswith(prefix):
            return f"{prefix}*{value[len(prefix):]}*"
    return f"*{value}*"


def _comment_lead(value: str) -> str:
    if not value or "*" in value or "_" in value:
        return value
    return f"_{value}_"


def _comment_link_label(link: LinkBlock) -> str:
    if link.kind == "vk":
        return CANONICAL_VK_COMMUNITY_LABEL

    label = canonicalize_youtube_link_label(link.kind, link.label).strip()
    if "*" in label or "_" in label:
        return label

    if link.kind == "primary_text" and label.startswith("📚 "):
        return f"📚 _{label[2:].strip()}_"
    if link.kind in {"site", "playlist"} and len(label) >= 2 and label[1:2] == " ":
        return f"{label[0]} *{label[2:]}*"
    return label


def _render_blocks(record: EditorialContentRecord, *, surface: str) -> str:
    links = _links(record, surface=surface)

    if surface == "comment":
        heading = _comment_heading(record.fact.heading)
        lead = _comment_lead(record.question.lead)
        link_lines = [f"{_comment_link_label(link)} {link.url}".strip() for link in links]
    else:
        heading = record.fact.heading
        lead = record.question.lead
        link_lines = [
            f"{canonicalize_youtube_link_label(link.kind, link.label)} {link.url}".strip() for link in links
        ]

    question = f"{lead} {record.question.text}".strip()
    blocks = [heading, record.fact.text, question, "\n".join(link_lines)]
    text = "\n\n".join(block for block in blocks if block).strip()

    if surface == "description":
        text, _ = autofix_youtube_description(text)
    return text


def _youtube_content_issues(record: EditorialContentRecord, *, surface: str) -> list[RenderIssue]:
    issues: list[RenderIssue] = []
    if not record.supports("youtube", surface):
        issues.append(
            RenderIssue(
                code="platform_surface_not_suitable",
                severity="error",
                message=f"Content record does not allow youtube.{surface} rendering.",
            )
        )

    if contains_banned_circle(record.fact.heading):
        issues.append(
            RenderIssue(
                code="forbidden_circle_marker",
                severity="error",
                message="Colored circle markers are forbidden.",
            )
        )

    links = _links(record, surface=surface)
    if not 2 <= len(links) <= 4:
        issues.append(
            RenderIssue(
                code="youtube_link_count",
                severity="error",
                message="YouTube editorial blocks require 2-4 compact links.",
            )
        )

    link_by_kind = {link.kind: link for link in links}
    required = {"site", "vk"}
    if record.profile in {"long_form_poetry", "music_cover", "cover_or_adaptation", "foreign_language_adaptation"}:
        required.add("playlist")
    if record.profile in {"short", "short_form"}:
        required.add("full_version")
    missing = sorted(required.difference(link_by_kind))
    if missing:
        issues.append(
            RenderIssue(
                code="youtube_required_links_missing",
                severity="error",
                message=f"YouTube profile {record.profile} is missing link kinds: {', '.join(missing)}.",
            )
        )
    return issues


class YouTubeCommentRenderer:
    platform: PlatformName = "youtube"
    surface: ContentSurface = "comment"

    def render(self, record: EditorialContentRecord) -> RenderedContent:
        text = _render_blocks(record, surface=self.surface)
        issues = _youtube_content_issues(record, surface=self.surface)
        try:
            text = validate_comment_text(text)
        except ValueError as exc:
            issues.append(RenderIssue(code="youtube_comment_invalid", severity="error", message=str(exc)))
        issues.extend(layout_issues(text, max_line_length=180))
        marker_count = sum(text.count(marker) for marker in _DECORATIVE_MARKERS)
        if marker_count > 4:
            issues.append(
                RenderIssue(
                    code="too_many_decorative_markers",
                    severity="error",
                    message="YouTube comment uses more than four decorative markers.",
                )
            )
        return RenderedContent(
            platform=self.platform,
            surface=self.surface,
            text=text,
            character_count=len(text),
            link_count=count_urls(text),
            issues=tuple(issues),
        )


class YouTubeDescriptionRenderer:
    platform: PlatformName = "youtube"
    surface: ContentSurface = "description"

    def render(self, record: EditorialContentRecord) -> RenderedContent:
        text = _render_blocks(record, surface=self.surface)
        issues = _youtube_content_issues(record, surface=self.surface)
        issues.extend(layout_issues(text, max_line_length=180))
        issues.extend(
            RenderIssue(
                code=finding.code,
                severity=finding.severity,
                message=finding.message,
            )
            for finding in validate_youtube_description(text)
        )
        if len(text) > 5000:
            issues.append(
                RenderIssue(
                    code="youtube_description_too_long",
                    severity="error",
                    message=f"YouTube description has {len(text)} characters; project limit is 5000.",
                )
            )
        return RenderedContent(
            platform=self.platform,
            surface=self.surface,
            text=text,
            character_count=len(text),
            link_count=count_urls(text),
            issues=tuple(issues),
        )


__all__ = ["YouTubeCommentRenderer", "YouTubeDescriptionRenderer"]
