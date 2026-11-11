"""Fail-closed tests for opt-in, private Telegraph browser authorization."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from scripts.lordchrist_telegraph_editor_login import send_editor_login

PAGE = "Rabstvo-svobody-11-11"
URL = "https://edit.telegra.ph/auth/abcdefghijklmnopqrstuvwxyz0123456789"


class FakeAPI:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.chat_type = "private"
        self.page_editable = True
        self.auth_url = URL
        self.send_ok = True

    def __call__(self, endpoint: str, fields: Mapping[str, str]) -> dict[str, Any]:
        self.calls.append((endpoint, dict(fields)))
        if endpoint.endswith("/getChat"):
            return {"ok": True, "result": {"type": self.chat_type, "id": 1234567}}
        if endpoint.endswith(f"/getPage/{PAGE}"):
            return {"ok": True, "result": {"path": PAGE, "can_edit": self.page_editable}}
        if endpoint.endswith("/getAccountInfo"):
            return {"ok": True, "result": {"short_name": "lordchrist", "auth_url": self.auth_url}}
        if endpoint.endswith("/sendMessage"):
            return {"ok": self.send_ok, "result": {"message_id": 15}}
        raise AssertionError(f"Unexpected API operation: {endpoint}")


def _send(fake: FakeAPI, chat_id: str = "1234567") -> None:
    send_editor_login(
        telegraph_token="existing-telegraph-secret",
        telegram_bot_token="existing-bot-secret",
        editor_chat_id=chat_id,
        post=fake,
    )


def test_delivers_only_one_private_link_without_logging_it(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAPI()
    _send(fake)
    assert [endpoint.rsplit("/", 1)[-1] for endpoint, _ in fake.calls] == [
        "getChat", PAGE, "getAccountInfo", "sendMessage"
    ]
    sent = fake.calls[-1][1]
    assert sent["chat_id"] == "1234567"
    assert sent["protect_content"] == "true"
    assert URL in sent["text"]
    out = capsys.readouterr().out
    assert URL not in out
    assert "existing-telegraph-secret" not in out
    assert "existing-bot-secret" not in out


@pytest.mark.parametrize("chat_id", ["", "-1001234", "0", "hello", "123 456"])
def test_disallows_unpinned_or_channel_recipient(chat_id: str) -> None:
    fake = FakeAPI()
    with pytest.raises(RuntimeError, match="private user chat ID"):
        _send(fake, chat_id)
    assert fake.calls == []


def test_rejects_a_group_chat_before_requesting_a_login_url() -> None:
    fake = FakeAPI()
    fake.chat_type = "supergroup"
    with pytest.raises(RuntimeError, match="not the pinned private"):
        _send(fake)
    assert len(fake.calls) == 1


def test_rejects_wrong_telegraph_account_before_minting_login() -> None:
    fake = FakeAPI()
    fake.page_editable = False
    with pytest.raises(RuntimeError, match="cannot edit"):
        _send(fake)
    assert len(fake.calls) == 2


@pytest.mark.parametrize(
    "url",
    [
        "http://edit.telegra.ph/auth/abcdefgh",
        "https://fake.example/auth/abcdefgh",
        "https://edit.telegra.ph/abcdefgh",
        "https://edit.telegra.ph/auth/abcdefgh?steal=1",
        "",
    ],
)
def test_never_sends_an_invalid_or_untrusted_authorization_url(url: str) -> None:
    fake = FakeAPI()
    fake.auth_url = url
    with pytest.raises(RuntimeError, match="valid secure one-use"):
        _send(fake)
    assert all(not endpoint.endswith("/sendMessage") for endpoint, _ in fake.calls)


def test_rejected_telegram_send_fails_without_printing_link(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAPI()
    fake.send_ok = False
    with pytest.raises(RuntimeError, match="private one-time login delivery rejected"):
        _send(fake)
    assert URL not in capsys.readouterr().out
