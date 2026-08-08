from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile
from video_channel_manager.telegram_html_entities import (
    GenericMessageEntity,
    message_entities_match,
    parse_telegram_html,
)
from video_channel_manager.telegram_models import DEFAULT_API_BASE, ProviderEffect
from video_channel_manager.telegram_transport import TelegramApiError, _api_call, _result_dict, _result_list

READ_ONLY_TRANSPORT_RETRIES = 2
MUTATION_TRANSPORT_RETRIES = 0


class GenericTargetProof(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-generic-target-proof"]
    schema_version: Literal[1]
    project_key: str
    channel_username: str
    profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    bot_id: int = Field(gt=0)
    bot_username: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_]+$")
    chat_id: int = Field(lt=0)
    chat_username: str = Field(min_length=5, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    chat_title: str = Field(min_length=1, max_length=255)
    chat_type: Literal["channel"]
    member_status: Literal["administrator", "creator"]
    can_post_messages: Literal[True]
    checked_at_utc: datetime

    @model_validator(mode="after")
    def timestamp_is_aware(self) -> "GenericTargetProof":
        if self.checked_at_utc.tzinfo is None:
            raise ValueError("target proof timestamp must be timezone-aware")
        return self


class GenericMessagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-generic-message-payload"]
    schema_version: Literal[2]
    project_key: str
    channel_username: str
    publication_id: str
    profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    provider_payload_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    html_text: str = Field(min_length=1, max_length=8192)
    expected_plain_text: str = Field(min_length=1, max_length=4096)
    expected_entities: tuple[GenericMessageEntity, ...]
    parse_mode: Literal["HTML"] = "HTML"
    link_preview_disabled: Literal[True] = True


class GenericPollPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-generic-poll-payload"]
    schema_version: Literal[4]
    project_key: str
    channel_username: str
    publication_id: str
    profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    provider_payload_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    question: str = Field(min_length=1, max_length=300)
    options: tuple[str, ...] = Field(min_length=2, max_length=12)
    poll_type: Literal["regular", "quiz"]
    correct_option_ids: tuple[int, ...] | None = None
    explanation: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1024)
    is_anonymous: bool = True
    allows_multiple_answers: bool = False
    allows_revoting: bool
    members_only: bool

    @model_validator(mode="after")
    def validate_quiz_fields(self) -> "GenericPollPayload":
        if any(not option.strip() or len(option) > 100 for option in self.options):
            raise ValueError("poll options must contain 1..100 visible characters")
        if self.poll_type == "quiz":
            if not self.correct_option_ids:
                raise ValueError("quiz requires at least one correct option id")
            if tuple(sorted(set(self.correct_option_ids))) != self.correct_option_ids:
                raise ValueError("quiz correct_option_ids must be unique and monotonically increasing")
            if any(index < 0 or index >= len(self.options) for index in self.correct_option_ids):
                raise ValueError("quiz correct option id is outside the options list")
            if len(self.correct_option_ids) > 1 and not self.allows_multiple_answers:
                raise ValueError("quiz with multiple correct answers must allow multiple answers")
        elif self.correct_option_ids is not None or self.explanation is not None:
            raise ValueError("regular poll must not include quiz-only fields")
        return self


class GenericSendReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-generic-send-receipt"]
    schema_version: Literal[1]
    project_key: str
    publication_id: str
    provider_payload_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    chat_id: int = Field(lt=0)
    chat_username: str
    message_id: int = Field(gt=0)
    message_url: str
    verified_at_utc: datetime
    provider_effect: Literal["verified"] = "verified"


