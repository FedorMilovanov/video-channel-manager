from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATIONS_DIR = ROOT / "docs" / "operations"


def test_agent_instructions_reference_current_sources_of_truth() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    required_sources = (
        "docs/operations/current-state.md",
        "docs/operations/project-identity-registry.md",
        ".github/copilot-instructions.md",
        "docs/operations/operational-artifact-standard.md",
        "docs/operations/operational-package-acceptance.md",
        "docs/operations/retirement-registry-v1.json",
        "docs/operations/operator-output-handoff-rule.md",
    )
    for relative_path in required_sources:
        assert relative_path in text
        assert (ROOT / relative_path).is_file()

    historical_sources = (
        "docs/operations/master-audit-marathon-v2-2026-08-04.md",
        "docs/operations/audit-register-v7-2026-08-05.json",
        "docs/operations/audit-register-v6-2026-08-05.json",
        "docs/operations/audit-register-v5-2026-08-05.json",
        "docs/operations/audit-register-v4-2026-08-05.json",
        "docs/operations/audit-register-v3-2026-08-05.json",
        "docs/operations/audit-register-v2-2026-08-04.json",
        "docs/operations/repository-integrity-audit-2026-08-05.md",
    )
    for relative_path in historical_sources:
        assert (ROOT / relative_path).is_file()
        assert relative_path not in text


def test_operations_index_has_no_broken_local_markdown_links() -> None:
    index_path = OPERATIONS_DIR / "README.md"
    text = index_path.read_text(encoding="utf-8")
    local_targets = re.findall(r"\[[^]]+\]\(([^)]+\.md)\)", text)
    assert local_targets
    broken = [target for target in local_targets if not (index_path.parent / target).resolve().is_file()]
    assert broken == []


def test_wave14_history_remains_machine_readable_but_not_live_state() -> None:
    register = json.loads((OPERATIONS_DIR / "audit-register-v7-2026-08-05.json").read_text(encoding="utf-8"))
    assert (
        register["program_state"]
        == "WAVES_0_14_COMPLETED_REPOSITORY_POLISHED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES"
    )
    proof = register["wave_14_repository_polish"]
    assert proof["merge"] == "626f83c6e5c068d7faa8b6d14163b42916faa769"  # type: ignore[index]
    assert proof["pull_request"] == 131  # type: ignore[index]
    assert proof["ci_run"] == 31000834701  # type: ignore[index]
    assert proof["pytest"] == "801 passed, 1 xfailed"  # type: ignore[index]
    assert proof["ruff_format"] == "451 files already formatted"  # type: ignore[index]
    assert register["provider_writes_during_wave_14"] == 0
    assert register["mutation_authorized"] is False

    current = (OPERATIONS_DIR / "current-state.md").read_text(encoding="utf-8")
    assert register["program_state"] not in current
    assert "main@626f83c6e5c068d7faa8b6d14163b42916faa769" not in current
    assert "No operational continuation is pending" not in current
    assert "Issue #154 is closed as **completed**" in current
    assert "Issue #154 remains **artifact-level open**" not in current


def test_lordchrist_checkpoint_preserves_no_replay_and_editorial_holds() -> None:
    current = (OPERATIONS_DIR / "current-state.md").read_text(encoding="utf-8")
    overlay = current.split("## LordChrist publication checkpoint", 1)[1].split("## Completion", 1)[0]

    for fact in (
        "[ordered queue](2026-11-21-zero-open-tasks-plan.md)",
        "[release calendar](2026-11-21-release-calendar.md)",
        "**QUIZ: EDITORIAL HOLD.**",
        "Local signoff JSON is not review provenance or authority",
        "`may_exist`",
        "#09 is already verified as Telegram message **1630**",
        "never repeat it",
        "do not increase pages 04/05",
        "`43098273140`",
        "unknown inputs",
        "do not replay or cancel blindly",
        "never publish at night",
    ):
        assert fact in overlay
    assert "Next planned item 8: 17 November" not in current
    for name in ("2026-11-21-zero-open-tasks-plan.md", "2026-11-21-release-calendar.md"):
        assert (OPERATIONS_DIR / name).is_file()


