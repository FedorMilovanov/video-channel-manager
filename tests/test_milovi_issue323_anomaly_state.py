from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_anomaly_state import (
    ANOMALY_CLIP_REMOTE_ID,
    ANOMALY_STATE_SCHEMA,
    ANOMALY_WALL_REMOTE_ID,
    LEGACY_FINALIZER_SCHEMA,
    MiloviIssue323AnomalyBlocked,
    load_anomaly_cleanup_state,
)


def _binding() -> dict[str, object]:
    return {
        "community_id": 68859909,
        "owner_id": -68859909,
        "anomaly_wall_remote_id": ANOMALY_WALL_REMOTE_ID,
        "anomaly_clip_remote_id": ANOMALY_CLIP_REMOTE_ID,
    }


def test_missing_state_creates_only_terminally_non_authoritative_cleanup_record(tmp_path: Path) -> None:
    path = tmp_path / "anomaly-state.json"

    payload = load_anomaly_cleanup_state(path)

    assert payload["schema_name"] == ANOMALY_STATE_SCHEMA
    assert payload["cleanup_475"] == {
        "status": "uninitialized_no_delete_authority",
        "delete_authority": False,
    }
    assert "promotion_plan" not in payload
    assert "clip_description_edits" not in payload
    assert "wall_message_edits" not in payload


def test_legacy_finalizer_journal_is_accepted_only_as_cleanup_evidence(tmp_path: Path) -> None:
    path = tmp_path / "legacy-finalizer.json"
    payload = {
        "schema_name": LEGACY_FINALIZER_SCHEMA,
        "schema_version": 1,
        **_binding(),
        "cleanup_475": {"status": "verified_absent", "delete_dispatch_started": True},
        "promotion_plan": {"manually_changed": {"clip_description_sha256": "deliberately-not-reviewed"}},
        "clip_description_edits": {"stale": {"status": "pending"}},
        "wall_message_edits": {"stale": {"status": "pending"}},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_anomaly_cleanup_state(path)

    assert loaded["cleanup_475"]["status"] == "verified_absent"
    assert loaded["promotion_plan"] == payload["promotion_plan"]
    # The loader deliberately does not derive or compare any promotion digest.
    assert loaded == payload


def test_legacy_or_new_state_with_wrong_provider_identity_blocks(tmp_path: Path) -> None:
    path = tmp_path / "anomaly-state.json"
    payload = {
        "schema_name": LEGACY_FINALIZER_SCHEMA,
        "schema_version": 1,
        **_binding(),
        "cleanup_475": {"status": "verified_absent"},
    }
    payload["owner_id"] = -1
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(MiloviIssue323AnomalyBlocked, match="binding mismatch"):
        load_anomaly_cleanup_state(path)
