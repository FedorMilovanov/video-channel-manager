from __future__ import annotations

import inspect

import pytest

import video_channel_manager.platforms.vk.milovi_token_clip_rollout as support
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS, SourceAsset


def _facts(*, duration: float = 59.0, width: int = 1080, height: int = 1920) -> dict[str, tuple[int, int, float]]:
    return {source_id: (width, height, duration) for source_id in ROLL_OUT_IDS}


def _asset() -> SourceAsset:
    return SourceAsset(
        source_id=ROLL_OUT_IDS[0],
        source_url=f"https://www.youtube.com/shorts/{ROLL_OUT_IDS[0]}",
        title="Milovi test",
        duration_seconds=59,
        media_path="unused.mp4",
        media_sha256="0" * 64,
        width=1080,
        height=1920,
        description="source marker",
        wall_message="wall",
    )


def test_issue323_state_support_uses_exact_reviewed_canary() -> None:
    assert len(ROLL_OUT_IDS) == 12
    assert ROLL_OUT_IDS[0] == support.CANARY_SOURCE_ID == "d48QLgOuiTs"


def test_all_12_short_vertical_media_facts_pass_provider_inert_gate() -> None:
    support.validate_token_clip_media_facts(_facts(duration=60.0))


def test_any_over_60_seconds_blocks_provider_inert_gate() -> None:
    facts = _facts()
    facts[ROLL_OUT_IDS[7]] = (1080, 1920, 60.001)
    with pytest.raises(support.MiloviTokenRolloutBlocked, match=r"<=60\.0s"):
        support.validate_token_clip_media_facts(facts)


def test_any_nonvertical_asset_blocks_provider_inert_gate() -> None:
    facts = _facts()
    facts[ROLL_OUT_IDS[3]] = (1920, 1080, 30.0)
    with pytest.raises(support.MiloviTokenRolloutBlocked, match="not_vertical"):
        support.validate_token_clip_media_facts(facts)


def test_clip_readiness_accepts_only_native_short_video() -> None:
    readiness = support.clip_readiness(_asset())
    assert readiness.allowed_types == ("short_video",)
    assert readiness.require_playable is True


def test_historical_token_module_has_no_execution_or_provider_write_surface() -> None:
    source = inspect.getsource(support)
    forbidden = (
        "run_issue_323_token_rollout",
        "def main(",
        'if __name__ == "__main__"',
        "execute_upload_operation",
        "VkWallWriter",
        "local_vk_write_lock",
        "begin_upload",
        "upload_file",
        "wall.delete",
    )
    assert [token for token in forbidden if token in source] == []