def test_jude_reconciliation_preserves_contradiction_and_scoped_guard() -> None:
    incident = (OPERATIONS_DIR / "2026-11-22-jude-actions-reconciliation.md").read_text(encoding="utf-8")
    for fact in (
        "43098273140",
        "116713949914",
        "`Cannot cancel a workflow run that is completed`",
        "`status=queued`",
        "`conclusion=null`",
        "Повторную или принудительную отмену",
        "0 jobs",
        "0 artifacts",
        "45014714988",
        "только заголовки одного аккаунта",
        "не останавливает",
        "не проверяет GitHub live, занятость сегодняшнего дня и время суток",
    ):
        assert fact in incident
    calendar = (OPERATIONS_DIR / "2026-11-21-release-calendar.md").read_text(encoding="utf-8")
    assert "**не подтверждённая отмена**" in calendar
    assert "2026-11-22-jude-actions-reconciliation.md" in calendar
    assert "блокирует все четыре этапа" in calendar


def test_legendary_poet_inventory_keeps_done_edits_and_project_identity() -> None:
    inventory = (OPERATIONS_DIR / "2026-11-21-open-work.md").read_text(encoding="utf-8")
    poet = inventory.split("Legendary Poet:", 1)[1].split("Lord God:", 1)[0]
    lord_god = inventory.split("Lord God:", 1)[1].split("LordChrist Shorts / видео:", 1)[0]

    assert "все 7/7 исправлений" in poet
    assert "уже выполнены на checkpoint; не повторять" in poet
    assert "8g_4EVWFb1g" in poet and "UgyUMAfJqC8hdzxSnfF4AaABAg" in poet
    assert "Lf0h4yXPVng" in poet and "комментарий только draft" in poet
    assert "WizaG8S085g::en-US" in poet and "`may_exist`" in poet
    assert "`reconciled_absent_after_403`" in poet
    assert "Это не доказывает отсутствия сейчас" in poet
    assert "#789" in poet and "#778" in poet
    assert "#789" not in lord_god and "#778" not in lord_god
    assert "#869" in lord_god


def test_platform_inventory_preserves_existing_reel_and_vk_wall_evidence() -> None:
    plan = (OPERATIONS_DIR / "2026-11-21-zero-open-tasks-plan.md").read_text(encoding="utf-8")
    blok = plan.split("- **#778,", 1)[1].split("- **#792,", 1)[0]
    milovi = plan.split("- **#792,", 1)[1].split("- **#790,", 1)[0]

    assert "18125909824868306" in blok and "#АлександрПушкин" in blok
    assert "тело существующего Reel" in blok and "уже называло Блока" in blok
    assert "не создавать Reel заново" in blok and "старый полный caption-план устарел" in blok
    assert "27/27" in milovi and "19 отдельных Clip-вложений" in milovi and "все 18" in milovi
    assert "Восемь прочих ordinary video" in milovi and "уже загружены" in milovi
    assert "`acodec=None` означает **звук неизвестен**" in milovi
    assert "не автоматическая отмена, перепубликация" in milovi
    assert "issuecomment-7051382962" in milovi and "issuecomment-7052639277" in milovi


def test_caption_reconciliation_is_historical_and_not_retry_authority() -> None:
    quota = (OPERATIONS_DIR / "youtube-api-quota-and-viewer-language-2026-11-13.md").read_text(encoding="utf-8")
    correction = next(line for line in quota.splitlines() if "reconciled_absent_after_403" in line)
    assert "WizaG8S085g::en-US" in correction
    assert "two owner `captions.list` reads" in correction
    assert "**12 November**" in correction
    assert "**not** proof of present-day absence or permission to insert" in correction
    assert "issuecomment-6874475550" in correction


def test_agent_instructions_preserve_current_identity_and_execution_boundaries() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    required = (
        "never by credential name alone",
        "Durable same-object keys must not include timestamps",
        "Release/content approval and provider execution authority are separate gates",
        "persist durable intent before dispatch",
        "zero blind mutation retries",
        "Unknown provider outcomes remain blocking",
        "PowerShell and shell wrappers orchestrate one repository-owned implementation",
        "Retired executors/packages never become runnable again",
        "repository implementation complete",
        "artifact complete",
        "provider rollout complete",
    )
    for fact in required:
        assert fact in text

    for stale in (
        "No operational continuation is pending",
        "main@626f83c6e5c068d7faa8b6d14163b42916faa769",
        "Do not group #32/#38 as Legendary Poet",
    ):
        assert stale not in text


