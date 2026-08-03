from __future__ import annotations

from copy import deepcopy

import pytest

from video_channel_manager.platforms.vk.catalog import (
    VK_CATALOG_PLAN_SCHEMA,
    VK_CATALOG_PLAN_VERSION,
    calculate_vk_catalog_plan_sha256,
)
from video_channel_manager.platforms.vk.catalog_upgrade import upgrade_vk_catalog_plan_identity


def _legacy_plan(*, source_channel_id: str, target_community_id: int) -> dict[str, object]:
    plan: dict[str, object] = {
        "schema_name": VK_CATALOG_PLAN_SCHEMA,
        "schema_version": 1,
        "policy_version": "vk-catalog-structured-v1",
        "source_channel_id": source_channel_id,
        "target_community_id": target_community_id,
        "text_operations": [{"operation_id": "video-text:update:1"}],
    }
    plan["plan_sha256"] = calculate_vk_catalog_plan_sha256(plan)
    return plan


def test_upgrade_infers_poet_from_exact_target_and_preserves_input() -> None:
    original = _legacy_plan(source_channel_id="legacy-unregistered-channel", target_community_id=235216998)

    upgraded = upgrade_vk_catalog_plan_identity(original)

    assert original["schema_version"] == 1
    assert "project_key" not in original
    assert upgraded["schema_version"] == VK_CATALOG_PLAN_VERSION
    assert upgraded["project_key"] == "legendary-poet"
    assert upgraded["text_operations"][0]["project_key"] == "legendary-poet"  # type: ignore[index]
    assert upgraded["plan_sha256"] == calculate_vk_catalog_plan_sha256(upgraded)


def test_upgrade_infers_poet_from_exact_source_when_target_is_legacy() -> None:
    original = _legacy_plan(
        source_channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ",
        target_community_id=123,
    )

    upgraded = upgrade_vk_catalog_plan_identity(original)

    assert upgraded["project_key"] == "legendary-poet"


def test_upgrade_rejects_cross_project_provider_targets() -> None:
    original = _legacy_plan(
        source_channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ",
        target_community_id=60805374,
    )

    with pytest.raises(ValueError, match="unknown or conflicting"):
        upgrade_vk_catalog_plan_identity(original)


def test_upgrade_rejects_tampered_legacy_plan_before_identity_changes() -> None:
    original = _legacy_plan(
        source_channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ",
        target_community_id=235216998,
    )
    tampered = deepcopy(original)
    tampered["target_community_id"] = 60805374

    with pytest.raises(ValueError, match="self-digest"):
        upgrade_vk_catalog_plan_identity(tampered)


def test_upgrade_rejects_conflicting_operation_project() -> None:
    original = _legacy_plan(
        source_channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ",
        target_community_id=235216998,
    )
    operation = original["text_operations"][0]  # type: ignore[index]
    operation["project_key"] = "lord-god-strength"
    original["plan_sha256"] = calculate_vk_catalog_plan_sha256(original)

    with pytest.raises(ValueError, match="operation project conflicts"):
        upgrade_vk_catalog_plan_identity(original)
