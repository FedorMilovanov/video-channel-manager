from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_transport import (
    MUTATION_TRANSPORT_RETRIES,
    READ_ONLY_TRANSPORT_RETRIES,
    GenericTargetProof,
    TelegramApiError,
    render_message_payload,
    render_poll_payload,
    send_message_once,
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


def _message_payload(profile):
    return render_message_payload(
        profile,
        publication_id="svodka-message-format-contract-test",
        html_text=(
            "- Сводка -\n\n"
            "⚡ <b>ТОЧНЫЙ ФАКТ</b>\n\n"
            "<i>Короткое пояснение.</i>\n\n"
            '📎 <a href="https://example.test/source">Первоисточник</a>\n\n'
            "#Сводка #Наука"
        ),
    )


def _url_free_message_payload(profile):
    return render_message_payload(
        profile,
        publication_id="svodka-message-no-url-contract-test",
        html_text=(
            "- Сводка -\n\n"
            "🧭 <b>ТОЧНЫЙ ТЕКСТ</b>\n\n"
            "<i>В сообщении нет ссылки, способной породить web preview.</i>\n\n"
            "#Сводка #Тест"
        ),
    )


def _telegram_result(
    payload,
    *,
    is_anonymous: bool = True,
    explanation: str | None = None,
    allows_revoting: bool | None = None,
    members_only: bool | None = None,
) -> dict[str, Any]:
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
                "allows_revoting": payload.allows_revoting if allows_revoting is None else allows_revoting,
                "members_only": payload.members_only if members_only is None else members_only,
                "correct_option_ids": list(payload.correct_option_ids or ()),
                "explanation": payload.explanation if explanation is None else explanation,
                "description": payload.description,
            },
        },
    }


def _message_result(
    payload,
    *,
    source_url: str | None = None,
    link_preview_disabled: bool = True,
    include_link_preview_options: bool = True,
) -> dict[str, Any]:
    entities = [entity.model_dump(mode="json", exclude_none=True) for entity in payload.expected_entities]
    if source_url is not None:
        for entity in entities:
            if entity["type"] == "text_link":
                entity["url"] = source_url
    entities.append({"type": "hashtag", "offset": 66, "length": 7})
    result: dict[str, Any] = {
        "message_id": 78,
        "chat": {
            "id": CHAT_ID,
            "username": "deep_info_life",
            "type": "channel",
        },
        "text": payload.expected_plain_text,
        "entities": entities,
    }
    if include_link_preview_options:
        result["link_preview_options"] = {"is_disabled": link_preview_disabled}
    return {"ok": True, "result": result}


def _client(body: dict[str, Any], captured: dict[str, Any] | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured["url"] = str(request.url)
            captured["json"] = __import__("json").loads(request.content.decode("utf-8"))
        return httpx.Response(200, json=body, request=request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_mutating_transport_never_retries_while_read_only_preflight_may_retry() -> None:
    assert MUTATION_TRANSPORT_RETRIES == 0
    assert READ_ONLY_TRANSPORT_RETRIES > 0


def test_send_message_once_verifies_exact_formatting_and_source_link_entities() -> None:
    profile = _profile()
    target = _target(profile)
    payload = _message_payload(profile)
    captured: dict[str, Any] = {}

    with _client(_message_result(payload), captured) as client:
        receipt = send_message_once(profile, target, payload, token="test-token", client=client, now=NOW)

    assert receipt.message_id == 78
    assert payload.schema_version == 2
    assert {entity.type for entity in payload.expected_entities} == {"bold", "italic", "text_link"}
    assert captured["json"]["text"] == payload.html_text
    assert captured["json"]["parse_mode"] == "HTML"
    assert captured["json"]["link_preview_options"] == {"is_disabled": True}


def test_send_message_once_accepts_omitted_link_preview_echo_for_url_free_message() -> None:
    profile = _profile()
    target = _target(profile)
    payload = _url_free_message_payload(profile)
    captured: dict[str, Any] = {}

    with _client(_message_result(payload, include_link_preview_options=False), captured) as client:
        receipt = send_message_once(profile, target, payload, token="test-token", client=client, now=NOW)

    assert receipt.message_id == 78
    assert receipt.provider_effect == "verified"
    assert captured["json"]["link_preview_options"] == {"is_disabled": True}


def test_send_message_once_rejects_omitted_link_preview_echo_for_url_bearing_message() -> None:
    profile = _profile()
    target = _target(profile)
    payload = _message_payload(profile)

    with _client(_message_result(payload, include_link_preview_options=False)) as client:
        with pytest.raises(TelegramApiError, match="omitted link-preview semantics") as exc_info:
            send_message_once(profile, target, payload, token="test-token", client=client, now=NOW)

    assert exc_info.value.provider_effect == "may_exist"


def test_send_message_once_rejects_returned_source_link_drift() -> None:
    profile = _profile()
    target = _target(profile)
    payload = _message_payload(profile)

    with _client(_message_result(payload, source_url="https://example.test/wrong")) as client:
        with pytest.raises(TelegramApiError, match="formatting or source-link") as exc_info:
            send_message_once(profile, target, payload, token="test-token", client=client, now=NOW)

    assert exc_info.value.provider_effect == "may_exist"


def test_send_message_once_rejects_returned_link_preview_drift() -> None:
    profile = _profile()
    target = _target(profile)
    payload = _message_payload(profile)

    with _client(_message_result(payload, link_preview_disabled=False)) as client:
        with pytest.raises(TelegramApiError, match="link-preview semantics") as exc_info:
            send_message_once(profile, target, payload, token="test-token", client=client, now=NOW)

    assert exc_info.value.provider_effect == "may_exist"


def test_send_poll_once_accepts_exact_quiz_and_uses_current_bot_api_fields() -> None:
    profile = _profile()
    target = _target(profile)
    payload = _payload(profile)
    captured: dict[str, Any] = {}

    with _client(_telegram_result(payload), captured) as client:
        receipt = send_poll_once(profile, target, payload, token="test-token", client=client, now=NOW)

    assert receipt.message_id == 77
    assert receipt.chat_id == CHAT_ID
    assert payload.schema_version == 4
    assert captured["json"]["correct_option_ids"] == [0]
    assert captured["json"]["is_anonymous"] is True
    assert captured["json"]["allows_multiple_answers"] is False
    assert captured["json"]["allows_revoting"] is False
    assert captured["json"]["members_only"] is False
    assert captured["json"]["explanation"] == payload.explanation
    assert captured["json"]["description"] == payload.description


def test_regular_poll_freezes_current_revoting_default_explicitly() -> None:
    profile = _profile()
    payload = render_poll_payload(
        profile,
        publication_id="svodka-regular-poll-contract-test",
        question="Какой вариант выбрать?",
        options=("Первый", "Второй"),
        poll_type="regular",
    )

    assert payload.allows_revoting is True
    assert payload.members_only is False


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


def test_send_poll_once_rejects_returned_revoting_drift() -> None:
    profile = _profile()
    target = _target(profile)
    payload = _payload(profile)

    with _client(_telegram_result(payload, allows_revoting=True)) as client:
        with pytest.raises(TelegramApiError, match="revoting") as exc_info:
            send_poll_once(profile, target, payload, token="test-token", client=client, now=NOW)

    assert exc_info.value.provider_effect == "may_exist"


def test_send_poll_once_rejects_returned_membership_drift() -> None:
    profile = _profile()
    target = _target(profile)
    payload = _payload(profile)

    with _client(_telegram_result(payload, members_only=True)) as client:
        with pytest.raises(TelegramApiError, match="membership") as exc_info:
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
