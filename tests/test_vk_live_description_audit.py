from __future__ import annotations

from copy import deepcopy

import pytest

from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef, VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.live_description_audit import (
    build_live_description_cleanup_plan,
    calculate_cleanup_plan_sha256,
    validate_live_description_cleanup_plan,
)


def _video(remote_id: str, title: str, description: str) -> VideoRecord:
    return VideoRecord(
        ref=RemoteRef(platform=PlatformName.VK, channel_id="235216998", remote_id=remote_id),
        title=title,
        description=description,
        duration_seconds=240,
        privacy_status="public",
        revision=f"sha256:{remote_id}",
    )


def _audit(videos: list[VideoRecord]) -> AuditPackage:
    return AuditPackage(
        channel=ChannelRecord(
            ref=RemoteRef(platform=PlatformName.VK, channel_id="235216998", remote_id="235216998"),
            title="The Legendary Poet",
            kind=ChannelKind.COMMUNITY,
        ),
        videos=videos,
    )


def _single_operation_plan() -> dict[str, object]:
    return build_live_description_cleanup_plan(
        _audit([_video("-235216998_1", "Фет", "Стихотворение написано в *1850 году*.")]),
        community_id=235216998,
    )


def test_full_live_plan_cleans_current_vk_text_without_rebuilding_wording() -> None:
    live = _audit(
        [
            _video(
                "-235216998_1",
                "Фет",
                "Стихотворение написано в *1850 году*.\n\n_Осенью того же года_ история изменилась.",
            )
        ]
    )

    plan = build_live_description_cleanup_plan(live, community_id=235216998)

    validate_live_description_cleanup_plan(plan)
    assert plan["schema_version"] == 2
    assert plan["policy_version"] == "vk-live-description-cleanup-v2"
    assert str(plan["plan_sha256"]).startswith("sha256:")
    assert str(plan["coverage_remote_ids_sha256"]).startswith("sha256:")
    assert plan["videos_checked"] == 1
    assert plan["operations_count"] == 1
    operation = plan["operations"][0]
    assert operation["before_description"].startswith("Стихотворение написано в *1850 году*")
    assert operation["after_description"].startswith("Стихотворение написано в 1850 году")
    assert "Осенью того же года история изменилась." in operation["after_description"]
    assert operation["removed_emphasis_pairs"] == 2
    assert operation["footer_added"] is True


def test_full_live_plan_checks_old_safe_review_and_foreign_videos() -> None:
    footer = (
        "Обычное описание без разметки.\n\n"
        "🎧 The Legendary Poet — русская поэзия, музыка и литературные материалы.\n"
        "🌐 https://thelegendarypoet.ru/"
    )
    live = _audit(
        [
            _video("-235216998_1", "Уже безопасно", footer),
            _video("-235216998_2", "Требует проверки", "Текст с <b>HTML</b>."),
            _video("-999_3", "Чужой владелец", "*Не трогать автоматически*"),
            _video("-235216998_4", "К ***", "Название К *** сохраняется."),
        ]
    )

    plan = build_live_description_cleanup_plan(live, community_id=235216998)

    validate_live_description_cleanup_plan(plan)
    assert plan["videos_checked"] == 4
    assert plan["already_safe_count"] == 1
    assert plan["review_only_count"] == 2
    assert plan["operations_count"] == 1
    assert plan["operations"][0]["title"] == "К ***"
    assert "К ***" in plan["operations"][0]["after_description"]
    reasons = {item["reason"] for item in plan["review_only"]}
    assert any("warning or error" in reason for reason in reasons)
    assert any("differs from community owner" in reason for reason in reasons)


def test_cleanup_plan_rejects_modified_operation_text() -> None:
    plan = deepcopy(_single_operation_plan())
    plan["operations"][0]["after_description"] += " подмена"
    plan["plan_sha256"] = calculate_cleanup_plan_sha256(plan)

    with pytest.raises(ValueError, match="after_sha256 is invalid"):
        validate_live_description_cleanup_plan(plan)


def test_cleanup_plan_rejects_duplicate_remote_id_across_sections() -> None:
    plan = deepcopy(_single_operation_plan())
    operation = plan["operations"][0]
    plan["already_safe"].append(
        {
            "remote_id": operation["remote_id"],
            "title": operation["title"],
            "before_sha256": operation["before_sha256"],
        }
    )
    plan["already_safe_count"] = 1
    plan["videos_checked"] = 2
    plan["plan_sha256"] = calculate_cleanup_plan_sha256(plan)

    with pytest.raises(ValueError, match="duplicate VK remote IDs"):
        validate_live_description_cleanup_plan(plan)


def test_cleanup_plan_rejects_count_mismatch() -> None:
    plan = deepcopy(_single_operation_plan())
    plan["operations_count"] = 2
    plan["plan_sha256"] = calculate_cleanup_plan_sha256(plan)

    with pytest.raises(ValueError, match="operations_count"):
        validate_live_description_cleanup_plan(plan)


def test_cleanup_plan_rejects_coverage_hash_mismatch() -> None:
    plan = deepcopy(_single_operation_plan())
    plan["coverage_remote_ids_sha256"] = "sha256:wrong"
    plan["plan_sha256"] = calculate_cleanup_plan_sha256(plan)

    with pytest.raises(ValueError, match="coverage_remote_ids_sha256"):
        validate_live_description_cleanup_plan(plan)


def test_cleanup_plan_rejects_self_digest_mismatch() -> None:
    plan = deepcopy(_single_operation_plan())
    plan["generated_at"] = "changed-after-review"

    with pytest.raises(ValueError, match="plan_sha256"):
        validate_live_description_cleanup_plan(plan)
