from __future__ import annotations

from collections import defaultdict

from video_channel_manager.exchange.audit_package import AuditFinding, AuditPackage
from video_channel_manager.platforms.youtube.client import YouTubeApiClient, YouTubeApiError
from video_channel_manager.platforms.youtube.gap_inventory import list_videos_with_gaps


class YouTubeInventoryService:
    def __init__(self, client: YouTubeApiClient) -> None:
        self.client = client

    def build_audit_package(self, channel_id: str) -> AuditPackage:
        channels = self.client.list_my_channels()
        channel = next((item for item in channels if item.ref.remote_id == channel_id), None)
        if channel is None:
            raise YouTubeApiError(
                f"Channel {channel_id} is not available to this OAuth account. Run 'youtube channels' to list choices."
            )
        videos, missing_ids, ordered_upload_ids, pagination_integrity = list_videos_with_gaps(self.client, channel_id)
        upload_positions: dict[str, list[int]] = defaultdict(list)
        for position, video_id in enumerate(ordered_upload_ids):
            upload_positions[video_id].append(position)
        repeated_uploads = {
            video_id: positions for video_id, positions in upload_positions.items() if len(positions) > 1
        }
        collections = self.client.list_collections(channel_id)
        memberships = self.client.list_memberships(
            channel_id=channel_id,
            collections=collections,
            known_video_ids={item.ref.remote_id for item in videos},
        )
        findings = [
            AuditFinding(
                rule_id="youtube.owner-upload-metadata-gap",
                severity="error",
                subject_key=f"youtube-video:{channel_id}:{video_id}",
                summary="Owner uploads playlist contains a video ID omitted by videos.list.",
                details={
                    "video_id": video_id,
                    "channel_id": channel_id,
                    "playlist_membership": True,
                    "metadata_available": False,
                    "resolution": "Investigate access/privacy/deletion state before content planning.",
                },
            )
            for video_id in missing_ids
        ]
        findings.extend(
            AuditFinding(
                rule_id="youtube.owner-uploads-duplicate-page-entry",
                severity="warning",
                subject_key=f"youtube-video:{channel_id}:{video_id}",
                summary="Owner uploads pagination repeated this ID; independent membership read agreed.",
                details={
                    "video_id": video_id,
                    "positions": positions,
                    "count": len(positions),
                    "resolution": "Repeated entries were collapsed only after a second full owner read matched the ID set.",
                    "pagination_integrity": pagination_integrity,
                },
            )
            for video_id, positions in repeated_uploads.items()
        )
        return AuditPackage(
            channel=channel,
            videos=videos,
            collections=collections,
            memberships=memberships,
            findings=findings,
            metadata={
                "source": "youtube-data-api-v3",
                "account_alias": self.client.account_alias,
                "read_only": True,
                "uploads_playlist_inventory": {
                    "ordered_upload_ids": ordered_upload_ids,
                    "upload_count": len(ordered_upload_ids),
                    "unique_upload_count": len(upload_positions),
                    "duplicate_upload_id_count": len(repeated_uploads),
                    "duplicate_upload_extra_occurrences": sum(len(p) - 1 for p in repeated_uploads.values()),
                    "duplicate_upload_positions": repeated_uploads,
                    "pagination_integrity": pagination_integrity,
                    "materialized_video_count": len(videos),
                    "missing_metadata_count": len(missing_ids),
                    "missing_metadata_ids": missing_ids,
                    "complete": not missing_ids and pagination_integrity["unique_id_set_reconciled"],
                },
            },
        )
