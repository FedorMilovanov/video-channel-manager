from __future__ import annotations

from types import SimpleNamespace

import pytest

import video_channel_manager.platforms.vk.milovi_token_clip_rollout as rollout
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS, SourceAsset


def _asset() -> SourceAsset:
    source_id = ROLL_OUT_IDS[0]
    return SourceAsset(
        source_id=source_id,
        source_url=f"https://www.youtube.com/shorts/{source_id}",
        title="Milovi cardinality test",
        duration_seconds=30,
        media_path="unused.mp4",
        media_sha256="0" * 64,
        width=1080,
        height=1920,
        description="unused",
        wall_message="unused",
    )


def _record(remote_id: str, *, source_id: str | None = None, video_type: str = "short_video") -> SimpleNamespace:
    marker_source = source_id or ROLL_OUT_IDS[0]
    return SimpleNamespace(
        description=f"reviewed copy https://www.youtube.com/shorts/{marker_source}",
        duration_seconds=30,
        metadata={"vk_video_type": video_type},
        ref=SimpleNamespace(remote_id=remote_id),
    )


def _install_inventory(monkeypatch: pytest.MonkeyPatch, records: list[SimpleNamespace]) -> None:
    package = SimpleNamespace(
        channel=SimpleNamespace(ref=SimpleNamespace(channel_id=68859909)),
        videos=records,
    )

    class _Inventory:
        def __init__(self, _client: object) -> None:
            pass

        def build_audit_package(self, community_id: str) -> SimpleNamespace:
            assert community_id == "68859909"
            return package

    monkeypatch.setattr(rollout, "VkInventoryService", _Inventory)


def test_clip_inventory_cardinality_zero_returns_no_adoption_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_inventory(monkeypatch, [_record("-68859909_1", source_id=ROLL_OUT_IDS[1])])

    assert rollout._find_existing_clip(object(), _asset()) is None  # type: ignore[arg-type]


def test_clip_inventory_cardinality_one_native_clip_is_exact_adoption(monkeypatch: pytest.MonkeyPatch) -> None:
    remote_id = "-68859909_456239240"
    _install_inventory(monkeypatch, [_record(remote_id)])

    assert rollout._find_existing_clip(object(), _asset()) == remote_id  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "records",
    [
        pytest.param(
            [_record("-68859909_456239240"), _record("-68859909_456239241")],
            id="two-native-clips",
        ),
        pytest.param(
            [
                _record("-68859909_456239240"),
                _record("-68859909_456239241", video_type="video"),
            ],
            id="one-native-plus-one-ordinary-video",
        ),
    ],
)
def test_clip_inventory_cardinality_more_than_one_matching_object_stops(
    monkeypatch: pytest.MonkeyPatch,
    records: list[SimpleNamespace],
) -> None:
    _install_inventory(monkeypatch, records)

    with pytest.raises(rollout.MiloviTokenRolloutBlocked, match="Multiple VK objects match"):
        rollout._find_existing_clip(object(), _asset())  # type: ignore[arg-type]


def test_single_ordinary_video_with_source_marker_stops_duplicate_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_inventory(monkeypatch, [_record("-68859909_456239240", video_type="video")])

    with pytest.raises(rollout.MiloviTokenRolloutBlocked, match="ordinary VK video"):
        rollout._find_existing_clip(object(), _asset())  # type: ignore[arg-type]
