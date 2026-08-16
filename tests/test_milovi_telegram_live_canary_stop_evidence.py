from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import video_channel_manager.milovi_telegram_live_canary as canary


def _seed_dispatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    state_path = tmp_path / "state.json"
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / "p18.jpg").write_bytes(b"jpeg")
    (runtime_dir / "caption.txt").write_text("caption", encoding="utf-8")
    state_path.write_text(
        json.dumps(
            {
                "schema_name": "video-channel-manager.milovi-exact-canary-dispatch-state",
                "schema_version": 1,
                "project_key": "milovi-cake",
                "publication_id": "milovi-cake-canary-001",
                "status": "dispatch_started",
                "provider_effect": "may_exist_after_next_step",
                "authorization_commit_sha": "reviewed-sha",
                "authorization_id": "auth-1",
                "message_id": None,
                "message_url": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(canary, "STATE_PATH", state_path)
    monkeypatch.setattr(canary, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setenv("GITHUB_SHA", "reviewed-sha")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "not-used-by-test")
    return state_path


def _state(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_transport_failure_persists_unknown_never_replay_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_path = _seed_dispatch(monkeypatch, tmp_path)

    def fail_call(*_args: Any, **kwargs: Any) -> tuple[int, dict[str, Any]]:
        assert kwargs["retries"] == 0
        raise RuntimeError("response decode lost")

    monkeypatch.setattr(canary, "_telegram_call", fail_call)

    with pytest.raises(SystemExit) as exc:
        canary.send()

    assert exc.value.code == 75
    observed = _state(state_path)
    assert observed["status"] == "unknown_requires_reconciliation"
    assert observed["provider_effect"] == "may_exist"
    assert observed["provider_write_may_have_occurred"] is True
    assert observed["last_durable_stage"] == "dispatch_started"
    assert observed["retry_policy"] == "never_replay"
    assert observed["required_next_action"] == "read_reconcile_exact_message_identity"
    assert observed["automatic_replay_allowed"] is False
    assert observed["stop_failure_type"] == "transport_or_response_decode_error"


def test_non_terminal_provider_response_persists_http_reconciliation_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_path = _seed_dispatch(monkeypatch, tmp_path)
    monkeypatch.setattr(
        canary,
        "_telegram_call",
        lambda *_args, **_kwargs: (503, {"ok": False, "description": "upstream unavailable"}),
    )

    with pytest.raises(SystemExit) as exc:
        canary.send()

    assert exc.value.code == 75
    observed = _state(state_path)
    assert observed["status"] == "unknown_requires_reconciliation"
    assert observed["provider_http_status"] == 503
    assert observed["last_durable_stage"] == "provider_response_received"
    assert observed["stop_failure_type"] == "non_terminal_provider_response"
    assert observed["retry_policy"] == "never_replay"


def test_malformed_success_response_is_unknown_not_replayable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_path = _seed_dispatch(monkeypatch, tmp_path)
    monkeypatch.setattr(canary, "_telegram_call", lambda *_args, **_kwargs: (200, {"ok": True, "result": None}))

    with pytest.raises(SystemExit) as exc:
        canary.send()

    assert exc.value.code == 75
    observed = _state(state_path)
    assert observed["status"] == "unknown_requires_reconciliation"
    assert observed["provider_write_may_have_occurred"] is True
    assert observed["last_durable_stage"] == "provider_success_response_received"
    assert observed["stop_failure_type"] == "malformed_success_response"
    assert observed["automatic_replay_allowed"] is False


def test_deterministic_rejection_records_successor_only_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_path = _seed_dispatch(monkeypatch, tmp_path)
    monkeypatch.setattr(
        canary,
        "_telegram_call",
        lambda *_args, **_kwargs: (400, {"ok": False, "description": "Bad Request: invalid file"}),
    )

    with pytest.raises(SystemExit) as exc:
        canary.send()

    assert exc.value.code == 76
    observed = _state(state_path)
    assert observed["status"] == "provider_rejected"
    assert observed["provider_effect"] == "rejected_before_message_creation"
    assert observed["provider_write_may_have_occurred"] is False
    assert observed["retry_policy"] == "requires_new_reviewed_successor_authorization"
    assert observed["required_next_action"] == "review_rejection_and_issue_explicit_successor_authorization"
    assert observed["automatic_replay_allowed"] is False
