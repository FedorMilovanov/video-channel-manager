from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_transport import render_message_payload
from video_channel_manager.telegram_research_update_probe import probe_research_channel_post

ROOT = Path(__file__).parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/lordchrist.json"
CHAT_ID = -1001295216957
USERNAME = "lordchrist"
ATTEMPTED = datetime(2026, 8, 10, 12, 58, 6, tzinfo=UTC)
ARTIFACT_SHA = "sha256:" + "a" * 64


def _payload():
    profile = load_channel_profile(PROFILE_PATH)
    return render_message_payload(
        profile,
        publication_id="lordchrist-research-recovery-probe-test",
        html_text=(
            "<b>📖 Не рекорд, а мера труда</b>\n\n"
            "Точный исследовательский текст без URL.\n\n"
            "✦ Благодарим Бога за верный труд."
        ),
    )


def _channel_post(payload, *, update_id: int = 800, message_id: int = 1700, seconds_after: int = 3) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "channel_post": {
            "message_id": message_id,
            "date": int(ATTEMPTED.timestamp()) + seconds_after,
            "chat": {"id": CHAT_ID, "username": USERNAME, "type": "channel"},
            "text": payload.expected_plain_text,
            "entities": [entity.model_dump(mode="json", exclude_none=True) for entity in payload.expected_entities],
        },
    }


def _probe_with_client(client: httpx.Client):
    return probe_research_channel_post(
        payload=_payload(),
        expected_chat_id=CHAT_ID,
        expected_chat_username=USERNAME,
        attempted_at_utc=ATTEMPTED,
        match_window_seconds=180,
        token="test-token",
        historical_run_id="31390497205",
        historical_run_attempt="1",
        historical_outcome_artifact_sha256=ARTIFACT_SHA,
        github_sha="b" * 40,
        api_base="https://telegram.test",
        client=client,
    )


def test_probe_stops_at_configured_webhook_without_get_updates() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        calls.append((request.url.path, body))
        return httpx.Response(200, json={"ok": True, "result": {"url": "https://example.test/hook"}}, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _probe_with_client(client)

    assert result.status == "webhook_configured"
    assert result.get_updates_called is False
    assert result.provider_write_performed is False
    assert len(calls) == 1
    assert calls[0][0].endswith("/getWebhookInfo")
    assert calls[0][1] == {}


def test_probe_finds_exact_channel_post_without_sending_offset_or_allowed_updates() -> None:
    payload = _payload()
    calls: list[tuple[str, dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        calls.append((request.url.path, body))
        if request.url.path.endswith("/getWebhookInfo"):
            result: Any = {"url": ""}
        else:
            result = [_channel_post(payload)]
        return httpx.Response(200, json={"ok": True, "result": result}, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _probe_with_client(client)

    assert result.status == "found"
    assert result.message_id == 1700
    assert result.message_url == "https://t.me/lordchrist/1700"
    assert result.matching_update_ids == (800,)
    assert result.updates_confirmed is False
    assert result.webhook_changed is False
    assert result.provider_write_performed is False
    assert len(calls) == 2
    get_updates_body = calls[1][1]
    assert calls[1][0].endswith("/getUpdates")
    assert get_updates_body == {"limit": 100, "timeout": 0}
    assert "offset" not in get_updates_body
    assert "allowed_updates" not in get_updates_body


def test_probe_rejects_text_or_time_drift_as_not_found() -> None:
    payload = _payload()
    wrong = _channel_post(payload, seconds_after=600)
    wrong["channel_post"]["text"] = payload.expected_plain_text + " drift"

    def handler(request: httpx.Request) -> httpx.Response:
        result: Any = {"url": ""} if request.url.path.endswith("/getWebhookInfo") else [wrong]
        return httpx.Response(200, json={"ok": True, "result": result}, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _probe_with_client(client)

    assert result.status == "not_found"
    assert result.message_id is None
    assert result.examined_updates == 1


def test_probe_fails_closed_when_more_than_one_exact_match_exists() -> None:
    payload = _payload()
    updates = [
        _channel_post(payload, update_id=800, message_id=1700, seconds_after=3),
        _channel_post(payload, update_id=801, message_id=1701, seconds_after=4),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        result: Any = {"url": ""} if request.url.path.endswith("/getWebhookInfo") else updates
        return httpx.Response(200, json={"ok": True, "result": result}, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _probe_with_client(client)

    assert result.status == "ambiguous"
    assert result.message_id is None
    assert result.matching_update_ids == (800, 801)
