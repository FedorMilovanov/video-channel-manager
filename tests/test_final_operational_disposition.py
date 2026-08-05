from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs" / "operations" / "audit-register-v5-2026-08-05.json"
DISPOSITION = (
    ROOT / "docs" / "operations" / "final-operational-disposition-2026-08-05.md"
)


def _register() -> dict[str, object]:
    return json.loads(REGISTER.read_text(encoding="utf-8"))


def test_final_register_is_fail_closed_and_credential_correct() -> None:
    data = _register()

    assert data["schema_name"] == "video-manager.audit-register-v5"
    assert data["verified_main_before_wave_13"] == (
        "1ee5de009cc573015d64fd92d0ab3f435304fb82"
    )
    assert data["credential_model"] == {
        "vk": "one_shared_user_access_token",
        "vk_project_selector": False,
        "youtube_oauth_aliases_are_channel_specific": True,
    }
    assert data["provider_queries_during_wave_13"] == 0
    assert data["provider_writes_during_wave_13"] == 0
    assert data["write_plans_created_during_wave_13"] == 0
    assert data["mutation_authorized"] is False
    assert data["automatic_execution"] is False


def test_final_issue_dispositions_are_exact() -> None:
    data = _register()
    dispositions = {
        item["issue"]: item for item in data["dispositions"]  # type: ignore[index]
    }

    assert set(dispositions) == {31, 32, 33, 38, 99, 119, 123}

    issue_31 = dispositions[31]
    assert issue_31["planned_state_reason"] == "completed"
    assert issue_31["evidence"]["queue_rows"] == 26
    assert issue_31["evidence"]["live_count"] == 26
    assert issue_31["evidence"]["missing_youtube_ids"] == []
    assert issue_31["evidence"]["thumbnail_repairs_verified"] == 26

    issue_119 = dispositions[119]
    assert issue_119["planned_state_reason"] == "completed"
    assert issue_119["evidence"]["bounded_source_count"] == 56
    assert issue_119["evidence"]["reviewed_existing_pairs_before_transfer"] == 41
    assert issue_119["evidence"]["verified_short_video_from_missing_set"] == 8
    assert issue_119["evidence"]["accepted_long_canary_requires_attention"] == 1
    assert issue_119["evidence"]["undispatched_blocked_long_items"] == 6
    assert issue_119["evidence"]["all_56_proven_native_clips"] is False
    assert issue_119["no_blind_replay"] is True

    issue_38 = dispositions[38]
    contract = issue_38["contract"]
    assert issue_38["planned_state_reason"] == "completed"
    assert contract["ordinary_video_is_native_clip_success"] is False
    assert contract["geometry_or_duration_proves_native_clip"] is False
    assert contract["automatic_over_60_second_native_clip_route_supported"] is False

    for issue in (32, 33, 99, 123):
        assert dispositions[issue]["planned_state_reason"] == "not_planned"
        assert dispositions[issue].get("provider_write_authorized", False) is False


def test_human_disposition_never_claims_false_completion() -> None:
    text = DISPOSITION.read_text(encoding="utf-8")

    required = (
        "No additional upload is required or authorized.",
        "It does not claim that all 56 targets are native Clips.",
        "The automatic over-60-second native-Clip route is unsupported.",
        "The non-authoritative 108-item automatic upload scope is retired.",
        "Any already existing remote article-wall object remains untouched",
        "No YouTube playlist mutation is authorized.",
    )
    for statement in required:
        assert statement in text

    prohibited = (
        "All 56 targets are native Clips.",
        "rerun the historical launcher",
        "all_56_proven_native_clips\": true",
        "provider_writes_during_wave_13\": 1",
        "mutation_authorized\": true",
    )
    for statement in prohibited:
        assert statement not in text
