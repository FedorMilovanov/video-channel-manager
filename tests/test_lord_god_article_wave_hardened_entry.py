from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lord_god_article_wave_v3 import link_cards_hardened_entry as entry  # noqa: E402


def verified_source_result(
    policy: dict[str, Any],
    contract: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = [
        {
            "operation_id": operation["operation_id"],
            "live_page_og_title": operation["title"],
            "live_page_og_description": (
                "Проверенное описание внешней карточки длиной более шестидесяти символов для безопасного Plan."
            ),
            "checks": {"og_image_dimensions_verified": True},
            "conflicts": [],
            "status": "verified",
        }
        for operation in policy["operations"]
    ]
    manifest = {
        "schema_name": "video-manager.vk-lord-god-article-link-card-hardened-sources",
        "schema_version": 2,
        "status": "verified",
        "expected_external_resources": 40,
        "external_urls_checked": 40,
        "article_pages_verified": 10,
        "live_content_markers_verified": 10,
        "og_images_verified": 10,
        "og_image_dimensions_verified": 10,
        "pinned_source_files_verified": 10,
        "pinned_metadata_files_verified": 10,
        "live_metadata_matches_pinned_source": 10,
        "prepared_jpeg_assets": 0,
        "vk_photo_uploads_required": False,
        "conflicts": 0,
        "conflicting_operations": 0,
        "global_conflicts": [],
        "items": rows,
        "delivery_contract_sha256": contract["contract_sha256"],
        "manifest_sha256": "sha256:test-manifest",
    }
    return rows, manifest


def ready_report(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "video-manager.vk-lord-god-article-link-card-hardened-preflight",
        "schema_version": 2,
        "description_match_mode": entry.DESCRIPTION_MATCH_MODE,
        "total_operations": 10,
        "ready": 10,
        "already_applied": 0,
        "conflicts": 0,
        "global_conflicts": [],
        "postponed_wall_posts": 0,
        "minimum_gap_minutes": 120,
        "states": [
            {
                "operation_id": operation["operation_id"],
                "state": "ready",
            }
            for operation in policy["operations"]
        ],
    }


def test_description_match_is_one_way_and_rejects_appended_text() -> None:
    expected = (
        "Проверенное полное описание карточки, которое может быть усечено "
        "ВКонтакте, но не может быть самовольно расширено."
    )
    truncated = expected[:60]

    assert entry.strict_description_matches(expected, expected)
    assert entry.strict_description_matches(truncated, expected)
    assert not entry.strict_description_matches(expected + " Лишний хвост.", expected)
    assert not entry.strict_description_matches(expected[:39], expected)
    assert not entry.strict_description_matches("", expected)


def test_active_hardened_plan_never_calls_execute_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    policy, contract = entry.core.load_hardened_policy(ROOT)
    rows, manifest = verified_source_result(policy, contract)
    report = ready_report(policy)
    output_dir = tmp_path / "data" / "vk-wall" / entry.DECISION_SET_ID

    monkeypatch.setattr(
        entry.core,
        "load_hardened_policy",
        lambda repo: (policy, contract),
    )
    monkeypatch.setattr(
        entry,
        "audit_sources",
        lambda *args, **kwargs: (rows, manifest),
    )
    monkeypatch.setattr(
        entry,
        "get_settings",
        lambda: SimpleNamespace(
            data_dir=tmp_path / "data",
            vk_api_version="5.199",
        ),
    )

    class FakeVkClient:
        def __init__(self, **kwargs: object) -> None:
            self.max_attempts = kwargs["max_attempts"]

        def get_community(self, community: int) -> Any:
            assert community == entry.COMMUNITY_ID
            return SimpleNamespace(
                ref=SimpleNamespace(remote_id=str(entry.COMMUNITY_ID)),
                metadata={"managed_by_token": True},
            )

    monkeypatch.setattr(entry, "VkApiClient", FakeVkClient)
    monkeypatch.setattr(entry, "wall_snapshot", lambda client: ([], []))
    monkeypatch.setattr(
        entry,
        "strict_preflight",
        lambda *args, **kwargs: report,
    )
    monkeypatch.setattr(
        entry.core,
        "review_markdown",
        lambda *args, **kwargs: "# hardened review\n",
    )
    monkeypatch.setattr(
        entry.core,
        "execute_scope",
        lambda **kwargs: pytest.fail("Plan must not execute remote writes"),
    )

    assert entry.run(tmp_path, mode="plan") == 0
    assert (output_dir / "link-card-source-audit.json").is_file()
    assert (output_dir / "link-card-preflight.json").is_file()
    assert (output_dir / "link-card-delivery-contract.json").is_file()
    written = json.loads((output_dir / "link-card-source-audit.json").read_text(encoding="utf-8"))
    assert written["status"] == "verified"
    assert written["og_image_dimensions_verified"] == 10


def test_strict_postflight_failure_overwrites_completed_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    policy, contract = entry.core.load_hardened_policy(ROOT)
    expectations = {
        str(operation["operation_id"]): {
            "title": str(operation["title"]),
            "description": "Проверенное полное описание карточки длиной более сорока символов.",
        }
        for operation in policy["operations"]
    }
    rejected = {
        "conflicts": 1,
        "already_applied": 0,
        "ready": 9,
        "global_conflicts": ["description mismatch"],
    }
    result = {"status": "completed", "operations": []}

    monkeypatch.setattr(entry, "wall_snapshot", lambda client: ([], []))
    monkeypatch.setattr(
        entry,
        "strict_preflight",
        lambda *args, **kwargs: rejected,
    )

    with pytest.raises(RuntimeError, match="strict link-card postflight rejected"):
        entry.verify_strict_postflight(
            mode="canary",
            policy=policy,
            contract=contract,
            expectations=expectations,
            read_client=object(),
            journal=entry.core.fresh_journal(policy, contract),
            output_dir=tmp_path,
            result=result,
        )

    written = json.loads(
        (tmp_path / "link-card-canary-result.json").read_text(encoding="utf-8")
    )
    assert written["status"] == "strict_postflight_failed"
    assert written["description_match_mode"] == entry.DESCRIPTION_MATCH_MODE
    assert written["strict_postflight_conflicts"] == 1


def test_blocked_source_audit_stops_before_vk_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    policy, contract = entry.core.load_hardened_policy(ROOT)
    rows, manifest = verified_source_result(policy, contract)
    rows[0]["status"] = "conflict"
    rows[0]["conflicts"] = [
        {
            "code": "og_image_changed_between_audit_passes",
            "detail": "first and second checksum differ",
        }
    ]
    manifest.update(
        {
            "status": "blocked",
            "og_image_dimensions_verified": 9,
            "conflicts": 1,
            "conflicting_operations": 1,
        }
    )

    monkeypatch.setattr(
        entry.core,
        "load_hardened_policy",
        lambda repo: (policy, contract),
    )
    monkeypatch.setattr(
        entry,
        "audit_sources",
        lambda *args, **kwargs: (rows, manifest),
    )
    monkeypatch.setattr(
        entry,
        "get_settings",
        lambda: pytest.fail("VK settings must not load after a blocked source audit"),
    )

    with pytest.raises(RuntimeError, match="source audit blocked"):
        entry.run(tmp_path, mode="plan")

    audit_path = tmp_path / "data" / "vk-wall" / entry.DECISION_SET_ID / "link-card-source-audit.json"
    assert audit_path.is_file()
    written = json.loads(audit_path.read_text(encoding="utf-8"))
    assert written["status"] == "blocked"
    assert written["conflicts"] == 1
