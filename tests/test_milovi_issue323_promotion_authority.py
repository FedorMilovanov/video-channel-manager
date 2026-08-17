from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "video_channel_manager"
VK = SRC / "platforms" / "vk"
CLI = SRC / "cli" / "vk.py"

RETIRED_EXECUTION_MODULES = (
    "milovi_issue323_finalize.py",
    "milovi_issue323_upload_wall_reconcile.py",
    "milovi_native_clip_browser.py",
    "milovi_native_clip_rollout.py",
)
RETIRED_IMPORT_TOKENS = (
    "milovi_issue323_finalize",
    "milovi_issue323_upload_wall_reconcile",
    "milovi_native_clip_browser",
    "milovi_native_clip_rollout",
)


def test_retired_issue323_execution_modules_are_absent() -> None:
    for filename in RETIRED_EXECUTION_MODULES:
        assert not (VK / filename).exists()
    assert not (SRC / "cli" / "vk_issue323_finalize.py").exists()


def test_issue323_cli_exposes_status_and_one_canonical_continuation_root() -> None:
    source = CLI.read_text(encoding="utf-8")
    assert source.count('@vk_app.command("milovi-323-status")') == 1
    assert source.count('@vk_app.command("milovi-323-continue")') == 1
    assert "milovi-323-rollout" not in source
    assert "milovi-323-finalize" not in source
    assert "run_issue_323_rollout" not in source
    assert "run_issue_323_token_rollout" not in source
    assert "run_issue_323_live_resume" not in source


def test_historical_token_and_live_modules_are_helper_only() -> None:
    forbidden_by_file = {
        "milovi_token_clip_rollout.py": (
            "run_issue_323_token_rollout",
            "def main(",
            'if __name__ == "__main__"',
            "execute_upload_operation",
            "VkWallWriter",
            "local_vk_write_lock",
            "begin_upload",
            "upload_file",
        ),
        "milovi_issue323_live_resume.py": (
            "run_issue_323_live_resume",
            "def main(",
            'if __name__ == "__main__"',
            "execute_upload_operation",
            "VkWallWriter",
            "local_vk_write_lock",
            "begin_upload",
            "upload_file",
        ),
    }
    for filename, forbidden in forbidden_by_file.items():
        source = (VK / filename).read_text(encoding="utf-8")
        assert [token for token in forbidden if token in source] == []


def test_issue323_modules_have_no_direct_retired_provider_mutation_calls() -> None:
    offenders: list[str] = []
    forbidden = (
        '"video.edit"',
        '"wall.edit"',
        '._call("wall.delete"',
        "execute_upload_operation(",
    )
    allowed = {"milovi_issue323_continue.py"}
    for path in sorted(VK.glob("milovi_issue323_*.py")):
        if path.name in allowed:
            continue
        source = path.read_text(encoding="utf-8")
        if any(token in source for token in forbidden):
            offenders.append(path.name)
    assert offenders == []


def test_provider_inert_read_model_cannot_mutate_or_acquire_media() -> None:
    source = (VK / "milovi_issue323_read_model.py").read_text(encoding="utf-8")
    forbidden = (
        "VkApiClient",
        "local_vk_write_lock",
        "execute_upload_operation",
        "begin_upload",
        "upload_file",
        "yt_dlp",
        "yt-dlp",
        "._call(",
    )
    assert [token for token in forbidden if token in source] == []


def test_no_source_or_regression_test_imports_retired_execution_modules() -> None:
    offenders: list[str] = []
    for base in (SRC, ROOT / "tests"):
        for path in sorted(base.rglob("*.py")):
            if path == Path(__file__).resolve():
                continue
            source = path.read_text(encoding="utf-8")
            if any(token in source for token in RETIRED_IMPORT_TOKENS):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_mutation_registers_do_not_advertise_retired_promotion_writers() -> None:
    retired = {
        "vk.video.issue323.promotion.edit",
        "vk.wall.issue323.promotion.edit",
        "vk.wall.issue323.anomaly.delete",
    }
    for relative in (
        "docs/operations/mutation-boundary-register.json",
        "docs/operations/mutation-fault-proof-register.json",
    ):
        payload = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        boundary_ids = {item["boundary_id"] for item in payload["boundaries"]}
        assert boundary_ids.isdisjoint(retired)
