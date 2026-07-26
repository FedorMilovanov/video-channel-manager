from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from video_channel_manager.editorial.content import parse_content_record
from video_channel_manager.editorial.content_plan import (
    build_content_plan,
    make_content_operation,
    operation_state,
    validate_content_plan,
    validate_preflight_state,
)
from video_channel_manager.platforms.youtube.renderers import YouTubeCommentRenderer

_SNAPSHOT = "snapshot/comments-20260725.json"
_SNAPSHOT_SHA256 = "sha256:" + "a" * 64


def _record():
    path = Path(__file__).resolve().parents[1] / "content" / "editorial" / "examples" / "tyutchev-night-sea.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return parse_content_record(payload)


def _create_operation():
    record = _record()
    rendered = YouTubeCommentRenderer().render(record)
    operation = make_content_operation(
        record=record,
        rendered=rendered,
        target_id="RQIlUvFf1KQ",
        action="create",
    )
    return operation, rendered.text


def _plan(operation):
    return build_content_plan(
        source_snapshot=_SNAPSHOT,
        source_snapshot_sha256=_SNAPSHOT_SHA256,
        source_snapshot_generated_at="2026-07-25T20:30:00+00:00",
        operations=[operation],
    )


def test_signed_plan_validates_and_is_idempotent_after_apply() -> None:
    operation, rendered_text = _create_operation()
    plan = _plan(operation)
    assert validate_content_plan(plan) == []
    assert (
        operation_state(
            operation,
            target_exists=False,
            current_text=None,
            current_revision=None,
        )
        == "ready"
    )
    assert (
        operation_state(
            operation,
            target_exists=True,
            current_text=rendered_text,
            current_revision="sha256:live",
        )
        == "already_applied"
    )
    assert (
        operation_state(
            operation,
            target_exists=True,
            current_text="different",
            current_revision="sha256:live",
        )
        == "conflict"
    )


def test_create_does_not_treat_missing_observation_as_absence() -> None:
    operation, _ = _create_operation()
    assert (
        operation_state(
            operation,
            target_exists=None,
            current_text=None,
            current_revision=None,
        )
        == "conflict"
    )


def test_update_requires_exact_before_revision_and_presence() -> None:
    record = _record()
    rendered = YouTubeCommentRenderer().render(record)
    with pytest.raises(ValueError, match="exact before-text"):
        make_content_operation(
            record=record,
            rendered=rendered,
            target_id="RQIlUvFf1KQ",
            action="update",
        )

    operation = make_content_operation(
        record=record,
        rendered=rendered,
        target_id="RQIlUvFf1KQ",
        action="update",
        expected_before_text="old text",
        expected_revision="sha256:old",
    )
    assert (
        operation_state(
            operation,
            target_exists=False,
            current_text=None,
            current_revision=None,
        )
        == "conflict"
    )
    assert (
        operation_state(
            operation,
            target_exists=True,
            current_text="old text",
            current_revision="sha256:old",
        )
        == "ready"
    )


def test_preflight_state_requires_snapshot_binding_unique_targets_and_explicit_existence() -> None:
    payload = {
        "source_snapshot": _SNAPSHOT,
        "source_snapshot_sha256": _SNAPSHOT_SHA256,
        "source_snapshot_generated_at": "2026-07-25T20:30:00+00:00",
        "targets": [
            {
                "platform": "youtube",
                "surface": "comment",
                "target_id": "RQIlUvFf1KQ",
                "exists": False,
                "current_text": None,
                "current_revision": None,
            }
        ],
    }
    state_by_key, errors = validate_preflight_state(
        payload,
        expected_source_snapshot=_SNAPSHOT,
        expected_source_snapshot_sha256=_SNAPSHOT_SHA256,
    )
    assert errors == []
    assert "youtube:comment:RQIlUvFf1KQ" in state_by_key

    mismatched = deepcopy(payload)
    mismatched["source_snapshot"] = "another-snapshot"
    _, errors = validate_preflight_state(
        mismatched,
        expected_source_snapshot=_SNAPSHOT,
        expected_source_snapshot_sha256=_SNAPSHOT_SHA256,
    )
    assert "state source_snapshot does not match the signed plan" in errors

    digest_mismatch = deepcopy(payload)
    digest_mismatch["source_snapshot_sha256"] = "sha256:" + "b" * 64
    _, errors = validate_preflight_state(
        digest_mismatch,
        expected_source_snapshot=_SNAPSHOT,
        expected_source_snapshot_sha256=_SNAPSHOT_SHA256,
    )
    assert "state source_snapshot_sha256 does not match the signed plan" in errors

    duplicate = deepcopy(payload)
    duplicate["targets"].append(deepcopy(duplicate["targets"][0]))
    _, errors = validate_preflight_state(
        duplicate,
        expected_source_snapshot=_SNAPSHOT,
        expected_source_snapshot_sha256=_SNAPSHOT_SHA256,
    )
    assert any(error.startswith("duplicate state target") for error in errors)

    ambiguous = deepcopy(payload)
    ambiguous["targets"][0].pop("exists")
    _, errors = validate_preflight_state(
        ambiguous,
        expected_source_snapshot=_SNAPSHOT,
        expected_source_snapshot_sha256=_SNAPSHOT_SHA256,
    )
    assert "targets[0].exists must be true or false" in errors


def test_plan_requires_snapshot_digest_aware_time_and_supported_surface() -> None:
    operation, _ = _create_operation()
    with pytest.raises(ValueError, match="source_snapshot_sha256"):
        build_content_plan(
            source_snapshot=_SNAPSHOT,
            source_snapshot_sha256="not-a-digest",
            source_snapshot_generated_at="2026-07-25T20:30:00+00:00",
            operations=[operation],
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        build_content_plan(
            source_snapshot=_SNAPSHOT,
            source_snapshot_sha256=_SNAPSHOT_SHA256,
            source_snapshot_generated_at="2026-07-25T20:30:00",
            operations=[operation],
        )

    plan = _plan(operation)
    invalid = deepcopy(plan)
    invalid_operations = invalid["operations"]
    assert isinstance(invalid_operations, list)
    invalid_operation = invalid_operations[0]
    assert isinstance(invalid_operation, dict)
    invalid_operation["surface"] = "post"
    assert any("unsupported youtube surface" in error for error in validate_content_plan(invalid))


def test_plan_tampering_and_duplicate_rendered_text_are_rejected() -> None:
    operation, _ = _create_operation()
    plan = _plan(operation)
    tampered = deepcopy(plan)
    operations = tampered["operations"]
    assert isinstance(operations, list)
    first = operations[0]
    assert isinstance(first, dict)
    first["rendered_text"] = "tampered"
    assert any("mismatch" in error for error in validate_content_plan(tampered))

    second_record = replace(
        _record(),
        content_id="tyutchev-night-sea-duplicate",
        variation_key="tyutchev-night-sea-duplicate",
        platform_targets={},
    )
    second_rendered = YouTubeCommentRenderer().render(second_record)
    second_operation = make_content_operation(
        record=second_record,
        rendered=second_rendered,
        target_id="another-target",
        action="create",
    )
    duplicate = build_content_plan(
        source_snapshot=_SNAPSHOT,
        source_snapshot_sha256=_SNAPSHOT_SHA256,
        source_snapshot_generated_at="2026-07-25T20:30:00+00:00",
        operations=[operation, second_operation],
    )
    assert any(error.startswith("duplicate rendered texts") for error in validate_content_plan(duplicate))
