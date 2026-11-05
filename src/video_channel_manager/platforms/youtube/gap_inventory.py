from __future__ import annotations

from typing import Any

from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.domain.models import RemoteRef, VideoRecord
from video_channel_manager.platforms.youtube.client import (
    YouTubeApiClient,
    YouTubeApiError,
    _chunks,
    _dict_field,
    _dict_items,
    _parse_datetime,
    _parse_duration,
    _revision,
    _best_thumbnail,
)


def list_videos_with_gaps(
    client: YouTubeApiClient,
    channel_id: str,
) -> tuple[list[VideoRecord], list[str], list[str], dict[str, Any]]:
    """Enumerate owner uploads, reconciling repeated pages before making a complete claim.

    Returns (videos, missing_ids, ordered_upload_ids, pagination_integrity).
    Missing IDs are evidence that
    YouTube exposed an upload in the owner uploads playlist but omitted its metadata
    from videos.list. They are deliberately not represented as fake VideoRecords.
    """

    uploads_playlist = client._uploads_playlist_id(channel_id)
    pagination_params: dict[str, str | int] = {
        "part": "contentDetails",
        "playlistId": uploads_playlist,
        "maxResults": 50,
    }
    playlist_items = client._list_all("playlistItems", params=pagination_params)
    ordered_ids: list[str] = []
    for item in playlist_items:
        video_id = str(_dict_field(item, "contentDetails").get("videoId") or "").strip()
        if video_id:
            ordered_ids.append(video_id)

    unique_ordered_ids = list(dict.fromkeys(ordered_ids))
    duplicate_page_entries = len(ordered_ids) - len(unique_ordered_ids)
    pagination_integrity: dict[str, Any] = {
        "validation_passes": 1,
        "unique_id_set_reconciled": not duplicate_page_entries,
        "second_pass_upload_count": None,
        "second_pass_unique_count": None,
    }
    if duplicate_page_entries:
        # A moving uploads playlist can repeat IDs at pagination boundaries.
        # A second independent full read must agree on exact membership; if it
        # does not, there is no defensible snapshot for downstream mutation.
        repeat_items = client._list_all("playlistItems", params=pagination_params)
        repeat_ids = [str(_dict_field(item, "contentDetails").get("videoId") or "").strip() for item in repeat_items]
        repeat_ids = [video_id for video_id in repeat_ids if video_id]
        if set(unique_ordered_ids) != set(repeat_ids):
            raise YouTubeApiError(
                "Owner uploads pagination changed unique video IDs between two read-only full passes; "
                "stop instead of publishing an incomplete channel inventory."
            )
        pagination_integrity = {
            "validation_passes": 2,
            "unique_id_set_reconciled": True,
            "second_pass_upload_count": len(repeat_ids),
            "second_pass_unique_count": len(set(repeat_ids)),
        }

    raw_by_id: dict[str, dict[str, Any]] = {}
    for batch in _chunks(unique_ordered_ids, 50):
        payload = client._get(
            "videos",
            params={
                "part": "snippet,contentDetails,status,fileDetails",
                "id": ",".join(batch),
                "maxResults": 50,
            },
        )
        for raw_item in _dict_items(payload):
            item_id = str(raw_item.get("id") or "").strip()
            if item_id:
                raw_by_id[item_id] = raw_item

    # Pagination may repeat an upload ID around page boundaries. Keep the raw
    # ordered list as evidence, but materialize exactly one VideoRecord per ID.
    # Missing metadata is likewise a set of *source IDs*, not page occurrences.
    missing_ids = list(dict.fromkeys(video_id for video_id in ordered_ids if video_id not in raw_by_id))
    records: list[VideoRecord] = []
    seen_ids: set[str] = set()
    for video_id in ordered_ids:
        if video_id in seen_ids:
            continue
        seen_ids.add(video_id)
        raw = raw_by_id.get(video_id)
        if raw is None:
            continue
        snippet = _dict_field(raw, "snippet")
        details = _dict_field(raw, "contentDetails")
        status = _dict_field(raw, "status")
        raw_tags = snippet.get("tags")
        records.append(
            VideoRecord(
                ref=RemoteRef(platform=PlatformName.YOUTUBE, channel_id=channel_id, remote_id=video_id),
                title=str(snippet.get("title") or video_id),
                description=str(snippet.get("description") or ""),
                duration_seconds=_parse_duration(str(details.get("duration") or "")),
                published_at=_parse_datetime(str(snippet.get("publishedAt") or "")),
                privacy_status=str(status.get("privacyStatus") or "") or None,
                tags=[str(tag) for tag in raw_tags] if isinstance(raw_tags, list) else [],
                thumbnail_url=_best_thumbnail(snippet.get("thumbnails")),
                revision=_revision(raw),
                metadata=raw,
            )
        )
    return records, missing_ids, ordered_ids, pagination_integrity
