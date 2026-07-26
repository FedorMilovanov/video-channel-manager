from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from video_channel_manager.editorial.content import parse_content_record
from video_channel_manager.editorial.content_plan import (
    ContentAction,
    build_content_plan,
    make_content_operation,
    seal_content_plan,
    validate_content_plan,
    validate_preflight_state,
)
from video_channel_manager.platforms.youtube.renderers import YouTubeCommentRenderer

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = "snapshot/comments-20260725.json"
SNAPSHOT_SHA256 = "sha256:" + "a" * 64
SNAPSHOT_TIME = "2026-07-25T20:30:00+00:00"


def _record():
    payload = json.loads((ROOT / "content" / "editorial" / "examples" / "tyutchev-night-sea.json").read_text())
    return parse_content_record(payload)


def _operation():
    record = _record()
    rendered = YouTubeCommentRenderer().render(record)
    return make_content_operation(record=record, rendered=rendered, target_id="RQIlUvFf1KQ", action="create")


def test_operation_is_bound_to_reviewed_platform_target() -> None:
    record = _record()
    rendered = YouTubeCommentRenderer().render(record)
    with pytest.raises(ValueError, match="does not match reviewed platform target"):
        make_content_operation(record=record, rendered=rendered, target_id="different-video", action="create")

    operation = make_content_operation(record=record, rendered=rendered, target_id="RQIlUvFf1KQ", action="create")
    assert operation["reviewed_target_id"] == "RQIlUvFf1KQ"


def test_operation_rejects_invalid_review_time_action_and_whitespace_target() -> None:
    record = _record()
    rendered = YouTubeCommentRenderer().render(record)
    with pytest.raises(ValueError, match="timezone-aware"):
        make_content_operation(
            record=replace(record, reviewed_at="2026-07-25T20:30:00"),
            rendered=rendered,
            target_id="RQIlUvFf1KQ",
            action="create",
        )
    with pytest.raises(ValueError, match="unsupported content action"):
        make_content_operation(
            record=record,
            rendered=rendered,
            target_id="RQIlUvFf1KQ",
            action=cast(ContentAction, "delete"),
        )
    with pytest.raises(ValueError, match="cannot contain whitespace"):
        make_content_operation(record=record, rendered=rendered, target_id="RQIl UvFf1KQ", action="create")


def test_plan_validation_requires_reviewed_target_binding() -> None:
    plan = build_content_plan(
        source_snapshot=SNAPSHOT,
        source_snapshot_sha256=SNAPSHOT_SHA256,
        source_snapshot_generated_at=SNAPSHOT_TIME,
        operations=[_operation()],
    )
    assert validate_content_plan(plan) == []

    missing = deepcopy(plan)
    missing["operations"][0].pop("reviewed_target_id")
    missing = seal_content_plan(missing)
    assert "operations[0].reviewed_target_id must be present" in validate_content_plan(missing)

    mismatch = deepcopy(plan)
    mismatch["operations"][0]["reviewed_target_id"] = "different-video"
    mismatch = seal_content_plan(mismatch)
    assert "operations[0].reviewed_target_id does not match target_id" in validate_content_plan(mismatch)


def test_state_timestamp_must_match_signed_snapshot_instant() -> None:
    state = {
        "source_snapshot": SNAPSHOT,
        "source_snapshot_sha256": SNAPSHOT_SHA256,
        "source_snapshot_generated_at": "2026-07-25T20:30:00Z",
        "targets": [],
    }
    _, errors = validate_preflight_state(
        state,
        expected_source_snapshot=SNAPSHOT,
        expected_source_snapshot_sha256=SNAPSHOT_SHA256,
        expected_source_snapshot_generated_at=SNAPSHOT_TIME,
    )
    assert errors == []

    state["source_snapshot_generated_at"] = "2026-07-25T20:31:00+00:00"
    _, errors = validate_preflight_state(
        state,
        expected_source_snapshot=SNAPSHOT,
        expected_source_snapshot_sha256=SNAPSHOT_SHA256,
        expected_source_snapshot_generated_at=SNAPSHOT_TIME,
    )
    assert "state source_snapshot_generated_at does not match the signed plan" in errors


def test_plan_creation_cannot_predate_source_snapshot() -> None:
    plan = build_content_plan(
        source_snapshot=SNAPSHOT,
        source_snapshot_sha256=SNAPSHOT_SHA256,
        source_snapshot_generated_at=SNAPSHOT_TIME,
        operations=[_operation()],
    )
    plan["created_at"] = "2026-07-25T20:29:00+00:00"
    plan = seal_content_plan(plan)
    assert "created_at cannot be earlier than source_snapshot_generated_at" in validate_content_plan(plan)

