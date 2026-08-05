from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATIONS = ROOT / "docs" / "operations"
HISTORY = ROOT / "docs" / "history" / "operational-attempts"


def test_package_a_governance_documents_exist_and_keep_zero_write_boundary() -> None:
    runbook = (OPERATIONS / "package-a-wave9-wave10-runbook.md").read_text(encoding="utf-8")
    checklist = (OPERATIONS / "package-a-release-checklist.md").read_text(encoding="utf-8")
    for text in (runbook, checklist):
        assert "video-manager-package-a" in text
        assert "provider" in text.casefold()
        assert "write" in text.casefold()
        assert "separate review" in text.casefold()
        assert "#31" in text
        assert "#32" in text
        assert "#38" in text
    assert "mode=ro" in runbook
    assert "PRAGMA query_only = ON" in runbook
    assert "does not authorize" in runbook
    assert "rollback" in checklist.casefold()


def test_retirement_registry_is_machine_readable_and_fail_closed() -> None:
    payload = json.loads((OPERATIONS / "retirement-registry-v1.json").read_text(encoding="utf-8"))
    assert payload["schema_name"] == "video-manager.retirement-registry"
    assert payload["schema_version"] == 1
    assert payload["execution_authority"] is False
    assert payload["provider_writes_authorized"] is False

    supported = {item["id"]: item for item in payload["supported_entrypoints"]}
    package_a = supported["package-a-read-only"]
    assert package_a == {
        "id": "package-a-read-only",
        "entrypoint": "video-manager-package-a",
        "scope": "wave-9a-wave-9b-wave-10-read-only-evidence",
        "provider_queries": 0,
        "provider_writes": 0,
        "write_plan_created": False,
        "status": "supported_read_only",
    }
    assert supported["production-operator"]["entrypoint"] == "scripts/operator/Invoke-VideoManager.ps1"

    retired = {item["id"]: item for item in payload["retired_families"]}
    required = {
        "legendary-poet-shorts-sync-v1-v4",
        "legendary-poet-48-clips",
        "lord-god-longform-old-launchers",
        "vk-audio-browser-internal-web",
        "direct-write-python-powershell-wrappers",
        "lord-god-sermon-month-v1-v3",
    }
    assert required <= retired.keys()
    for item in retired.values():
        assert item["execution_prohibited"] is True
        assert item["status"] in {"retired_non_executable", "archived_not_core_supported"}

    for archive in payload["history_archives"]:
        source_pr = archive.get("source_pr")
        if source_pr is not None:
            assert source_pr == 85
            assert archive["source_head"] == "84761c0eca19483e9c64044fd03c1d769aeb199e"
        else:
            assert isinstance(archive.get("source_file"), str)
            source_sha256 = archive.get("source_sha256")
            assert isinstance(source_sha256, str)
            assert len(source_sha256) == 64
            assert set(source_sha256) <= set("0123456789abcdef")
        assert archive["status"] == "documentation_only_non_executable"
        assert archive["execution_prohibited"] is True
        assert (ROOT / archive["path"]).is_dir()


def test_operational_history_archive_contains_no_executable_or_package_files() -> None:
    assert HISTORY.is_dir()
    files = tuple(path for path in HISTORY.rglob("*") if path.is_file())
    assert files
    assert {path.suffix.casefold() for path in files} <= {".md", ".json"}
    forbidden = {".py", ".pyw", ".ps1", ".bat", ".cmd", ".exe", ".zip", ".sqlite", ".db"}
    assert not [path for path in files if path.suffix.casefold() in forbidden]

    index = (HISTORY / "README.md").read_text(encoding="utf-8")
    assert "Nothing here is a supported Python or PowerShell entrypoint" in index
    assert "Nothing here authorizes VK or YouTube writes" in index


def test_legendary_poet_archive_manifest_is_non_executable_and_complete() -> None:
    manifest_path = HISTORY / "legendary-poet-vk-clips-2026-08-03-04" / "ARTIFACT-MANIFEST.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["schema_name"] == "video-channel-manager.historical-attempt-archive"
    assert payload["project_key"] == "legendary-poet"
    assert payload["execution_authority"] is False
    assert payload["provider_writes_authorized"] is False
    assert len(payload["artifacts"]) == 17
    assert [item["sequence"] for item in payload["artifacts"]] == list(range(1, 18))
    for item in payload["artifacts"]:
        assert item["status"] == "historical_non_executable_snapshot"
        assert len(item["sha256"]) == 64
        assert set(item["sha256"]) <= set("0123456789abcdef")
        assert item["bytes"] > 0
        assert item["lines"] > 0


def test_production_python_does_not_import_operational_history() -> None:
    offending: list[str] = []
    for path in (ROOT / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if "docs/history/operational-attempts" in node.value.replace("\\", "/"):
                    offending.append(path.relative_to(ROOT).as_posix())
    assert offending == []
