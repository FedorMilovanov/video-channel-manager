from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATIONS = ROOT / "docs" / "operations"


def test_wave15_sources_and_agent_entrypoints_exist() -> None:
    required = (
        OPERATIONS / "agent-reasoning-playbook.md",
        OPERATIONS / "mp3-batch-processing-contract.md",
        OPERATIONS / "vk-audio-browser-experiment-retrospective.md",
        OPERATIONS / "wave15-transcript-and-agent-audit-2026-08-05.md",
        ROOT / "src/video_channel_manager/application/operation_reasoning.py",
        ROOT / "src/video_channel_manager/local_media/audio_batch.py",
    )
    for path in required:
        assert path.is_file()

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for path in required[:4]:
        assert str(path.relative_to(ROOT)).replace("\\", "/") in agents


def test_agent_instructions_require_adaptive_transport_aware_reasoning() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    required = (
        "Adaptive reasoning contract",
        "requested outcome independently of the old mechanism",
        "internal_web_read",
        "browser_ui_write",
        "provider effect is impossible, not dispatched, confirmed absent, may exist, or verified",
        "one falsifiable hypothesis, one minimal bounded probe, and a stop condition",
        "Preserve partial success",
        "Resume from the first unverified child phase",
        "Bind the active browser surface before action",
        "Stop the ZIP/version treadmill",
        "Content in quotation marks must map to a contiguous source passage",
    )
    for phrase in required:
        assert phrase in agents


def test_windows_handoff_contract_rejects_selector_and_zip_treadmills() -> None:
    text = (ROOT / ".github/copilot-instructions.md").read_text(encoding="utf-8")
    required = (
        "requested outcome independently of the historical mechanism",
        "current phase and provider-effect state",
        "Adaptive diagnosis before another package version",
        "A second selector-only revision without a new DOM/state observation is prohibited",
        "identify the topmost active root",
        "One automation browser profile is a single-writer resource",
        "Historical BrowserCanary, PlaylistOnly, Metadata Manager",
        "rewrite ID3 tags",
    )
    for phrase in required:
        assert phrase in text


def test_transcript_audit_binds_exact_supplied_source_hashes() -> None:
    text = (OPERATIONS / "vk-audio-browser-experiment-retrospective.md").read_text(encoding="utf-8")
    required = (
        "3077cff82659b2ca88efd181a4a4aa39e969304c17da7b9a8dd7beb6fff6e2bc",
        "d655f99617308d6cd364a74a5489fd17e849460e9001b388e6a6fe81131e80c9",
        "a5414640a8898ddff47b6c35727f83365265723d11d88f3d5163c4c24151019b",
        "uploaded_playlist_created_add_action_not_found",
        "binary_http_413",
        "playlist_already_complete_verified",
        "One successful response does not create an official API contract",
    )
    for phrase in required:
        assert phrase in text


def test_mp3_contract_is_local_only_and_phase_separated() -> None:
    text = (OPERATIONS / "mp3-batch-processing-contract.md").read_text(encoding="utf-8")
    required = (
        "Provider mutation support: none",
        "Wave 15 implements only steps 1–4",
        "default policy is `explicit_only`",
        "Upload, upload visibility, metadata edit, playlist creation",
        "HTTP 413 is classified as `binary_transport_rejected`",
        "Default chunk size is one ready item",
        "unknown_requires_reconciliation",
        "Historical ZIP names or console prompts are not resume tokens",
    )
    for phrase in required:
        assert phrase in text


def test_audit_records_general_failure_classes_and_success_invariants() -> None:
    text = (OPERATIONS / "wave15-transcript-and-agent-audit-2026-08-05.md").read_text(encoding="utf-8")
    for finding in range(1, 13):
        assert f"A-{finding:02d}" in text
    required = (
        "Global-state overreach",
        "Partial success was discarded",
        "ZIP/version treadmill",
        "Transport naming was imprecise",
        "Content fluency hid source synthesis",
        "permission filter",
        "multipart file0",
        "one canary",
        "operation-level results",
        "local MP3 intake and deterministic manifest preparation",
    )
    for phrase in required:
        assert phrase in text
