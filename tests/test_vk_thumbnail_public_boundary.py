from __future__ import annotations

import ast
from pathlib import Path

import video_channel_manager.platforms.vk as vk
from video_channel_manager.platforms.vk.thumbnail_lifecycle import execute_thumbnail_operation
from video_channel_manager.platforms.vk.thumbnail_writer import VerifiedVkThumbnailWriter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "video_channel_manager"


def test_public_vk_thumbnail_api_exposes_only_verified_lifecycle() -> None:
    assert vk.execute_thumbnail_operation is execute_thumbnail_operation
    assert vk.VerifiedVkThumbnailWriter is VerifiedVkThumbnailWriter
    assert not hasattr(vk, "VkThumbnailWriter")


def test_production_code_cannot_import_low_level_thumbnail_writer_directly() -> None:
    violations: list[str] = []
    allowed = {
        SRC / "platforms" / "vk" / "thumbnail_writer.py",
    }
    for path in SRC.rglob("*.py"):
        if path in allowed:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "video_channel_manager.platforms.vk.thumbnails":
                imported = {alias.name for alias in node.names}
                if "VkThumbnailWriter" in imported:
                    violations.append(str(path.relative_to(ROOT)))
    assert violations == []
