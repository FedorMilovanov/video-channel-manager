from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import video_channel_manager.telegram_lordchrist_outcome_cli as outcome_cli


def _base_argv(command: str, *extra: str, root_extra: tuple[str, ...] = ()) -> list[str]:
    return [
        "telegram_lordchrist_outcome_cli",
        "--queue",
        "queue.json",
        "--ledger",
        "ledger.json",
        *root_extra,
        command,
        "--dispatch",
        "dispatch.json",
        "--rendered",
        "rendered.json",
        *extra,
    ]


def _install_common_stubs(monkeypatch: pytest.MonkeyPatch) -> tuple[object, Any, Any, object]:
    queue = object()
    ledger = SimpleNamespace(entries={"pub-1": SimpleNamespace(publication_id="pub-1")})
    envelope = SimpleNamespace(publication_id="pub-1")
    rendered = object()
    monkeypatch.setattr(outcome_cli, "load_queue", lambda path: queue)
    monkeypatch.setattr(outcome_cli, "load_ledger", lambda path, loaded_queue: ledger)
    monkeypatch.setattr(outcome_cli, "load_dispatch", lambda path: envelope)
    monkeypatch.setattr(outcome_cli, "load_rendered_post", lambda path: rendered)
    return queue, ledger, envelope, rendered


def test_verify_evidence_cli_reports_exact_persisted_state(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    queue, ledger, envelope, rendered = _install_common_stubs(monkeypatch)
    entry = SimpleNamespace(
        publication_id="pub-1",
        state="dispatching",
        provider_effect="may_exist",
        intent_id="intent-1",
    )

    def verify(actual_queue: object, actual_ledger: object, actual_envelope: object, actual_rendered: object) -> Any:
        assert (actual_queue, actual_ledger, actual_envelope, actual_rendered) == (
            queue,
            ledger,
            envelope,
            rendered,
        )
        return entry

    monkeypatch.setattr(outcome_cli, "verify_lordchrist_persisted_evidence", verify)
    monkeypatch.setattr(sys, "argv", _base_argv("verify-evidence"))

    assert outcome_cli.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "verified": True,
        "publication_id": "pub-1",
        "state": "dispatching",
        "provider_effect": "may_exist",
        "intent_id": "intent-1",
    }


def test_capture_cli_requires_policy_before_outcome_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_common_stubs(monkeypatch)
    monkeypatch.setattr(sys, "argv", _base_argv("capture", "--output", "outcome.json"))

    with pytest.raises(ValueError, match="exact presentation policy"):
        outcome_cli.main()


def test_capture_cli_persists_structured_provider_outcome(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    queue, ledger, envelope, rendered = _install_common_stubs(monkeypatch)
    published_at = datetime(2026, 8, 8, 18, 0, tzinfo=UTC)
    captured_entry = SimpleNamespace(
        provider_effect="verified",
        state="published",
        message_id=1472,
        published_at_utc=published_at,
    )
    captured = SimpleNamespace(publication_id="pub-1", entry=captured_entry)
    policy = object()
    saved: list[tuple[Path, object]] = []
    monkeypatch.setattr(outcome_cli, "load_presentation_policy", lambda path: policy)

    def capture(
        actual_queue: object,
        actual_envelope: object,
        actual_rendered: object,
        actual_policy: object,
        actual_entry: object,
    ) -> Any:
        assert actual_queue is queue
        assert actual_envelope is envelope
        assert actual_rendered is rendered
        assert actual_policy is policy
        assert actual_entry is ledger.entries["pub-1"]
        return captured

    monkeypatch.setattr(outcome_cli, "capture_lordchrist_provider_outcome", capture)
    monkeypatch.setattr(outcome_cli, "save_model", lambda path, model: saved.append((path, model)))
    monkeypatch.setattr(
        sys,
        "argv",
        _base_argv(
            "capture",
            "--output",
            "outcome.json",
            root_extra=("--presentation-policy", "policy.json"),
        ),
    )

    assert outcome_cli.main() == 0
    assert saved == [(Path("outcome.json"), captured)]
    payload = json.loads(capsys.readouterr().out)
    assert payload["captured"] is True
    assert payload["publication_id"] == "pub-1"
    assert payload["provider_effect"] == "verified"
    assert payload["message_id"] == 1472
    assert payload["published_at_utc"] == published_at.isoformat()
    assert payload["output"] == "outcome.json"


def test_apply_cli_updates_and_saves_ledger_without_provider_access(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    queue, ledger, envelope, rendered = _install_common_stubs(monkeypatch)
    outcome = object()
    published_at = datetime(2026, 8, 8, 18, 0, tzinfo=UTC)
    applied = SimpleNamespace(
        publication_id="pub-1",
        provider_effect="verified",
        state="published",
        message_id=1472,
        message_url="https://t.me/lordchrist/1472",
        published_at_utc=published_at,
    )
    saved: list[tuple[Path, object]] = []
    monkeypatch.setattr(outcome_cli, "load_lordchrist_provider_outcome", lambda path: outcome)

    def apply(
        actual_queue: object,
        actual_ledger: object,
        actual_envelope: object,
        actual_rendered: object,
        actual_outcome: object,
    ) -> Any:
        assert (actual_queue, actual_ledger, actual_envelope, actual_rendered, actual_outcome) == (
            queue,
            ledger,
            envelope,
            rendered,
            outcome,
        )
        return applied

    monkeypatch.setattr(outcome_cli, "apply_lordchrist_provider_outcome", apply)
    monkeypatch.setattr(outcome_cli, "save_ledger", lambda path, model: saved.append((path, model)))
    monkeypatch.setattr(sys, "argv", _base_argv("apply", "--outcome", "outcome.json"))

    assert outcome_cli.main() == 0
    assert saved == [(Path("ledger.json"), ledger)]
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "applied": True,
        "publication_id": "pub-1",
        "provider_effect": "verified",
        "state": "published",
        "message_id": 1472,
        "message_url": "https://t.me/lordchrist/1472",
        "published_at_utc": published_at.isoformat(),
    }
