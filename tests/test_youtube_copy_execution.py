from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from video_channel_manager.platforms.youtube.copy_execution import (
    preflight_copy_operations,
    reconcile_copy_operations,
    verify_copy_operations,
)
from video_channel_manager.platforms.youtube.write_lock import local_youtube_write_lock
from video_channel_manager.platforms.youtube.writer import YouTubeRevisionConflictError, YouTubeWriteError


@dataclass
class Snapshot:
    video_id: str
    channel_id: str
    title: str
    description: str
    revision: str


class FakeWriter:
    def __init__(self, snapshots: dict[str, Snapshot]) -> None:
        self.snapshots = snapshots

    def read_description(self, video_id: str) -> Snapshot:
        return self.snapshots[video_id]


def _operation(*, before: str = "Before", after: str = "After", revision: str = "rev-1") -> dict[str, str]:
    return {
        "video_id": "video-1",
        "channel_id": "channel-1",
        "expected_revision": revision,
        "before_description": before,
        "after_description": after,
    }


def test_preflight_is_idempotent_after_youtube_normalization() -> None:
    writer = FakeWriter(
        {
            "video-1": Snapshot(
                video_id="video-1",
                channel_id="channel-1",
                title="Title",
                description="After\n",
                revision="rev-2",
            )
        }
    )
    result = preflight_copy_operations([_operation()], confirm_channel="channel-1", writer=writer)
    assert result.prepared == []
    assert result.already_applied == 1
    assert result.revision_drift_tolerated == 0


def test_preflight_tolerates_revision_drift_only_when_before_text_matches() -> None:
    writer = FakeWriter(
        {
            "video-1": Snapshot(
                video_id="video-1",
                channel_id="channel-1",
                title="Current title",
                description="Before",
                revision="server-refreshed",
            )
        }
    )
    result = preflight_copy_operations([_operation()], confirm_channel="channel-1", writer=writer)
    assert len(result.prepared) == 1
    assert result.prepared[0]["title"] == "Current title"
    assert result.prepared[0]["revision_drift"] is True
    assert result.revision_drift_tolerated == 1


def test_preflight_refuses_third_description_state() -> None:
    writer = FakeWriter(
        {
            "video-1": Snapshot(
                video_id="video-1",
                channel_id="channel-1",
                title="Title",
                description="Manual edit",
                revision="rev-2",
            )
        }
    )
    with pytest.raises(YouTubeRevisionConflictError):
        preflight_copy_operations([_operation()], confirm_channel="channel-1", writer=writer)


def test_final_postflight_reports_whole_batch_mismatch() -> None:
    writer = FakeWriter(
        {
            "video-1": Snapshot(
                video_id="video-1",
                channel_id="channel-1",
                title="Title",
                description="Changed again",
                revision="rev-3",
            )
        }
    )
    failures = verify_copy_operations([_operation()], confirm_channel="channel-1", writer=writer)
    assert failures == [
        {
            "video_id": "video-1",
            "reason": "live description does not match the planned after-state",
        }
    ]


def test_local_write_lock_rejects_second_process_context(tmp_path: Path) -> None:
    lock = tmp_path / "youtube.lock"
    with local_youtube_write_lock(lock, account="account", channel_id="channel"):
        with pytest.raises(YouTubeWriteError):
            with local_youtube_write_lock(lock, account="account", channel_id="channel"):
                pass
    assert not lock.exists()


def test_reconcile_reads_after_state_without_mutating_owner_video() -> None:
    writer = FakeWriter({"video-1": Snapshot("video-1", "channel-1", "Title", "After\n", "rev-2")})
    row = reconcile_copy_operations([_operation()], confirm_channel="channel-1", writer=writer)[0]
    assert row["state"] == "live_after"
    assert row["video_id"] == "video-1"
    assert row["provider_mutations"] == 0
    assert row["safe_to_replay"] is False
    assert row["planned_after_sha256"].startswith("sha256:")


def test_reconcile_before_state_is_not_retry_authority() -> None:
    writer = FakeWriter({"video-1": Snapshot("video-1", "channel-1", "Title", "Before", "rev-3")})
    rows = reconcile_copy_operations([_operation()], confirm_channel="channel-1", writer=writer)
    assert rows[0]["state"] == "live_before"
    assert rows[0]["safe_to_replay"] is False


def test_reconcile_unknown_third_state_is_explicit_conflict() -> None:
    writer = FakeWriter({"video-1": Snapshot("video-1", "channel-1", "Title", "Concurrent edit", "rev-3")})
    rows = reconcile_copy_operations([_operation()], confirm_channel="channel-1", writer=writer)
    assert rows[0]["state"] == "live_third_state"
    assert rows[0]["safe_to_replay"] is False


def test_reconcile_refuses_live_wrong_channel() -> None:
    writer = FakeWriter({"video-1": Snapshot("video-1", "wrong-channel", "Title", "After", "rev-2")})
    with pytest.raises(YouTubeRevisionConflictError, match="Owner mismatch"):
        reconcile_copy_operations([_operation()], confirm_channel="channel-1", writer=writer)


def test_reconcile_refuses_unsigned_target_change_or_duplicate_id() -> None:
    writer = FakeWriter({"video-1": Snapshot("video-1", "channel-1", "Title", "After", "rev-2")})
    with pytest.raises(ValueError, match="--confirm-channel"):
        reconcile_copy_operations([_operation()], confirm_channel="", writer=writer)
    with pytest.raises(ValueError, match="No YouTube copy"):
        reconcile_copy_operations([], confirm_channel="channel-1", writer=writer)
    with pytest.raises(ValueError, match="does not belong"):
        reconcile_copy_operations(
            [{**_operation(), "channel_id": "wrong-channel"}],
            confirm_channel="channel-1",
            writer=writer,
        )
    with pytest.raises(ValueError, match="Duplicate YouTube copy video ID"):
        reconcile_copy_operations([_operation(), _operation()], confirm_channel="channel-1", writer=writer)
