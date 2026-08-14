from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast

import httpx

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile
from video_channel_manager.telegram_models import DEFAULT_API_BASE
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof
from video_channel_manager.telegram_transport import TelegramApiError, _api_call, _result_dict

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
    checks the exact bot membership for administrator status and posting permission.
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

        member = _result_dict(
            _api_call(
                http_client,
                api_base=api_base,
                token=token,
                method="getChatMember",
                payload={"chat_id": chat_id, "user_id": bot_id},
                mutation=False,
            ),
            method="getChatMember",
            provider_effect="not_dispatched",
        )
        member_user = member.get("user")
        if not isinstance(member_user, dict):
            raise TelegramApiError("posting bot membership has no user identity", provider_effect="not_dispatched")
        try:
            member_user_id = int(member_user["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TelegramApiError(
                "posting bot membership has no valid numeric user id", provider_effect="not_dispatched"
            ) from exc
        if member_user_id != bot_id:
            raise TelegramApiError("posting bot membership resolved to a different user", provider_effect="not_dispatched")
        if member_user.get("is_bot") is not True:
            raise TelegramApiError("posting bot membership did not resolve to a bot", provider_effect="not_dispatched")
        member_username = str(member_user.get("username") or "")
        if member_username and member_username.casefold() != bot_username.casefold():
            raise TelegramApiError(
                "posting bot membership username differs from token identity", provider_effect="not_dispatched"
            )

        status = str(member.get("status") or "")
        if status not in {"administrator", "creator"}:
            raise TelegramApiError("posting bot is not a channel administrator", provider_effect="not_dispatched")
        can_post = status == "creator" or member.get("can_post_messages") is True
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
