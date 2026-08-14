from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from video_channel_manager.telegram_channel_discovery import discover_channel_target
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_transport import TelegramApiError

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"


def test_discovery_resolves_numeric_id_and_proves_same_admin_bot() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    calls: list[tuple[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        payload = json.loads(request.content.decode("utf-8")) if request.content else {}
        calls.append((method, payload.get("chat_id")))
        if method == "getMe":
            result: object = {"id": 8716602202, "is_bot": True, "username": "preaching_mp3_bot"}
        elif method == "getChat":
            assert payload["chat_id"] in {"@deep_info_life", -1002233445566}
            result = {
                "id": -1002233445566,
                "username": "deep_info_life",
                "title": "СВОДКА",
                "type": "channel",
            }
        elif method == "getChatMember":
            assert payload == {"chat_id": -1002233445566, "user_id": 8716602202}
            result = {
                "status": "administrator",
                "can_post_messages": True,
                "user": {"id": 8716602202, "is_bot": True, "username": "preaching_mp3_bot"},
            }
        else:
            raise AssertionError(method)
        return httpx.Response(200, json={"ok": True, "result": result})

    now = datetime(2026, 8, 8, 0, 30, tzinfo=UTC)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        proof = discover_channel_target(
            profile,
            token="test-token",
            expected_bot_id=8716602202,
            expected_bot_username="preaching_mp3_bot",
            client=client,
            now=now,
        )

    assert proof.project_key == "svodka"
    assert proof.channel_username == "@deep_info_life"
    assert proof.chat_id == -1002233445566
    assert proof.chat_username == "deep_info_life"
    assert proof.bot_id == 8716602202
    assert proof.bot_username == "preaching_mp3_bot"
    assert proof.can_post_messages is True
    assert calls == [
        ("getMe", None),
        ("getChat", "@deep_info_life"),
        ("getChat", -1002233445566),
        ("getChatMember", -1002233445566),
    ]


def test_discovery_rejects_bot_without_posting_permission() -> None:
    profile = load_channel_profile(PROFILE_PATH)

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        payload = json.loads(request.content.decode("utf-8")) if request.content else {}
        if method == "getMe":
            result: object = {"id": 8716602202, "is_bot": True, "username": "preaching_mp3_bot"}
        elif method == "getChat":
            result = {
                "id": -1002233445566,
                "username": "deep_info_life",
                "title": "СВОДКА",
                "type": "channel",
            }
        elif method == "getChatMember":
            assert payload == {"chat_id": -1002233445566, "user_id": 8716602202}
            result = {
                "status": "administrator",
                "can_post_messages": False,
                "user": {"id": 8716602202, "is_bot": True, "username": "preaching_mp3_bot"},
            }
        else:
            raise AssertionError(method)
        return httpx.Response(200, json={"ok": True, "result": result})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TelegramApiError, match="lacks can_post_messages"):
            discover_channel_target(
                profile,
                token="test-token",
                expected_bot_id=8716602202,
                expected_bot_username="preaching_mp3_bot",
                client=client,
                now=datetime(2026, 8, 8, 0, 30, tzinfo=UTC),
            )


def test_discovery_rejects_member_identity_mismatch() -> None:
    profile = load_channel_profile(PROFILE_PATH)

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        if method == "getMe":
            result: object = {"id": 8716602202, "is_bot": True, "username": "preaching_mp3_bot"}
        elif method == "getChat":
            result = {
                "id": -1002233445566,
                "username": "deep_info_life",
                "title": "СВОДКА",
                "type": "channel",
            }
        elif method == "getChatMember":
            result = {
                "status": "administrator",
                "can_post_messages": True,
                "user": {"id": 9999999999, "is_bot": True, "username": "other_bot"},
            }
        else:
            raise AssertionError(method)
        return httpx.Response(200, json={"ok": True, "result": result})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TelegramApiError, match="membership resolved to a different user"):
            discover_channel_target(
                profile,
                token="test-token",
                expected_bot_id=8716602202,
                expected_bot_username="preaching_mp3_bot",
                client=client,
                now=datetime(2026, 8, 8, 0, 30, tzinfo=UTC),
            )
