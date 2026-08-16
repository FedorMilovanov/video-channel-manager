from __future__ import annotations

import json
import os
import pathlib
import sys
from datetime import UTC, datetime

import httpx

STATE_PATH = pathlib.Path("content/telegram/milovi-cake/live/canary-dispatch-state.json")
RUNTIME_DIR = pathlib.Path(".runtime/milovi-canary")
CHAT_ID = -1002215328390
CHAT_USERNAME = "MiloviCake"


def main() -> int:
    if os.environ.get("GITHUB_RUN_ATTEMPT") != "1":
        raise SystemExit("GitHub rerun forbidden for exact canary")
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if state.get("status") != "dispatch_started" or state.get("message_id") is not None:
        raise SystemExit("dispatch-started barrier missing or already consumed")
    if state.get("authorization_commit_sha") != os.environ.get("GITHUB_SHA"):
        raise SystemExit("dispatch state is not bound to this authorization commit")

    jpeg = (RUNTIME_DIR / "p18.jpg").read_bytes()
    caption = (RUNTIME_DIR / "caption.txt").read_text(encoding="utf-8")
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    try:
        with httpx.Client(
            timeout=httpx.Timeout(connect=15, read=45, write=45, pool=15),
            transport=httpx.HTTPTransport(retries=0),
            trust_env=False,
        ) as client:
            response = client.post(
                f"https://api.telegram.org/bot{token}/sendPhoto",
                data={"chat_id": str(CHAT_ID), "caption": caption},
                files={"photo": ("p18.jpg", jpeg, "image/jpeg")},
            )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        print(
            "Telegram transport outcome is unknown; dispatch_started barrier remains; automatic replay forbidden",
            file=sys.stderr,
        )
        raise SystemExit(75) from exc

    try:
        body = response.json()
    except ValueError as exc:
        print("Telegram returned non-JSON; provider outcome treated as unknown", file=sys.stderr)
        raise SystemExit(75) from exc
    if response.status_code != 200 or not isinstance(body, dict) or body.get("ok") is not True:
        description = str(body.get("description") or "") if isinstance(body, dict) else ""
        print(
            f"Telegram rejected exact canary HTTP={response.status_code} description={description}; no automatic replay",
            file=sys.stderr,
        )
        raise SystemExit(76)

    message = body.get("result")
    if not isinstance(message, dict):
        raise SystemExit("Telegram success response has no message")
    chat = message.get("chat")
    if not isinstance(chat, dict):
        raise SystemExit("Telegram success response has no chat identity")
    if int(chat["id"]) != CHAT_ID or str(chat.get("type") or "") != "channel":
        raise SystemExit("Telegram returned unexpected chat id/type")
    if str(chat.get("username") or "").casefold() != CHAT_USERNAME.casefold():
        raise SystemExit("Telegram returned unexpected chat username")
    if str(message.get("caption") or "") != caption:
        raise SystemExit("Telegram returned caption drift")
    photos = message.get("photo")
    if not isinstance(photos, list) or not photos:
        raise SystemExit("Telegram returned no photo collection")
    message_id = int(message["message_id"])
    if message_id <= 0:
        raise SystemExit("Telegram returned invalid message_id")

    state.update(
        {
            "status": "verified",
            "provider_effect": "verified",
            "verified_at_utc": datetime.now(tz=UTC).isoformat(),
            "message_id": message_id,
            "message_url": f"https://t.me/{CHAT_USERNAME}/{message_id}",
            "returned_chat_id": int(chat["id"]),
            "returned_chat_username": str(chat.get("username") or ""),
            "returned_photo_count": len(photos),
        }
    )
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "verified",
                "message_id": message_id,
                "message_url": state["message_url"],
                "provider_effect": "verified",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
