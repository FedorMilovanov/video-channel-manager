from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from video_channel_manager.telegram_models import (
    CHANNEL_USERNAME,
    DEFAULT_API_BASE,
    DispatchEnvelope,
    LedgerEntry,
    ProviderEffect,
    TargetProof,
    TelegramLedger,
    TelegramQueue,
)
from video_channel_manager.telegram_presentation import (
    DEFAULT_PRESENTATION_POLICY,
    PresentationPolicy,
    RenderedTelegramPost,
    formatting_entities_match,
    verify_rendered_post,
)
from video_channel_manager.telegram_state import utc_now, verify_dispatch_against_queue, verify_persisted_intent

READ_ONLY_TRANSPORT_RETRIES = 2
MUTATION_TRANSPORT_RETRIES = 0


class TelegramApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        provider_effect: ProviderEffect,
        retryable: bool = False,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_effect = provider_effect
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


def _safe_transport_error(prefix: str, exc: Exception) -> str:
    # Never serialize httpx exception strings or request URLs. Telegram embeds
    # the BotFather token in the request path, and the state branch is public.
    return f"{prefix}: {type(exc).__name__}"


def _api_call(
    client: httpx.Client,
    *,
    api_base: str,
    token: str,
    method: str,
    payload: dict[str, Any],
    mutation: bool,
) -> Any:
    url = f"{api_base.rstrip('/')}/bot{token}/{method}"
    try:
        response = client.post(url, json=payload)
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
        raise TelegramApiError(
            _safe_transport_error("Telegram connection failure", exc),
            provider_effect="not_dispatched",
            retryable=True,
        ) from exc
    except (httpx.ReadTimeout, httpx.ReadError, httpx.WriteError, httpx.WriteTimeout, httpx.RemoteProtocolError) as exc:
        raise TelegramApiError(
            _safe_transport_error("Telegram transport outcome unavailable", exc),
            provider_effect="may_exist" if mutation else "not_dispatched",
            retryable=not mutation,
        ) from exc
    except httpx.HTTPError as exc:
        raise TelegramApiError(
            _safe_transport_error("Telegram HTTP transport failure", exc),
            provider_effect="may_exist" if mutation else "not_dispatched",
            retryable=not mutation,
        ) from exc

    try:
        body = response.json()
    except ValueError as exc:
        raise TelegramApiError(
            f"Telegram returned non-JSON HTTP {response.status_code}",
            provider_effect="may_exist" if mutation else "not_dispatched",
            retryable=not mutation,
        ) from exc

    if not isinstance(body, dict):
        raise TelegramApiError(
            "Telegram returned a non-object response",
            provider_effect="may_exist" if mutation else "not_dispatched",
        )

    if not response.is_success or body.get("ok") is not True:
        description = str(body.get("description") or f"HTTP {response.status_code}")[:500]
        error_code_raw = body.get("error_code", response.status_code)
        try:
            error_code = int(error_code_raw)
        except (TypeError, ValueError):
            error_code = response.status_code

        parameters = body.get("parameters")
        retry_after: int | None = None
        if isinstance(parameters, dict) and parameters.get("retry_after") is not None:
            try:
                retry_after = int(parameters["retry_after"])
            except (TypeError, ValueError):
                retry_after = None

        if mutation:
            if error_code == 429:
                effect: ProviderEffect = "confirmed_absent"
                retryable = True
            elif error_code >= 500:
                effect = "may_exist"
                retryable = False
            else:
                effect = "confirmed_absent"
                retryable = False
        else:
            effect = "not_dispatched"
            retryable = error_code == 429 or error_code >= 500

        raise TelegramApiError(
            f"Telegram rejected request: {description}",
            provider_effect=effect,
            retryable=retryable,
            retry_after_seconds=retry_after,
        )

    if "result" not in body:
        raise TelegramApiError(
            "Telegram response has no result",
            provider_effect="may_exist" if mutation else "not_dispatched",
        )
    return body["result"]


def _result_dict(result: Any, *, method: str, provider_effect: ProviderEffect) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise TelegramApiError(f"Telegram {method} result is not an object", provider_effect=provider_effect)
    return result


def _result_list(result: Any, *, method: str) -> list[Any]:
    if not isinstance(result, list):
        raise TelegramApiError(f"Telegram {method} result is not a list", provider_effect="not_dispatched")
    return result


def _validate_channel_record(chat: dict[str, Any], *, expected_chat_id: int) -> tuple[int, str, str]:
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
    if actual_username.casefold() != CHANNEL_USERNAME.removeprefix("@").casefold():
        raise TelegramApiError(
            "resolved Telegram channel username does not match configured target",
            provider_effect="not_dispatched",
        )
    if actual_type != "channel":
        raise TelegramApiError("resolved Telegram target is not a channel", provider_effect="not_dispatched")
    return actual_chat_id, actual_username, actual_type


