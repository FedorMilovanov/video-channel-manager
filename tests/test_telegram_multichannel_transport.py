from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_transport import (
    GenericTargetProof,
    TelegramApiError,
    render_poll_payload,
    send_poll_once,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
CHAT_ID = -1003527567039
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"
NOW = datetime(2026, 8, 8, 1, 0, tzinfo=UTC)


def _profile():
    return load_channel_profile(PROFILE_PATH).model_copy(update={"provider_writes_authorized": True})


def _target(profile) -> GenericTargetProof:
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
        checked_at_utc=NOW,
    )


def _payload(profile):
    return render_poll_payload(
        profile,
        publication_id="svodka-transport-contract-test",
        question="Какой вариант верный?",
        options=("Первый", "Второй"),
        poll_type="quiz",
        correct_option_ids=(0,),
        explanation="Верный ответ — первый вариант.",
        description="- Сводка -\n\n📎 https://example.test/source\n\n#Сводка #Тест",
        is_anonymous=True,
    )


def _telegram_result(payload, *, is_anonymous: bool = True, explanation: str | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "result": {
            "message_id": 77,
            "chat": {
                "id": CHAT_ID,
                "username": "deep_info_life",
                "type": "channel",
            },
            "poll": {
                "id": "poll-contract-test",
                "question": payload.question,
                "options": [{"text": option, "voter_count": 0} for option in payload.options],
                "type": payload.poll_type,
                "is_anonymous": is_anonymous,
                "allows_multiple_answers": payload.allows_multiple_answers,
                "correct_option_ids": list(payload.correct_option_ids or ()),
                "explanation": payload.explanation if explanation is None else explanation,
                "description": payload.description,
            },
        },
    }


def _client(body: dict[str, Any], captured: dict[str, Any] | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured["url"] = str(request.url)
            captured["json"] = __import__("json").loads(request.content.decode("utf-8"))
        return httpx.Response(200, json=body, request=request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_send_poll_once_accepts_exact_quiz_and_uses_current_bot_api_fields() -> None:
    profile = _profile()
    target = _target(profile)
    payload = _payload(profile)
    captured: dict[str, Any] = {}

    with _client(_telegram_result(payload), captured) as client:
        receipt = send_poll_once(profile, target, payload, token="test-token", client=client, now=NOW)

    assert receipt.message_id == 77
    assert receipt.chat_id == CHAT_ID
    assert captured["json"]["correct_option_ids"] == [0]
    assert captured["json"]["is_anonymous"] is True
    assert captured["json"]["allows_multiple_answers"] is False
    assert captured["json"]["explanation"] == payload.explanation
    assert captured["json"]["description"] == payload.description


def test_multiple_correct_quiz_requires_multiple_answer_semantics() -> None:
    profile = _profile()

    with pytest.raises(ValueError, match="must allow multiple answers"):
        render_poll_payload(
            profile,
            publication_id="svodka-multi-answer-contract-test",
            question="Выберите правильные варианты",
            options=("Первый", "Второй", "Третий"),
            poll_type="quiz",
            correct_option_ids=(0, 1),
        )

    payload = render_poll_payload(
        profile,
        publication_id="svodka-multi-answer-contract-test",
        question="Выберите правильные варианты",
        options=("Первый", "Второй", "Третий"),
        poll_type="quiz",
        correct_option_ids=(0, 1),
        allows_multiple_answers=True,
    )
    assert payload.allows_multiple_answers is True


def test_send_poll_once_rejects_returned_anonymity_drift() -> None:
    profile = _profile()
    target = _target(profile)
    payload = _payload(profile)

    with _client(_telegram_result(payload, is_anonymous=False)) as client:
        with pytest.raises(TelegramApiError, match="anonymity") as exc_info:
            send_poll_once(profile, target, payload, token="test-token", client=client, now=NOW)

    assert exc_info.value.provider_effect == "may_exist"


def test_send_poll_once_rejects_returned_quiz_explanation_drift() -> None:
    profile = _profile()
    target = _target(profile)
    payload = _payload(profile)

    with _client(_telegram_result(payload, explanation="Подменённое объяснение")) as client:
        with pytest.raises(TelegramApiError, match="explanation") as exc_info:
            send_poll_once(profile, target, payload, token="test-token", client=client, now=NOW)

    assert exc_info.value.provider_effect == "may_exist"
