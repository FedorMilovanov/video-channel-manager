from __future__ import annotations

import inspect

import pytest

import video_channel_manager.platforms.vk.milovi_token_clip_rollout as rollout
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


def test_token_rollout_uses_exact_reviewed_canary_and_confirmation() -> None:
    assert len(ROLL_OUT_IDS) == 12
    assert ROLL_OUT_IDS[0] == rollout.CANARY_SOURCE_ID == "d48QLgOuiTs"
    assert rollout.EXECUTION_CONFIRMATION == "ISSUE_323_UPLOAD_12_CLIPS_AND_POSTPONE_DAILY"


def test_all_12_short_vertical_media_facts_pass_provider_inert_gate() -> None:
    rollout.validate_token_clip_media_facts(_facts(duration=60.0))


def test_any_over_60_seconds_blocks_whole_batch_before_writes() -> None:
    facts = _facts()
    facts[ROLL_OUT_IDS[7]] = (1080, 1920, 60.001)
    with pytest.raises(rollout.MiloviTokenRolloutBlocked, match=r"<=60\.0s"):
        rollout.validate_token_clip_media_facts(facts)


def test_any_nonvertical_asset_blocks_whole_batch_before_writes() -> None:
    facts = _facts()
    facts[ROLL_OUT_IDS[3]] = (1920, 1080, 30.0)
    with pytest.raises(rollout.MiloviTokenRolloutBlocked, match="not_vertical"):
        rollout.validate_token_clip_media_facts(facts)


def test_token_clip_readiness_accepts_only_native_short_video() -> None:
    readiness = rollout.clip_readiness(_asset())
    assert readiness.allowed_types == ("short_video",)
    assert readiness.require_playable is True


def test_rollout_module_has_no_browser_adapter_dependency() -> None:
    source = inspect.getsource(rollout)
    assert "milovi_native_clip_browser" not in source
    assert "playwright" not in source.casefold()


def test_wrong_execution_phrase_stops_before_creating_artifacts(tmp_path) -> None:
    output = tmp_path / "result.json"
    journal = tmp_path / "journal.json"
    with pytest.raises(rollout.MiloviTokenRolloutBlocked, match="Exact confirmation"):
        rollout.run_issue_323_token_rollout(
            confirmation="WRONG",
            output_path=output,
            journal_path=journal,
            schedule_path=tmp_path / "schedule.json",
            work_dir=tmp_path / "work",
        )
    assert not output.exists()
    assert not journal.exists()
