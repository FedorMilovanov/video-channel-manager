from __future__ import annotations

from pathlib import Path


def test_vk_scan_status_output_is_legacy_windows_safe() -> None:
    text = Path("src/video_channel_manager/cli/vk.py").read_text(encoding="utf-8")

    assert "Exported AuditPackage ->" in text
    assert "Exported AuditPackage →" not in text
    assert "Reading VK community inventory..." in text
    assert "Reading VK community inventory…" not in text


def test_vk_cli_does_not_claim_read_only_capability_when_mutation_routes_exist() -> None:
    text = Path("src/video_channel_manager/cli/vk.py").read_text(encoding="utf-8")

    assert "VK read-only inventory plus explicitly guarded provider mutation workflows." in text
    assert "provider writes require command-specific confirmation." in text
    assert "Read-only VK community, video, and album inventory." not in text
    assert "The token is used only for read-only API calls by this version." not in text
    assert '@vk_app.command("milovi-323-rollout")' in text
