"""Source-bounded Lord God Instagram carousel publisher, 16–21 November 2026.

GitHub workflow_dispatch is GET-only preflight. Only approved schedule events in a
narrow Moscow date/time window may create five children, one parent and publish.
No blind retries after an uncertain Meta provider outcome.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, time as clock
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

GRAPH = "https://graph.facebook.com/v26.0"
PAGE = "1457892317403899"
INSTAGRAM = "17841433845016161"
HANDLE = "thelordgodismystrength"
ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "content/instagram/lord-god-strength-carousel-wave-20261116.json"
ASSETS = ROOT / "content/instagram/lord-god-strength-carousel-wave-20261116-assets.json"
RELEASE = (
    "https://github.com/FedorMilovanov/video-channel-manager/releases/download/"
    "lord-god-instagram-carousels-20261116-21/"
)
MOSCOW = ZoneInfo("Europe/Moscow")
EXPECTED = [
    ("01-heart", "2026-11-16"),
    ("02-congresses", "2026-11-17"),
    ("03-peter4", "2026-11-18"),
    ("04-christ", "2026-11-19"),
    ("05-jude", "2026-11-20"),
    ("06-spirits", "2026-11-21"),
]


def api(token: str, endpoint: str, *, data: dict | None = None) -> dict:
    body = None if data is None else urlencode(data).encode("utf-8")
    request = Request(
        GRAPH + "/" + endpoint.lstrip("/"),
        data=body,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=35) as response:
            result = json.load(response)
    except HTTPError as exc:
        try:
            error = json.loads(exc.read().decode("utf-8")).get("error", {})
            code = str(error.get("code", "unknown"))
        except (ValueError, AttributeError, TypeError):
            code = "unknown"
        raise RuntimeError(f"META_HTTP_{exc.code}_CODE_{code}") from None
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("META_CONNECTION_" + type(exc).__name__) from None
    if not isinstance(result, dict):
        raise TypeError("Unexpected Meta response format")
    return result


def validated_plan() -> tuple[list[dict], dict[str, dict]]:
    manifest = json.loads(PLAN.read_text(encoding="utf-8"))
    assets = json.loads(ASSETS.read_text(encoding="utf-8"))
    if (
        manifest.get("project") != "lord-god-strength"
        or manifest.get("account_id") != INSTAGRAM
        or manifest.get("page_id") != PAGE
        or manifest.get("tz") != "Europe/Moscow"
    ):
        raise RuntimeError("Unexpected target account or timezone")
    items = manifest.get("items", [])
    if len(items) != 6 or [(x["id"], x["date"]) for x in items] != EXPECTED:
        raise RuntimeError("Unexpected schedule or post ordering")
    by_name = {x["name"]: x for x in assets}
    if len(assets) != 30 or len(by_name) != 30:
        raise RuntimeError("Asset manifest must contain 30 unique slides")
    expected_files = set()
    for item in items:
        if item.get("time") != "12:45" or item.get("surface") != "carousel":
            raise RuntimeError("Unexpected publication time or surface")
        if len(item.get("caption", "")) > 2200 or not item["caption"].strip():
            raise RuntimeError("Caption missing or too long")
        slides = item.get("slides", [])
        if len(slides) != 5 or [x["index"] for x in slides] != [1, 2, 3, 4, 5]:
            raise RuntimeError("Five ordered slides required")
        for slide in slides:
            name = slide["image"]
            metadata = by_name.get(name)
            if (
                name != f"{item['id']}-slide-{slide['index']:02d}.jpg"
                or metadata is None
                or metadata["id"] != item["id"]
                or metadata["slide"] != slide["index"]
                or metadata["width"] != 1080
                or metadata["height"] != 1350
                or len(metadata["sha256"]) != 64
                or metadata["bytes"] < 40_000
                or metadata["bytes"] > 8_000_000
            ):
                raise RuntimeError("Unexpected image metadata: " + name)
            expected_files.add(name)
    if set(by_name) != expected_files:
        raise RuntimeError("Unbound image asset")
    return items, by_name


def media_url(metadata: dict) -> str:
    name = metadata["name"]
    url = RELEASE + name
    try:
        with urlopen(Request(url, headers={"Accept": "image/jpeg"}), timeout=40) as response:
            final = urlparse(response.url)
            if final.scheme != "https" or final.hostname not in {
                "github.com",
                "release-assets.githubusercontent.com",
            }:
                raise RuntimeError("Untrusted asset redirect host")
            payload = response.read(8_100_000)
    except (URLError, HTTPError, TimeoutError) as exc:
        raise RuntimeError("ASSET_DOWNLOAD_" + type(exc).__name__) from None
    if len(payload) != metadata["bytes"] or hashlib.sha256(payload).hexdigest() != metadata["sha256"]:
        raise RuntimeError("ASSET_INTEGRITY_FAILURE_" + name)
    if not payload.startswith(bytes((255, 216, 255))):
        raise RuntimeError("ASSET_NOT_JPEG_" + name)
    return url


def validate_identity(token: str) -> None:
    owner = api(token, "me?fields=id")
    if str(owner.get("id")) != PAGE:
        raise RuntimeError("Wrong Facebook Page token")
    page = api(token, PAGE + "?fields=id,instagram_business_account{id,username}")
    account = page.get("instagram_business_account") or {}
    if str(page.get("id")) != PAGE or str(account.get("id")) != INSTAGRAM or account.get("username") != HANDLE:
        raise RuntimeError("Wrong Instagram binding")
    quota = api(token, INSTAGRAM + "/content_publishing_limit?fields=quota_usage,config")
    if not quota.get("data"):
        raise RuntimeError("Instagram publishing quota unavailable")


def find_existing(token: str, caption: str) -> dict | None:
    listing = api(token, INSTAGRAM + "/media?fields=id,caption,media_type,permalink,timestamp&limit=100")
    for media in listing.get("data", []):
        if media.get("caption", "").strip() == caption.strip():
            return media
    return None


def poll_finished(token: str, container: str) -> None:
    for _ in range(15):
        obj = api(token, container + "?fields=status_code")
        status = obj.get("status_code")
        if status == "FINISHED":
            return
        if status in {"ERROR", "EXPIRED", "FAILED", "PUBLISHED"}:
            raise RuntimeError("Unexpected container status " + str(status))
        time.sleep(3)
    raise RuntimeError("Container not ready; NO blind retry")


def preflight(token: str, items: list[dict], assets: dict[str, dict]) -> None:
    for item in items:
        for slide in item["slides"]:
            media_url(assets[slide["image"]])
        previous = find_existing(token, item["caption"])
        print("PREFLIGHT", item["id"], item["date"], "EXISTS" if previous else "READY", flush=True)
    print("PREFLIGHT_OK_NO_POST", flush=True)


def scheduled(token: str, items: list[dict], assets: dict[str, dict]) -> None:
    if os.getenv("GITHUB_EVENT_NAME") != "schedule":
        raise RuntimeError("Provider writes require genuine scheduled GitHub event")
    now = datetime.now(MOSCOW)
    matches = [x for x in items if x["date"] == now.strftime("%Y-%m-%d")]
    if not matches:
        print("NO_SCHEDULED_POST_FOR_DATE", now.date(), flush=True)
        return
    if len(matches) != 1 or not (clock(12, 45) <= now.time() < clock(14, 0)):
        raise RuntimeError("Outside the exact 12:45–14:00 MSK window")
    item = matches[0]
    urls = [media_url(assets[x["image"]]) for x in item["slides"]]
    previous = find_existing(token, item["caption"])
    if previous:
        print("ALREADY_PUBLISHED_SKIP", item["id"], previous.get("id"), previous.get("permalink"), flush=True)
        return
    print("CAROUSEL_BEGIN", item["id"], "images", len(urls), flush=True)
    children = []
    for index, url in enumerate(urls, start=1):
        child = api(token, INSTAGRAM + "/media", data={"image_url": url, "is_carousel_item": "true"})
        child_id = str(child.get("id", ""))
        if not child_id.isdecimal():
            raise RuntimeError("Unknown carousel child outcome; NO blind retry")
        print("CAROUSEL_CHILD_CREATED", item["id"], index, child_id, flush=True)
        poll_finished(token, child_id)
        children.append(child_id)
    parent = api(
        token,
        INSTAGRAM + "/media",
        data={"media_type": "CAROUSEL", "caption": item["caption"], "children": ",".join(children)},
    )
    parent_id = str(parent.get("id", ""))
    if not parent_id.isdecimal():
        raise RuntimeError("Unknown carousel parent outcome; NO blind retry")
    print("CAROUSEL_PARENT_CREATED", item["id"], parent_id, flush=True)
    poll_finished(token, parent_id)
    # Never send a second media_publish after ambiguous provider/network responses.
    print("PUBLISH_REQUESTING", item["id"], parent_id, flush=True)
    published = api(token, INSTAGRAM + "/media_publish", data={"creation_id": parent_id})
    media_id = str(published.get("id", ""))
    if not media_id.isdecimal():
        raise RuntimeError("Unknown publish response; no blind retry")
    print("PUBLISH_RESPONSE_ID", item["id"], media_id, flush=True)
    detail = api(token, media_id + "?fields=id,caption,media_type,permalink,timestamp")
    if (
        str(detail.get("id")) != media_id
        or detail.get("media_type") != "CAROUSEL_ALBUM"
        or detail.get("caption", "").strip() != item["caption"].strip()
        or not detail.get("permalink")
    ):
        raise RuntimeError("Published carousel readback incomplete; NO retry")
    print("PUBLISHED_CONFIRMED", item["id"], media_id, detail["permalink"], flush=True)


def main() -> None:
    items, assets = validated_plan()
    mode = os.getenv("LORD_GOD_CLOUD_MODE", "")
    if mode not in {"preflight", "scheduled"}:
        raise RuntimeError("Invalid execution mode")
    token = os.getenv("LORD_GOD_PAGE_TOKEN", "")
    if len(token) < 35:
        raise RuntimeError("Dedicated Instagram secret missing")
    validate_identity(token)
    if mode == "preflight":
        preflight(token, items, assets)
    else:
        scheduled(token, items, assets)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, TypeError, KeyError, OSError) as exc:
        print("SAFE_STOP", type(exc).__name__, str(exc)[:180], file=sys.stderr)
        sys.exit(1)
