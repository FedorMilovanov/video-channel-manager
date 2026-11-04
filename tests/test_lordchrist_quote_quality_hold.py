"""The revoked v4 quote edition must never reach Telegram or state mutation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.lordchrist_quote_quality_hold import (
    QuoteEditorialHold,
    main,
    require_quote_v4_editorial_release,
)

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
HOLD = CONTENT / "quote-v4-editorial-safety-hold.json"
ACTIVATION = CONTENT / "quote-v4-runtime-activation.json"
QUEUE = CONTENT / "verified-30-posts.json"
WORKFLOW = ROOT / ".github/workflows/lordchrist-telegram-poster.yml"


def _assert_hold(*, hold: Path = HOLD, activation: Path = ACTIVATION, queue: Path = QUEUE) -> str:
    with pytest.raises(QuoteEditorialHold) as result:
        require_quote_v4_editorial_release(hold_path=hold, activation_path=activation, queue_path=queue)
    return str(result.value)


def test_approved_old_v4_is_now_blocked_before_any_mutation() -> None:
    assert "EDITORIAL QUALITY HOLD" in _assert_hold()
    assert main(["--hold", str(HOLD), "--activation", str(ACTIVATION), "--queue", str(QUEUE)]) == 23


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("status", "released_without_review"),
        ("queue_digest", "sha256:" + "a" * 64),
        ("release_id", "lordchrist-puritan-spurgeon-v5"),
        ("schema_version", 99),
        ("approved_queue_file_sha256", "sha256:" + "b" * 64),
    ],
)
def test_mutating_any_safety_hold_binding_fails_closed(tmp_path: Path, field: str, replacement: object) -> None:
    data = json.loads(HOLD.read_text(encoding="utf-8"))
    data[field] = replacement
    altered = tmp_path / "hold.json"
    altered.write_text(json.dumps(data), encoding="utf-8")
    assert "fail closed" in _assert_hold(hold=altered)


def test_missing_or_corrupt_hold_fails_closed(tmp_path: Path) -> None:
    assert "Missing or unreadable" in _assert_hold(hold=tmp_path / "missing.json")
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("not-json", encoding="utf-8")
    assert "Missing or unreadable" in _assert_hold(hold=corrupt)


def test_queue_bytes_changed_fails_closed(tmp_path: Path) -> None:
    tampered = tmp_path / "queue.json"
    tampered.write_bytes(QUEUE.read_bytes() + b"\n")
    assert "fail closed" in _assert_hold(queue=tampered)


def test_workflow_guard_runs_after_readonly_proof_and_before_first_write() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    gate = "      - name: Enforce exact quote-v4 editorial quality hold before any state or provider write"
    assert text.count(gate) == 1
    assert text.index("      - name: Enforce publication gates") < text.index(gate)
    assert text.index(gate) < text.index("      - name: Enable state writer for one-time v4 ledger initialization")
    section = text.split(gate, 1)[1].split("      - name:", 1)[0]
    assert "if: steps.intent.outputs.do_publish == 'true'" in section
    assert "python -m video_channel_manager.lordchrist_quote_quality_hold" in section
    assert "quote-v4-editorial-safety-hold.json" in section
    assert section.count(" " + chr(92) + "\n") == 3
    assert " " + chr(92) * 2 + "\n" not in section
    assert "sendMessage" not in section
    assert "sendRichMessage" not in section
    assert "persist" not in section.lower()
