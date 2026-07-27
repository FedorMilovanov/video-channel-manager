from __future__ import annotations

from copy import deepcopy

import pytest

from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef, VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.catalog import text_sha256
from video_channel_manager.platforms.vk.editorial_correction_wave import build_vk_reviewed_correction_wave


def _ref(remote_id: str) -> RemoteRef:
    return RemoteRef(platform=PlatformName.VK, channel_id="235216998", remote_id=remote_id)


def _audit() -> AuditPackage:
    description = "Комментарий о вере.\n\n1912 г."
    return AuditPackage(
        channel=ChannelRecord(
            ref=_ref("235216998"),
            title="The Legendary Poet",
            kind=ChannelKind.COMMUNITY,
        ),
        videos=[
            VideoRecord(
                ref=_ref("-235216998_456239046"),
                title="Исповедь Самоубийцы",
                description=description,
                duration_seconds=180,
                privacy_status="public",
                revision="sha256:test",
            )
        ],
        collections=[],
        memberships=[],
    )


def _decisions() -> dict[str, object]:
    description = "Комментарий о вере.\n\n1912 г."
    return {
        "decision_set_id": "test-correction",
        "target_community_id": 235216998,
        "source_plan_sha256": "sha256:source-plan",
        "source_review_bundle_sha256": "sha256:review-bundle",
        "shared_replacements": [
            {
                "replacement_id": "faith",
                "old": "Комментарий о вере.",
                "new": "О вере по биографии нельзя судить окончательно.",
                "expected_count": 1,
                "reason": "Remove unverifiable judgment.",
            },
            {
                "replacement_id": "date",
                "old": "1912 г.",
                "new": "1913–1915 гг.",
                "expected_count": 1,
                "reason": "Use academic dating.",
            },
        ],
        "sources": [
            {
                "source_id": "feb",
                "authority": "ФЭБ",
                "url": "https://feb-web.ru/example",
                "supports": "Academic dating.",
            }
        ],
        "decisions": [
            {
                "decision_id": "correct-video",
                "target_video_id": "-235216998_456239046",
                "expected_title": "Исповедь Самоубийцы",
                "expected_description_sha256": text_sha256(description),
                "replacement_ids": ["faith", "date"],
                "source_ids": ["feb"],
            }
        ],
    }


def test_reviewed_correction_wave_is_exact_and_description_only() -> None:
    plan = build_vk_reviewed_correction_wave(
        _audit(),
        _decisions(),
        source_review_bundle_sha256="sha256:review-bundle",
    )

    assert plan["operation_scope"] == "editorial_only"
    assert plan["component_scope"] == "descriptions_only"
    assert plan["correction_scope"] == "reviewed_factual_and_sensitive"
    assert plan["summary"]["descriptions_to_update"] == 1
    assert plan["summary"]["titles_to_update"] == 0
    assert plan["summary"]["albums_to_rename"] == 0
    assert plan["summary"]["placements_to_add"] == 0
    assert plan["summary"]["placements_to_remove"] == 0
    assert plan["summary"]["videos_to_delete"] == 0

    operation = plan["video_text_operations"][0]
    assert operation["before_title"] == operation["after_title"]
    assert operation["title_changed"] is False
    assert operation["description_changed"] is True
    assert operation["reviewed_correction"] is True
    assert operation["after_description"] == ("О вере по биографии нельзя судить окончательно.\n\n1913–1915 гг.")
    assert [item["replacement_id"] for item in operation["applied_replacements"]] == ["faith", "date"]
    assert operation["source_evidence"][0]["source_id"] == "feb"


def test_reviewed_correction_wave_rejects_review_bundle_mismatch() -> None:
    with pytest.raises(ValueError, match="Review bundle SHA-256"):
        build_vk_reviewed_correction_wave(
            _audit(),
            _decisions(),
            source_review_bundle_sha256="sha256:wrong",
        )


def test_reviewed_correction_wave_rejects_description_drift() -> None:
    decisions = deepcopy(_decisions())
    decisions["decisions"][0]["expected_description_sha256"] = "sha256:wrong"

    with pytest.raises(ValueError, match="Description guard mismatch"):
        build_vk_reviewed_correction_wave(
            _audit(),
            decisions,
            source_review_bundle_sha256="sha256:review-bundle",
        )


def test_reviewed_correction_wave_rejects_ambiguous_replacement() -> None:
    decisions = deepcopy(_decisions())
    decisions["shared_replacements"][1]["old"] = "г."
    decisions["shared_replacements"][1]["expected_count"] = 2

    with pytest.raises(ValueError, match="expected 2 matches"):
        build_vk_reviewed_correction_wave(
            _audit(),
            decisions,
            source_review_bundle_sha256="sha256:review-bundle",
        )
