"""One-time browser login for the EXISTING @lordchrist Telegraph account.

Manual operator utility. No account creation, token rotation, page edits or
channel publication. The five-minute login URL is sent only to a pinned private
Telegram chat; it must never appear in CI logs, artifacts or repository state.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TELEGRAPH_PAGE = "Rabstvo-svobody-11-11"
AUTH_URL_PATTERN = re.compile(r"https://edit\.telegra\.ph/auth/[A-Za-z0-9_-]{8,256}\Z")
MAX_API_RESPONSE_BYTES = 65_536


def post_form(url: str, fields: Mapping[str, str]) -> dict[str, Any]:
    """Send an HTTPS POST, keeping all credentials out of URL query strings."""
    request = Request(
        url,
        data=urlencode(fields).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=12) as response:
            data = response.read(MAX_API_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError):
        # Telegram Bot API URLs contain a token in their path. Never include
        # that URL or the original exception in logs/tracebacks.
        raise RuntimeError("Telegraph editor login API request failed; no secrets logged") from None
    if len(data) > MAX_API_RESPONSE_BYTES:
        raise RuntimeError("Telegraph editor login API returned an oversized response")
    try:
        payload = json.loads(data)
    except (UnicodeDecodeError, ValueError, TypeError):
        raise RuntimeError("Telegraph editor login API returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise RuntimeError("Telegraph editor login API response is not an object")
    return payload


def _api_result(data: dict[str, Any], operation: str) -> dict[str, Any]:
    if data.get("ok") is not True or not isinstance(data.get("result"), dict):
        # Never echo raw remote errors: some could repeat supplied parameters.
        raise RuntimeError(f"Telegraph editor login: {operation} rejected")
    return data["result"]


def send_editor_login(
    *,
    telegraph_token: str,
    telegram_bot_token: str,
    editor_chat_id: str,
    post: Callable[[str, Mapping[str, str]], dict[str, Any]] = post_form,
) -> None:
    """Verify editor ownership and deliver one transient login URL privately."""
    if not telegraph_token or not telegram_bot_token:
        raise RuntimeError("Existing Telegraph and Telegram bot secrets are required")
    if not re.fullmatch(r"[1-9][0-9]{0,18}", editor_chat_id):
        raise RuntimeError("Editor recipient must be an explicitly configured private user chat ID")

    bot_api = f"https://api.telegram.org/bot{telegram_bot_token}"
    recipient = _api_result(
        post(f"{bot_api}/getChat", {"chat_id": editor_chat_id}), "private chat verification"
    )
    if recipient.get("type") != "private" or recipient.get("id") != int(editor_chat_id):
        raise RuntimeError("Editor recipient is not the pinned private Telegram user chat")

    page = _api_result(
        post(
            f"https://api.telegra.ph/getPage/{TELEGRAPH_PAGE}",
            {"access_token": telegraph_token, "return_content": "false"},
        ),
        "published page ownership verification",
    )
    if page.get("can_edit") is not True or page.get("path") != TELEGRAPH_PAGE:
        raise RuntimeError("Existing Telegraph account cannot edit the verified @lordchrist page")

    account = _api_result(
        post(
            "https://api.telegra.ph/getAccountInfo",
            {"access_token": telegraph_token, "fields": '["short_name","auth_url"]'},
        ),
        "existing account authorization",
    )
    auth_url = account.get("auth_url")
    if not isinstance(auth_url, str) or not AUTH_URL_PATTERN.fullmatch(auth_url):
        raise RuntimeError("Telegraph did not return a valid secure one-use browser authorization URL")

    message = (
        "Авторизация редактора Telegraph для статей @lordchrist.\n\n"
        "Откройте ссылку в том браузере (или внешнем браузере телефона), "
        "в котором хотите видеть кнопку EDIT:\n"
        f"{auth_url}\n\n"
        "Ссылка одноразовая и действует 5 минут. После входа просто открывайте "
        "обычные ссылки на статьи; повторная авторизация не требуется, "
        "пока этот браузер сохраняет сеанс. Никому не пересылайте это сообщение."
    )
    _api_result(
        post(
            f"{bot_api}/sendMessage",
            {
                "chat_id": editor_chat_id,
                "text": message,
                "disable_web_page_preview": "true",
                "protect_content": "true",
            },
        ),
        "private one-time login delivery",
    )
    print("One-time Telegraph editor login delivered to the pinned private chat (no URL logged).")


def main() -> None:
    send_editor_login(
        telegraph_token=os.environ.get("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "").strip(),
        telegram_bot_token=os.environ.get("LORDCHRIST_TELEGRAM_BOT_TOKEN", "").strip(),
        editor_chat_id=os.environ.get("LORDCHRIST_TELEGRAPH_EDITOR_CHAT_ID", "").strip(),
    )


if __name__ == "__main__":
    main()
