from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from video_channel_manager.telegram_multichannel_transport import GenericMessagePayload, GenericTargetProof
from video_channel_manager.telegram_rich_provider import (
    RICH_MUTATION_TRANSPORT_RETRIES,
    ArchivedTelegramRichOutcome,
    HttpxTelegramRichMutationProvider,
    TelegramRichMessageDocument,
    TelegramRichOutcomeArchiveReceipt,
    TelegramRichProviderResponse,
    TelegramRichProviderTimeout,
    TelegramRichRequestTimeout,
    TelegramRichTargetBinding,
    publish_rich_once,
)

NOW = datetime(2026, 8, 10, 20, 0, tzinfo=UTC)
CHAT_ID = -1003527567039
BOT_ID = 8716602202
PROFILE_SHA256 = "sha256:" + "1" * 64
BINDING_SHA256 = "sha256:" + "2" * 64
_FALLBACK_DIGEST_INPUT = {
    "kind": "message",
    "project_key": "svodka",
    "channel_username": "@deep_info_life",
    "publication_id": "svodka-rich-provider-contract",
    "profile_sha256": PROFILE_SHA256,
    "html_text": "Сводка",
    "expected_plain_text": "Сводка",
    "expected_entities": [],
    "parse_mode": "HTML",
    "link_preview_disabled": True,
}
PAYLOAD_SHA256 = (
    "sha256:"
    + hashlib.sha256(
        json.dumps(_FALLBACK_DIGEST_INPUT, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
)


class FakeProvider:
    def __init__(self, result: TelegramRichProviderResponse | Exception) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def send_rich_message(
        self,
        *,
        chat_id: int,
        rich_message: dict[str, Any],
        timeout: TelegramRichRequestTimeout,
    ) -> TelegramRichProviderResponse:
        self.calls.append({"chat_id": chat_id, "rich_message": rich_message, "timeout": timeout})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeArchiver:
    def __init__(self, events: list[str] | None = None, *, wrong_digest: bool = False) -> None:
        self.events = events
        self.wrong_digest = wrong_digest
        self.archived: list[bytes] = []

    def archive(
        self,
        outcome_bytes: bytes,
        *,
        outcome_sha256: str,
    ) -> TelegramRichOutcomeArchiveReceipt:
        if self.events is not None:
            self.events.append("archive")
        self.archived.append(outcome_bytes)
        return TelegramRichOutcomeArchiveReceipt(
            schema_name="video-channel-manager.telegram-rich-outcome-archive-receipt",
            schema_version=1,
            outcome_sha256=("sha256:" + "f" * 64) if self.wrong_digest else outcome_sha256,
            archive_reference="fake://durable/provider-outcome.json",
            durable_before_state_mutation=True,
        )


def _binding() -> TelegramRichTargetBinding:
    return TelegramRichTargetBinding(
        schema_name="video-channel-manager.telegram-rich-target-binding",
        schema_version=1,
        project_key="svodka",
        channel_username="@deep_info_life",
        profile_sha256=PROFILE_SHA256,
        target_binding_sha256=BINDING_SHA256,
        chat_id=CHAT_ID,
        chat_username="deep_info_life",
        bot_id=BOT_ID,
        bot_username="preaching_mp3_bot",
    )


def _target(*, chat_id: int = CHAT_ID, bot_id: int = BOT_ID) -> GenericTargetProof:
    return GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key="svodka",
        channel_username="@deep_info_life",
        profile_sha256=PROFILE_SHA256,
        bot_id=bot_id,
        bot_username="preaching_mp3_bot",
        chat_id=chat_id,
        chat_username="deep_info_life",
        chat_title="СВОДКА",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=NOW,
    )


def _fallback() -> GenericMessagePayload:
    return GenericMessagePayload(
        schema_name="video-channel-manager.telegram-generic-message-payload",
        schema_version=2,
        project_key="svodka",
        channel_username="@deep_info_life",
        publication_id="svodka-rich-provider-contract",
        profile_sha256=PROFILE_SHA256,
        provider_payload_sha256=PAYLOAD_SHA256,
        html_text="Сводка",
        expected_plain_text="Сводка",
        expected_entities=(),
        parse_mode="HTML",
        link_preview_disabled=True,
    )


def _input_rich_message() -> dict[str, Any]:
    return {
        "blocks": [
            {"type": "heading", "text": "Сводка", "size": 2},
            {
                "type": "photo",
                "photo": {"type": "photo", "media": "telegram-file-id"},
                "caption": {"text": "Проверенное изображение"},
            },
            {"type": "paragraph", "text": [{"type": "bold", "text": "Точный факт"}, "."]},
        ],
        "skip_entity_detection": True,
    }


def _returned_rich_message(*, media_unique_id: str = "stable-photo-unique-id") -> dict[str, Any]:
    return {
        "blocks": [
            {"type": "heading", "text": "Сводка", "size": 2},
            {
                "type": "photo",
                "photo": [
                    {
                        "file_id": "returned-photo-file-id",
                        "file_unique_id": media_unique_id,
                        "width": 1280,
                        "height": 720,
                        "file_size": 123456,
                    }
                ],
                "caption": {"text": "Проверенное изображение"},
            },
            {"type": "paragraph", "text": [{"type": "bold", "text": "Точный факт"}, "."]},
        ]
    }


def _document() -> TelegramRichMessageDocument:
    return TelegramRichMessageDocument(
        schema_name="video-channel-manager.telegram-rich-message-document",
        schema_version=1,
        publication_id="svodka-rich-provider-contract",
        target=_binding(),
        input_rich_message=_input_rich_message(),
        expected_returned_rich_message=_returned_rich_message(),
        legacy_fallback=_fallback(),
    )


def _telegram_response(
    *,
    rich_message: Any = None,
    chat_id: int = CHAT_ID,
    chat_username: str = "deep_info_life",
    message_id: Any = 901,
) -> TelegramRichProviderResponse:
    result: dict[str, Any] = {
        "message_id": message_id,
        "chat": {"id": chat_id, "username": chat_username, "type": "channel"},
        "rich_message": _returned_rich_message() if rich_message is None else rich_message,
    }
    return TelegramRichProviderResponse(status_code=200, body={"ok": True, "result": result})


def _publish(provider: FakeProvider, *, archiver: FakeArchiver | None = None) -> ArchivedTelegramRichOutcome:
    return publish_rich_once(
        _document(),
        _target(),
        provider,
        archiver or FakeArchiver(),
        now=NOW,
    )


def test_success_requires_exact_chat_message_id_structure_and_media_and_archives_before_state() -> None:
    events: list[str] = []
    provider = FakeProvider(_telegram_response())
    archiver = FakeArchiver(events)

    def mutate_state(archived: ArchivedTelegramRichOutcome) -> None:
        assert archived.outcome.provider_effect == "verified"
        events.append("state")

    archived = publish_rich_once(
        _document(),
        _target(),
        provider,
        archiver,
        state_mutation=mutate_state,
        now=NOW,
    )

    outcome = archived.outcome
    assert outcome.provider_effect == "verified"
    assert outcome.message_id == 901
    assert outcome.message_url == "https://t.me/deep_info_life/901"
    assert outcome.returned_chat_verified is True
    assert outcome.structure_verification == "exact"
    assert outcome.media_verification == "exact"
    assert outcome.returned_rich_structure_sha256 == outcome.expected_rich_structure_sha256
    assert outcome.returned_media_sha256 == outcome.expected_media_sha256
    assert outcome.automatic_retry_allowed is False
    assert events == ["archive", "state"]
    assert len(provider.calls) == 1
    assert provider.calls[0]["chat_id"] == CHAT_ID
    assert provider.calls[0]["rich_message"] == _input_rich_message()
    assert isinstance(provider.calls[0]["timeout"], TelegramRichRequestTimeout)
    assert archiver.archived == [outcome.archive_bytes]


def test_timeout_before_request_is_not_dispatched_and_never_retried() -> None:
    provider = FakeProvider(TelegramRichProviderTimeout(request_may_have_been_dispatched=False))

    outcome = _publish(provider).outcome

    assert outcome.provider_effect == "not_dispatched"
    assert outcome.dispatch_phase == "before_request"
    assert outcome.provider_call_count == 1
    assert outcome.mutation_request_count == 0
    assert outcome.automatic_retry_allowed is False
    assert len(provider.calls) == 1


def test_timeout_after_possible_mutation_is_may_exist_and_never_retried_or_fallen_back() -> None:
    document = _document()
    assert document.legacy_fallback is not None
    assert document.legacy_fallback.provider_payload_sha256 == PAYLOAD_SHA256
    provider = FakeProvider(TelegramRichProviderTimeout(request_may_have_been_dispatched=True))

    outcome = _publish(provider).outcome

    assert outcome.provider_effect == "may_exist"
    assert outcome.dispatch_phase == "request_may_have_been_dispatched"
    assert outcome.mutation_request_count == 1
    assert outcome.message_id is None
    assert outcome.automatic_retry_allowed is False
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    ("body", "expected_error"),
    [
        ({"ok": True, "result": "not-a-message"}, "result is missing or malformed"),
        (["not", "an", "object"], "malformed non-object response"),
        ({"ok": True}, "result is missing or malformed"),
    ],
)
def test_malformed_result_is_may_exist(body: Any, expected_error: str) -> None:
    provider = FakeProvider(TelegramRichProviderResponse(status_code=200, body=body))

    outcome = _publish(provider).outcome

    assert outcome.provider_effect == "may_exist"
    assert expected_error in (outcome.error or "")
    assert outcome.message_id is None
    assert len(provider.calls) == 1


