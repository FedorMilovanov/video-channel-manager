from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.milovi_telegram_video_artifacts import conversion_argv


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "milovi-telegram-video-artifacts.yml"
CONTRACT = ROOT / "content" / "telegram" / "milovi-cake" / "video-conversion-contract-2026-08.json"


def test_conversion_command_is_native_mp4_provider_free_and_no_upscale() -> None:
    argv = conversion_argv(Path("source.webm"), Path("milovi-v01.mp4"), source_has_audio=False)
    command = " ".join(argv)

    assert argv[0] == "ffmpeg"
    assert "-c:v libx264" in command
    assert "-pix_fmt yuv420p" in command
    assert "-movflags +faststart" in command
    assert "-fps_mode passthrough" in command
    assert "scale=trunc(iw/2)*2:trunc(ih/2)*2" in command
    assert "-an" in argv
    assert "-threads 1" in command
    assert "-y" not in argv


def test_audio_requires_separate_review_instead_of_automatic_conversion() -> None:
    with pytest.raises(ValueError, match="audio requires a separate exact editorial review"):
        conversion_argv(Path("source.webm"), Path("milovi-v01.mp4"), source_has_audio=True)


def test_conversion_execution_gate_is_explicit_and_provider_free() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["conversion_execution_ready"] is True
    assert contract["provider_write_authorized"] is False
    assert contract["source_mutation_allowed"] is False
    assert contract["document_fallback_allowed"] is False


def test_video_artifact_workflow_has_no_telegram_or_provider_writer_path() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    trigger = text.split("permissions:", 1)[0]

    assert "workflow_dispatch:" in trigger
    assert "push:" in trigger
    assert "branches: [main]" in trigger
    assert "contents: write" in text
    assert "pull-requests: write" not in text
    assert "conversion_execution_ready" in text
    assert "provider_write_authorized" in text
    assert "source_mutation_allowed" in text
    assert "TELEGRAM_BOT_TOKEN" not in text
    assert "send-once" not in text
    assert "telegram_multichannel_cli" not in text
    assert "provider_access_performed" in text
    assert "provider_write_performed" in text
    assert "state/milovi-cake-telegram" not in text
    assert "[skip ci]" not in text.casefold()


def test_video_artifact_workflow_is_exact_source_and_no_overwrite() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "c4eb3bf6ed6fd5c3c9e4c2d857e53d8bae093370" in text
    assert "repository: FedorMilovanov/Milovi_Cake" in text
    assert "main advanced before Milovi video artifact build" in text
    assert "main advanced during Milovi video artifact build" in text
    assert "content-addressed artifact branch already exists; refusing overwrite" in text
    assert "agent/milovi-video-accepted-${evidence_sha:0:12}" in text
    assert "git push origin" in text
