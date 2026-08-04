from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "scripts" / "operator" / "powershell-wrappers.json"
SUPPORTED_PATH = "scripts/operator/Invoke-VideoManager.ps1"
STATUSES = {"supported", "compatibility_only", "retired"}
RETIRED_GUARD = "Stop-VcmRetiredWrapper"
RISK_MARKERS = (
    "apply_vk_editorial_cleanup_plan.py",
    "run_vk_p1_final_megawave_resume.py",
    "recover_youtube_comment_wave.py",
    "schedule_lord_god_article_wave_v3.py",
    "schedule_lord_god_wall_tail_current.py",
    "vk_shorts_reset_current.py",
    "run_vk_wall_wave.py",
    "--execute",
)


def _registry() -> dict[str, object]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _canonical_text_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _code_without_comments(path: Path) -> str:
    return "\n".join(
        line for line in path.read_text(encoding="utf-8-sig").splitlines() if not line.lstrip().startswith("#")
    )


def test_every_powershell_wrapper_is_classified_exactly_once() -> None:
    registry = _registry()
    assert registry["schema_name"] == "video-manager.powershell-wrapper-registry"
    assert registry["schema_version"] == 1

    wrappers = registry["wrappers"]
    assert isinstance(wrappers, list)
    registered_paths = [str(item["path"]).replace("\\", "/") for item in wrappers]
    discovered_paths = sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / "scripts").rglob("*.ps1"))

    test_files = registry["test_files"]
    assert isinstance(test_files, list)
    test_paths = [str(item["path"]).replace("\\", "/") for item in test_files]
    discovered_all = sorted(path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*.ps1"))

    assert len(registered_paths) == len(set(registered_paths))
    assert len(test_paths) == len(set(test_paths))
    assert sorted(registered_paths) == discovered_paths
    assert sorted(registered_paths + test_paths) == discovered_all
    assert {str(item["status"]) for item in wrappers} <= STATUSES


def test_registry_hashes_bind_every_wrapper_to_reviewed_content() -> None:
    registry = _registry()
    for section in ("wrappers", "test_files"):
        for item in registry[section]:
            expected = str(item["sha256"])
            assert re.fullmatch(r"[0-9a-f]{64}", expected), item["path"]
            assert _canonical_text_sha256(ROOT / str(item["path"])) == expected, item["path"]


def test_single_supported_wrapper_has_no_historical_operator_antipatterns() -> None:
    wrappers = _registry()["wrappers"]
    supported = [item for item in wrappers if item["status"] == "supported"]
    assert [item["path"] for item in supported] == [SUPPORTED_PATH]
    assert supported[0]["provider_write_capable"] is True

    text = _code_without_comments(ROOT / SUPPORTED_PATH)
    prohibited = (
        "LastWriteTime",
        "C:\\Users\\",
        "Select-String",
        "Tee-Object",
        "& py ",
        "& python ",
        "& pwsh ",
        "& powershell ",
    )
    for marker in prohibited:
        assert marker not in text
    assert "RequestSha256" in text
    assert "Invoke-VcmOperatorRequest" in text


def test_retired_provider_write_wrappers_stop_before_historical_executor_markers() -> None:
    wrappers = _registry()["wrappers"]
    retired = [item for item in wrappers if item["status"] == "retired"]
    assert retired
    for item in retired:
        assert item["provider_write_capable"] is True
        path = ROOT / str(item["path"])
        text = _code_without_comments(path)
        guard_index = text.find(RETIRED_GUARD)
        assert guard_index >= 0, item["path"]
        marker_indexes = [text.find(marker) for marker in RISK_MARKERS if text.find(marker) >= 0]
        if marker_indexes:
            assert guard_index < min(marker_indexes), item["path"]


def test_compatibility_wrappers_are_explicitly_non_provider_write() -> None:
    wrappers = _registry()["wrappers"]
    compatibility = [item for item in wrappers if item["status"] == "compatibility_only"]
    assert {item["path"] for item in compatibility} == {
        "scripts/Invoke-VkWallContentAudit.ps1",
        "scripts/check.ps1",
        "scripts/setup.ps1",
    }
    assert all(item["provider_write_capable"] is False for item in compatibility)
