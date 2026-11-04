"""Regression proof for durable claim -> provider -> durable receipt ordering."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from video_channel_manager import lordchrist_telegraph_staged as staged
from video_channel_manager.lordchrist_telegraph_publisher import JPEG_MAGIC, save_ledger

ROOT = Path(__file__).resolve().parents[1]
PUB_ID = "lordchrist-telegraph-charnock-05"
MEDIA = "https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/" + "a" * 40


class FakeTransport:
    def __init__(
        self, *, page_error: bool = False, telegram_error: bool = False, content_too_big: bool = False
    ) -> None:
        self.page_error = page_error
        self.telegram_error = telegram_error
        self.content_too_big = content_too_big
        self.pages = 0
        self.messages = 0

    def get_status(self, url: str) -> tuple[int, bytes]:
        if url.endswith(".jpg"):
            return 200, JPEG_MAGIC + b"JFIF"
        return 200, b"<html>Telegraph</html>"

    def post_multipart(self, url: str, fields: Mapping[str, bytes]) -> dict[str, Any]:
        _ = fields
        if url.endswith("/getAccountInfo"):
            return {"ok": True, "result": {"short_name": "lordchrist"}}
        if url.endswith("/createPage"):
            self.pages += 1
            if self.page_error:
                raise RuntimeError("ambiguous timeout after Telegraph page mutation")
            if self.content_too_big:
                return {"ok": False, "error": "CONTENT_TOO_BIG"}
            return {
                "ok": True,
                "result": {"url": "https://telegra.ph/Verified-Charnock-05", "path": "Verified-Charnock-05"},
            }
        raise AssertionError(f"Unexpected Telegraph mutation: {url}")

    def read_json(self, url: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.post_json(url, payload)

    def post_json(self, url: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        _ = payload
        if url.endswith("/getMe"):
            return {"ok": True, "result": {"id": 8716602202}}
        if url.endswith("/getChat"):
            return {"ok": True, "result": {"id": -1001295216957}}
        if url.endswith("/sendMessage"):
            self.messages += 1
            if self.telegram_error:
                raise RuntimeError("ambiguous timeout after Telegram send mutation")
            return {
                "ok": True,
                "result": {"message_id": 1777, "link_preview_options": {"prefer_large_media": True}},
            }
        raise AssertionError(f"Unexpected Telegram mutation: {url}")


@pytest.fixture
def execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> argparse.Namespace:
    ledger_path = tmp_path / "ledger.json"
    save_ledger(
        ledger_path,
        {
            "schema_name": "video-channel-manager.lordchrist-telegraph-ledger",
            "schema_version": 1,
            "project_key": "lord-god-strength",
            "entries": {},
        },
    )
    monkeypatch.setenv("GITHUB_REPOSITORY", "FedorMilovanov/video-channel-manager")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_RUN_ID", "123456789")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    return argparse.Namespace(
        stage="prepare-page",
        publication_id=PUB_ID,
        media_base_url=MEDIA,
        repo_root=ROOT,
        queue=staged.DEFAULT_QUEUE_PATH,
        ledger=ledger_path,
        run_id="123456789",
        run_attempt=1,
        github_sha="a" * 40,
    )


def _state(args: argparse.Namespace) -> dict[str, Any]:
    return json.loads(args.ledger.read_text(encoding="utf-8"))["entries"][PUB_ID]


def test_staged_complete_release_requires_both_persisted_claims(
    execution: argparse.Namespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = FakeTransport()
    monkeypatch.setattr(staged, "HttpxLiveTransport", lambda: first)
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "original-persistent-account")
    monkeypatch.setenv("LORDCHRIST_TELEGRAM_BOT_TOKEN", "test-bot-token")

    staged.execute(execution)
    assert _state(execution)["state"] == "page_dispatch_claimed"
    with pytest.raises(RuntimeError, match="no reinitialization"):
        staged.execute(execution)

    execution.stage = "send-page"
    staged.execute(execution)
    assert _state(execution)["state"] == "page_published"
    assert first.pages == 1

    execution.stage = "prepare-telegram"
    staged.execute(execution)
    assert _state(execution)["state"] == "telegram_dispatch_claimed"

    execution.stage = "send-telegram"
    staged.execute(execution)
    assert _state(execution)["state"] == "published"
    assert _state(execution)["telegram_message_id"] == 1777
    assert first.messages == 1
    with pytest.raises(RuntimeError, match="no replay or skipped stage"):
        staged.execute(execution)
    assert first.messages == 1


def test_ambiguous_page_response_preserves_blocking_claim(
    execution: argparse.Namespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = FakeTransport(page_error=True)
    monkeypatch.setattr(staged, "HttpxLiveTransport", lambda: transport)
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "original-persistent-account")
    staged.execute(execution)
    execution.stage = "send-page"
    with pytest.raises(RuntimeError, match="ambiguous timeout"):
        staged.execute(execution)
    assert transport.pages == 1
    assert _state(execution)["state"] == "page_dispatch_claimed"
    execution.stage = "prepare-page"
    with pytest.raises(RuntimeError, match="no reinitialization"):
        staged.execute(execution)
    assert transport.pages == 1


def test_split_failure_never_makes_second_telegraph_page(
    execution: argparse.Namespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = FakeTransport(content_too_big=True)
    monkeypatch.setattr(staged, "HttpxLiveTransport", lambda: transport)
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "original-persistent-account")
    staged.execute(execution)
    execution.stage = "send-page"
    with pytest.raises(RuntimeError, match="refuses a second createPage"):
        staged.execute(execution)
    assert transport.pages == 1
    assert _state(execution)["state"] == "page_dispatch_claimed"


def test_ambiguous_telegram_response_preserves_blocking_claim(
    execution: argparse.Namespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = FakeTransport(telegram_error=True)
    monkeypatch.setattr(staged, "HttpxLiveTransport", lambda: transport)
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "original-persistent-account")
    monkeypatch.setenv("LORDCHRIST_TELEGRAM_BOT_TOKEN", "test-bot-token")
    staged.execute(execution)
    execution.stage = "send-page"
    staged.execute(execution)
    execution.stage = "prepare-telegram"
    staged.execute(execution)
    execution.stage = "send-telegram"
    with pytest.raises(RuntimeError, match="ambiguous timeout"):
        staged.execute(execution)
    assert transport.messages == 1
    assert _state(execution)["state"] == "telegram_dispatch_claimed"
    execution.stage = "prepare-page"
    with pytest.raises(RuntimeError, match="no reinitialization"):
        staged.execute(execution)


def test_rerun_attempt_fails_before_accessing_state(
    execution: argparse.Namespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    execution.run_attempt = 2
    with pytest.raises(RuntimeError, match="Exact first-attempt"):
        staged.execute(execution)
    assert PUB_ID not in json.loads(execution.ledger.read_text(encoding="utf-8"))["entries"]


def test_telegraph_workflow_persists_each_claim_before_provider_mutation() -> None:
    text = (ROOT / ".github/workflows/lordchrist-telegraph-poster.yml").read_text(encoding="utf-8")
    ordered = (
        "Prepare exact durable Telegraph dispatch claim",
        "Persist and verify claimed Telegraph intent before public mutation",
        "Send exactly one claimed Telegraph page",
        "Persist and verify Telegraph receipt before Telegram preparation",
        "Prepare durable Telegram dispatch claim",
        "Persist and verify Telegram dispatch claim before public mutation",
        "Send exactly one claimed Telegram post",
        "Persist verified terminal Telegram receipt",
    )
    offsets = [text.index(name) for name in ordered]
    assert offsets == sorted(offsets)
    assert text.count('git -C "$state_dir" push origin HEAD:state/lordchrist-telegram') == 4
    assert "GITHUB_RUN_ATTEMPT" in text
    assert "LORDCHRIST_TELEGRAPH_POSTING_ENABLED" in text
    assert "inputs.confirm" in text
