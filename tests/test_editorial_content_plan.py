from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from video_channel_manager.editorial.content import parse_content_record
from video_channel_manager.editorial.content_plan import (
    build_content_plan,
    make_content_operation,
    operation_state,
    validate_content_plan,
)
from video_channel_manager.platforms.youtube.renderers import YouTubeCommentRenderer


def _record():
    path = Path(__file__).resolve().parents[1] / "content" / "editorial" / "examples" / "tyutchev-night-sea.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return parse_content_record(payload)


def test_signed_plan_validates_and_is_idempotent_after_apply() -> None:
    record = _record()
    rendered = YouTubeCommentRenderer().render(record)
    operation = make_content_operation(
        record=record,
        rendered=rendered,
        target_id="RQIlUvFf1KQ",
        action="create",
    )
    plan = build_content_plan(
        source_snapshot="snapshot/comments-20260725.json",
        source_snapshot_generated_at="2026-07-25T20:30:00+00:00",
        operations=[operation],
    )
    assert validate_content_plan(plan) == []
    assert operation_state(operation, current_text=None, current_revision=None) == "ready"
    assert operation_state(operation, current_text=rendered.text, current_revision=None) == "already_applied"
    assert operation_state(operation, current_text="different", current_revision=None) == "conflict"


def test_update_requires_exact_before_and_revision() -> None:
    record = _record()
    rendered = YouTubeCommentRenderer().render(record)
    with pytest.raises(ValueError, match="exact before-text"):
        make_content_operation(
            record=record,
            rendered=rendered,
            target_id="RQIlUvFf1KQ",
            action="update",
        )


def test_plan_tampering_and_duplicate_rendered_text_are_rejected() -> None:
    record = _record()
    rendered = YouTubeCommentRenderer().render(record)
    operation = make_content_operation(
        record=record,
        rendered=rendered,
        target_id="RQIlUvFf1KQ",
        action="create",
    )
    plan = build_content_plan(
        source_snapshot="snapshot/comments-20260725.json",
        source_snapshot_generated_at="2026-07-25T20:30:00+00:00",
        operations=[operation],
    )
    tampered = deepcopy(plan)
    operations = tampered["operations"]
    assert isinstance(operations, list)
    first = operations[0]
    assert isinstance(first, dict)
    first["rendered_text"] = "tampered"
    assert any("mismatch" in error for error in validate_content_plan(tampered))

    duplicate = build_content_plan(
        source_snapshot="snapshot/comments-20260725.json",
        source_snapshot_generated_at="2026-07-25T20:30:00+00:00",
        operations=[operation, dict(operation, target_id="another-target")],
    )
    assert any(error.startswith("duplicate rendered texts") for error in validate_content_plan(duplicate))
