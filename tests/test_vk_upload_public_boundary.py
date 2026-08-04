from __future__ import annotations

import ast
from pathlib import Path

from video_channel_manager.platforms.vk import execute_upload_operation as public_execute_upload_operation
from video_channel_manager.platforms.vk.upload_media import execute_upload_operation as safe_execute_upload_operation


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "video_channel_manager"
LEGACY_MODULE = "video_channel_manager.platforms.vk.upload_lifecycle"


def test_public_vk_upload_entrypoint_is_wave_8d_authorized_facade() -> None:
    assert public_execute_upload_operation is safe_execute_upload_operation


def test_production_code_does_not_import_legacy_upload_executor_directly() -> None:
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        if path.name in {"upload_media.py", "upload_lifecycle.py"}:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module != LEGACY_MODULE:
                continue
            if any(alias.name == "execute_upload_operation" for alias in node.names):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
