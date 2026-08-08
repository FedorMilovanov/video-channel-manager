from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from video_channel_manager.svodka_queue import load_svodka_draft
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_models import CHANNEL_USERNAME, PROJECT_KEY
from video_channel_manager.telegram_multichannel_transport import (
    GenericTargetProof,
    preflight_channel,
    render_message_payload,
    render_poll_payload,
    send_poll_once,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"


def test_new_multichannel_profile_does_not_change_legacy_lordchrist_identity() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    assert profile.project_key == "svodka"
    assert profile.channel_username == "@deep_info_life"
    assert profile.publication_id_prefix == "svodka-"
    assert profile.daily_verified_limit == 2
    assert profile.provider_writes_authorized is False
    assert profile.digest.startswith("sha256:")

    assert PROJECT_KEY == "lord-god-strength"
    assert CHANNEL_USERNAME == "@lordchrist"


def test_svodka_draft_is_strictly_bound_to_profile_and_keeps_provider_writes_disabled() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    queue = load_svodka_draft(QUEUE_PATH, profile)
    assert len(queue.posts) == 14
    assert queue.provider_writes_authorized is False
    assert queue.review_state == "draft_review_required"
    assert [post.sequence for post in queue.posts] == list(range(1, 15))
    assert queue.posts[6].format == "quiz"
    assert queue.posts[6].quiz is not None
    assert queue.posts[12].format == "quiz"
    assert queue.posts[12].quiz is not None
    assert queue.digest.startswith("sha256:")


def test_message_preview_is_deterministic_and_bound_to_channel_profile() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    queue = load_svodka_draft(QUEUE_PATH, profile)
    first = queue.posts[0]
    left = render_message_payload(profile, publication_id=first.publication_id, html_text=first.html_text)
    right = render_message_payload(profile, publication_id=first.publication_id, html_text=first.html_text)
    assert left == right
    assert left.channel_username == "@deep_info_life"
    assert left.profile_sha256 == profile.digest
    assert "<b>" not in left.expected_plain_text
    assert left.provider_payload_sha256.startswith("sha256:")


def test_generic_preflight_resolves_svodka_exactly_without_lordchrist_hardcoding() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        calls.append(method)
        payload = json.loads(request.content.decode("utf-8")) if request.content else {}
        if method == "getMe":
            result: object = {"id": 42, "is_bot": True, "username": "svodka_test_bot"}
        elif method == "getChat":
            assert payload["chat_id"] in {-1001234567890, "@deep_info_life"}
            result = {
                "id": -1001234567890,
                "username": "deep_info_life",
                "title": "СВОДКА",
                "type": "channel",
            }
        elif method == "getChatAdministrators":
            assert payload == {"chat_id": -1001234567890, "return_bots": True}
            result = [
                {
                    "status": "administrator",
                    "can_post_messages": True,
                    "user": {"id": 42, "is_bot": True, "username": "svodka_test_bot"},
                }
            ]
        else:
            raise AssertionError(method)
        return httpx.Response(200, json={"ok": True, "result": result})

    now = datetime(2026, 8, 8, 0, 0, tzinfo=UTC)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        proof = preflight_channel(
            profile,
            token="test-token",
            expected_chat_id=-1001234567890,
            expected_bot_id=42,
            expected_bot_username="svodka_test_bot",
            client=client,
            now=now,
        )

    assert proof.project_key == "svodka"
    assert proof.channel_username == "@deep_info_life"
    assert proof.chat_username == "deep_info_life"
    assert proof.can_post_messages is True
    assert calls == ["getMe", "getChat", "getChat", "getChatAdministrators"]


def test_disabled_profile_blocks_poll_write_before_transport() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    now = datetime(2026, 8, 8, 0, 0, tzinfo=UTC)
    target = GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        bot_id=42,
        bot_username="svodka_test_bot",
        chat_id=-1001234567890,
        chat_username="deep_info_life",
        chat_title="СВОДКА",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=now,
    )
    payload = render_poll_payload(
        profile,
        publication_id="svodka-quiz-disabled-write",
        question="Тестовый вопрос?",
        options=("Да", "Нет"),
        poll_type="quiz",
        correct_option_ids=(0,),
        explanation="Тестовая проверка safety gate.",
    )

    with pytest.raises(ValueError, match="provider writes are not authorized"):
        send_poll_once(profile, target, payload, token="must-not-be-used", now=now)


def test_generic_transport_can_render_and_verify_quiz_poll_without_live_network() -> None:
    base_profile = load_channel_profile(PROFILE_PATH)
    profile = base_profile.model_copy(update={"provider_writes_authorized": True})
    now = datetime(2026, 8, 8, 0, 0, tzinfo=UTC)
    target = GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key="svodka",
        channel_username="@deep_info_life",
        profile_sha256=profile.digest,
        bot_id=42,
        bot_username="svodka_test_bot",
        chat_id=-1001234567890,
        chat_username="deep_info_life",
        chat_title="СВОДКА",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=now,
    )
    payload = render_poll_payload(
        profile,
        publication_id="svodka-quiz-test-poll",
        question="Что горячее поверхности Солнца?",
        options=("Канал молнии", "Лава", "Кипящая вода"),
        poll_type="quiz",
        correct_option_ids=(0,),
        explanation="NOAA: канал молнии может быть значительно горячее поверхности Солнца.",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        assert method == "sendPoll"
        body = json.loads(request.content.decode("utf-8"))
        assert body["chat_id"] == target.chat_id
        assert body["type"] == "quiz"
        assert body["correct_option_ids"] == [0]
        assert "correct_option_id" not in body
        result = {
            "message_id": 777,
            "chat": {"id": target.chat_id, "username": target.chat_username, "type": "channel"},
            "poll": {
                "id": "poll-id",
                "question": payload.question,
                "options": [{"text": option, "voter_count": 0} for option in payload.options],
                "total_voter_count": 0,
                "is_closed": False,
                "is_anonymous": True,
                "type": "quiz",
                "allows_multiple_answers": payload.allows_multiple_answers,
                "allows_revoting": payload.allows_revoting,
                "members_only": payload.members_only,
                "description": payload.description,
                "correct_option_ids": list(payload.correct_option_ids or ()),
                "explanation": payload.explanation,
            },
        }
        return httpx.Response(200, json={"ok": True, "result": result})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        receipt = send_poll_once(profile, target, payload, token="test-token", client=client, now=now)

    assert receipt.provider_effect == "verified"
    assert receipt.message_id == 777
    assert receipt.message_url == "https://t.me/deep_info_life/777"
