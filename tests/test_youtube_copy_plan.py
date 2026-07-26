from __future__ import annotations

from copy import deepcopy

import pytest

from video_channel_manager.platforms.youtube.copy_plan import (
    calculate_copy_plan_sha256,
    finalize_copy_plan,
    sha256_text,
    validate_copy_plan,
)


def _plan(*, before: str = "Старое", after: str = "Новое") -> dict[str, object]:
    plan: dict[str, object] = {
        "ruleset": "youtube-copy-safe-v2",
        "generated_at": "2026-07-25T00:00:00+00:00",
        "source_audit_package": "audit.json",
        "source_audit_sha256": "sha256:source",
        "target_channel_id": "UC-channel",
        "read_only": True,
        "videos_checked": 2,
        "operations_count": 1,
        "blocked_operations_count": 0,
        "unresolved_error_videos": 1,
        "fix_code_counts": {},
        "operations": [
            {
                "operation": "replace_video_description",
                "platform": "youtube",
                "ruleset": "youtube-copy-safe-v2",
                "channel_id": "UC-channel",
                "video_id": "video-1",
                "title": "Видео 1",
                "expected_revision": "sha256:revision",
                "before_description": before,
                "after_description": after,
                "before_sha256": sha256_text(before),
                "after_sha256": sha256_text(after),
                "fixes": [],
            }
        ],
        "unresolved": [
            {
                "video_id": "video-2",
                "channel_id": "UC-channel",
                "title": "Видео 2",
                "errors": [{"code": "manual_review", "message": "Проверить"}],
            }
        ],
    }
    return finalize_copy_plan(plan, checked_video_ids=["video-2", "video-1"])


def test_copy_plan_stores_sorted_exact_coverage_and_self_digest() -> None:
    plan = _plan()

    validate_copy_plan(plan)
    assert plan["schema_version"] == 3
    assert plan["checked_video_ids"] == ["video-1", "video-2"]
    assert str(plan["checked_video_ids_sha256"]).startswith("sha256:")
    assert plan["plan_sha256"] == calculate_copy_plan_sha256(plan)


def test_copy_plan_accepts_empty_before_description() -> None:
    plan = _plan(before="", after="Новый текст")

    validate_copy_plan(plan)
    assert plan["operations"][0]["before_sha256"] == sha256_text("")


def test_copy_plan_rejects_modified_after_text() -> None:
    plan = deepcopy(_plan())
    plan["operations"][0]["after_description"] = "Подмена"
    plan["plan_sha256"] = calculate_copy_plan_sha256(plan)

    with pytest.raises(ValueError, match="after_sha256 is invalid"):
        validate_copy_plan(plan)


def test_copy_plan_rejects_target_channel_drift() -> None:
    plan = deepcopy(_plan())
    plan["operations"][0]["channel_id"] = "UC-other"
    plan["plan_sha256"] = calculate_copy_plan_sha256(plan)

    with pytest.raises(ValueError, match="not UC-channel"):
        validate_copy_plan(plan)


def test_copy_plan_rejects_coverage_hash_mismatch() -> None:
    plan = deepcopy(_plan())
    plan["checked_video_ids_sha256"] = "sha256:wrong"
    plan["plan_sha256"] = calculate_copy_plan_sha256(plan)

    with pytest.raises(ValueError, match="checked_video_ids_sha256"):
        validate_copy_plan(plan)


def test_copy_plan_rejects_operation_outside_checked_ids() -> None:
    plan = deepcopy(_plan())
    plan["operations"][0]["video_id"] = "video-3"
    plan["plan_sha256"] = calculate_copy_plan_sha256(plan)

    with pytest.raises(ValueError, match="absent from checked_video_ids"):
        validate_copy_plan(plan)


def test_copy_plan_rejects_duplicate_id_across_sections() -> None:
    plan = deepcopy(_plan())
    plan["unresolved"][0]["video_id"] = "video-1"
    plan["plan_sha256"] = calculate_copy_plan_sha256(plan)

    with pytest.raises(ValueError, match="repeats video IDs"):
        validate_copy_plan(plan)


def test_copy_plan_rejects_self_digest_mismatch() -> None:
    plan = deepcopy(_plan())
    plan["generated_at"] = "changed-after-review"

    with pytest.raises(ValueError, match="plan_sha256"):
        validate_copy_plan(plan)


def test_copy_plan_rejects_legacy_schema() -> None:
    plan = deepcopy(_plan())
    plan["schema_version"] = 2
    plan["plan_sha256"] = calculate_copy_plan_sha256(plan)

    with pytest.raises(ValueError, match="schema_version 3"):
        validate_copy_plan(plan)
