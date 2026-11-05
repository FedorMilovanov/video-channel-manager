from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from scripts.autofix_youtube_copy import _build_plan
from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef
from video_channel_manager.platforms.youtube.client import YouTubeApiClient, YouTubeApiError
from video_channel_manager.platforms.youtube.gap_inventory import list_videos_with_gaps
from video_channel_manager.platforms.youtube.models import InstalledClientConfig, OAuthToken
from video_channel_manager.platforms.youtube.service import YouTubeInventoryService
from video_channel_manager.platforms.youtube.store import TokenStore


class FakeYoutube:
    account_alias = "fedor-milovanov"

    def __init__(self, ids: list[str], *, missing: set[str] | None = None, second_ids: list[str] | None = None) -> None:
        self.ids = ids
        self.missing = missing or set()
        self.second_ids = second_ids
        self.upload_list_calls = 0

    def list_my_channels(self) -> list[ChannelRecord]:
        return [
            ChannelRecord(
                ref=RemoteRef(platform=PlatformName.YOUTUBE, channel_id="UC1", remote_id="UC1"),
                title="Lord God",
                kind=ChannelKind.VIDEO_CHANNEL,
            )
        ]

    def _uploads_playlist_id(self, channel_id: str) -> str:
        assert channel_id == "UC1"
        return "UU1"

    def _list_all(self, resource: str, *, params: dict[str, Any]) -> list[dict[str, Any]]:
        assert resource == "playlistItems"
        assert params["playlistId"] == "UU1"
        self.upload_list_calls += 1
        ids = self.second_ids if self.upload_list_calls == 2 and self.second_ids is not None else self.ids
        return [{"contentDetails": {"videoId": video_id}} for video_id in ids]

    def _get(self, resource: str, *, params: dict[str, Any]) -> dict[str, Any]:
        assert resource == "videos"
        assert "fileDetails" in params["part"]
        return {
            "items": [
                {
                    "id": video_id,
                    "snippet": {
                        "title": "Source title",
                        "description": "Source description",
                        "channelId": "UC1",
                    },
                    "contentDetails": {"duration": "PT6M"},
                    "status": {"privacyStatus": "public"},
                }
                for video_id in params["id"].split(",")
                if video_id not in self.missing
            ]
        }

    def list_collections(self, channel_id: str) -> list[Any]:
        assert channel_id == "UC1"
        return []

    def list_memberships(self, *, channel_id: str, collections: list[Any], known_video_ids: set[str]) -> list[Any]:
        assert channel_id == "UC1"
        assert collections == []
        assert known_video_ids == {"VID1"} or known_video_ids == {"VID1", "VID2"}
        return []


def test_pagination_repeat_does_not_duplicate_video_records_or_missing_ids() -> None:
    client = FakeYoutube(["VID1", "VID1", "VID2", "VID1", "VID2"], missing={"VID2"})
    videos, missing, raw_ids, integrity = list_videos_with_gaps(client, "UC1")
    assert [v.ref.remote_id for v in videos] == ["VID1"]
    assert missing == ["VID2"]
    assert raw_ids == ["VID1", "VID1", "VID2", "VID1", "VID2"]
    assert integrity["validation_passes"] == 2
    assert integrity["unique_id_set_reconciled"] is True


def test_package_reconciles_stable_duplicate_positions() -> None:
    client = FakeYoutube(["VID1", "VID1", "VID2", "VID1", "VID2"])
    package = YouTubeInventoryService(client).build_audit_package("UC1")
    assert [v.ref.remote_id for v in package.videos] == ["VID1", "VID2"]
    state = package.metadata["uploads_playlist_inventory"]
    assert state["upload_count"] == 5
    assert state["unique_upload_count"] == 2
    assert state["duplicate_upload_id_count"] == 2
    assert state["duplicate_upload_extra_occurrences"] == 3
    assert state["duplicate_upload_positions"] == {"VID1": [0, 1, 3], "VID2": [2, 4]}
    assert state["complete"] is True
    assert state["pagination_integrity"]["validation_passes"] == 2
    assert [f.rule_id for f in package.findings] == [
        "youtube.owner-uploads-duplicate-page-entry",
        "youtube.owner-uploads-duplicate-page-entry",
    ]
    assert all(f.severity == "warning" for f in package.findings)


def test_duplicate_free_package_is_complete() -> None:
    package = YouTubeInventoryService(FakeYoutube(["VID1", "VID2"])).build_audit_package("UC1")
    assert len(package.videos) == 2
    state = package.metadata["uploads_playlist_inventory"]
    assert state["duplicate_upload_id_count"] == 0
    assert state["complete"] is True
    assert package.findings == []


def test_description_planner_blocks_incomplete_duplicate_inventory(tmp_path: Path) -> None:
    payload = {
        "metadata": {"uploads_playlist_inventory": {"complete": False}},
        "videos": [],
    }
    with pytest.raises(ValueError, match="incomplete or has duplicate"):
        _build_plan(payload, tmp_path / "not_read.json")


def test_legacy_list_videos_fails_closed_on_repeated_upload_ids(tmp_path: Path) -> None:
    store = TokenStore(tmp_path)
    store.save_token(
        "fedor-milovanov",
        OAuthToken(
            access_token="test-access",
            refresh_token="test-refresh",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        resource = request.url.path.rsplit("/", 1)[-1]
        if resource == "channels":
            return httpx.Response(
                200,
                json={"items": [{"id": "UC1", "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]},
            )
        if resource == "playlistItems":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"contentDetails": {"videoId": "VID1"}},
                        {"contentDetails": {"videoId": "VID1"}},
                    ]
                },
            )
        raise AssertionError("Must refuse duplicates before querying video metadata")

    client = YouTubeApiClient(
        client_config=InstalledClientConfig(client_id="id", client_secret="secret"),
        token_store=store,
        account_alias="fedor-milovanov",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/youtube/v3",
    )
    with pytest.raises(YouTubeApiError, match="repeated video IDs"):
        client.list_videos("UC1")


def test_changed_second_owner_upload_set_fails_closed_before_video_reads() -> None:
    client = FakeYoutube(["VID1", "VID1", "VID2"], second_ids=["VID1", "VID3"])
    with pytest.raises(YouTubeApiError, match="changed unique video IDs"):
        list_videos_with_gaps(client, "UC1")
    assert client.upload_list_calls == 2


def test_missing_metadata_blocks_complete_claim_even_with_stable_repeated_pages() -> None:
    client = FakeYoutube(["VID1", "VID2", "VID1"], missing={"VID2"})
    package = YouTubeInventoryService(client).build_audit_package("UC1")
    state = package.metadata["uploads_playlist_inventory"]
    assert state["unique_upload_count"] == 2
    assert state["materialized_video_count"] == 1
    assert state["missing_metadata_ids"] == ["VID2"]
    assert state["complete"] is False
    assert [f.severity for f in package.findings] == ["error", "warning"]
