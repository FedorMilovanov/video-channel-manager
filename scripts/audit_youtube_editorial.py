#!/usr/bin/env python3
"""Generate a deterministic read-only editorial audit from an AuditPackage.

This script never calls YouTube and never mutates remote data. It reports
candidates that still require editorial or Shorts-format confirmation.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

SHORTS_CUTOFF = datetime.fromisoformat("2024-10-15T00:00:00+00:00")
TITLE_LIMIT = 100
DESCRIPTION_LIMIT = 5000

MULTI_BLANK_RE = re.compile(r"\n{3,}")
TEMPLATE_RE = re.compile(
    r"(?:это не просто|уникальн(?:ая|ое|ый)|глубок(?:ий|ая|ое) смысл|"
    r"вечные вопросы|ожившая классика|никого не оставит равнодушным)",
    re.IGNORECASE,
)
PUNCT_OUTSIDE_RE = re.compile(r"(?:\*[^*\n]+\*|_[^_\n]+_)[,.:;!?…]")
VERSION_RE = re.compile(r"\b(?:version|версия)\s*[-–—]?\s*\d+\b", re.IGNORECASE)
ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200d\ufeff]")
SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class VideoView:
    video_id: str
    title: str
    description: str
    duration_seconds: int | None
    published_at: datetime | None
    privacy_status: str | None
    tags: list[str]
    metadata: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "VideoView":
        ref = payload.get("ref") if isinstance(payload.get("ref"), dict) else {}
        published = payload.get("published_at")
        return cls(
            video_id=str(ref.get("remote_id") or ""),
            title=str(payload.get("title") or ""),
            description=str(payload.get("description") or ""),
            duration_seconds=(
                payload.get("duration_seconds") if isinstance(payload.get("duration_seconds"), int) else None
            ),
            published_at=(
                datetime.fromisoformat(published.replace("Z", "+00:00")) if isinstance(published, str) else None
            ),
            privacy_status=(str(payload.get("privacy_status")) if payload.get("privacy_status") is not None else None),
            tags=[str(item) for item in payload.get("tags", []) if isinstance(item, str)],
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )


def normalize_title(value: str) -> str:
    return SPACE_RE.sub(" ", ZERO_WIDTH_RE.sub("", value)).strip().casefold()


def first_paragraph(description: str) -> str:
    parts = re.split(r"\n\s*\n", description.strip(), maxsplit=1)
    return parts[0] if parts else ""


def max_paragraph_length(description: str) -> int:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", description) if part.strip()]
    return max((len(part) for part in paragraphs), default=0)


def video_dimensions(video: VideoView) -> tuple[int, int] | None:
    file_details = video.metadata.get("fileDetails")
    if not isinstance(file_details, dict):
        return None
    streams = file_details.get("videoStreams")
    if not isinstance(streams, list):
        return None
    for stream in streams:
        if not isinstance(stream, dict):
            continue
        width = stream.get("widthPixels")
        height = stream.get("heightPixels")
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            rotation = str(stream.get("rotation") or "none")
            if rotation in {"clockwise", "counterClockwise"}:
                width, height = height, width
            return width, height
    return None


def shorts_status(video: VideoView) -> tuple[str, str]:
    duration = video.duration_seconds
    published = video.published_at
    dimensions = video_dimensions(video)
    explicit = "#shorts" in f"{video.title}\n{video.description}".casefold()

    if duration is None or published is None:
        return "needs_review", "missing duration or publication date"
    if published < SHORTS_CUTOFF:
        return "long_form", "uploaded before the three-minute Shorts cutoff"
    if duration > 180:
        return "long_form", "duration exceeds three minutes"
    if dimensions is None:
        reason = "duration is at most three minutes but file geometry is unavailable"
        if explicit:
            reason += "; #Shorts is only a hint"
        return "needs_review", reason
    width, height = dimensions
    if width <= height:
        return "short", f"confirmed square/vertical source ({width}x{height})"
    return "long_form", f"confirmed horizontal source ({width}x{height})"


def playlist_memberships(payload: dict[str, Any]) -> tuple[dict[str, set[str]], dict[str, str]]:
    playlist_titles: dict[str, str] = {}
    for collection in payload.get("collections", []):
        if not isinstance(collection, dict):
            continue
        ref = collection.get("ref") if isinstance(collection.get("ref"), dict) else {}
        playlist_id = str(ref.get("remote_id") or "")
        if playlist_id:
            playlist_titles[playlist_id] = str(collection.get("title") or playlist_id)

    memberships: dict[str, set[str]] = defaultdict(set)
    for item in payload.get("memberships", []):
        if not isinstance(item, dict):
            continue
        video_ref = item.get("video_ref") if isinstance(item.get("video_ref"), dict) else {}
        collection_ref = item.get("collection_ref") if isinstance(item.get("collection_ref"), dict) else {}
        video_id = str(video_ref.get("remote_id") or "")
        playlist_id = str(collection_ref.get("remote_id") or "")
        if video_id and playlist_id:
            memberships[video_id].add(playlist_id)
    return memberships, playlist_titles


def render_report(payload: dict[str, Any], source: Path) -> str:
    videos = [VideoView.from_payload(item) for item in payload.get("videos", []) if isinstance(item, dict)]
    memberships, playlist_titles = playlist_memberships(payload)

    duplicate_groups: dict[str, list[VideoView]] = defaultdict(list)
    for video in videos:
        duplicate_groups[normalize_title(video.title)].append(video)
    duplicate_groups = {key: group for key, group in duplicate_groups.items() if key and len(group) > 1}

    short_counts: Counter[str] = Counter()
    shorts_in_playlists: list[tuple[VideoView, set[str], str]] = []
    review_short_candidates: list[tuple[VideoView, str]] = []
    long_without_playlist: list[VideoView] = []

    for video in videos:
        status, reason = shorts_status(video)
        short_counts[status] += 1
        current = memberships.get(video.video_id, set())
        if status == "short" and current:
            shorts_in_playlists.append((video, current, reason))
        elif status == "needs_review":
            review_short_candidates.append((video, reason))
        elif status == "long_form" and not current:
            long_without_playlist.append(video)

    empty_descriptions = [video for video in videos if not video.description.strip()]
    short_descriptions = [video for video in videos if 0 < len(video.description) < 300]
    near_limit = [video for video in videos if len(video.description) >= 4500]
    title_over_limit = [video for video in videos if len(video.title) > TITLE_LIMIT]
    description_over_limit = [video for video in videos if len(video.description) > DESCRIPTION_LIMIT]
    first_formatted = [
        video
        for video in videos
        if "*" in first_paragraph(video.description) or "_" in first_paragraph(video.description)
    ]
    first_symbol = [
        video
        for video in videos
        if first_paragraph(video.description) and not first_paragraph(video.description)[0].isalnum()
    ]
    multiple_blanks = [video for video in videos if MULTI_BLANK_RE.search(video.description)]
    long_paragraphs = [video for video in videos if max_paragraph_length(video.description) > 700]
    punctuation_outside = [video for video in videos if PUNCT_OUTSIDE_RE.search(video.description)]
    templates = [video for video in videos if TEMPLATE_RE.search(video.description)]

    title_metrics = {
        "@TheLegendaryPoet": sum("@thelegendarypoet" in video.title.casefold() for video in videos),
        "#TheLegendaryPoet": sum("#thelegendarypoet" in video.title.casefold() for video in videos),
        "Version/Версия": sum(bool(VERSION_RE.search(video.title)) for video in videos),
        "служебный дефис": sum(" - " in video.title for video in videos),
    }

    lines: list[str] = [
        "# Deterministic YouTube editorial audit",
        "",
        f"Source: `{source}`",
        f"Generated from snapshot: `{payload.get('snapshot_id', 'unknown')}`",
        "",
        "> Read-only report. Every candidate still requires human review before a ChangePlan.",
        "",
        "## Totals",
        "",
        f"- Videos: **{len(videos)}**",
        f"- Playlists: **{len(playlist_titles)}**",
        f"- Memberships: **{sum(len(value) for value in memberships.values())}**",
        f"- Exact normalized duplicate-title groups: **{len(duplicate_groups)}**",
        "",
        "## Shorts classification",
        "",
        f"- Confirmed Shorts: **{short_counts['short']}**",
        f"- Confirmed long-form: **{short_counts['long_form']}**",
        f"- Needs geometry/manual review: **{short_counts['needs_review']}**",
        f"- Confirmed Shorts currently in playlists: **{len(shorts_in_playlists)}**",
        "",
        "`#Shorts` and duration alone are not authoritative. Square/vertical source geometry is required for uploads after 2024-10-15.",
        "",
        "## Description checks",
        "",
        f"- Empty: **{len(empty_descriptions)}**",
        f"- Under 300 characters: **{len(short_descriptions)}**",
        f"- At or above 4500 characters: **{len(near_limit)}**",
        f"- Above platform limit: **{len(description_over_limit)}**",
        f"- First paragraph contains formatting markers: **{len(first_formatted)}**",
        f"- First paragraph starts with a non-alphanumeric symbol: **{len(first_symbol)}**",
        f"- Three or more consecutive line breaks: **{len(multiple_blanks)}**",
        f"- Paragraph longer than 700 characters: **{len(long_paragraphs)}**",
        f"- High-confidence punctuation outside emphasis: **{len(punctuation_outside)}**",
        f"- Template-language candidates: **{len(templates)}**",
        "",
        "## Title checks",
        "",
    ]
    lines.extend(f"- {name}: **{value}**" for name, value in title_metrics.items())
    lines.append(f"- Above 100-character platform limit: **{len(title_over_limit)}**")

    lines.extend(["", "## Duplicate-title groups", ""])
    for group in sorted(duplicate_groups.values(), key=lambda items: items[0].title.casefold()):
        lines.append(f"### {group[0].title}")
        lines.append("")
        for video in sorted(group, key=lambda item: item.duration_seconds or -1):
            status, reason = shorts_status(video)
            playlists = (
                ", ".join(sorted(playlist_titles.get(pid, pid) for pid in memberships.get(video.video_id, set())))
                or "none"
            )
            lines.append(
                f"- `{video.video_id}` — {video.duration_seconds or '?'} sec — `{status}` — "
                f"playlists: {playlists} — {reason}"
            )
        lines.append("")

    lines.extend(["## Long-form videos without playlists", ""])
    if not long_without_playlist:
        lines.append("None detected with current evidence.")
    else:
        for video in sorted(long_without_playlist, key=lambda item: item.published_at or datetime.min, reverse=True):
            lines.append(f"- `{video.video_id}` — {video.duration_seconds or '?'} sec — {video.title}")

    lines.extend(["", "## Shorts candidates requiring geometry", ""])
    for video, reason in review_short_candidates:
        explicit = "#shorts" in f"{video.title}\n{video.description}".casefold()
        if explicit or (video.duration_seconds is not None and video.duration_seconds <= 180):
            playlist_count = len(memberships.get(video.video_id, set()))
            lines.append(
                f"- `{video.video_id}` — {video.duration_seconds or '?'} sec — playlists: {playlist_count} — "
                f"{video.title} — {reason}"
            )

    lines.extend(
        [
            "",
            "## Policy notes",
            "",
            "- Do not mutate YouTube from this report.",
            "- Do not remove playlist memberships until Shorts status is confirmed.",
            "- Preserve original values and revisions in every ChangePlan.",
            "- Fact-check literary claims separately; this script checks structure, not historical truth.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit_package", type=Path)
    parser.add_argument("--output", "-o", type=Path)
    args = parser.parse_args()

    try:
        payload = json.loads(args.audit_package.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if not isinstance(payload, dict) or payload.get("schema_name") != "video-manager.audit-package":
        parser.error("Input is not a video-manager AuditPackage")

    report = render_report(payload, args.audit_package)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(args.output)
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
