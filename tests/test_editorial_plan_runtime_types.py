from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.editorial._content_plan_common import (
    parse_aware_datetime,
    valid_sha256,
    valid_stable_id,
)
from video_channel_manager.editorial.content import parse_content_record
from video_channel_manager.editorial.content_plan import (
    build_content_plan,
    make_content_operation,
    operation_state,
    seal_content_plan,
    validate_content_plan,
)
from video_channel_manager.platforms.youtube.renderers import YouTubeCommentRenderer

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = "snapshot/comments-20260725.json"
SNAPSHOT_SHA256 = "sha256:" + "a" * 64
SNAPSHOT_TIME = "2026-07-25T20:30:00+00:00"


def _record():
    path = ROOT / "content" / "editorial" / "examples" / "tyutchev-night-sea.json"
    return parse_content_record(json.loads(path.read_text(encoding="utf-8")))


def _operation(*, action: str = "create"):
    record = _record()
    rendered = YouTubeCommentRenderer().render(record)
    kwargs: dict[str, object] = {}
    if action == "update":
        kwargs = {
            "expected_before_text": "old text",
            "expected_revision": "sha256:old",
        }
    return make_content_operation(
        record=record,
        rendered=rendered,
        target_id="RQIlUvFf1KQ",
        action=action,  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )


def _plan(operation: dict[str, object] | None = None) -> dict[str, object]:
    return build_content_plan(
        source_snapshot=SNAPSHOT,
        source_snapshot_sha256=SNAPSHOT_SHA256,
        source_snapshot_generated_at=SNAPSHOT_TIME,
        operations=[operation or _operation()],
    )


def test_common_plan_helpers_do_not_coerce_scalars() -> None:
    assert valid_sha256(123) is False
    assert valid_sha256(True) is False
    assert valid_stable_id(123) is False
    assert parse_aware_datetime(123) is None


def test_operation_state_fails_closed_for_non_string_runtime_values() -> None:
    create = _operation()
    create["rendered_text"] = 123
    assert (
        operation_state(
            create,
            target_exists=True,
            current_text="123",
            current_revision="revision",
        )
        == "conflict"
    )

    update = _operation(action="update")
    update["expected_before_text"] = 123
    assert (
        operation_state(
            update,
            target_exists=True,
            current_text="123",
            current_revision="sha256:old",
        )
        == "conflict"
    )
    assert (
        operation_state(
            _operation(),
            target_exists=True,
            current_text=123,  # type: ignore[arg-type]
            current_revision=None,
        )
        == "conflict"
    )


def test_sealing_rejects_non_string_operation_identity() -> None:
    plan = _plan()
    operation = plan["operations"][0]
    assert isinstance(operation, dict)

    operation["operation_id"] = 123
    with pytest.raises(ValueError, match="operation_id must be a nonblank string"):
        seal_content_plan(plan)

    operation["operation_id"] = "valid-id"
    operation["action"] = True
    with pytest.raises(ValueError, match="action must be create or update"):
        seal_content_plan(plan)


def test_plan_validation_reports_strict_envelope_and_operation_types() -> None:
    plan = _plan()
    operation = plan["operations"][0]
    assert isinstance(operation, dict)
    plan["schema_version"] = True
    plan["operation_set_sha256"] = 123
    plan["counts"] = {"create": True}
    plan["plan_sha256"] = 456
    operation["operation_id"] = 789
    operation["rendered_sha256"] = 101
    operation["expected_before_sha256"] = 102
    operation["source_ids_sha256"] = 103
    operation["review_status"] = True

    errors = validate_content_plan(plan)

    expected = {
        "schema_version must be 2",
        "operation_set_sha256 must be a string",
        "counts must map create/update to nonnegative integers",
        "plan_sha256 must be a string",
        "operations[0].operation_id must be a nonblank string",
        "operations[0].rendered_sha256 must be a string",
        "operations[0].expected_before_sha256 must be a string or null",
        "operations[0].source_ids_sha256 must be a string",
        "operations[0].review_status must be a string",
    }
    assert expected.issubset(set(errors))


def test_plan_validation_does_not_crash_on_unhashable_action() -> None:
    plan = _plan()
    operation = plan["operations"][0]
    assert isinstance(operation, dict)
    operation["action"] = []

    errors = validate_content_plan(plan)

    assert "operations[0].action must be a string" in errors
    assert "operations[0].action must be create or update" in errors


def test_operation_state_rejects_invalid_action_even_when_text_matches() -> None:
    operation = _operation()
    current_text = operation["rendered_text"]
    assert isinstance(current_text, str)
    operation["action"] = "delete"

    assert (
        operation_state(
            operation,
            target_exists=True,
            current_text=current_text,
            current_revision=None,
        )
        == "conflict"
    )


def test_operation_state_rejects_hash_tampering_even_when_text_matches() -> None:
    operation = _operation()
    current_text = operation["rendered_text"]
    assert isinstance(current_text, str)
    operation["rendered_sha256"] = "sha256:" + "0" * 64

    assert (
        operation_state(
            operation,
            target_exists=True,
            current_text=current_text,
            current_revision=None,
        )
        == "conflict"
    )