def test_wrong_chat_is_may_exist_even_when_structure_and_message_id_are_observed() -> None:
    provider = FakeProvider(_telegram_response(chat_id=-1009999999999, chat_username="wrong_channel"))

    outcome = _publish(provider).outcome

    assert outcome.provider_effect == "may_exist"
    assert outcome.returned_chat_verified is False
    assert outcome.observed_message_id == 901
    assert outcome.message_id is None
    assert outcome.structure_verification == "exact"
    assert outcome.media_verification == "exact"


@pytest.mark.parametrize("message_id", [None, 0, -1, True, "901", "not-an-id"])
def test_missing_or_invalid_message_id_is_may_exist(message_id: Any) -> None:
    provider = FakeProvider(_telegram_response(message_id=message_id))

    outcome = _publish(provider).outcome

    assert outcome.provider_effect == "may_exist"
    assert outcome.observed_message_id is None
    assert outcome.message_id is None
    assert "message_id" in (outcome.error or "")


def test_rich_structure_mismatch_is_may_exist_and_preserves_returned_digest() -> None:
    returned = _returned_rich_message()
    returned["blocks"][0]["text"] = "Подменённая сводка"
    provider = FakeProvider(_telegram_response(rich_message=returned))

    outcome = _publish(provider).outcome

    assert outcome.provider_effect == "may_exist"
    assert outcome.structure_verification == "mismatch"
    assert outcome.media_verification == "exact"
    assert outcome.returned_rich_structure_sha256 is not None
    assert outcome.returned_rich_structure_sha256 != outcome.expected_rich_structure_sha256
    assert outcome.message_id is None


