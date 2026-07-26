from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from video_channel_manager.platforms.youtube.models import ChannelIdentity, OAuthToken, YouTubeAccount
from video_channel_manager.platforms.youtube.store import TokenStore


def test_token_and_account_registry_round_trip(tmp_path: Path) -> None:
    store = TokenStore(tmp_path)
    token = OAuthToken(
        access_token="access",
        refresh_token="refresh",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    store.save_token("legendary-poet", token)
    store.save_account(
        YouTubeAccount(
            alias="legendary-poet",
            token_file=str(store.token_path("legendary-poet")),
            channels=[ChannelIdentity(channel_id="UC1", title="Legendary Poet", url="https://youtube/UC1")],
        )
    )
    assert store.load_token("legendary-poet").refresh_token == "refresh"
    accounts = store.list_accounts()
    assert [item.alias for item in accounts] == ["legendary-poet"]
    assert accounts[0].channels[0].channel_id == "UC1"
    assert not store.token_path("legendary-poet").with_suffix(".json.tmp").exists()


def test_alias_rejects_path_traversal(tmp_path: Path) -> None:
    store = TokenStore(tmp_path)
    with pytest.raises(ValueError):
        store.token_path("../secret")
