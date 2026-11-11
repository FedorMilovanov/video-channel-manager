"""Cloud-only, date-scoped Instagram photo publishing; never depends on a local PC.

This script may only publish the four source-bound Lord God quote cards.
Github workflow_dispatch is preflight only. Scheduled event allows one post for exact Moscow date.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from datetime import time as clock
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

GRAPH = "https://graph.facebook.com/v26.0"
FACEBOOK_PAGE = "1457892317403899"
INSTAGRAM_ACCOUNT = "17841433845016161"
INSTAGRAM_USERNAME = "thelordgodismystrength"
APP_ID = "1528850542618219"
RELEASE = "https://github.com/FedorMilovanov/video-channel-manager/releases/download/lord-god-ig-quote-media-20261111/"
PLAN = Path(__file__).resolve().parents[2] / "content/instagram/lord-god-strength-quote-cloud-20261111.json"
MOSCOW = ZoneInfo("Europe/Moscow")


def request_json(endpoint: str, token: str, *, data: dict | None = None) -> dict:
    url = GRAPH + "/" + endpoint.lstrip("/")
    body = None if data is None else urlencode(data).encode("utf-8")
    req = Request(
        url,
        data=body,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=35) as resp:
            obj = json.load(resp)
    except HTTPError as error:
        try:
            payload = json.loads(error.read().decode("utf-8"))
            code = payload.get("error", {}).get("code", "unknown")
        except (ValueError, KeyError, TypeError):
            code = "unknown"
        raise RuntimeError(f"Meta HTTP {error.code}, code {code}") from None
    except URLError as error:
        raise RuntimeError("Meta connection failed (" + type(error).__name__ + ")") from None
    if not isinstance(obj, dict):
        raise TypeError("Invalid Meta response shape")
    return obj


def media_verified(item: dict) -> str:
    filename = item["image"]
    if filename not in {
        "01-charnock-4x5.jpg",
        "02-owen-4x5.jpg",
        "03-bunyan-4x5.jpg",
        "04-watson-4x5.jpg",
    }:
        raise RuntimeError("Image not in approved release")
    url = RELEASE + filename
    try:
        with urlopen(Request(url, headers={"Accept": "image/jpeg"}), timeout=40) as resp:
            final = urlparse(resp.url)
            if final.scheme != "https" or final.hostname not in {
                "github.com",
                "release-assets.githubusercontent.com",
            }:
                raise RuntimeError("Media downloaded from unexpected host")
            payload = resp.read(10_000_000)
    except (URLError, HTTPError) as error:
        raise RuntimeError("Media download failed (" + type(error).__name__ + ")") from None
    if len(payload) != item["size_bytes"] or hashlib.sha256(payload).hexdigest() != item["sha256"]:
        raise RuntimeError("Media SHA-256/size mismatch")
    if not payload.startswith(bytes((255, 216, 255))):
        raise RuntimeError("Media not JPEG")
    return url


def read_plan() -> list[dict]:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if (plan["project"], plan["account_id"], plan["page_id"], plan["tz"]) != (
        "lord-god-strength",
        INSTAGRAM_ACCOUNT,
        FACEBOOK_PAGE,
        "Europe/Moscow",
    ):
        raise RuntimeError("Wrong project/account")
    rows = plan["items"]
    expected = [
        ("01-charnock", "2026-11-12"),
        ("02-owen", "2026-11-13"),
        ("03-bunyan", "2026-11-14"),
        ("04-watson", "2026-11-15"),
    ]
    if len(rows) != 4 or [(x["id"], x["date"]) for x in rows] != expected:
        raise RuntimeError("Unexpected four-day schedule")
    if any(x["time"] != "12:45" or len(x["caption"]) > 2200 for x in rows):
        raise RuntimeError("Unexpected scheduled time or caption length")
    return rows


def verify_identity(token: str) -> None:
    owner = request_json("me?fields=id", token)
    if str(owner.get("id")) != FACEBOOK_PAGE:
        raise RuntimeError("Wrong Facebook PAGE token")
    page = request_json(FACEBOOK_PAGE + "?fields=id,instagram_business_account{id,username}", token)
    instagram = page.get("instagram_business_account") or {}
    if (
        str(page.get("id")) != FACEBOOK_PAGE
        or str(instagram.get("id")) != INSTAGRAM_ACCOUNT
        or instagram.get("username") != INSTAGRAM_USERNAME
    ):
        raise RuntimeError("Wrong Instagram account linkage")
    quota = request_json(INSTAGRAM_ACCOUNT + "/content_publishing_limit?fields=quota_usage,config", token)
    if not quota.get("data"):
        raise RuntimeError("Instagram publishing quota unavailable")


def find_published(token: str, caption: str) -> dict | None:
    """Fail closed if the provider feed is incomplete or contains duplicate captions.

    Only follow provider cursors on our own fixed Graph API endpoint: never
    dereference untrusted paging.next URLs or put the Page token in a URL.
    """
    matches: list[dict] = []
    after: str | None = None
    seen_cursors: set[str] = set()
    for page in range(5):
        params = {"fields": "id,caption,media_type,permalink,timestamp", "limit": "100"}
        if after:
            params["after"] = after
        listing = request_json(INSTAGRAM_ACCOUNT + "/media?" + urlencode(params), token)
        media = listing.get("data")
        if not isinstance(media, list):
            raise RuntimeError("Meta media list incomplete; do not publish")
        for item in media:
            if not isinstance(item, dict):
                raise RuntimeError("Unexpected Meta media record; do not publish")
            if str(item.get("caption", "")).strip() == caption.strip():
                matches.append(item)
        paging = listing.get("paging") or {}
        if not isinstance(paging, dict):
            raise RuntimeError("Meta pagination malformed; do not publish")
        if not paging.get("next"):
            break
        cursors = paging.get("cursors") or {}
        if not isinstance(cursors, dict):
            raise RuntimeError("Meta pagination cursors malformed; do not publish")
        cursor = cursors.get("after")
        if not isinstance(cursor, str) or not cursor or cursor in seen_cursors or not media:
            raise RuntimeError("Meta pagination cursor invalid; do not publish")
        if page == 4:
            raise RuntimeError("Meta media listing exceeds safe verification limit; do not publish")
        seen_cursors.add(cursor)
        after = cursor
    if len(matches) > 1:
        raise RuntimeError("Duplicate approved photo caption in Meta feed; do not publish")
    if not matches:
        return None
    existing = matches[0]
    parsed = urlparse(str(existing.get("permalink", "")))
    if (
        not str(existing.get("id", "")).isdecimal()
        or existing.get("media_type") != "IMAGE"
        or parsed.scheme != "https"
        or (parsed.hostname or "").lower() not in {"instagram.com", "www.instagram.com"}
        or not isinstance(existing.get("timestamp"), str)
        or not existing["timestamp"]
    ):
        raise RuntimeError("Matching photo has incomplete Meta proof; do not publish")
    return existing


def main() -> None:
    rows = read_plan()
    mode = os.environ.get("LORD_GOD_CLOUD_MODE", "")
    if mode not in {"preflight", "scheduled"}:
        raise RuntimeError("Requires approved preflight/scheduled mode")
    token = os.environ.get("LORD_GOD_PAGE_TOKEN", "")
    if len(token) < 35:
        raise RuntimeError("Cloud secret missing")
    verify_identity(token)
    today = datetime.now(MOSCOW)
    if mode == "preflight":
        for item in rows:
            media_verified(item)
            found = find_published(token, item["caption"])
            print(
                "PREFLIGHT",
                item["id"],
                item["date"],
                "ALREADY_PUBLISHED" if found else "READY",
                flush=True,
            )
        print("PREFLIGHT_OK_NO_POST", flush=True)
        return
    current = today.strftime("%Y-%m-%d")
    matches = [x for x in rows if x["date"] == current]
    if len(matches) != 1:
        print("NO_SCHEDULED_POST_FOR_DATE", current, flush=True)
        return
    if not (clock(12, 45) <= today.time() < clock(14, 0)):
        raise RuntimeError("Outside 12:45-14:00 Moscow publication window")
    item = matches[0]
    image_url = media_verified(item)
    already = find_published(token, item["caption"])
    if already:
        print("ALREADY_PUBLISHED_SKIP", item["id"], already.get("id"), flush=True)
        return
    print("POST_START", item["id"], current, flush=True)
    created = request_json(
        INSTAGRAM_ACCOUNT + "/media",
        token,
        data={"image_url": image_url, "caption": item["caption"]},
    )
    container = str(created.get("id", ""))
    if not container.isdecimal():
        raise RuntimeError("Media container ID unavailable, no publish call")
    print("CONTAINER_CREATED", container, flush=True)
    for _ in range(20):
        stage = request_json(container + "?fields=status_code", token)
        status = stage.get("status_code")
        if status == "FINISHED":
            break
        if status in {"ERROR", "EXPIRED", "FAILED"}:
            raise RuntimeError("Media container " + str(status))
        time.sleep(3)
    else:
        raise RuntimeError("Media processing incomplete; do not blind retry")
    # No automatic action retry; an uncertain media_publish outcome requires reconciliation.
    print("PUBLISH_REQUESTING", item["id"], flush=True)
    result = request_json(INSTAGRAM_ACCOUNT + "/media_publish", token, data={"creation_id": container})
    media_id = str(result.get("id", ""))
    if not media_id.isdecimal():
        raise RuntimeError("Uncertain publish response; do not blindly retry")
    # This is only a container-publish response, not yet verified content.
    # Preserve the returned ID for reconciliation if the provider readback is incomplete.
    print("MEDIA_PUBLISH_ID_UNCONFIRMED", item["id"], media_id, flush=True)
    detail = request_json(media_id + "?fields=id,caption,media_type,permalink,timestamp", token)
    permalink = str(detail.get("permalink", ""))
    parsed_url = urlparse(permalink)
    timestamp = str(detail.get("timestamp", ""))
    try:
        published_at = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if published_at.tzinfo is None:
            raise ValueError("Missing timezone")
        published_day = published_at.astimezone(MOSCOW).strftime("%Y-%m-%d")
    except ValueError:
        raise RuntimeError("Provider publication timestamp missing or invalid; do not retry") from None
    if (
        str(detail.get("id", "")) != media_id
        or str(detail.get("caption", "")).strip() != item["caption"].strip()
        or detail.get("media_type") != "IMAGE"
        or parsed_url.scheme != "https"
        or (parsed_url.hostname or "").lower() not in {"instagram.com", "www.instagram.com"}
        or published_day != current
    ):
        raise RuntimeError("Provider photo media, date, caption or permalink not proven; do not retry")
    print("PUBLISHED_CONFIRMED", item["id"], media_id, permalink, flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, TypeError, KeyError, OSError) as exc:
        print(
            "SAFE_FAILURE_NO_BLIND_RETRY",
            type(exc).__name__,
            str(exc)[:200],
            file=sys.stderr,
        )
        sys.exit(1)
