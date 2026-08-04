from __future__ import annotations

from dataclasses import dataclass

from video_channel_manager.application.cross_platform import (
    CrossPlatformComparison,
    render_comparison_markdown,
)
from video_channel_manager.domain.enums import CollectionKind, OperationType, RiskLevel
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.exchange.change_plan import ChangeOperation, ChangePlan


@dataclass(frozen=True, slots=True)
class PlacementSummary:
    existing_collection_placements: int
    pending_collection_placements: int

    @property
    def total_placements(self) -> int:
        return self.existing_collection_placements + self.pending_collection_placements


def summarize_placements(comparison: CrossPlatformComparison) -> PlacementSummary:
    existing = sum(
        gap.missing_placement_count for gap in comparison.collection_gaps if gap.target_collection_id is not None
    )
    pending = sum(gap.missing_placement_count for gap in comparison.collection_gaps if gap.target_collection_id is None)
    return PlacementSummary(
        existing_collection_placements=existing,
        pending_collection_placements=pending,
    )


def render_detailed_comparison_markdown(comparison: CrossPlatformComparison) -> str:
    summary = summarize_placements(comparison)
    rendered = render_comparison_markdown(comparison)
    section_marker = "\n## Конфликты сопоставления видео\n"
    if section_marker not in rendered:
        raise ValueError("comparison Markdown section structure changed unexpectedly")
    placement_summary = "\n".join(
        [
            f"- Недостающих размещений в уже существующих коллекциях: **{summary.existing_collection_placements}**.",
            f"- Размещений, ожидающих создания отсутствующих коллекций: **{summary.pending_collection_placements}**.",
            f"- Всего требуемых размещений: **{summary.total_placements}**.",
            "",
        ]
    )
    return rendered.replace(section_marker, f"\n{placement_summary}## Конфликты сопоставления видео\n", 1)


def build_disabled_transfer_plan(
    source: AuditPackage,
    target: AuditPackage,
    comparison: CrossPlatformComparison,
) -> ChangePlan:
    source_videos = {video.ref.remote_id: video for video in source.videos}
    candidates = [
        item
        for item in comparison.missing_on_target
        if item.privacy_status == "public" and (item.duration_seconds or 0) > 180
    ]
    operations: list[ChangeOperation] = []
    for item in sorted(candidates, key=lambda candidate: candidate.title.casefold()):
        source_video = source_videos[item.ref.remote_id]
        operations.append(
            ChangeOperation(
                operation=OperationType.TRANSFER_VIDEO,
                target=source_video.ref,
                payload={
                    "destination_channel_id": target.channel.ref.channel_id,
                    "destination_platform": target.channel.ref.platform.value,
                    "collection_titles": item.collection_titles,
                },
                expected_revision=source_video.revision,
                risk=RiskLevel.MEDIUM,
                rationale="Public source video longer than three minutes is absent from the target snapshot.",
                enabled=False,
            )
        )
    return ChangePlan(
        source_snapshot_id=source.snapshot_id,
        title="Disabled plan: transfer public full-length videos to VK",
        channel=source.channel.ref,
        operations=operations,
        notes=(
            "Generated from a read-only cross-platform comparison. Every operation is disabled. "
            "The current VK adapter has no upload executor; review media sources, rights, titles, "
            "descriptions, thumbnails, and destination albums before enabling anything."
        ),
    )


def build_disabled_collection_plan(
    target: AuditPackage,
    comparison: CrossPlatformComparison,
) -> ChangePlan:
    target_videos = {video.ref.remote_id: video for video in target.videos}
    operations: list[ChangeOperation] = []

    for gap in comparison.collection_gaps:
        if gap.target_collection_id is not None:
            continue
        placeholder = f"pending:create:{gap.source_collection_id}"
        operations.append(
            ChangeOperation(
                operation=OperationType.CREATE_COLLECTION,
                target=target.channel.ref,
                payload={
                    "title": gap.source_title,
                    "kind": CollectionKind.VIDEO_ALBUM.value,
                    "source_collection_id": gap.source_collection_id,
                    "placeholder_collection_id": placeholder,
                },
                risk=RiskLevel.LOW,
                rationale="The source playlist has no title-matched VK video album.",
                enabled=False,
            )
        )

    for gap in comparison.collection_gaps:
        collection_id = gap.target_collection_id or f"pending:create:{gap.source_collection_id}"
        for target_video_id in gap.missing_target_video_ids:
            target_video = target_videos[target_video_id]
            operations.append(
                ChangeOperation(
                    operation=OperationType.ADD_TO_COLLECTION,
                    target=target_video.ref,
                    payload={
                        "collection_id": collection_id,
                        "collection_title": gap.source_title,
                    },
                    expected_revision=target_video.revision,
                    risk=RiskLevel.LOW,
                    rationale="Matched VK video is absent from the corresponding album membership snapshot.",
                    enabled=False,
                )
            )

    return ChangePlan(
        source_snapshot_id=target.snapshot_id,
        title="Disabled plan: create and populate VK video albums",
        channel=target.channel.ref,
        operations=operations,
        notes=(
            "Generated from a read-only comparison. Every operation is disabled. Placeholder collection IDs "
            "beginning with 'pending:create:' must be resolved to real VK album IDs after creation. "
            "No remote write executor is present in this version."
        ),
    )
