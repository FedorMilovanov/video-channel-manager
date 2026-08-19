from __future__ import annotations

import json
from pathlib import Path

from video_channel_manager.milovi_telegram_video_artifacts import conversion_argv


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "milovi-telegram-video-artifacts.yml"
SOURCE_PROBE_WORKFLOW = ROOT / ".github" / "workflows" / "milovi-telegram-video-source-probe.yml"
CONTRACT = ROOT / "content" / "telegram" / "milovi-cake" / "video-conversion-contract-2026-08.json"


def test_silent_conversion_command_is_native_mp4_provider_free_and_no_upscale() -> None:
    argv = conversion_argv(Path("source.webm"), Path("milovi-v01.mp4"), source_has_audio=False)
    command = " ".join(argv)

    assert argv[0] == "ffmpeg"
    assert "-c:v libx264" in command
    assert "-pix_fmt yuv420p" in command
    assert "-movflags +faststart" in command
    assert "-fps_mode passthrough" in command
    assert "scale=trunc(iw/2)*2:trunc(ih/2)*2" in command
    assert "-an" in argv
    assert "-map 0:a:0" not in command
    assert "-threads 1" in command
    assert "-y" not in argv


def test_reviewed_source_audio_is_preserved_as_one_aac_stream() -> None:
    argv = conversion_argv(Path("source.webm"), Path("milovi-v01.mp4"), source_has_audio=True)
    command = " ".join(argv)

    assert "-map 0:v:0" in command
    assert "-map 0:a:0" in command
    assert "-an" not in argv
    assert "-c:a aac" in command
    assert "-b:a 128k" in command
    assert "-ar 48000" in command
    assert "-ac 2" in command
    assert "-map_metadata -1" in command
    assert "-map_chapters -1" in command


def test_conversion_execution_gate_is_explicit_provider_free_and_audio_reviewed() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    review = contract["source_audio_review"]
    audio = contract["output_policy"]["audio_policy"]

    assert contract["conversion_execution_ready"] is True
    assert contract["provider_write_authorized"] is False
    assert contract["source_mutation_allowed"] is False
    assert contract["document_fallback_allowed"] is False
    assert review["status"] == "exact_probe_reviewed_for_transport_preservation"
    assert review["workflow_run_id"] == 32301057940
    assert review["artifact_id"] == 9383216524
    assert review["reviewed_video_count"] == 16
    assert review["required_audio_stream_count_per_source"] == 1
    assert review["required_source_audio_codec"] == "opus"
    assert review["required_source_audio_sample_rate_hz"] == 48000
    assert review["required_source_audio_channels"] == 2
    assert audio["source_audio_codec_reviewed"] == "opus"
    assert audio["output_audio_codec"] == "aac"
    assert audio["audio_bitrate_target"] == "128k"
    assert audio["sample_rate_hz"] == 48000
    assert audio["channels"] == 2
    assert audio["extra_audio_streams_allowed"] is False


def test_video_artifact_workflow_has_read_only_pr_proof_and_no_provider_writer_path() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    trigger = text.split("permissions:", 1)[0]

    assert "workflow_dispatch:" in trigger
    assert "pull_request:" in trigger
    assert "push:" in trigger
    assert "branches: [main]" in trigger
    assert "permissions:\n  contents: read" in text
    assert "prove-provider-free-artifacts:" in text
    assert "permissions:\n      contents: read" in text
    assert "permissions:\n      contents: write" in text
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


def test_video_artifact_workflow_hardens_exact_head_and_runner_without_weakening_main() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "group: milovi-telegram-video-artifacts-${{ github.event_name }}-${{ github.ref }}" in text
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in text
    assert text.count("timeout-minutes: 45") == 2
    assert "ref: ${{ github.event.pull_request.head.sha }}" in text
    assert "milovi-telegram-video-pr-proof-${{ github.event.pull_request.head.sha }}" in text
    assert text.count("https://archive.ubuntu.com/ubuntu/") == 2
    assert text.count('Acquire::Retries "3";') == 2
    assert text.count('Acquire::http::Timeout "20";') == 2
    assert text.count('Acquire::https::Timeout "20";') == 2
    assert "if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'" in text


def test_video_artifact_workflow_installs_exact_toolchain_and_preserves_main_no_overwrite() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "c4eb3bf6ed6fd5c3c9e4c2d857e53d8bae093370" in text
    assert "repository: FedorMilovanov/Milovi_Cake" in text
    assert text.count("sudo apt-get install -y --no-install-recommends ffmpeg") == 2
    assert "ffmpeg -version | head -n 1" in text
    assert "ffprobe -version | head -n 1" in text
    assert "main advanced before Milovi video artifact build" in text
    assert "main advanced during Milovi video artifact build" in text
    assert "content-addressed artifact branch already exists; refusing overwrite" in text
    assert "agent/milovi-video-accepted-${evidence_sha:0:12}" in text
    assert "git push origin" in text


def test_source_probe_workflow_proves_all_16_without_repository_or_provider_write() -> None:
    text = SOURCE_PROBE_WORKFLOW.read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in text
    assert "repository: FedorMilovanov/Milovi_Cake" in text
    assert "c4eb3bf6ed6fd5c3c9e4c2d857e53d8bae093370" in text
    assert "Probe all 16 exact sources without conversion" in text
    assert '"audio_stream_count": len(audios)' in text
    assert '"audio_codecs": [stream.get("codec_name") for stream in audios]' in text
    assert "provider_access_performed" in text
    assert "provider_write_performed" in text
    assert "git push" not in text
    assert "TELEGRAM_BOT_TOKEN" not in text


def test_source_probe_workflow_hardens_exact_head_and_cancels_only_stale_pr_probe() -> None:
    text = SOURCE_PROBE_WORKFLOW.read_text(encoding="utf-8")

    assert "group: milovi-telegram-video-source-probe-${{ github.event_name }}-${{ github.ref }}" in text
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in text
    assert "timeout-minutes: 30" in text
    assert "ref: ${{ github.event.pull_request.head.sha }}" in text
    assert "milovi-telegram-video-source-probes-${{ github.event.pull_request.head.sha || github.sha }}" in text
    assert text.count("https://archive.ubuntu.com/ubuntu/") == 1
    assert text.count('Acquire::Retries "3";') == 1
    assert text.count('Acquire::http::Timeout "20";') == 1
    assert text.count('Acquire::https::Timeout "20";') == 1
