from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "video_channel_manager"
VK = SRC / "platforms" / "vk"


def test_retired_issue323_finalizer_has_no_importable_or_cli_surface() -> None:
    assert not (VK / "milovi_issue323_finalize.py").exists()
    assert not (SRC / "cli" / "vk_issue323_finalize.py").exists()
    app_source = (SRC / "cli" / "app.py").read_text(encoding="utf-8")
    assert "vk_issue323_finalize" not in app_source
    assert "milovi-323-finalize" not in app_source


def test_issue323_modules_have_no_direct_promotion_edit_authority() -> None:
    offenders: list[str] = []
    for path in sorted(VK.glob("milovi_issue323_*.py")):
        source = path.read_text(encoding="utf-8")
        if '"video.edit"' in source or '"wall.edit"' in source:
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


def test_no_source_or_regression_test_imports_retired_finalizer() -> None:
    offenders: list[str] = []
    for base in (SRC, ROOT / "tests"):
        for path in sorted(base.rglob("*.py")):
            if path == Path(__file__).resolve():
                continue
            source = path.read_text(encoding="utf-8")
            if "milovi_issue323_finalize" in source:
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
