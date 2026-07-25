from __future__ import annotations

from video_channel_manager.editorial.content import (
    EditorialContentRecord,
    balanced_emphasis,
    contains_banned_circle,
)
from video_channel_manager.editorial.linking import ordered_links
from video_channel_manager.editorial.rendering import (
    ContentSurface,
    PlatformName,
    RenderIssue,
    RenderedContent,
    count_urls,
    layout_issues,
)
from video_channel_manager.platforms.youtube.comments import validate_comment_text

_DECORATIVE_MARKERS = ("📖", "📌", "🎧", "📚", "❄️", "⚔️", "🌊", "🎭", "📝", "🎼", "🕯️", "🗂️")


def _links(record: EditorialContentRecord, *, surface: str):
    return ordered_links(record, platform="youtube", surface=surface)


def _render_blocks(record: EditorialContentRecord, *, surface: str) -> str:
    links = _links(record, surface=surface)
    question = f"{record.question.lead} {record.question.text}".strip()
    link_lines = [f"{link.label} {link.url}".strip() for link in links]
    blocks = [record.fact.heading, record.fact.text, question, "\n".join(link_lines)]
    return "\n\n".join(block for block in blocks if block).strip()


def _youtube_style_issues(record: EditorialContentRecord, *, surface: str) -> list[RenderIssue]:
    issues: list[RenderIssue] = []
    if not record.supports("youtube", surface):
        issues.append(
            RenderIssue(
                code="platform_surface_not_suitable",
                severity="error",
                message=f"Content record does not allow youtube.{surface} rendering.",
            )
        )
    heading = record.fact.heading
    if "*" not in heading and "_" not in heading:
        issues.append(
            RenderIssue(
                code="youtube_heading_emphasis_required",
                severity="error",
                message="YouTube heading must use restrained bold or italic emphasis.",
            )
        )
    if not balanced_emphasis(heading):
        issues.append(
            RenderIssue(
                code="unbalanced_emphasis",
                severity="error",
                message="YouTube emphasis markers are unbalanced.",
            )
        )
    if contains_banned_circle(heading):
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
    site = link_by_kind.get("site")
    if site is not None and not (site.label.startswith("📌 ") and "*" in site.label):
        issues.append(
            RenderIssue(
                code="youtube_site_label_style",
                severity="error",
                message="Site link label must use the compact 📌 bold style.",
            )
        )
    playlist = link_by_kind.get("playlist")
    if playlist is not None and not (playlist.label.startswith("🎧 ") and "*" in playlist.label):
        issues.append(
            RenderIssue(
                code="youtube_playlist_label_style",
                severity="error",
                message="Playlist link label must use the compact 🎧 bold style.",
            )
        )
    vk = link_by_kind.get("vk")
    if vk is not None and vk.label != "*Сообщество проекта VK:*":
        issues.append(
            RenderIssue(
                code="youtube_vk_label_style",
                severity="error",
                message="VK link label must be exactly *Сообщество проекта VK:*.",
            )
        )
    primary = link_by_kind.get("primary_text")
    if primary is not None and not (primary.label.startswith("📚 ") and ("*" in primary.label or "_" in primary.label)):
        issues.append(
            RenderIssue(
                code="youtube_primary_text_label_style",
                severity="error",
                message="Primary-text link label must use the compact 📚 emphasized style.",
            )
        )
    return issues


class YouTubeCommentRenderer:
    platform: PlatformName = "youtube"
    surface: ContentSurface = "comment"

    def render(self, record: EditorialContentRecord) -> RenderedContent:
        text = _render_blocks(record, surface=self.surface)
        issues = _youtube_style_issues(record, surface=self.surface)
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
        issues = _youtube_style_issues(record, surface=self.surface)
        issues.extend(layout_issues(text, max_line_length=180))
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
