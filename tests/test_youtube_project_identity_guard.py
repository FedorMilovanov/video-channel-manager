from __future__ import annotations

from pathlib import Path

import pytest

from video_channel_manager.editorial import (
    PROJECT_YOUTUBE_OAUTH_ALIASES,
    require_youtube_project_identity,
)
from video_channel_manager.editorial._project_profiles import (
    LEGENDARY_POET,
    LORD_GOD_STRENGTH,
    MILOVI_CAKE,
    PROJECT_CHANNEL_IDS,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs/operations/project-identity-registry.md"


def test_youtube_project_identity_map_matches_canonical_registry() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    expected = {
        LORD_GOD_STRENGTH: ("fedor-milovanov", "UCeSJsC6go2c9pdJCuUI1BYA"),
        LEGENDARY_POET: ("legendary-poet", "UC-78ys2S3cQ3lpqgXfo-SvQ"),
        MILOVI_CAKE: ("milovi-cake", "UCMDnxfGZiBqcDzgUV1zjFpw"),
    }

    assert PROJECT_YOUTUBE_OAUTH_ALIASES == {key: value[0] for key, value in expected.items()}
    assert PROJECT_CHANNEL_IDS == {key: frozenset({value[1]}) for key, value in expected.items()}
    assert len(set(PROJECT_YOUTUBE_OAUTH_ALIASES.values())) == len(PROJECT_YOUTUBE_OAUTH_ALIASES)
    for project_key, (account_alias, channel_id) in expected.items():
        assert f"`{project_key}`" in text
        assert f"`{account_alias}`" in text
        assert f"`{channel_id}`" in text


def test_exact_project_account_channel_triples_are_accepted() -> None:
    require_youtube_project_identity(
        project_key=LORD_GOD_STRENGTH,
        account_alias="fedor-milovanov",
        channel_id="UCeSJsC6go2c9pdJCuUI1BYA",
    )
    require_youtube_project_identity(
        project_key=LEGENDARY_POET,
        account_alias="legendary-poet",
        channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ",
    )
    require_youtube_project_identity(
        project_key=MILOVI_CAKE,
        account_alias="milovi-cake",
        channel_id="UCMDnxfGZiBqcDzgUV1zjFpw",
    )


def test_cross_project_youtube_alias_or_channel_is_rejected() -> None:
    with pytest.raises(ValueError, match="OAuth alias differs"):
        require_youtube_project_identity(
            project_key=LEGENDARY_POET,
            account_alias="fedor-milovanov",
            channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ",
        )
    with pytest.raises(ValueError, match="channel differs"):
        require_youtube_project_identity(
            project_key=LEGENDARY_POET,
            account_alias="legendary-poet",
            channel_id="UCeSJsC6go2c9pdJCuUI1BYA",
        )
    with pytest.raises(ValueError, match="unknown project_key"):
        require_youtube_project_identity(
            project_key="unknown-project",
            account_alias="legendary-poet",
            channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ",
        )
