from __future__ import annotations

import inspect
from datetime import UTC, datetime

import pytest

import video_channel_manager.platforms.vk.milovi_canary_reconcile as reconcile
from video_channel_manager.platforms.vk.milovi_token_clip_rollout import MiloviTokenRolloutBlocked
from video_channel_manager.platforms.vk.wall_safety import build_wall_snapshot


def _baseline(*, captured_at: datetime):
    return build_wall_snapshot(
        community_id=68859909,
        published_items=[],
        postponed_items=[],
        published_pages=2,
        postponed_pages=1,
        complete=True,
        captured_at=captured_at,
    )


def _wall_safety(snapshot):
    return {
        "before_snapshot_sha256": snapshot.snapshot_sha256,
        "before_captured_at": snapshot.captured_at,
        "before_published_pages": snapshot.published_pages,
        "before_postponed_pages": snapshot.postponed_pages,
    }


def test_exact_incident_identity_is_pinned() -> None:
    assert reconcile.EXECUTION_CONFIRMATION == "ISSUE_323_RECONCILE_CANARY_456239225"
    assert reconcile.EXPECTED_REMOTE_ID == "-68859909_456239225"


def test_fresh_identical_wall_can_reproduce_historical_digest() -> None:
    historical = _baseline(captured_at=datetime(2026, 8, 13, 14, 38, 7, tzinfo=UTC))
    current = _baseline(captured_at=datetime(2026, 8, 13, 16, 0, 0, tzinfo=UTC))

    normalized = reconcile.normalize_current_wall_to_historical_capture(current, _wall_safety(historical))

    assert current.snapshot_sha256 != historical.snapshot_sha256
    assert normalized.snapshot_sha256 == historical.snapshot_sha256
    assert normalized.captured_at == historical.captured_at
    assert normalized.posts == current.posts


def test_changed_wall_cannot_be_reconciled_by_timestamp_normalization() -> None:
    historical = _baseline(captured_at=datetime(2026, 8, 13, 14, 38, 7, tzinfo=UTC))
    current = build_wall_snapshot(
        community_id=68859909,
        published_items=[
            {
                "owner_id": -68859909,
                "id": 123,
                "date": 1786639000,
                "text": "unrelated wall change",
                "attachments": [],
            }
        ],
        postponed_items=[],
        published_pages=2,
        postponed_pages=1,
        complete=True,
        captured_at=datetime(2026, 8, 13, 16, 0, 0, tzinfo=UTC),
    )

    with pytest.raises(MiloviTokenRolloutBlocked, match="not byte-equivalent"):
        reconcile.normalize_current_wall_to_historical_capture(current, _wall_safety(historical))


def test_reconciler_source_has_no_provider_mutation_dispatch() -> None:
    source = inspect.getsource(reconcile)
    assert ".begin_upload(" not in source
    assert ".upload_file(" not in source
    assert "ensure_postponed_wall_post" not in source
    assert "wall.post" not in source