def _sha256_payload(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_publication_id(profile: TelegramChannelProfile, publication_id: str) -> None:
    if not publication_id.startswith(profile.publication_id_prefix):
        raise ValueError(f"publication_id must start with {profile.publication_id_prefix!r}")
    if len(publication_id) > 96:
        raise ValueError("publication_id is too long")


def _require_provider_write_authorized(profile: TelegramChannelProfile) -> None:
    if not profile.provider_writes_authorized:
        raise ValueError("provider writes are not authorized by the selected Telegram channel profile")


def render_message_payload(
    profile: TelegramChannelProfile,
    *,
    publication_id: str,
    html_text: str,
) -> GenericMessagePayload:
    _validate_publication_id(profile, publication_id)
    expected_plain_text, expected_entities = parse_telegram_html(html_text)
    if len(expected_plain_text) > 4096:
        raise ValueError("Telegram message exceeds 4096 plain-text characters")
    digest_input: dict[str, Any] = {
        "kind": "message",
        "project_key": profile.project_key,
        "channel_username": profile.channel_username,
        "publication_id": publication_id,
        "profile_sha256": profile.digest,
        "html_text": html_text,
        "expected_plain_text": expected_plain_text,
        "expected_entities": [entity.model_dump(mode="json") for entity in expected_entities],
        "parse_mode": "HTML",
        "link_preview_disabled": True,
    }
    return GenericMessagePayload(
        schema_name="video-channel-manager.telegram-generic-message-payload",
        schema_version=2,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        publication_id=publication_id,
        profile_sha256=profile.digest,
        provider_payload_sha256=_sha256_payload(digest_input),
        html_text=html_text,
        expected_plain_text=expected_plain_text,
        expected_entities=expected_entities,
    )


def render_poll_payload(
    profile: TelegramChannelProfile,
    *,
    publication_id: str,
    question: str,
    options: tuple[str, ...],
    poll_type: Literal["regular", "quiz"],
    correct_option_ids: tuple[int, ...] | None = None,
    explanation: str | None = None,
    description: str | None = None,
    is_anonymous: bool = True,
    allows_multiple_answers: bool = False,
    allows_revoting: bool | None = None,
    members_only: bool = False,
) -> GenericPollPayload:
    _validate_publication_id(profile, publication_id)
    effective_allows_revoting = poll_type == "regular" if allows_revoting is None else allows_revoting
    digest_input: dict[str, Any] = {
        "kind": "poll",
        "project_key": profile.project_key,
        "channel_username": profile.channel_username,
        "publication_id": publication_id,
        "profile_sha256": profile.digest,
        "question": question,
        "options": list(options),
        "poll_type": poll_type,
        "correct_option_ids": list(correct_option_ids) if correct_option_ids is not None else None,
        "explanation": explanation,
        "description": description,
        "is_anonymous": is_anonymous,
        "allows_multiple_answers": allows_multiple_answers,
        "allows_revoting": effective_allows_revoting,
        "members_only": members_only,
    }
    return GenericPollPayload(
        schema_name="video-channel-manager.telegram-generic-poll-payload",
        schema_version=4,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        publication_id=publication_id,
        profile_sha256=profile.digest,
        provider_payload_sha256=_sha256_payload(digest_input),
        question=question,
        options=options,
        poll_type=poll_type,
        correct_option_ids=correct_option_ids,
        explanation=explanation,
        description=description,
        is_anonymous=is_anonymous,
        allows_multiple_answers=allows_multiple_answers,
        allows_revoting=effective_allows_revoting,
        members_only=members_only,
    )


def _validate_channel_record(
    chat: dict[str, Any],
    *,
    profile: TelegramChannelProfile,
    expected_chat_id: int,
) -> tuple[int, str, Literal["channel"]]:
    try:
        actual_chat_id = int(chat["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TelegramApiError("Telegram channel has no valid numeric id", provider_effect="not_dispatched") from exc
    actual_username = str(chat.get("username") or "")
    actual_type = str(chat.get("type") or "")
    if actual_chat_id != expected_chat_id:
        raise TelegramApiError(
            "resolved Telegram channel id does not match configured target", provider_effect="not_dispatched"
        )
    if actual_username.casefold() != profile.bare_username.casefold():
        raise TelegramApiError(
            "resolved Telegram channel username does not match configured target", provider_effect="not_dispatched"
        )
    if actual_type != "channel":
        raise TelegramApiError("resolved Telegram target is not a channel", provider_effect="not_dispatched")
    return actual_chat_id, actual_username, "channel"


def preflight_channel(
    profile: TelegramChannelProfile,
    *,
    token: str,
    expected_chat_id: int,
    expected_bot_id: int,
    expected_bot_username: str,
    api_base: str = DEFAULT_API_BASE,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> GenericTargetProof:
    own_client = client is None
    http_client = client or httpx.Client(
        timeout=httpx.Timeout(connect=15, read=30, write=30, pool=15),
        transport=httpx.HTTPTransport(retries=READ_ONLY_TRANSPORT_RETRIES),
        trust_env=False,
    )
    try:
        me = _result_dict(
            _api_call(http_client, api_base=api_base, token=token, method="getMe", payload={}, mutation=False),
            method="getMe",
            provider_effect="not_dispatched",
        )
        try:
            bot_id = int(me["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TelegramApiError("resolved bot has no valid numeric id", provider_effect="not_dispatched") from exc
        bot_username = str(me.get("username") or "")
        if me.get("is_bot") is not True:
            raise TelegramApiError("configured credential did not resolve to a bot", provider_effect="not_dispatched")
        if bot_id != expected_bot_id:
            raise TelegramApiError("resolved bot id does not match configured bot", provider_effect="not_dispatched")
        if bot_username.casefold() != expected_bot_username.removeprefix("@").casefold():
            raise TelegramApiError(
                "resolved bot username does not match configured bot", provider_effect="not_dispatched"
            )

        numeric_chat = _result_dict(
            _api_call(
                http_client,
                api_base=api_base,
                token=token,
                method="getChat",
                payload={"chat_id": expected_chat_id},
                mutation=False,
            ),
            method="getChat",
            provider_effect="not_dispatched",
        )
        actual_chat_id, actual_username, actual_type = _validate_channel_record(
            numeric_chat,
            profile=profile,
            expected_chat_id=expected_chat_id,
        )
        alias_chat = _result_dict(
            _api_call(
                http_client,
                api_base=api_base,
                token=token,
                method="getChat",
                payload={"chat_id": profile.channel_username},
                mutation=False,
            ),
            method="getChat",
            provider_effect="not_dispatched",
        )
        _validate_channel_record(alias_chat, profile=profile, expected_chat_id=expected_chat_id)

        administrators = _result_list(
            _api_call(
                http_client,
                api_base=api_base,
                token=token,
                method="getChatAdministrators",
                payload={"chat_id": actual_chat_id, "return_bots": True},
                mutation=False,
            ),
            method="getChatAdministrators",
        )
        matching_member: dict[str, Any] | None = None
        for candidate in administrators:
            if not isinstance(candidate, dict):
                continue
            user = candidate.get("user")
            if not isinstance(user, dict):
                continue
            try:
                candidate_id = int(user.get("id", 0))
            except (TypeError, ValueError):
                continue
            if candidate_id == bot_id:
                matching_member = candidate
                break
        if matching_member is None:
            raise TelegramApiError(
                "posting bot is absent from the channel administrator list", provider_effect="not_dispatched"
            )
        status = str(matching_member.get("status") or "")
        if status not in {"administrator", "creator"}:
            raise TelegramApiError("posting bot is not a channel administrator", provider_effect="not_dispatched")
        can_post = status == "creator" or matching_member.get("can_post_messages") is True
        if not can_post:
            raise TelegramApiError("posting bot lacks can_post_messages", provider_effect="not_dispatched")
        member_status = cast(Literal["administrator", "creator"], status)

        return GenericTargetProof(
            schema_name="video-channel-manager.telegram-generic-target-proof",
            schema_version=1,
            project_key=profile.project_key,
            channel_username=profile.channel_username,
            profile_sha256=profile.digest,
            bot_id=bot_id,
            bot_username=bot_username,
            chat_id=actual_chat_id,
            chat_username=actual_username,
            chat_title=str(numeric_chat.get("title") or profile.channel_title),
            chat_type=actual_type,
            member_status=member_status,
            can_post_messages=True,
            checked_at_utc=now or datetime.now(tz=UTC),
        )
    finally:
        if own_client:
            http_client.close()


def _verified_target(profile: TelegramChannelProfile, target: GenericTargetProof, now: datetime) -> None:
    if target.project_key != profile.project_key or target.profile_sha256 != profile.digest:
        raise ValueError("target proof is not bound to the selected channel profile")
    if target.channel_username.casefold() != profile.channel_username.casefold():
        raise ValueError("target proof channel username differs from the selected profile")
    age = now - target.checked_at_utc.astimezone(UTC)
    if age < -timedelta(minutes=1) or age > timedelta(minutes=15):
        raise ValueError("target proof is stale or has an invalid future timestamp")


def _receipt(
    profile: TelegramChannelProfile,
    *,
    publication_id: str,
    payload_sha256: str,
    target: GenericTargetProof,
    message_id: int,
    now: datetime,
) -> GenericSendReceipt:
    return GenericSendReceipt(
        schema_name="video-channel-manager.telegram-generic-send-receipt",
        schema_version=1,
        project_key=profile.project_key,
        publication_id=publication_id,
        provider_payload_sha256=payload_sha256,
        chat_id=target.chat_id,
        chat_username=target.chat_username,
        message_id=message_id,
        message_url=f"https://t.me/{target.chat_username}/{message_id}",
        verified_at_utc=now,
    )


def _verify_returned_chat(message: dict[str, Any], target: GenericTargetProof) -> None:
    returned_chat = message.get("chat")
    if not isinstance(returned_chat, dict):
        raise TelegramApiError("Telegram returned a message without chat identity", provider_effect="may_exist")
    try:
        returned_chat_id = int(returned_chat.get("id", 0))
    except (TypeError, ValueError) as exc:
        raise TelegramApiError("Telegram returned an invalid message chat id", provider_effect="may_exist") from exc
    returned_username = str(returned_chat.get("username") or "")
    returned_type = str(returned_chat.get("type") or "")
    if (
        returned_chat_id != target.chat_id
        or returned_username.casefold() != target.chat_username.casefold()
        or returned_type != "channel"
    ):
        raise TelegramApiError("Telegram returned a message for an unexpected chat", provider_effect="may_exist")


def _message_id(message: dict[str, Any]) -> int:
    try:
        message_id = int(message["message_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TelegramApiError("Telegram returned an invalid message_id", provider_effect="may_exist") from exc
    if message_id <= 0:
        raise TelegramApiError("Telegram returned an invalid message_id", provider_effect="may_exist")
    return message_id


def send_message_once(
    profile: TelegramChannelProfile,
    target: GenericTargetProof,
    payload: GenericMessagePayload,
    *,
    token: str,
    api_base: str = DEFAULT_API_BASE,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> GenericSendReceipt:
    _require_provider_write_authorized(profile)
    effective_now = now or datetime.now(tz=UTC)
    _verified_target(profile, target, effective_now)
    if payload.project_key != profile.project_key or payload.profile_sha256 != profile.digest:
        raise ValueError("message payload is not bound to the selected channel profile")
    if payload.channel_username.casefold() != profile.channel_username.casefold():
        raise ValueError("message payload target differs from selected channel profile")

    own_client = client is None
    http_client = client or httpx.Client(
        timeout=httpx.Timeout(connect=15, read=45, write=30, pool=15),
        transport=httpx.HTTPTransport(retries=MUTATION_TRANSPORT_RETRIES),
        trust_env=False,
    )
    try:
        message = _result_dict(
            _api_call(
                http_client,
                api_base=api_base,
                token=token,
                method="sendMessage",
                payload={
                    "chat_id": target.chat_id,
                    "text": payload.html_text,
                    "parse_mode": payload.parse_mode,
                    "link_preview_options": {"is_disabled": payload.link_preview_disabled},
                },
                mutation=True,
            ),
            method="sendMessage",
            provider_effect="may_exist",
        )
        _verify_returned_chat(message, target)
        if str(message.get("text") or "") != payload.expected_plain_text:
            raise TelegramApiError(
                "Telegram returned plain text that differs from the exact provider payload",
                provider_effect="may_exist",
            )
        if not message_entities_match(payload.expected_entities, message.get("entities")):
            raise TelegramApiError(
                "Telegram returned formatting or source-link entities that differ from the exact provider payload",
                provider_effect="may_exist",
            )
        returned_preview = message.get("link_preview_options")
        if not isinstance(returned_preview, dict) or returned_preview.get("is_disabled") is not True:
            raise TelegramApiError(
                "Telegram returned link-preview semantics that differ from the exact provider payload",
                provider_effect="may_exist",
            )
        message_id = _message_id(message)
        return _receipt(
            profile,
            publication_id=payload.publication_id,
            payload_sha256=payload.provider_payload_sha256,
            target=target,
            message_id=message_id,
            now=effective_now,
        )
    finally:
        if own_client:
            http_client.close()


def send_poll_once(
    profile: TelegramChannelProfile,
    target: GenericTargetProof,
    payload: GenericPollPayload,
    *,
    token: str,
    api_base: str = DEFAULT_API_BASE,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> GenericSendReceipt:
    _require_provider_write_authorized(profile)
    effective_now = now or datetime.now(tz=UTC)
    _verified_target(profile, target, effective_now)
    if payload.project_key != profile.project_key or payload.profile_sha256 != profile.digest:
        raise ValueError("poll payload is not bound to the selected channel profile")
    if payload.channel_username.casefold() != profile.channel_username.casefold():
        raise ValueError("poll payload target differs from selected channel profile")

    provider_payload: dict[str, Any] = {
        "chat_id": target.chat_id,
        "question": payload.question,
        "options": [{"text": option} for option in payload.options],
        "type": payload.poll_type,
        "is_anonymous": payload.is_anonymous,
        "allows_multiple_answers": payload.allows_multiple_answers,
        "allows_revoting": payload.allows_revoting,
        "members_only": payload.members_only,
    }
    if payload.description:
        provider_payload["description"] = payload.description
    if payload.poll_type == "quiz":
        provider_payload["correct_option_ids"] = list(payload.correct_option_ids or ())
        if payload.explanation:
            provider_payload["explanation"] = payload.explanation

    own_client = client is None
    http_client = client or httpx.Client(
        timeout=httpx.Timeout(connect=15, read=45, write=30, pool=15),
        transport=httpx.HTTPTransport(retries=MUTATION_TRANSPORT_RETRIES),
        trust_env=False,
    )
    try:
        message = _result_dict(
            _api_call(
                http_client,
                api_base=api_base,
                token=token,
                method="sendPoll",
                payload=provider_payload,
                mutation=True,
            ),
            method="sendPoll",
            provider_effect="may_exist",
        )
        _verify_returned_chat(message, target)
        poll = message.get("poll")
        if not isinstance(poll, dict):
            raise TelegramApiError("Telegram returned a message without poll data", provider_effect="may_exist")
        if str(poll.get("question") or "") != payload.question or str(poll.get("type") or "") != payload.poll_type:
            raise TelegramApiError(
                "Telegram returned poll metadata that differs from payload", provider_effect="may_exist"
            )
        raw_options = poll.get("options")
        if not isinstance(raw_options, list):
            raise TelegramApiError("Telegram returned invalid poll options", provider_effect="may_exist")
        returned_options = tuple(str(option.get("text") or "") for option in raw_options if isinstance(option, dict))
        if returned_options != payload.options:
            raise TelegramApiError(
                "Telegram returned poll options that differ from payload", provider_effect="may_exist"
            )
        if poll.get("is_anonymous") is not payload.is_anonymous:
            raise TelegramApiError(
                "Telegram returned poll anonymity that differs from payload", provider_effect="may_exist"
            )
        if poll.get("allows_multiple_answers") is not payload.allows_multiple_answers:
            raise TelegramApiError(
                "Telegram returned poll multiple-answer semantics that differ from payload", provider_effect="may_exist"
            )
        if poll.get("allows_revoting") is not payload.allows_revoting:
            raise TelegramApiError(
                "Telegram returned poll revoting semantics that differ from payload", provider_effect="may_exist"
            )
        if poll.get("members_only") is not payload.members_only:
            raise TelegramApiError(
                "Telegram returned poll membership semantics that differ from payload", provider_effect="may_exist"
            )
        if str(poll.get("description") or "") != (payload.description or ""):
            raise TelegramApiError(
                "Telegram returned poll description that differs from payload", provider_effect="may_exist"
            )
        if payload.poll_type == "quiz":
            raw_correct = poll.get("correct_option_ids")
            if not isinstance(raw_correct, list):
                raise TelegramApiError("Telegram returned quiz without correct_option_ids", provider_effect="may_exist")
            try:
                returned_correct = tuple(int(index) for index in raw_correct)
            except (TypeError, ValueError) as exc:
                raise TelegramApiError(
                    "Telegram returned invalid quiz correct_option_ids", provider_effect="may_exist"
                ) from exc
            if returned_correct != payload.correct_option_ids:
                raise TelegramApiError(
                    "Telegram returned quiz answer ids that differ from payload", provider_effect="may_exist"
                )
            if str(poll.get("explanation") or "") != (payload.explanation or ""):
                raise TelegramApiError(
                    "Telegram returned quiz explanation that differs from payload", provider_effect="may_exist"
                )
        message_id = _message_id(message)
        return _receipt(
            profile,
            publication_id=payload.publication_id,
            payload_sha256=payload.provider_payload_sha256,
            target=target,
            message_id=message_id,
            now=effective_now,
        )
    finally:
        if own_client:
            http_client.close()


__all__ = [
    "GenericMessagePayload",
    "GenericPollPayload",
    "GenericSendReceipt",
    "GenericTargetProof",
    "ProviderEffect",
    "TelegramApiError",
    "preflight_channel",
    "render_message_payload",
    "render_poll_payload",
    "send_message_once",
    "send_poll_once",
]
