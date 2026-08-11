from __future__ import annotations

import copy

import pytest

from video_channel_manager.platforms.vk.clips_candidate_triage import (
    build_owner_only_risk_triage,
    classify_owner_only_clip,
)
from video_channel_manager.platforms.vk.clips_owner_reconciliation import build_owner_clips_wall_reconciliation

MILOVI_COMMUNITY_ID = 68859909
MILOVI_OWNER_ID = -68859909


def _probe_clip(video_id: int, title: str, description: str = "") -> dict[str, object]:
    return {
        "remote_id": f"{MILOVI_OWNER_ID}_{video_id}",
        "owner_id": MILOVI_OWNER_ID,
        "video_id": video_id,
        "type": "short_video",
        "is_native_clip": True,
        "title": title,
        "description": description,
    }


def _owner_probe(clips: list[dict[str, object]], *, status: str = "ok") -> dict[str, object]:
    return {
        "schema": "vk-owner-clips-experimental-probe-v2",
        "project_key": "milovi-cake",
        "read_only": True,
        "provider_effect": "safe_read_only",
        "community": {
            "community_id": MILOVI_COMMUNITY_ID,
            "owner_id": MILOVI_OWNER_ID,
            "managed_by_token": True,
        },
        "provider_probe": {
            "status": status,
            "provider_reported_total": len(clips) if status == "ok" else None,
            "pagination_complete": status == "ok",
        },
        "coverage": {
            "clip_count": len(clips),
            "surface_complete_claim": False,
            "required_remote_ids": [],
            "required_remote_ids_found_as_clips": [],
            "required_remote_ids_missing_from_probe": [],
        },
        "clips": clips,
    }


def _wall_post(video_id: int, title: str) -> dict[str, object]:
    return {
        "id": 1000 + video_id,
        "owner_id": MILOVI_OWNER_ID,
        "attachments": [
            {
                "type": "video",
                "video": {
                    "id": video_id,
                    "owner_id": MILOVI_OWNER_ID,
                    "type": "short_video",
                    "title": title,
                    "description": "",
                    "width": 1080,
                    "height": 1920,
                },
            }
        ],
    }


