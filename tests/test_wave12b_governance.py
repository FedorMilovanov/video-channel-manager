from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATIONS = ROOT / "docs" / "operations"


def _payload() -> dict[str, object]:
    return json.loads((OPERATIONS / "audit-register-v4-2026-08-05.json").read_text(encoding="utf-8"))


def test_wave12b_credential_model_separates_vk_token_from_project_identity() -> None:
    payload = _payload()
    assert payload["schema_name"] == "video-manager.audit-register-v4"
    assert payload["schema_version"] == "4.1"
    assert payload["predecessor_register"] == {
        "path": "docs/operations/audit-register-v3-2026-08-05.json",
        "blob_sha": "b6eed2621c87581ce145acea871a690387382e54",
        "schema_version": "3.2",
        "role": "Wave 12A completed project-bound machine state",
    }
    assert (ROOT / payload["predecessor_register"]["path"]).is_file()

    vk = payload["credential_model"]["vk"]
    assert vk["credential_kind"] == "one_shared_user_access_token"
    assert vk["local_alias"] == "legendary-poet"
    assert vk["project_selector"] is False
    assert vk["managed_communities"] == [60805374, 235216998]
    assert vk["selection_fields"] == ["project_key", "vk_community_id", "vk_owner_id"]

    youtube = payload["credential_model"]["youtube"]
    assert youtube["credential_kind"] == "channel_specific_oauth_aliases"
    assert youtube["aliases"] == {
        "fedor-milovanov": "UCeSJsC6go2c9pdJCuUI1BYA",
        "legendary-poet": "UC-78ys2S3cQ3lpqgXfo-SvQ",
    }
    assert youtube["exact_channel_binding_required"] is True


def test_wave12b_completed_issue_graph_preserves_real_and_deferred_scope() -> None:
    payload = _payload()
    assert payload["active_operational_issues"] == [31, 32, 33, 38, 99, 119]
    assert 37 not in payload["active_operational_issues"]
    assert payload["deferred_product_issues"] == [123]

    dispositions = {item["issue"]: item for item in payload["closed_issue_dispositions"]}
    assert set(dispositions) == {2, 3, 4, 5, 37}
    assert dispositions[2]["state_reason"] == "completed"
    assert dispositions[3]["state_reason"] == "not_planned"
    assert dispositions[4] == {
        "issue": 4,
        "disposition": "superseded_playlist_remainder_issue_123",
        "state_reason": "not_planned",
    }
    assert dispositions[5]["state_reason"] == "completed"
    assert dispositions[37]["state_reason"] == "completed"

    assert payload["issue_37_completion_evidence"] == {
        "replaced_short_items": 34,
        "protected_wall_post": 12400,
        "protected_wall_post_remained_present": True,
        "historical_executor_retired": True,
        "broad_cleanup_authorized": False,
    }


def test_wave12b_reconciliation_document_is_explicit_and_fail_closed() -> None:
    text = (OPERATIONS / "milestone-and-credential-reconciliation-2026-08-05.md").read_text(encoding="utf-8")
    required = (
        "one **user access token source**",
        "It is not a project selector",
        "YouTube OAuth account aliases",
        "This does not imply a second VK token",
        "### #2 — YouTube OAuth and read-only inventory",
        "### #3 — deterministic audits and external-AI packages",
        "### #4 — safe YouTube playlist and metadata execution",
        "Issue #123 owns that deferred product scope",
        "### #5 — VK organizer, comparison, and resumable transfer",
        "### #37 — Shorts wall cleanup after post 12400",
        "protected post `12400` remained present",
        "Provider queries: `0`",
        "Provider writes: `0`",
        "Write plans: `0`",
    )
    for fact in required:
        assert fact in text

    for claim in (
        "The VK alias selects the project",
        "Issue #37 is an active operational owner",
        "provider writes authorized",
    ):
        assert claim not in text


def test_wave12b_completed_proof_never_promotes_live_state_or_write_authorization() -> None:
    payload = _payload()
    assert payload["verified_main"] == "38296d07f8b6e948a6c5c4846bb66bf116bcfb72"
    assert payload["wave_12b_exact_head"] == "ffd275e9173db5a46bdde85f318dfa08ca83adb3"
    assert payload["wave_12b_ci_run"] == 30988821430
    assert payload["wave_12b_evidence_level"] == "self_tested_credential_and_issue_graph_governance"
    assert payload["wave_12b_status"] == "completed"
    assert payload["program_state"] == (
        "WAVES_0_12B_ENGINEERING_GOVERNANCE_COMPLETED_LIVE_RECONCILIATION_PENDING_NO_PROVIDER_WRITES"
    )
    assert payload["quality_evidence"]["pytest"] == "789 passed, 1 xfailed"
    assert payload["provider_queries_during_wave_12b"] == 0
    assert payload["provider_writes_during_wave_12b"] == 0
    assert payload["write_plans_created_during_wave_12b"] == 0
    assert payload["live_counts_are_fresh"] is False
    assert payload["mutation_authorized"] is False
    assert payload["automatic_execution"] is False