def test_wave12a_predecessor_overlay_remains_valid_and_fail_closed() -> None:
    overlay_path = OPERATIONS_DIR / "audit-register-v3-2026-08-05.json"
    payload = json.loads(overlay_path.read_text(encoding="utf-8"))
    assert payload["schema_name"] == "video-manager.audit-register-v3"
    assert payload["schema_version"] == "3.2"
    assert payload["predecessor_register"] == {
        "path": "docs/operations/audit-register-v2-2026-08-04.json",
        "blob_sha": "739146b63cfb3207a6b8d2d7a12698b3e54c28dd",
        "schema_version": "2.9",
        "role": "complete historical finding and source ledger",
    }
    assert payload["wave_12a_status"] == "completed"
    assert payload["provider_queries_during_wave_12a"] == 0
    assert payload["provider_writes_during_wave_12a"] == 0
    assert payload["write_plans_created_during_wave_12a"] == 0
    assert payload["live_counts_are_fresh"] is False
    assert payload["mutation_authorized"] is False
    assert payload["automatic_execution"] is False


def test_wave11_predecessor_register_remains_valid_and_fail_closed() -> None:
    register_path = OPERATIONS_DIR / "audit-register-v2-2026-08-04.json"
    payload = json.loads(register_path.read_text(encoding="utf-8"))
    assert payload["schema_name"] == "video-manager.audit-register-v2"
    assert payload["schema_version"] == "2.9"
    assert payload["wave_11_code_head"] == "eeab53b779e5ea4af5d3dcc08d79e41812739e04"
    assert payload["wave_11_ci_run"] == 30967195938
    assert payload["wave_11_evidence_level"] == "self_tested_source_bound_governance"
    assert payload["source_line_count"] == 7413
    assert len(payload["sources"]) == 8

    findings = {item["id"]: item for item in payload["findings"]}
    for finding_id in (
        "PACKAGE-TRUTH-001",
        "VK-PERMISSION-001",
        "HISTORY-002",
        "ARCHIVE-001",
        "RECOVERY-001",
        "CONTROL-001",
        "GOV-001",
    ):
        assert findings[finding_id]["status"] == "fixed"
    assert findings["LIVE-LORD-001"]["status"] == "requires_reconciliation"
    assert findings["LIVE-POET-001"]["status"] == "requires_reconciliation"
    assert findings["AUDIO-001"]["status"] == "separate_system"


def test_operational_contract_and_memory_sources_exist() -> None:
    required = (
        ROOT / "src/video_channel_manager/tools/operational_package_acceptance.py",
        OPERATIONS_DIR / "operational-package-acceptance.md",
        OPERATIONS_DIR / "retirement-registry-v1.json",
        ROOT / "docs/history/operational-attempts/lord-god-sermon-month-2026-08-05/SOURCE-METADATA.json",
        ROOT / ".github/copilot-instructions.md",
        OPERATIONS_DIR / "project-memory-changelog.d/2026-08-05-wave-12a.md",
        OPERATIONS_DIR / "project-memory-changelog.d/2026-08-05-wave-12b.md",
        OPERATIONS_DIR / "milestone-and-credential-reconciliation-2026-08-05.md",
        OPERATIONS_DIR / "final-operational-disposition-2026-08-05.md",
        OPERATIONS_DIR / "repository-integrity-audit-2026-08-05.md",
        OPERATIONS_DIR / "audit-register-v7-2026-08-05.json",
        OPERATIONS_DIR / "audit-register-v6-2026-08-05.json",
    )
    for path in required:
        assert path.is_file()

    source = required[0].read_text(encoding="utf-8")
    assert "provider_writes_authorized: Literal[False]" in source
    assert "automatic_execution: Literal[False]" in source
    assert "PROJECT_IDENTITIES" in source
