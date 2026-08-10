from __future__ import annotations

import pytest

from video_channel_manager.editorial._project_profiles import (
    MILOVI_CAKE,
    PROJECT_CHANNEL_IDS,
    PROJECT_VK_COMMUNITY_IDS,
    PROJECT_YOUTUBE_OAUTH_ALIASES,
    require_youtube_project_identity,
    resolve_project_key,
)
from video_channel_manager.platforms.vk.publishing import VK_PUBLICATION_PROFILES


def test_milovi_exact_provider_identity_is_registered() -> None:
    assert PROJECT_CHANNEL_IDS[MILOVI_CAKE] == frozenset({"UCMDnxfGZiBqcDzgUV1zjFpw"})
    assert PROJECT_YOUTUBE_OAUTH_ALIASES[MILOVI_CAKE] == "milovi-cake"
    assert PROJECT_VK_COMMUNITY_IDS[MILOVI_CAKE] == frozenset({68859909})
    assert VK_PUBLICATION_PROFILES[MILOVI_CAKE].site_url == "https://milovicake.ru/"

    require_youtube_project_identity(
        project_key=MILOVI_CAKE,
        account_alias="milovi-cake",
        channel_id="UCMDnxfGZiBqcDzgUV1zjFpw",
    )
    assert (
        resolve_project_key(
            {
                "project_key": MILOVI_CAKE,
                "channel_id": "UCMDnxfGZiBqcDzgUV1zjFpw",
                "community_id": 68859909,
                "owner_id": -68859909,
            }
        )
        == MILOVI_CAKE
    )


def test_milovi_rejects_cross_project_provider_mix() -> None:
    assert (
        resolve_project_key(
            {
                "project_key": MILOVI_CAKE,
                "community_id": 235216998,
                "owner_id": -235216998,
            }
        )
        is None
    )
    assert (
        resolve_project_key(
            {
                "project_key": "legendary-poet",
                "channel_id": "UCMDnxfGZiBqcDzgUV1zjFpw",
            }
        )
        is None
    )

    with pytest.raises(ValueError, match="OAuth alias differs"):
        require_youtube_project_identity(
            project_key=MILOVI_CAKE,
            account_alias="legendary-poet",
            channel_id="UCMDnxfGZiBqcDzgUV1zjFpw",
        )

    with pytest.raises(ValueError, match="channel differs"):
        require_youtube_project_identity(
            project_key=MILOVI_CAKE,
            account_alias="milovi-cake",
            channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ",
        )
