from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_transport import (
    GenericTargetProof,
    render_message_payload,
    render_poll_payload,
    send_message_once,
    send_poll_once,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/svodka.json"
CHAT_ID = -1003527567039
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"


def _profile():
    return load_channel_profile(PROFILE_PATH).model_copy(update={"provider_writes_authorized": True})


def _fresh_target(profile) -> GenericTargetProof:
    return GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        bot_id=BOT_ID,
        bot_username=BOT_USERNAME,
        chat_id=CHAT_ID,
        chat_username="deep_info_life",
        chat_title="СВОДКА",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=datetime.now(tz=UTC),
    )


def _timed_client(body: dict[str, Any], observed: dict[str, datetime]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        observed["provider_response_at"] = datetime.now(tz=UTC)
        return httpx.Response(200, json=body, request=request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_message_receipt_verification_time_is_not_before_provider_response() -> None:
    profile = _profile()
    target = _fresh_target(profile)
    payload = render_message_payload(
        profile,
        publication_id="svodka-receipt-time-message-test",
        html_text="<b>Тест</b>",
    )
    body: dict[str, Any] = {
        "ok": True,
        "result": {
            "message_id": 9001,
            "chat": {"id": CHAT_ID, "username": "deep_info_life", "type": "channel"},
            "text": payload.expected_plain_text,
            "entities": [entity.model_dump(mode="json", exclude_none=True) for entity in payload.expected_entities],
            "link_preview_options": {"is_disabled": True},
        },
    }
    observed: dict[str, datetime] = {}

    with _timed_client(body, observed) as client:
        receipt = send_message_once(profile, target, payload, token="test-token", client=client)

    assert receipt.verified_at_utc >= observed["provider_response_at"]


def test_poll_receipt_verification_time_is_not_before_provider_response() -> None:
    profile = _profile()
    target = _fresh_target(profile)
    payload = render_poll_payload(
        profile,
        publication_id="svodka-receipt-time-poll-test",
        question="Выберите вариант",
        options=("Первый", "Второй"),
        poll_type="regular",
    )
    body: dict[str, Any] = {
        "ok": True,
        "result": {
            "message_id": 9002,
            "chat": {"id": CHAT_ID, "username": "deep_info_life", "type": "channel"},
            "poll": {
                "id": "poll-receipt-time-test",
                "question": payload.question,
                "options": [{"text": option, "voter_count": 0} for option in payload.options],
                "type": payload.poll_type,
                "is_anonymous": payload.is_anonymous,
                "allows_multiple_answers": payload.allows_multiple_answers,
                "allows_revoting": payload.allows_revoting,
                "members_only": payload.members_only,
                "description": "",
            },
        },
    }
    observed: dict[str, datetime] = {}

    with _timed_client(body, observed) as client:
        receipt = send_poll_once(profile, target, payload, token="test-token", client=client)

    assert receipt.verified_at_utc >= observed["provider_response_at"]
