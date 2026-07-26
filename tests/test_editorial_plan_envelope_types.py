from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from video_channel_manager.editorial.content import parse_content_record
from video_channel_manager.editorial.content_plan import (
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


def _operation():
    payload = json.loads((ROOT / "content" / "editorial" / "examples" / "tyutchev-night-sea.json").read_text())
    record = parse_content_record(payload)
    rendered = YouTubeCommentRenderer().render(record)
    return make_content_operation(record=record, rendered=rendered, target_id="RQIlUvFf1KQ", action="create")


def test_plan_and_state_envelopes_reject_non_string_metadata() -> None:
    plan = build_content_plan(
        source_snapshot=SNAPSHOT,
        source_snapshot_sha256=SNAPSHOT_SHA256,
        source_snapshot_generated_at=SNAPSHOT_TIME,
        operations=[_operation()],
    )
    malformed = deepcopy(plan)
    malformed["source_snapshot"] = 123
    malformed["source_snapshot_generated_at"] = 2026
    malformed["created_at"] = 2026
    malformed["mode"] = True
    malformed = seal_content_plan(malformed)
    errors = validate_content_plan(malformed)
    assert "source_snapshot must be a nonblank string" in errors
    assert "source_snapshot_generated_at must be a string" in errors
    assert "created_at must be a string" in errors
    assert "mode must be a string" in errors

    state = {
        "source_snapshot": 123,
        "source_snapshot_sha256": 456,
        "source_snapshot_generated_at": 2026,
        "targets": [],
    }
    _, state_errors = validate_preflight_state(
        state,
        expected_source_snapshot=SNAPSHOT,
        expected_source_snapshot_sha256=SNAPSHOT_SHA256,
        expected_source_snapshot_generated_at=SNAPSHOT_TIME,
    )
    assert "state source_snapshot must be a string" in state_errors
    assert "state source_snapshot_sha256 must be a string" in state_errors
    assert "state source_snapshot_generated_at must be a string" in state_errors
