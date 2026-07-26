from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from video_channel_manager.editorial.content import EditorialContentRecord

PlatformName = Literal["youtube", "vk"]
ContentSurface = Literal["comment", "description", "video_description", "post"]
IssueSeverity = Literal["warning", "error"]

_URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
_ORPHAN_LABEL_RE = re.compile(r"^(?:vk|сайт|сообщество|плейлист|альбом|текст|источник)\s*:$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class RenderIssue:
    code: str
    severity: IssueSeverity
    message: str
    line_number: int | None = None


@dataclass(frozen=True, slots=True)
class RenderedContent:
    platform: PlatformName
    surface: ContentSurface
    text: str
    character_count: int
    link_count: int
    issues: tuple[RenderIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


class ContentRenderer(Protocol):
    platform: PlatformName
    surface: ContentSurface

    def render(self, record: EditorialContentRecord) -> RenderedContent: ...


def count_urls(value: str) -> int:
    return len(_URL_RE.findall(value))


def layout_issues(value: str, *, max_line_length: int) -> tuple[RenderIssue, ...]:
    issues: list[RenderIssue] = []
    lines = value.splitlines()
    for index, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        if _ORPHAN_LABEL_RE.fullmatch(line):
            issues.append(
                RenderIssue(
                    code="orphan_link_label",
                    severity="error",
                    message="Link labels must stay on the same line as their URL.",
                    line_number=index,
                )
            )
        urls = _URL_RE.findall(line)
        if urls and len(line) > max_line_length:
            issues.append(
                RenderIssue(
                    code="long_link_line",
                    severity="warning",
                    message=(
                        f"Link line has {len(line)} characters and may wrap awkwardly on mobile; "
                        "shorten the label when possible."
                    ),
                    line_number=index,
                )
            )
        if line.endswith(":") and not urls:
            issues.append(
                RenderIssue(
                    code="dangling_label",
                    severity="warning",
                    message="A line ending with ':' has no value or URL on the same line.",
                    line_number=index,
                )
            )
    return tuple(issues)


__all__ = [
    "ContentRenderer",
    "ContentSurface",
    "IssueSeverity",
    "PlatformName",
    "RenderIssue",
    "RenderedContent",
    "count_urls",
    "layout_issues",
]
