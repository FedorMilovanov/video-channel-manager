from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, cast

import httpx

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile
from video_channel_manager.telegram_models import DEFAULT_API_BASE
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof
from video_channel_manager.telegram_transport import TelegramApiError, _api_call, _result_dict, _result_list

READ_ONLY_TRANSPORT_RETRIES = 2


def discover_channel_target(
    profile: TelegramChannelProfile,
    *,
    token: str,
    expected_bot_id: int,
    expected_bot_username: str,
    api_base: str = DEFAULT_API_BASE,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> GenericTargetProof:
    """Resolve an exact numeric channel ID from the immutable profile username.

    This operation is read-only. It proves the token identity, resolves the public
    username, round-trips the resulting numeric chat ID back through getChat, and
    checks that the same bot is an administrator with posting permission.
    """

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
        try:
            chat_id = int(alias_chat["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TelegramApiError(
                "resolved Telegram channel has no valid numeric id", provider_effect="not_dispatched"
            ) from exc
        chat_username = str(alias_chat.get("username") or "")
        chat_type = str(alias_chat.get("type") or "")
        if chat_id >= 0:
            raise TelegramApiError("resolved Telegram channel id must be negative", provider_effect="not_dispatched")
        if chat_username.casefold() != profile.bare_username.casefold():
            raise TelegramApiError(
                "resolved Telegram username differs from immutable channel profile", provider_effect="not_dispatched"
            )
        if chat_type != "channel":
            raise TelegramApiError("resolved Telegram target is not a channel", provider_effect="not_dispatched")

        numeric_chat = _result_dict(
            _api_call(
                http_client,
                api_base=api_base,
                token=token,
                method="getChat",
                payload={"chat_id": chat_id},
                mutation=False,
            ),
            method="getChat",
            provider_effect="not_dispatched",
        )
        try:
            numeric_id = int(numeric_chat["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TelegramApiError("numeric getChat returned no valid id", provider_effect="not_dispatched") from exc
        numeric_username = str(numeric_chat.get("username") or "")
        numeric_type = str(numeric_chat.get("type") or "")
        if (
            numeric_id != chat_id
            or numeric_username.casefold() != profile.bare_username.casefold()
            or numeric_type != "channel"
        ):
            raise TelegramApiError(
                "numeric and username Telegram target resolution disagree", provider_effect="not_dispatched"
            )

        administrators = _result_list(
            _api_call(
                http_client,
                api_base=api_base,
                token=token,
                method="getChatAdministrators",
                payload={"chat_id": chat_id, "return_bots": True},
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
            chat_id=chat_id,
            chat_username=chat_username,
            chat_title=str(alias_chat.get("title") or profile.channel_title),
            chat_type="channel",
            member_status=member_status,
            can_post_messages=True,
            checked_at_utc=now or datetime.now(tz=UTC),
        )
    finally:
        if own_client:
            http_client.close()
