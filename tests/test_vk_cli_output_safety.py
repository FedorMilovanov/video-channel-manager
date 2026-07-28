from __future__ import annotations

from pathlib import Path


def test_vk_scan_status_output_is_legacy_windows_safe() -> None:
    text = Path("src/video_channel_manager/cli/vk.py").read_text(encoding="utf-8")

    assert "Exported AuditPackage ->" in text
    assert "Exported AuditPackage →" not in text
    assert "Reading VK community inventory..." in text
    assert "Reading VK community inventory…" not in text
