from __future__ import annotations

from datetime import datetime
from pathlib import Path

from video_channel_manager.lordchrist_research_rollout import (
    FIRST_CANARY_PUBLICATION_ID,
    load_lordchrist_research_rollout_approval,
    materialize_lordchrist_research_rollout,
)
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_research import load_research_queue
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "content/telegram/channels/lordchrist.json"
BINDING = ROOT / "content/telegram/channels/lordchrist-target-binding.json"
QUEUE = ROOT / "content/telegram/lordchrist/research-queues/calvin-spurgeon-macarthur-v2.json"
APPROVAL = ROOT / "content/telegram/lordchrist/research-queues/rollout-approval-2026-08.json"
WORKFLOW = ROOT / ".github/workflows/lordchrist-research-v2-publisher.yml"
LEGACY = ROOT / ".github/workflows/lordchrist-telegram-poster.yml"


def test_exact_rollout_materializes_only_from_reviewed_identity(tmp_path: Path) -> None:
    approval = load_lordchrist_research_rollout_approval(APPROVAL)
    base_profile = load_channel_profile(PROFILE)
    binding = load_target_binding(BINDING, base_profile)
    release, runtime_profile = materialize_lordchrist_research_rollout(
        profile_path=PROFILE,
        queue_path=QUEUE,
        binding_path=BINDING,
        approval_path=APPROVAL,
        release_output_path=tmp_path / "release.json",
        runtime_profile_output_path=tmp_path / "profile.json",
    )
    assert base_profile.provider_writes_authorized is False
    assert runtime_profile.provider_writes_authorized is True
    assert runtime_profile.digest == base_profile.digest
    assert release.release_authorized is True
    assert release.candidate_digest() == approval.candidate_sha256
    assert release.digest == approval.approved_release_sha256
    assert release.target_binding_sha256 == binding.digest
    assert release.chat_id == -1001295216957
    assert release.bot_id == 8716602202
    assert release.items[0].publication_id == FIRST_CANARY_PUBLICATION_ID
    assert [item.scheduled_at.isoformat() for item in release.items] == [
        "2026-08-10T15:00:00+03:00",
        "2026-08-12T15:00:00+03:00",
        "2026-08-14T15:00:00+03:00",
        "2026-08-16T15:00:00+03:00",
        "2026-08-18T15:00:00+03:00",
    ]


def test_canonical_research_and_profile_remain_inert() -> None:
    profile = load_channel_profile(PROFILE)
    research = load_research_queue(QUEUE)
    assert profile.provider_writes_authorized is False
    assert profile.daily_verified_limit == 1
    assert research.schedule.state == "staged"
    assert research.schedule.activation_at_utc is None
    assert research.schedule.canary_publication_id is None
    assert research.schedule.canary_message_id is None
    assert research.live_eligible is False


def test_research_v2_provider_workflow_is_retired_without_restoring_a_writer() -> None:
    assert not WORKFLOW.exists()
    assert LEGACY.exists()
    legacy = LEGACY.read_text(encoding="utf-8")
    assert "group: lordchrist-telegram-publisher" in legacy


def test_historical_cross_track_limits_remain_frozen_in_approval() -> None:
    approval = load_lordchrist_research_rollout_approval(APPROVAL)
    assert approval.per_track_daily_verified_limit == 1
    assert approval.cross_track_daily_verified_limit == 2
    assert approval.cross_track_guard_issue == 246


def test_approval_binds_issue_and_today_start() -> None:
    approval = load_lordchrist_research_rollout_approval(APPROVAL)
    assert approval.owning_issue == 242
    assert approval.first_canary_publication_id == FIRST_CANARY_PUBLICATION_ID
    assert approval.start_at == datetime.fromisoformat("2026-08-10T15:00:00+03:00")
