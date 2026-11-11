"""Read-only cloud proof of Lord God Instagram Reels published by the existing local queue.

This tool has no POST function or provider mutation code. Running it cannot publish.
Only immutable date, source ID and exact caption SHA256 are stored in this repository.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "content/instagram/lord-god-strength-reels-cloud-readback-20261112.json"
GRAPH = "https://graph.facebook.com/v26.0"
PAGE_ID = "1457892317403899"
INSTAGRAM_ID = "17841433845016161"
USERNAME = "thelordgodismystrength"
MOSCOW = ZoneInfo("Europe/Moscow")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def plan_items() -> list[dict]:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if (
        plan.get("schema") != "lord-god-instagram-reels-readback-plan-v1"
        or plan.get("project") != "lord-god-strength"
        or plan.get("instagram_account_id") != INSTAGRAM_ID
        or plan.get("facebook_page_id") != PAGE_ID
        or plan.get("instagram_handle") != USERNAME
        or plan.get("timezone") != "Europe/Moscow"
        or plan.get("intended_release_time") != "19:00"
    ):
        raise RuntimeError("Readback manifest identity or schedule mismatch")
    items = plan["items"]
    if len(items) != 12:
        raise RuntimeError("Readback manifest must have exactly 12 rows")
    expected_days = [f"2026-11-{day:02d}" for day in range(10, 22)]
    if [item["date"] for item in items] != expected_days:
        raise RuntimeError("Readback manifest dates have drifted")
    if len({item["source_youtube_id"] for item in items}) != 12:
        raise RuntimeError("Duplicate source ID")
    for item in items:
        if not SHA256.fullmatch(item["caption_sha256"]) or not SHA256.fullmatch(item["video_sha256"]):
            raise RuntimeError("Invalid frozen SHA-256")
        if not (0 < item["video_size_bytes"] <= 1_000_000_000):
            raise RuntimeError("Unexpected video size")
        expected_key = f"lord-god-strength.{item['date']}.yt-{item['source_youtube_id']}.reel-v1"
        if item["publication_key"] != expected_key:
            raise RuntimeError("Publication key mismatch")
    return items


def graph_get(token: str, path: str, *, params: dict | None = None) -> dict:
    """The sole provider request path. It is ALWAYS GET, never mutates Meta."""
    url = GRAPH + "/" + path.lstrip("/")
    if params:
        url += "?" + urlencode(params)
    req = Request(url, method="GET", headers={"Authorization": "Bearer " + token, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"Meta GET HTTP {exc.code}; no publication actions performed") from None
    except URLError as exc:
        raise RuntimeError("Meta GET network error " + type(exc).__name__) from None
    if not isinstance(payload, dict):
        raise RuntimeError("Meta GET returned non-object JSON")
    return payload


def check_identity(token: str) -> None:
    self_data = graph_get(token, "me", params={"fields": "id"})
    if str(self_data.get("id")) != PAGE_ID:
        raise RuntimeError("Unexpected Page owner")
    page = graph_get(token, PAGE_ID, params={"fields": "instagram_business_account{id,username}"})
    account = page.get("instagram_business_account") or {}
    if str(account.get("id")) != INSTAGRAM_ID or account.get("username") != USERNAME:
        raise RuntimeError("Unexpected Instagram account binding")


def list_recent_media(token: str) -> list[dict]:
    rows: list[dict] = []
    after: str | None = None
    seen: set[str] = set()
    for _ in range(5):
        params = {"fields": "id,caption,media_type,media_product_type,permalink,timestamp", "limit": "100"}
        if after:
            params["after"] = after
        response = graph_get(token, INSTAGRAM_ID + "/media", params=params)
        data = response.get("data")
        if not isinstance(data, list):
            raise RuntimeError("Meta media GET did not return data array")
        for item in data:
            if isinstance(item, dict):
                rows.append(item)
        cursor = ((response.get("paging") or {}).get("cursors") or {}).get("after")
        if not data or not isinstance(cursor, str) or not cursor or cursor in seen:
            break
        seen.add(cursor)
        after = cursor
    return rows


def verify_item(item: dict, rows: list[dict]) -> dict:
    exact = [
        media
        for media in rows
        if hashlib.sha256(str(media.get("caption", "")).encode("utf-8")).hexdigest()
        == item["caption_sha256"]
    ]
    if len(exact) > 1:
        raise RuntimeError("DUPLICATE_CAPTION: multiple Meta media records match one approved source")
    if not exact:
        return {"state": "NOT_PUBLISHED", "source": item["source_youtube_id"], "date": item["date"]}
    media = exact[0]
    media_id = str(media.get("id", ""))
    permalink = str(media.get("permalink", ""))
    if (
        not media_id.isdecimal()
        or media.get("media_product_type") != "REELS"
        or media.get("media_type") not in {"VIDEO", "REELS"}
        or urlsplit(permalink).scheme != "https"
        or (urlsplit(permalink).hostname or "").lower() not in {"instagram.com", "www.instagram.com"}
    ):
        raise RuntimeError("MATCHED_CAPTION_BUT_MEDIA_ID_TYPE_OR_PERMALINK_INVALID")
    raw_timestamp = str(media.get("timestamp", ""))
    try:
        posted = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
        if posted.tzinfo is None:
            raise ValueError("Timestamp is missing timezone")
        posted_day = posted.astimezone(MOSCOW).strftime("%Y-%m-%d")
    except ValueError:
        raise RuntimeError("Meta published timestamp invalid") from None
    if posted_day != item["date"]:
        raise RuntimeError(f"MATCHED_CAPTION_WRONG_DATE expected={item['date']} actual={posted_day}")
    return {
        "state": "PROVIDER_CONFIRMED",
        "source": item["source_youtube_id"],
        "date": item["date"],
        "media_id": media_id,
        "permalink": permalink,
    }


def main() -> int:
    items = plan_items()
    mode = os.getenv("LORD_GOD_REELS_PROOF_MODE", "")
    if mode not in {"scheduled", "preflight"}:
        raise RuntimeError("Readback mode must be scheduled or preflight")
    token = os.getenv("LORD_GOD_PAGE_TOKEN", "")
    if len(token) < 35:
        raise RuntimeError("Dedicated Page token secret missing")
    check_identity(token)
    rows = list_recent_media(token)
    print("READ_ONLY_META_MEDIA_COUNT", len(rows), flush=True)
    if mode == "preflight":
        print("CLOUD_READBACK_READY_NO_PROVIDER_WRITES", flush=True)
        return 0

    today = datetime.now(MOSCOW).strftime("%Y-%m-%d")
    match = [item for item in items if item["date"] == today]
    if len(match) != 1 or today < "2026-11-12" or today > "2026-11-21":
        print("NO_EXPECTED_RELEASE_FOR_DATE", today, flush=True)
        return 0
    result = verify_item(match[0], rows)
    if result["state"] == "PROVIDER_CONFIRMED":
        print("REEL_PROVEN_BY_META", result["date"], result["source"], result["media_id"], result["permalink"], flush=True)
        return 0
    print("REEL_MISSING_ON_META", result["date"], result["source"], flush=True)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, KeyError, TypeError, OSError) as error:
        print("READ_ONLY_MONITOR_FAILED", type(error).__name__, str(error)[:180], file=sys.stderr)
        sys.exit(1)