def preflight_target(
    *,
    token: str,
    expected_chat_id: int,
    expected_bot_id: int,
    expected_bot_username: str,
    api_base: str = DEFAULT_API_BASE,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> TargetProof:
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
            expected_chat_id=expected_chat_id,
        )

        alias_chat = _result_dict(
            _api_call(
                http_client,
                api_base=api_base,
                token=token,
                method="getChat",
                payload={"chat_id": CHANNEL_USERNAME},
                mutation=False,
            ),
            method="getChat",
            provider_effect="not_dispatched",
        )
        _validate_channel_record(alias_chat, expected_chat_id=expected_chat_id)

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

        return TargetProof(
            schema_name="video-channel-manager.telegram-target-proof",
            schema_version=2,
            bot_id=bot_id,
            bot_username=bot_username,
            chat_id=actual_chat_id,
            chat_username="lordchrist",
            chat_title=str(numeric_chat.get("title") or CHANNEL_USERNAME),
            chat_type=actual_type,
            member_status=status,
            can_post_messages=True,
            checked_at_utc=now or utc_now(),
        )
    finally:
        if own_client:
            http_client.close()


def dispatch_prepared(
    queue: TelegramQueue,
    envelope: DispatchEnvelope,
    ledger: TelegramLedger,
    *,
    token: str,
    rendered: RenderedTelegramPost | None = None,
    presentation_policy: PresentationPolicy = DEFAULT_PRESENTATION_POLICY,
    api_base: str = DEFAULT_API_BASE,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> LedgerEntry:
    effective_now = now or utc_now()
    if effective_now.tzinfo is None:
        raise ValueError("dispatch timestamp must be timezone-aware")
    dispatch_age = effective_now - envelope.prepared_at_utc.astimezone(UTC)
    if dispatch_age < -timedelta(minutes=1) or dispatch_age > timedelta(minutes=15):
        raise ValueError("prepared dispatch expired or has an invalid future timestamp")
    if envelope.dispatch_mode == "scheduled" and envelope.scheduled_slot is None:
        raise ValueError("scheduled provider dispatch requires exact editorial slot")

    post = verify_dispatch_against_queue(queue, envelope)
    entry = verify_persisted_intent(queue, ledger, envelope)

    if rendered is None:
        # Backward-compatible direct API mode for historical callers and legacy
        # tests. The production CLI requires an explicit persisted rendered
        # proof and therefore never takes this branch after presentation-v1.
        provider_payload: dict[str, Any] = {
            "chat_id": envelope.target.chat_id,
            "text": envelope.text,
            "link_preview_options": {"is_disabled": True},
        }
        expected_text = envelope.text
        expected_entities = None
    else:
        verify_rendered_post(post, presentation_policy, rendered)
        if rendered.source_payload_sha256 != envelope.payload_sha256:
            raise ValueError("rendered provider payload is not bound to the prepared source payload")
        provider_payload = {
            "chat_id": envelope.target.chat_id,
            "text": rendered.html_text,
            "parse_mode": rendered.parse_mode,
            "link_preview_options": {"is_disabled": rendered.link_preview_disabled},
        }
        expected_text = rendered.text
        expected_entities = rendered.expected_entities

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
                mutation=True,
                payload=provider_payload,
            ),
            method="sendMessage",
            provider_effect="may_exist",
        )
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
            returned_chat_id != envelope.target.chat_id
            or returned_username.casefold() != envelope.target.chat_username.casefold()
            or returned_type != "channel"
        ):
            raise TelegramApiError("Telegram returned a message for an unexpected chat", provider_effect="may_exist")
        if str(message.get("text") or "") != expected_text:
            raise TelegramApiError(
                "Telegram returned plain text that differs from the exact provider payload",
                provider_effect="may_exist",
            )
        if expected_entities is not None and not formatting_entities_match(expected_entities, message.get("entities")):
            raise TelegramApiError(
                "Telegram returned formatting entities that differ from the rendered provider payload",
                provider_effect="may_exist",
            )
        try:
            message_id = int(message["message_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TelegramApiError("Telegram returned an invalid message_id", provider_effect="may_exist") from exc
        if message_id <= 0:
            raise TelegramApiError("Telegram returned an invalid message_id", provider_effect="may_exist")

        entry.state = "published"
        entry.provider_effect = "verified"
        entry.message_id = message_id
        entry.message_url = f"https://t.me/{envelope.target.chat_username}/{message_id}"
        entry.published_at_utc = effective_now
        entry.last_error = None
        return entry
    except TelegramApiError as exc:
        entry.provider_effect = exc.provider_effect
        entry.last_error = str(exc)[:1000]
        if exc.provider_effect == "may_exist":
            entry.state = "unknown"
        elif exc.retryable:
            entry.state = "pending"
            entry.intent_id = None
        else:
            entry.state = "failed"
            entry.intent_id = None
        return entry
    finally:
        if own_client:
            http_client.close()
