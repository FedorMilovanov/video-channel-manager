from __future__ import annotations

from pathlib import Path

from video_channel_manager.platforms.vk import execute_upload_operation as public_execute_upload_operation
from video_channel_manager.platforms.vk.upload_media import execute_upload_operation as safe_execute_upload_operation


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "video_channel_manager"


def test_public_vk_upload_entrypoint_is_wave_8d_authorized_facade() -> None:
    assert public_execute_upload_operation is safe_execute_upload_operation


def test_production_code_does_not_import_legacy_upload_executor_directly() -> None:
    forbidden = "execute_upload_operation as"
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        if path.name in {"upload_media.py", "upload_lifecycle.py"}:
            continue
        text = path.read_text(encoding="utf-8")
        if "platforms.vk.upload_lifecycle import" in text and forbidden in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