def test_media_mismatch_is_may_exist_and_never_claims_semantic_verification() -> None:
    provider = FakeProvider(
        _telegram_response(rich_message=_returned_rich_message(media_unique_id="different-media-identity"))
    )

    outcome = _publish(provider).outcome

    assert outcome.provider_effect == "may_exist"
    assert outcome.structure_verification == "mismatch"
    assert outcome.media_verification == "mismatch"
    assert outcome.returned_media_sha256 is not None
    assert outcome.returned_media_sha256 != outcome.expected_media_sha256
    assert "media" in (outcome.error or "")
    assert outcome.message_id is None


def test_missing_or_partial_rich_structure_is_never_verified() -> None:
    missing = FakeProvider(_telegram_response(rich_message={"not_blocks": []}))

    outcome = _publish(missing).outcome

    assert outcome.provider_effect == "may_exist"
    assert outcome.structure_verification == "malformed"
    assert outcome.message_id is None
    assert "complete exact rich structure" in (outcome.error or "")


@pytest.mark.parametrize(
    ("status_code", "body", "effect"),
    [
        (400, {"ok": False, "error_code": 400, "description": "Bad Request"}, "confirmed_absent"),
        (429, {"ok": False, "error_code": 429, "description": "Too Many Requests"}, "confirmed_absent"),
        (500, {"ok": False, "error_code": 500, "description": "Internal Server Error"}, "may_exist"),
        (502, None, "may_exist"),
    ],
)
def test_http_errors_are_classified_without_retry(status_code: int, body: Any, effect: str) -> None:
    provider = FakeProvider(TelegramRichProviderResponse(status_code=status_code, body=body))

    outcome = _publish(provider).outcome

    assert outcome.provider_effect == effect
    assert outcome.http_status_code == status_code
    assert outcome.automatic_retry_allowed is False
    assert len(provider.calls) == 1


def test_exact_bot_and_target_binding_failure_is_impossible_without_provider_call() -> None:
    provider = FakeProvider(_telegram_response())

    archived = publish_rich_once(_document(), _target(bot_id=BOT_ID + 1), provider, FakeArchiver(), now=NOW)

    assert archived.outcome.provider_effect == "impossible"
    assert archived.outcome.bot_identity_verification == "mismatch"
    assert archived.outcome.provider_call_count == 0
    assert archived.outcome.mutation_request_count == 0
    assert provider.calls == []


def test_archive_digest_failure_blocks_state_mutation() -> None:
    events: list[str] = []
    provider = FakeProvider(_telegram_response())
    archiver = FakeArchiver(events, wrong_digest=True)

    with pytest.raises(ValueError, match="archive receipt digest"):
        publish_rich_once(
            _document(),
            _target(),
            provider,
            archiver,
            state_mutation=lambda _: events.append("state"),
            now=NOW,
        )

    assert events == ["archive"]
    assert len(provider.calls) == 1


def test_httpx_provider_uses_exact_official_method_and_one_post() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {}}, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with HttpxTelegramRichMutationProvider(
            token="not-a-live-token",
            api_base="https://api.telegram.test",
            http_client=client,
        ) as provider:
            response = provider.send_rich_message(
                chat_id=CHAT_ID,
                rich_message=_input_rich_message(),
                timeout=TelegramRichRequestTimeout(),
            )

    assert response.status_code == 200
    assert len(requests) == 1
    assert requests[0].url.path == "/botnot-a-live-token/sendRichMessage"
    assert json.loads(requests[0].content) == {
        "chat_id": CHAT_ID,
        "rich_message": _input_rich_message(),
    }


def test_mutating_rich_transport_has_zero_retries_and_explicit_request_timeouts() -> None:
    assert RICH_MUTATION_TRANSPORT_RETRIES == 0
    timeout = TelegramRichRequestTimeout()
    assert timeout.connect_seconds == 15
    assert timeout.read_seconds == 45
    assert timeout.write_seconds == 30
    assert timeout.pool_seconds == 15
