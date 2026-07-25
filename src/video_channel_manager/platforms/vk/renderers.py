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
from video_channel_manager.platforms.vk.text import render_vk_video_description


def _plain(value: str, *, context: str) -> tuple[str, list[RenderIssue]]:
    rendered = render_vk_video_description(value, site_url="", brand_line="")
    issues = [
        RenderIssue(
            code=f"vk_{context}_{issue.code}",
            severity=issue.severity,
            message=issue.message,
        )
        for issue in rendered.issues
    ]
    return rendered.text, issues


def _link_line(label: str, url: str, *, index: int) -> tuple[str, list[RenderIssue]]:
    plain_label, issues = _plain(label, context=f"link_{index}")
    plain_label = plain_label.strip()
    separator = " " if plain_label.endswith((":", "：", "—", "–", "-")) else ": "
    return f"{plain_label}{separator}{url}".strip(), issues


def _selected_links(record: EditorialContentRecord, *, surface: str) -> tuple[LinkBlock, ...]:
    links = list(ordered_links(record, platform="vk", surface=surface))
    if surface != "comment" or len(links) <= 2:
        return tuple(links)
    priority = {"primary_text": 0, "full_version": 0, "site": 1, "vk": 2, "playlist": 3, "vk_album": 3}
    links.sort(key=lambda item: priority.get(item.kind, 4))
    return tuple(links[:2])


def _render_vk(record: EditorialContentRecord, *, surface: str) -> tuple[str, list[RenderIssue]]:
    issues: list[RenderIssue] = []
    if not record.supports("vk", surface):
        issues.append(
            RenderIssue(
                code="platform_surface_not_suitable",
                severity="error",
                message=f"Content record does not allow vk.{surface} rendering.",
            )
        )
    heading, heading_issues = _plain(record.fact.heading, context="heading")
    fact, fact_issues = _plain(record.fact.text, context="fact")
    question, question_issues = _plain(
        f"{record.question.lead} {record.question.text}".strip(),
        context="question",
    )
    issues.extend(heading_issues)
    issues.extend(fact_issues)
    issues.extend(question_issues)

    selected_links = _selected_links(record, surface=surface)
    link_lines: list[str] = []
    for index, link in enumerate(selected_links):
        line, link_issues = _link_line(link.label, link.url, index=index)
        link_lines.append(line)
        issues.extend(link_issues)
    blocks = [heading, fact, question, "\n".join(link_lines)]
    text = "\n\n".join(block for block in blocks if block).strip()

    all_links = ordered_links(record, platform="vk", surface=surface)
    if surface == "comment" and len(all_links) > len(selected_links):
        issues.append(
            RenderIssue(
                code="vk_comment_links_compacted",
                severity="warning",
                message="VK comment renderer kept only the two most relevant links for a compact mobile layout.",
            )
        )
    link_kinds = {link.kind for link in selected_links}
    if surface in {"video_description", "post"}:
        missing = sorted({"site", "vk"}.difference(link_kinds))
        if missing:
            issues.append(
                RenderIssue(
                    code="vk_required_links_missing",
                    severity="error",
                    message=f"VK {surface} is missing link kinds: {', '.join(missing)}.",
                )
            )
    if contains_banned_circle(text):
        issues.append(
            RenderIssue(
                code="forbidden_circle_marker",
                severity="error",
                message="Colored circle markers are forbidden.",
            )
        )
    issues.extend(layout_issues(text, max_line_length=140))
    return text, issues


class VKVideoDescriptionRenderer:
    platform: PlatformName = "vk"
    surface: ContentSurface = "video_description"

    def render(self, record: EditorialContentRecord) -> RenderedContent:
        text, issues = _render_vk(record, surface=self.surface)
        if len(text) > 5000:
            issues.append(
                RenderIssue(
                    code="vk_video_description_too_long",
                    severity="error",
                    message=f"VK video description has {len(text)} characters; project limit is 5000.",
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


class VKPostRenderer:
    platform: PlatformName = "vk"
    surface: ContentSurface = "post"

    def render(self, record: EditorialContentRecord) -> RenderedContent:
        text, issues = _render_vk(record, surface=self.surface)
        if len(text) > 8000:
            issues.append(
                RenderIssue(
                    code="vk_post_too_long",
                    severity="error",
                    message=f"VK post has {len(text)} characters; editorial safety limit is 8000.",
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


class VKCommentRenderer:
    platform: PlatformName = "vk"
    surface: ContentSurface = "comment"

    def render(self, record: EditorialContentRecord) -> RenderedContent:
        text, issues = _render_vk(record, surface=self.surface)
        if len(text) > 3000:
            issues.append(
                RenderIssue(
                    code="vk_comment_too_long",
                    severity="error",
                    message=f"VK comment has {len(text)} characters; editorial safety limit is 3000.",
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


__all__ = ["VKCommentRenderer", "VKPostRenderer", "VKVideoDescriptionRenderer"]
