"""CLI failure messages for the read-only account inspection stay secret-free."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from video_channel_manager import lordchrist_jude_telegraph_readonly as probe


def test_unknown_method_is_rejected_without_contacting_provider() -> None:
    def never(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("unexpected HTTP request")

    with httpx.Client(transport=httpx.MockTransport(never)) as client:
        with pytest.raises(probe.ProbeError, match="Unsupported"):
            probe._read(client, "sensitive-token", "unexpected-method", {})


def test_owned_and_borrowed_http_client_lifecycles_are_explicit() -> None:
    with probe._ReadClient() as owned:
        assert owned.owns_http_client is True
        assert owned.client.follow_redirects is False
        assert owned.client.trust_env is False
        owned_client = owned.client
    assert owned_client.is_closed

    borrowed = httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200)))
    with probe._ReadClient(borrowed) as owner:
        assert owner.owns_http_client is False
        assert owner.client is borrowed
    assert not borrowed.is_closed
    borrowed.close()


def test_provider_error_body_is_not_exposed() -> None:
    secret = "not-a-real-access-token"
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={"ok": False, "error": secret}))
    with httpx.Client(transport=transport) as client:
        with pytest.raises(probe.ProbeError) as caught:
            probe._read(client, secret, "getAccountInfo", {"fields": '["page_count"]'})
    assert secret not in str(caught.value)


def test_cli_missing_token_is_a_safe_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.delenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("LEDGER_SHA", "b" * 40)
    assert probe.main(["--ledger", str(ledger)]) == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert "Read-only Jude account probe stopped" in captured.err
    assert "Traceback" not in captured.err


def test_cli_missing_ledger_stops_safely(tmp_path: Path, capsys) -> None:
    assert probe.main(["--ledger", str(tmp_path / "missing.json")]) == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert "missing or malformed" in captured.err
    assert "Traceback" not in captured.err
