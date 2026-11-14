"""Provider-inert proof of four approved Lord God Instagram quote photos."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "content/instagram/lord-god-strength-quote-cloud-20261111.json"
PLAN_SHA256 = "529afa8711bc3fd5c071fb322bea90d13d85b2c3e49fc188cd34a62761e352b3"
GRAPH = "https://graph.facebook.com/v26.0"
PAGE = "1457892317403899"
ACCOUNT = "17841433845016161"
HANDLE = "thelordgodismystrength"
MOSCOW = ZoneInfo("Europe/Moscow")
EXPECTED = [
    ("01-charnock", "2026-11-12"),
    ("02-owen", "2026-11-13"),
    ("03-bunyan", "2026-11-14"),
    ("04-watson", "2026-11-15"),
]


def read_plan() -> list[dict]:
    raw = PLAN.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise RuntimeError("Frozen approved quote plan SHA-256 mismatch")
    doc = json.loads(raw)
    if (doc.get("project"), doc.get("account_id"), doc.get("page_id"), doc.get("tz")) != (
        "lord-god-strength",
        ACCOUNT,
        PAGE,
        "Europe/Moscow",
    ):
        raise RuntimeError("Unexpected quote plan account or project")
    items = doc.get("items")
    if not isinstance(items, list) or len(items) != 4:
        raise RuntimeError("Expected four approved quotes")
    if [(item["id"], item["date"]) for item in items] != EXPECTED:
        raise RuntimeError("Quote IDs/dates changed")
    if any(item["time"] != "12:45" or not item.get("caption") or len(item["caption"]) > 2200 for item in items):
        raise RuntimeError("Unexpected quote time or caption")
    return items


def graph_get(token: str, path: str, params: dict | None = None) -> dict:
    url = GRAPH + "/" + path.lstrip("/")
    if params:
        url += "?" + urlencode(params)
    req = Request(url, headers={"Authorization": "Bearer " + token, "Accept": "application/json"}, method="GET")
    try:
        with urlopen(req, timeout=28) as response:
            data = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"Meta photo readback HTTP {exc.code}") from None
    except URLError:
        raise RuntimeError("Meta photo readback network error") from None
    if not isinstance(data, dict):
        raise RuntimeError("Meta GET malformed response")
    return data


def verify_identity(token: str) -> None:
    own = graph_get(token, "me", {"fields": "id"})
    page = graph_get(token, PAGE, {"fields": "id,instagram_business_account{id,username}"})
    ig = page.get("instagram_business_account") or {}
    if (
        str(own.get("id")) != PAGE
        or str(page.get("id")) != PAGE
        or str(ig.get("id")) != ACCOUNT
        or ig.get("username") != HANDLE
    ):
        raise RuntimeError("Instagram photo receipt account mismatch")


def list_media(token: str) -> list[dict]:
    media: list[dict] = []
    after: str | None = None
    seen: set[str] = set()
    for page in range(5):
        params = {"fields": "id,caption,media_type,permalink,timestamp", "limit": "100"}
        if after:
            params["after"] = after
        result = graph_get(token, ACCOUNT + "/media", params)
        rows = result.get("data")
        if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
            raise RuntimeError("Meta IMAGE media list incomplete")
        media.extend(rows)
        if "paging" not in result:
            return media
        paging = result["paging"]
        if not isinstance(paging, dict):
            raise RuntimeError("Meta IMAGE paging malformed")
        if "next" not in paging:
            return media
        if not isinstance(paging["next"], str) or not paging["next"]:
            raise RuntimeError("Meta IMAGE next malformed")
        cursor_set = paging.get("cursors")
        if not isinstance(cursor_set, dict):
            raise RuntimeError("Meta IMAGE paging cursor malformed")
        cursor = cursor_set.get("after")
        if not rows or not isinstance(cursor, str) or not cursor or cursor in seen or page == 4:
            raise RuntimeError("Meta IMAGE paging incomplete or looping")
        seen.add(cursor)
        after = cursor
    raise RuntimeError("Meta IMAGE paging did not terminate")


def exact_receipt(item: dict, media: list[dict]) -> dict | None:
    candidates = [x for x in media if str(x.get("caption", "")).strip() == item["caption"].strip()]
    if len(candidates) > 1:
        raise RuntimeError("Duplicate approved IMAGE caption in Meta")
    if not candidates:
        return None
    post = candidates[0]
    media_id, permalink = str(post.get("id", "")), str(post.get("permalink", ""))
    url = urlsplit(permalink)
    try:
        moment = dt.datetime.fromisoformat(str(post.get("timestamp", "")).replace("Z", "+00:00"))
        if moment.tzinfo is None:
            raise ValueError("Missing timestamp zone")
        day = moment.astimezone(MOSCOW).strftime("%Y-%m-%d")
    except ValueError:
        raise RuntimeError("Invalid IMAGE receipt timestamp") from None
    if (
        not media_id.isdecimal()
        or post.get("media_type") != "IMAGE"
        or url.scheme != "https"
        or (url.hostname or "").lower() not in {"instagram.com", "www.instagram.com"}
        or not url.path.startswith("/p/")
        or day != item["date"]
    ):
        raise RuntimeError("IMAGE receipt not proven for exact account/day")
    return {"id": media_id, "permalink": permalink}

def scheduled_receipt_date(now: dt.datetime) -> str | None:
    """Use the most recent STARTED 13:35 Moscow photo receipt window.

    An overdue GitHub cron after local midnight must not silently switch to
    tomorrow's approved image, nor report a future image as missing.
    """
    if now.tzinfo is None:
        raise ValueError("Photo readback clock must be timezone-aware")
    local = now.astimezone(MOSCOW)
    day = local.date()
    if local.time() < dt.time(13, 35):
        day -= dt.timedelta(days=1)
    if not dt.date(2026, 11, 12) <= day <= dt.date(2026, 11, 15):
        return None
    return day.isoformat()


def main() -> int:
    items = read_plan()
    mode = os.getenv("LORD_GOD_QUOTE_RECEIPT_MODE", "")
    if mode not in {"scheduled", "preflight"}:
        raise RuntimeError("Unapproved readback mode")
    token = os.getenv("LORD_GOD_PAGE_TOKEN", "")
    if len(token) < 35:
        raise RuntimeError("Dedicated Page token missing")
    verify_identity(token)
    feed = list_media(token)
    now = dt.datetime.now(MOSCOW)
    if mode == "preflight":
        for row in items:
            evidence = exact_receipt(row, feed)
            print("IMAGE_RECEIPT_PREFLIGHT", row["id"], "PROVEN" if evidence else "NOT_YET_PUBLISHED", flush=True)
        print("QUOTE_READBACK_PREFLIGHT_OK_NO_POST", flush=True)
        return 0
    today = scheduled_receipt_date(now)
    if today is None:
        print("NO_STARTED_IMAGE_RECEIPT_WINDOW", flush=True)
        return 0
    matches = [x for x in items if x["date"] == today]
    if len(matches) != 1:
        raise RuntimeError("Frozen photo manifest missing exact started receipt date")
    result = exact_receipt(matches[0], feed)
    if result is None:
        print("IMAGE_MISSING_ON_META", matches[0]["id"], today, flush=True)
        return 2
    print("IMAGE_PROVEN_BY_META", matches[0]["id"], today, result["id"], result["permalink"], flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, KeyError, TypeError, OSError) as error:
        print("READ_ONLY_QUOTE_MONITOR_FAILED", type(error).__name__, str(error)[:160], file=sys.stderr)
        sys.exit(1)
