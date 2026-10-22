"""`telegram_binding_cli` turns verified target evidence into the pinned channel binding.

The runbook says it "re-checks the live Telegram target from the pinned ID immediately before any
future provider mutation", and the workflow guard test only asserted that the module name appears
in the workflow text. The module had 0% coverage: nothing proved that it refuses a proof which
belongs to another profile, and nothing proved which of the two evidence sources it used.

These tests execute `main()` with a real profile and synthetic (provider-free) evidence.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from video_channel_manager import telegram_target_binding_cli as cli
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "content/telegram/channels/svodka.json"
LEGACY_PROFILE = ROOT / "content/telegram/channels/lordchrist.json"
CHECKED_AT = datetime(2026, 10, 22, 6, 0, tzinfo=UTC)


def _profile():
    return load_channel_profile(PROFILE)


def _proof(**overrides: object) -> dict[str, object]:
    profile = _profile()
    binding = load_target_binding(ROOT / "content/telegram/channels/svodka-target-binding.json", profile)
    payload: dict[str, object] = {
        "schema_name": "video-channel-manager.telegram-generic-target-proof",
        "schema_version": 1,
        "project_key": profile.project_key,
        "channel_username": profile.channel_username,
        "profile_sha256": profile.digest,
        "bot_id": binding.bot_id,
        "bot_username": binding.bot_username,
        "chat_id": binding.chat_id,
        "chat_username": profile.bare_username,
        "chat_title": profile.channel_title,
        "chat_type": "channel",
        "member_status": "administrator",
        "can_post_messages": True,
        "checked_at_utc": CHECKED_AT.isoformat(),
    }
    payload.update(overrides)
    return payload


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _run(monkeypatch: pytest.MonkeyPatch, argv: list[str], capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    monkeypatch.setattr("sys.argv", ["python -m video_channel_manager.telegram_binding_cli", *argv])
    assert cli.main() == 0
    return json.loads(capsys.readouterr().out)


def test_main_writes_a_profile_bound_binding_from_a_target_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    proof_path = _write(tmp_path / "proof.json", _proof())
    output = tmp_path / "binding.json"

    printed = _run(monkeypatch, ["--profile", str(PROFILE), "--proof", str(proof_path), "--output", str(output)], capsys)

    assert printed["bound"] is True
    assert printed["evidence_source"] == "generic_target_proof"
    assert printed["provider_write_performed"] is False
    assert printed["chat_id"] == _proof()["chat_id"]
    binding = load_target_binding(output, _profile())
    assert binding.digest == printed["binding_sha256"]
    assert binding.profile_sha256 == _profile().digest
    assert binding.project_key == _profile().project_key


def test_main_refuses_a_proof_written_for_another_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Evidence is only valid for the profile it was produced against."""

    foreign = _write(
        tmp_path / "proof.json",
        _proof(project_key="lord-god-strength", channel_username="@lordchrist"),
    )
    output = tmp_path / "binding.json"

    monkeypatch.setattr(
        "sys.argv",
        ["python -m video_channel_manager.telegram_binding_cli", "--profile", str(PROFILE), "--proof", str(foreign), "--output", str(output)],
    )

    with pytest.raises(ValueError, match="differs from selected channel profile"):
        cli.main()

    assert not output.exists()


def test_main_refuses_a_proof_without_posting_permission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proof_path = _write(tmp_path / "proof.json", _proof(can_post_messages=False))
    output = tmp_path / "binding.json"

    monkeypatch.setattr(
        "sys.argv",
        ["python -m video_channel_manager.telegram_binding_cli", "--profile", str(PROFILE), "--proof", str(proof_path), "--output", str(output)],
    )

    with pytest.raises(ValueError):
        cli.main()

    assert not output.exists()


def test_main_requires_exactly_one_evidence_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    proof_path = _write(tmp_path / "proof.json", _proof())
    dispatch_path = _write(tmp_path / "dispatch.json", {})

    monkeypatch.setattr(
        "sys.argv",
        [
            "python -m video_channel_manager.telegram_binding_cli",
            "--profile",
            str(PROFILE),
            "--proof",
            str(proof_path),
            "--legacy-dispatch",
            str(dispatch_path),
            "--output",
            str(tmp_path / "binding.json"),
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 2


def test_main_requires_an_evidence_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "python -m video_channel_manager.telegram_binding_cli",
            "--profile",
            str(PROFILE),
            "--output",
            str(tmp_path / "binding.json"),
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 2


def _legacy_dispatch() -> dict[str, object]:
    """A v4 dispatch envelope is the second accepted evidence source; it is @lordchrist only."""

    profile = load_channel_profile(LEGACY_PROFILE)
    binding = load_target_binding(ROOT / "content/telegram/channels/lordchrist-target-binding.json", profile)
    return {
        "schema_name": "video-channel-manager.telegram-dispatch",
        "schema_version": 4,
        "project_key": "lord-god-strength",
        "channel_username": "@lordchrist",
        "queue_digest": "sha256:" + "1" * 64,
        "publication_id": "lordchrist-cli-behaviour-test",
        "sequence": 1,
        "intent_id": "intent-cli-behaviour-0001",
        "workflow_run_id": "1",
        "workflow_run_attempt": "1",
        "github_sha": "0" * 40,
        "github_workflow_sha": "0" * 40,
        "payload_sha256": "sha256:" + "2" * 64,
        "text": "Т" * 120,
        "dispatch_mode": "manual",
        "target": {
            "schema_name": "video-channel-manager.telegram-target-proof",
            "schema_version": 2,
            "bot_id": binding.bot_id,
            "bot_username": binding.bot_username,
            "chat_id": binding.chat_id,
            "chat_username": "lordchrist",
            "chat_title": profile.channel_title,
            "chat_type": "channel",
            "member_status": "administrator",
            "can_post_messages": True,
            "checked_at_utc": CHECKED_AT.isoformat(),
        },
        "prepared_at_utc": CHECKED_AT.isoformat(),
    }


def test_main_accepts_a_verified_legacy_dispatch_as_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    dispatch_path = _write(tmp_path / "dispatch.json", _legacy_dispatch())
    output = tmp_path / "binding.json"

    printed = _run(
        monkeypatch,
        [
            "--profile",
            str(LEGACY_PROFILE),
            "--legacy-dispatch",
            str(dispatch_path),
            "--output",
            str(output),
        ],
        capsys,
    )

    assert printed["evidence_source"] == "legacy_verified_dispatch"
    assert printed["provider_write_performed"] is False
    binding = load_target_binding(output, load_channel_profile(LEGACY_PROFILE))
    assert binding.chat_id == printed["chat_id"]