def _reconciliation(
    owner_probe: dict[str, object],
    *,
    wall_posts: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return build_owner_clips_wall_reconciliation(
        project_key="milovi-cake",
        community_id=MILOVI_COMMUNITY_ID,
        owner_id=MILOVI_OWNER_ID,
        published_posts=wall_posts or [],
        owner_probe=owner_probe,
    )


def test_text_only_risk_rules_are_review_labels_never_mutation_authority() -> None:
    cases = [
        (_probe_clip(1, "Торт Шрек"), "IP_HOLD_HIDE", "shrek"),
        (_probe_clip(2, "Minecraft cake"), "IP_GUIDELINE_REVIEW", "minecraft"),
        (_probe_clip(3, "Торт с лисичкой"), "VISUAL_REVIEW", "fox"),
        (_probe_clip(4, "Клубничный торт"), "AMBIGUOUS_REVIEW", None),
    ]

    for item, expected_disposition, expected_signal in cases:
        result = classify_owner_only_clip(item)
        assert result["risk_disposition"] == expected_disposition
        if expected_signal == "shrek":
            assert result["ip_hold_signals"] == ["shrek"]
        elif expected_signal == "minecraft":
            assert result["guideline_review_signals"] == ["minecraft"]
        elif expected_signal == "fox":
            assert result["visual_review_signals"] == ["fox"]
        assert result["provider_mutation_authorized"] is False
        assert result["delete_authorized"] is False
        assert result["hide_authorized"] is False
        assert result["upload_authorized"] is False


def test_trademark_naming_and_cross_project_text_are_separate_review_signals() -> None:
    trademark = classify_owner_only_clip(_probe_clip(10, "Торт Сникерс"))
    cross_project = classify_owner_only_clip(_probe_clip(11, "Сергей Есенин — оформление торта"))

    assert trademark["risk_disposition"] == "AMBIGUOUS_REVIEW"
    assert trademark["trademark_naming_review"] is True
    assert trademark["trademark_naming_signals"] == ["snickers"]
    assert trademark["delete_authorized"] is False

    assert cross_project["risk_disposition"] == "AMBIGUOUS_REVIEW"
    assert cross_project["cross_project_signal_review"] is True
    assert cross_project["cross_project_signals"] == ["yesenin"]
    assert cross_project["delete_authorized"] is False


def test_triage_processes_only_reconciliation_owner_only_ids() -> None:
    both = _probe_clip(20, "Торт Шрек")
    owner_only = _probe_clip(21, "Minecraft торт")
    probe = _owner_probe([both, owner_only])
    reconciliation = _reconciliation(probe, wall_posts=[_wall_post(20, "Торт Шрек")])

    result = build_owner_only_risk_triage(
        project_key="milovi-cake",
        community_id=MILOVI_COMMUNITY_ID,
        owner_id=MILOVI_OWNER_ID,
        reconciliation=reconciliation,
        owner_probe=probe,
    )

    assert result["summary"]["owner_only_candidate_count"] == 1
    assert result["summary"]["risk_disposition_counts"] == {"IP_GUIDELINE_REVIEW": 1}
    assert [item["remote_id"] for item in result["candidates"]] == [f"{MILOVI_OWNER_ID}_21"]
    assert result["provider_writes"] == 0
    assert result["provider_mutation_authorized"] is False
    assert result["triage_sha256"].startswith("sha256:")


def test_triage_binds_exact_owner_probe_bytes_from_reconciliation() -> None:
    probe = _owner_probe([_probe_clip(30, "Торт Шрек")])
    reconciliation = _reconciliation(probe)
    tampered_probe = copy.deepcopy(probe)
    tampered_probe["clips"][0]["title"] = "Другой заголовок"  # type: ignore[index]

    with pytest.raises(ValueError, match="owner probe bytes differ"):
        build_owner_only_risk_triage(
            project_key="milovi-cake",
            community_id=MILOVI_COMMUNITY_ID,
            owner_id=MILOVI_OWNER_ID,
            reconciliation=reconciliation,
            owner_probe=tampered_probe,
        )


def test_triage_rejects_tampered_reconciliation_digest() -> None:
    probe = _owner_probe([_probe_clip(40, "Торт Шрек")])
    reconciliation = _reconciliation(probe)
    reconciliation["status"] = "tampered"

    with pytest.raises(ValueError, match="canonical digest mismatch"):
        build_owner_only_risk_triage(
            project_key="milovi-cake",
            community_id=MILOVI_COMMUNITY_ID,
            owner_id=MILOVI_OWNER_ID,
            reconciliation=reconciliation,
            owner_probe=probe,
        )


def test_partial_or_error_probe_may_classify_observed_owner_only_items_but_never_authorizes_mutation() -> None:
    probe = _owner_probe([_probe_clip(50, "Торт Шрек")], status="error")
    reconciliation = _reconciliation(probe)

    result = build_owner_only_risk_triage(
        project_key="milovi-cake",
        community_id=MILOVI_COMMUNITY_ID,
        owner_id=MILOVI_OWNER_ID,
        reconciliation=reconciliation,
        owner_probe=probe,
    )

    assert result["input_evidence"]["owner_probe_status"] == "error"
    assert result["summary"]["owner_only_candidate_count"] == 1
    assert result["candidates"][0]["risk_disposition"] == "IP_HOLD_HIDE"
    assert result["provider_mutation_authorized"] is False


def test_triage_rejects_cross_project_identity_before_using_evidence() -> None:
    probe = _owner_probe([_probe_clip(60, "Клубничный торт")])
    reconciliation = _reconciliation(probe)

    with pytest.raises(ValueError, match="canonical project identity"):
        build_owner_only_risk_triage(
            project_key="legendary-poet",
            community_id=MILOVI_COMMUNITY_ID,
            owner_id=MILOVI_OWNER_ID,
            reconciliation=reconciliation,
            owner_probe=probe,
        )
