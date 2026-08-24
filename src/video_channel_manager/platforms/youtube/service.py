from __future__ import annotations

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
        videos, missing_ids, ordered_upload_ids = list_videos_with_gaps(self.client, channel_id)
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
                    "materialized_video_count": len(videos),
                    "missing_metadata_count": len(missing_ids),
                    "missing_metadata_ids": missing_ids,
                    "complete": not missing_ids,
                },
            },
        )
