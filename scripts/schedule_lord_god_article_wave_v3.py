#!/usr/bin/env python3
"""Audit and schedule ten theological article posts with explicit wall photos.

The plan mode is read-only. It verifies 30 pinned public resources (ten article
pages, ten source images, and ten source files at an exact repository commit),
materializes deterministic JPEG assets locally, validates the managed VK group,
checks that a wall-photo upload server is available, and audits published and
postponed wall posts.

Canary and apply use a staged, resumable journal. Mutation calls never retry
automatically. A saved photo token is reused after interruption, and ambiguous
photo-save or wall-post outcomes block further writes until reconciliation.
No edit, delete, pin, repost, or immediate-publication method is implemented.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import httpx

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkApiError, VkTokenStore
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.wall_content_audit import fetch_wall_posts

PROJECT_KEY = "lord-god-strength"
COMMUNITY_ID = 60805374
OWNER_ID = -60805374
ACCOUNT_ALIAS = "legendary-poet"  # Shared credential alias only.
DECISION_SET_ID = "lord-god-article-wave-v3-202608"
POLICY_PATH = Path("content/policies/lord-god-article-wave-v3-202608.json")
EXPECTED_POLICY_SHA = "sha256:58f35a6783789c4b98293bc82414030ca913a21813d3da800fad8cc96d133856"
MOSCOW = timezone(timedelta(hours=3), name="UTC+03:00")
MIN_GAP_SECONDS = 2 * 60 * 60
MIN_FUTURE_SECONDS = 10 * 60
POST_WAIT_SECONDS = 90
JPEG_WIDTH = 1200
JPEG_HEIGHT = 630
JPEG_MIN_BYTES = 10_000
UPLOAD_TIMEOUT_SECONDS = 120.0
HTTP_TIMEOUT_SECONDS = 45.0
URL_RE = re.compile(r"https://gospod-bog\.ru/[^\s<>\"']+")
TRAILING_URL_PUNCTUATION = ".,;:!?)]}»”\""
BLOCKING_JOURNAL_STAGES = frozenset(
    {
        "photo_save_intent",
        "photo_save_unknown",
        "wall_post_intent",
        "wall_post_unknown",
        "wall_post_accepted_unverified",
    }
)
RESUMABLE_WITH_PHOTO = frozenset({"photo_saved", "wall_post_rejected"})


class PageMetadata(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.canonical = ""
        self.og_url = ""
        self.og_title = ""
        self.og_description = ""
        self.og_image = ""
        self.robots: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {str(key).lower(): str(value or "").strip() for key, value in attrs}
        name = tag.lower()
        if name == "meta":
            property_name = (
                attributes.get("property") or attributes.get("name") or ""
            ).lower()
            content = attributes.get("content", "")
            if property_name == "og:url" and not self.og_url:
                self.og_url = content
            elif property_name == "og:title" and not self.og_title:
                self.og_title = content
            elif property_name == "og:description" and not self.og_description:
                self.og_description = content
            elif property_name == "og:image" and not self.og_image:
                self.og_image = content
            elif property_name in {"robots", "googlebot", "yandex"}:
                self.robots.append(content.lower())
        elif name == "link" and "canonical" in attributes.get("rel", "").lower().split():
            if not self.canonical:
                self.canonical = attributes.get("href", "")


def now_iso() -> str:
    return datetime.now(UTC).astimezone().isoformat()


def canonical_text(value: object) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def canonical_sha(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def bytes_sha(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def message_sha(value: object) -> str:
    return bytes_sha(canonical_text(value).encode())


def normalize_url(value: object) -> str:
    source = str(value or "").strip().rstrip(TRAILING_URL_PUNCTUATION)
    parsed = urlsplit(source)
    path = parsed.path or "/"
    if path != "/" and "." not in path.rsplit("/", 1)[-1]:
        path = path.rstrip("/") + "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def read_json(path: Path, fallback: object) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else fallback


def load_policy(repo: Path) -> dict[str, Any]:
    value = json.loads((repo / POLICY_PATH).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Article policy root must be an object")
    return value


def validate_policy(policy: dict[str, Any]) -> None:
    expected = {
        "schema_name": "video-manager.vk-lord-god-article-wave-policy",
        "schema_version": 3,
        "decision_set_id": DECISION_SET_ID,
        "project_key": PROJECT_KEY,
        "source_repository": "FedorMilovanov/gb-is-my-strength",
        "source_repository_commit": "aed8ed2244ad566b0458e490f629d394122dbf95",
        "vk_community_id": COMMUNITY_ID,
        "vk_owner_id": OWNER_ID,
        "schedule_timezone": "UTC+03:00",
        "schedule_hour": 14,
        "minimum_gap_minutes": 120,
        "attachment_mode": "explicit-wall-photo-plus-text-link",
        "asset_mode": "materialized-jpeg-1200x630",
    }
    for key, value in expected.items():
        if policy.get(key) != value:
            raise ValueError(f"Article policy identity mismatch: {key}")

    actual_sha = canonical_sha(
        {key: value for key, value in policy.items() if key != "policy_sha256"}
    )
    if policy.get("policy_sha256") != actual_sha or actual_sha != EXPECTED_POLICY_SHA:
        raise ValueError("Article policy digest mismatch")

    operations = policy.get("operations")
    if not isinstance(operations, list) or len(operations) != 10:
        raise ValueError("Article policy must contain exactly ten operations")

    expected_dates = [
        int(datetime(2026, 8, day, 14, 0, tzinfo=MOSCOW).timestamp())
        for day in range(3, 13)
    ]
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    seen_images: set[str] = set()
    for ordinal, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict):
            raise ValueError(f"Operation {ordinal} is not an object")
        if operation.get("ordinal") != ordinal:
            raise ValueError(f"Invalid operation ordinal: {ordinal}")
        operation_id = str(operation.get("operation_id") or "")
        article_url = normalize_url(operation.get("url"))
        image_url = normalize_url(operation.get("image_url"))
        message = canonical_text(operation.get("message"))
        publish_at = datetime.fromisoformat(str(operation.get("publish_at") or ""))
        publish_date = operation.get("publish_date")
        source_path = str(operation.get("source_path") or "").strip()

        if not operation_id.startswith(f"{DECISION_SET_ID}-{ordinal:02d}-"):
            raise ValueError(f"Invalid operation identity: {ordinal}")
        if not article_url.startswith("https://gospod-bog.ru/"):
            raise ValueError(f"Invalid article URL: {ordinal}")
        if not image_url.startswith("https://gospod-bog.ru/images/"):
            raise ValueError(f"Invalid image URL: {ordinal}")
        if not source_path.startswith("src/") or ".." in Path(source_path).parts:
            raise ValueError(f"Invalid source path: {ordinal}")
        if article_url not in message or not 400 <= len(message) <= 1000:
            raise ValueError(f"Invalid post length or missing article URL: {ordinal}")
        if "💬" not in message:
            raise ValueError(f"Missing discussion question: {ordinal}")
        if operation.get("message_sha256") != message_sha(message):
            raise ValueError(f"Message digest mismatch: {ordinal}")
        if not isinstance(publish_date, int) or publish_date != expected_dates[ordinal - 1]:
            raise ValueError(f"Unexpected publication epoch: {ordinal}")
        if int(publish_at.timestamp()) != publish_date:
            raise ValueError(f"Schedule mismatch: {ordinal}")
        if publish_at.astimezone(MOSCOW).strftime("%H:%M") != "14:00":
            raise ValueError(f"Unexpected article hour: {ordinal}")
        if operation_id in seen_ids or article_url in seen_urls:
            raise ValueError("Duplicate operation ID or article URL")

        seen_ids.add(operation_id)
        seen_urls.add(article_url)
        seen_images.add(image_url)

    if len(seen_images) != 10:
        raise ValueError("Every article must have its own reviewed image")


def find_ffmpeg() -> str:
    configured = str(os.environ.get("FFMPEG_BINARY") or "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return str(candidate)
        raise RuntimeError(f"FFMPEG_BINARY does not exist: {candidate}")
    discovered = shutil.which("ffmpeg")
    if not discovered:
        raise RuntimeError("ffmpeg is required to prepare article images")
    return discovered


def webp_dimensions(payload: bytes) -> tuple[int, int] | None:
    if len(payload) < 30 or payload[:4] != b"RIFF" or payload[8:12] != b"WEBP":
        return None
    offset = 12
    while offset + 8 <= len(payload):
        chunk_type = payload[offset : offset + 4]
        chunk_size = int.from_bytes(payload[offset + 4 : offset + 8], "little")
        data_start = offset + 8
        data_end = data_start + chunk_size
        if data_end > len(payload):
            return None
        data = payload[data_start:data_end]
        if chunk_type == b"VP8X" and len(data) >= 10:
            return (
                1 + int.from_bytes(data[4:7], "little"),
                1 + int.from_bytes(data[7:10], "little"),
            )
        if chunk_type == b"VP8 " and len(data) >= 10 and data[3:6] == b"\x9d\x01\x2a":
            return (
                int.from_bytes(data[6:8], "little") & 0x3FFF,
                int.from_bytes(data[8:10], "little") & 0x3FFF,
            )
        if chunk_type == b"VP8L" and len(data) >= 5 and data[0] == 0x2F:
            bits = int.from_bytes(data[1:5], "little")
            return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
        offset = data_end + (chunk_size % 2)
    return None


def convert_webp_to_jpeg(payload: bytes, *, ffmpeg: str) -> bytes:
    dimensions = webp_dimensions(payload)
    if dimensions is None:
        raise RuntimeError("Source image is not a readable WebP")
    width, height = dimensions
    if width < 600 or height < 315:
        raise RuntimeError("Source image is below 600x315")
    ratio = width / height
    target_ratio = JPEG_WIDTH / JPEG_HEIGHT
    if abs(ratio - target_ratio) > 0.08:
        raise RuntimeError(
            f"Source image ratio {ratio:.4f} is too far from target {target_ratio:.4f}"
        )

    completed = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-vf",
            f"scale={JPEG_WIDTH}:{JPEG_HEIGHT}:flags=lanczos",
            "-frames:v",
            "1",
            "-pix_fmt",
            "yuvj420p",
            "-q:v",
            "2",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "pipe:1",
        ],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=60,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg image conversion failed: {detail}")
    jpeg = completed.stdout
    if (
        len(jpeg) < JPEG_MIN_BYTES
        or not jpeg.startswith(b"\xff\xd8")
        or not jpeg.endswith(b"\xff\xd9")
    ):
        raise RuntimeError("ffmpeg did not produce a complete usable JPEG")
    return jpeg


def source_raw_url(policy: dict[str, Any], operation: dict[str, Any]) -> str:
    repository = str(policy["source_repository"])
    commit = str(policy["source_repository_commit"])
    path = quote(str(operation["source_path"]), safe="/")
    return f"https://raw.githubusercontent.com/{repository}/{commit}/{path}"


def materialize_and_verify_sources(
    policy: dict[str, Any],
    *,
    assets_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    assets_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_ffmpeg()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/148 Safari/537.36"
        )
    }
    rows: list[dict[str, Any]] = []
    checked_urls: list[str] = []

    with httpx.Client(
        headers=headers,
        follow_redirects=True,
        timeout=HTTP_TIMEOUT_SECONDS,
    ) as http:
        for operation in policy["operations"]:
            operation_id = str(operation["operation_id"])
            article_url = normalize_url(operation["url"])
            image_url = normalize_url(operation["image_url"])
            raw_url = source_raw_url(policy, operation)

            page_response = http.get(article_url)
            page_response.raise_for_status()
            checked_urls.append(article_url)
            if "text/html" not in page_response.headers.get("content-type", "").lower():
                raise RuntimeError(f"Article is not HTML: {operation_id}")

            metadata = PageMetadata()
            metadata.feed(page_response.text)
            canonical = normalize_url(
                urljoin(article_url, metadata.canonical or metadata.og_url or article_url)
            )
            og_url = normalize_url(urljoin(article_url, metadata.og_url or canonical))
            live_image = normalize_url(urljoin(article_url, metadata.og_image))
            if canonical != article_url or og_url != article_url:
                raise RuntimeError(f"Canonical metadata differs: {operation_id}")
            if live_image != image_url:
                raise RuntimeError(
                    f"Live OG image differs: {operation_id}: {live_image} != {image_url}"
                )
            if not metadata.og_title or len(metadata.og_title.strip()) < 12:
                raise RuntimeError(f"Missing usable og:title: {operation_id}")
            if not metadata.og_description or len(metadata.og_description.strip()) < 60:
                raise RuntimeError(f"Missing usable og:description: {operation_id}")
            if any("noindex" in directive for directive in metadata.robots):
                raise RuntimeError(f"Article is marked noindex: {operation_id}")

            image_response = http.get(image_url)
            image_response.raise_for_status()
            checked_urls.append(image_url)
            if not image_response.headers.get("content-type", "").lower().startswith(
                "image/webp"
            ):
                raise RuntimeError(f"OG image is not served as WebP: {operation_id}")
            image_bytes = image_response.content
            jpeg = convert_webp_to_jpeg(image_bytes, ffmpeg=ffmpeg)
            asset_path = assets_dir / f"{operation_id}.jpg"
            temporary = asset_path.with_suffix(".jpg.tmp")
            temporary.write_bytes(jpeg)
            temporary.replace(asset_path)

            source_response = http.get(raw_url)
            source_response.raise_for_status()
            checked_urls.append(raw_url)
            source_bytes = source_response.content
            if len(source_bytes) < 40:
                raise RuntimeError(f"Pinned source file is unexpectedly small: {operation_id}")

            rows.append(
                {
                    "operation_id": operation_id,
                    "article_url": article_url,
                    "canonical_url": canonical,
                    "og_title": metadata.og_title,
                    "og_description_length": len(metadata.og_description),
                    "image_url": image_url,
                    "image_content_type": image_response.headers.get("content-type"),
                    "image_bytes": len(image_bytes),
                    "image_sha256": bytes_sha(image_bytes),
                    "source_url": raw_url,
                    "source_bytes": len(source_bytes),
                    "source_sha256": bytes_sha(source_bytes),
                    "asset_path": str(asset_path),
                    "asset_bytes": len(jpeg),
                    "asset_sha256": bytes_sha(jpeg),
                    "asset_width": JPEG_WIDTH,
                    "asset_height": JPEG_HEIGHT,
                    "status": "verified",
                }
            )

    if len(checked_urls) != 30 or len(set(checked_urls)) != 30:
        raise RuntimeError("The source audit did not cover 30 unique URLs")
    manifest = {
        "schema_name": "video-manager.vk-lord-god-article-assets",
        "schema_version": 3,
        "generated_at": now_iso(),
        "policy_sha256": policy["policy_sha256"],
        "external_urls_checked": 30,
        "article_pages_verified": 10,
        "source_images_verified": 10,
        "pinned_source_files_verified": 10,
        "items": rows,
    }
    manifest["manifest_sha256"] = canonical_sha(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )
    return rows, manifest


def validate_materialized_asset(
    operation: dict[str, Any],
    assets_by_id: dict[str, dict[str, Any]],
) -> bytes:
    operation_id = str(operation["operation_id"])
    row = assets_by_id.get(operation_id)
    if not isinstance(row, dict):
        raise RuntimeError(f"Missing prepared asset: {operation_id}")
    asset_path = Path(str(row.get("asset_path") or ""))
    if not asset_path.is_file():
        raise RuntimeError(f"Prepared asset file is missing: {operation_id}")
    payload = asset_path.read_bytes()
    if bytes_sha(payload) != row.get("asset_sha256"):
        raise RuntimeError(f"Prepared asset checksum differs: {operation_id}")
    if len(payload) != row.get("asset_bytes"):
        raise RuntimeError(f"Prepared asset size differs: {operation_id}")
    if not payload.startswith(b"\xff\xd8") or not payload.endswith(b"\xff\xd9"):
        raise RuntimeError(f"Prepared asset is not a complete JPEG: {operation_id}")
    return payload


def photo_token(photo: object) -> str | None:
    if not isinstance(photo, dict):
        return None
    owner_id = photo.get("owner_id")
    photo_id = photo.get("id")
    if not isinstance(owner_id, int) or not isinstance(photo_id, int):
        return None
    access_key = str(photo.get("access_key") or "").strip()
    base = f"photo{owner_id}_{photo_id}"
    return f"{base}_{access_key}" if access_key else base


def post_reference(post: dict[str, Any], queue: str) -> dict[str, Any]:
    text = canonical_text(post.get("text"))
    text_urls = sorted(
        {
            normalize_url(match.group(0))
            for match in URL_RE.finditer(text)
            if normalize_url(match.group(0))
        }
    )
    link_urls: list[str] = []
    photo_tokens: list[str] = []
    attachments = post.get("attachments")
    for attachment in attachments if isinstance(attachments, list) else []:
        if not isinstance(attachment, dict):
            continue
        attachment_type = str(attachment.get("type") or "")
        if attachment_type == "photo":
            token = photo_token(attachment.get("photo"))
            if token:
                photo_tokens.append(token)
        elif attachment_type == "link":
            link = attachment.get("link")
            if isinstance(link, dict):
                value = normalize_url(link.get("url") or link.get("target_url"))
                if value:
                    link_urls.append(value)

    owner_id = post.get("owner_id")
    post_id = post.get("id")
    return {
        "queue": queue,
        "owner_id": owner_id if isinstance(owner_id, int) else None,
        "post_id": post_id if isinstance(post_id, int) else None,
        "date": post.get("date") if isinstance(post.get("date"), int) else None,
        "message": text,
        "text_urls": sorted(set(text_urls)),
        "link_urls": sorted(set(link_urls)),
        "photo_tokens": sorted(set(photo_tokens)),
        "has_photo": bool(photo_tokens),
        "url": (
            f"https://vk.ru/wall{owner_id}_{post_id}"
            if isinstance(owner_id, int) and isinstance(post_id, int)
            else None
        ),
    }


def wall_snapshot(
    client: VkApiClient,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return (
        fetch_wall_posts(client, community_id=COMMUNITY_ID, filter_name="owner"),
        fetch_wall_posts(client, community_id=COMMUNITY_ID, filter_name="postponed"),
    )


def index_wall(
    published: list[dict[str, Any]],
    postponed: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    postponed_refs: list[dict[str, Any]] = []
    for queue, posts in (("published", published), ("postponed", postponed)):
        for post in posts:
            reference = post_reference(post, queue)
            if queue == "postponed":
                postponed_refs.append(reference)
            for url in set(reference["text_urls"] + reference["link_urls"]):
                by_url[url].append(reference)
    return dict(by_url), postponed_refs


def exact_reference(
    operation: dict[str, Any],
    reference: dict[str, Any],
    *,
    expected_photo_token: str | None,
) -> bool:
    article_url = normalize_url(operation["url"])
    if reference["message"] != canonical_text(operation["message"]):
        return False
    if article_url not in reference["text_urls"]:
        return False
    if not reference["has_photo"]:
        return False
    if reference["queue"] == "postponed" and reference["date"] != operation["publish_date"]:
        return False
    if expected_photo_token and expected_photo_token not in reference["photo_tokens"]:
        return False
    return True


def fresh_journal(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "video-manager.vk-lord-god-article-wave-journal",
        "schema_version": 3,
        "decision_set_id": DECISION_SET_ID,
        "policy_sha256": policy["policy_sha256"],
        "operations": {},
    }


def load_journal(path: Path, policy: dict[str, Any]) -> dict[str, Any]:
    journal = read_json(path, fresh_journal(policy))
    if not isinstance(journal, dict):
        raise RuntimeError("Invalid local article journal")
    if (
        journal.get("decision_set_id") != DECISION_SET_ID
        or journal.get("policy_sha256") != policy["policy_sha256"]
    ):
        operations = journal.get("operations")
        stages = {
            str(value.get("stage") or "")
            for value in operations.values()
            if isinstance(operations, dict) and isinstance(value, dict)
        }
        if stages - {"", "prepared", "photo_upload_failed", "photo_save_rejected"}:
            raise RuntimeError(
                "Local journal belongs to another plan and contains remote-write state"
            )
        return fresh_journal(policy)
    operations = journal.get("operations")
    if not isinstance(operations, dict):
        raise RuntimeError("Invalid journal operations map")
    return journal


def preflight(
    policy: dict[str, Any],
    published: list[dict[str, Any]],
    postponed: list[dict[str, Any]],
    journal: dict[str, Any],
    *,
    minimum_future_seconds: int = MIN_FUTURE_SECONDS,
) -> dict[str, Any]:
    by_url, postponed_refs = index_wall(published, postponed)
    journal_ops = journal["operations"]
    current = int(datetime.now(UTC).timestamp())
    states: list[dict[str, Any]] = []
    conflicts: list[str] = []

    for operation in policy["operations"]:
        operation_id = str(operation["operation_id"])
        article_url = normalize_url(operation["url"])
        entry = journal_ops.get(operation_id)
        entry = entry if isinstance(entry, dict) else {}
        stage = str(entry.get("stage") or "")
        expected_photo = str(entry.get("photo_token") or "").strip() or None
        references = by_url.get(article_url, [])
        exact = [
            ref
            for ref in references
            if exact_reference(
                operation,
                ref,
                expected_photo_token=expected_photo,
            )
        ]
        nearby = [
            ref
            for ref in postponed_refs
            if ref not in exact
            and isinstance(ref.get("date"), int)
            and abs(int(ref["date"]) - int(operation["publish_date"])) < MIN_GAP_SECONDS
        ]

        if len(exact) == 1 and len(references) == 1 and not nearby:
            state = "already_applied"
            detail = "one exact post with the reviewed text URL and a wall photo exists"
        elif references:
            state = "conflict"
            detail = "article URL already appears in another wall post"
        elif nearby:
            state = "conflict"
            detail = "another postponed post is within the two-hour safety gap"
        elif stage in BLOCKING_JOURNAL_STAGES:
            state = "conflict"
            detail = f"journal stage requires reconciliation: {stage}"
        elif stage == "verified":
            state = "conflict"
            detail = "journal says verified but no exact wall post was found"
        elif int(operation["publish_date"]) <= current + minimum_future_seconds:
            state = "conflict"
            detail = "approved publication time is no longer safely in the future"
        else:
            state = "ready"
            detail = (
                f"resumable from {stage}"
                if stage in RESUMABLE_WITH_PHOTO
                else "article is absent and the surrounding time window is free"
            )

        if state == "conflict":
            conflicts.append(f"{operation_id}: {detail}")
        states.append(
            {
                "operation_id": operation_id,
                "ordinal": operation["ordinal"],
                "article_title": operation["title"],
                "article_url": article_url,
                "publish_at": operation["publish_at"],
                "state": state,
                "detail": detail,
                "journal_stage": stage or None,
                "references": references,
                "nearby_postponed_posts": nearby,
            }
        )

    counts = Counter(item["state"] for item in states)
    return {
        "schema_name": "video-manager.vk-lord-god-article-wave-preflight",
        "schema_version": 3,
        "generated_at": now_iso(),
        "policy_sha256": policy["policy_sha256"],
        "published_wall_posts": len(published),
        "postponed_wall_posts": len(postponed),
        "minimum_gap_minutes": MIN_GAP_SECONDS // 60,
        "total_operations": len(states),
        "ready": counts["ready"],
        "already_applied": counts["already_applied"],
        "conflicts": counts["conflict"],
        "global_conflicts": conflicts,
        "states": states,
    }


def state_fingerprint(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "operation_id": item["operation_id"],
            "state": item["state"],
            "journal_stage": item["journal_stage"],
            "references": item["references"],
            "nearby_postponed_posts": item["nearby_postponed_posts"],
        }
        for item in report["states"]
    ]


def verify_upload_server(read_client: VkApiClient) -> dict[str, Any]:
    response = read_client._call(
        "photos.getWallUploadServer",
        params={"group_id": COMMUNITY_ID},
    )
    upload_url = (
        str(response.get("upload_url") or "").strip()
        if isinstance(response, dict)
        else ""
    )
    parsed = urlsplit(upload_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("photos.getWallUploadServer returned no usable HTTPS URL")
    return {
        "method": "photos.getWallUploadServer",
        "group_id": COMMUNITY_ID,
        "upload_server_host": parsed.netloc,
        "verified": True,
    }


def upload_photo_bytes(upload_url: str, *, operation_id: str, jpeg: bytes) -> dict[str, Any]:
    with httpx.Client(
        follow_redirects=True,
        timeout=UPLOAD_TIMEOUT_SECONDS,
    ) as http:
        response = http.post(
            upload_url,
            files={
                "photo": (
                    f"{operation_id}.jpg",
                    jpeg,
                    "image/jpeg",
                )
            },
        )
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("VK upload server returned a non-object response")
    photo_value = payload.get("photo")
    hash_value = payload.get("hash")
    server_value = payload.get("server")
    if not isinstance(photo_value, str) or not photo_value.strip():
        raise RuntimeError("VK upload response has no photo value")
    if not isinstance(hash_value, str) or not hash_value.strip():
        raise RuntimeError("VK upload response has no hash value")
    if not isinstance(server_value, int):
        raise RuntimeError("VK upload response server value is not an integer")
    return {
        "photo": photo_value,
        "hash": hash_value,
        "server": server_value,
    }


def set_journal_stage(
    journal: dict[str, Any],
    journal_path: Path,
    operation: dict[str, Any],
    stage: str,
    **values: object,
) -> dict[str, Any]:
    operations = journal["operations"]
    operation_id = str(operation["operation_id"])
    entry = operations.get(operation_id)
    if not isinstance(entry, dict):
        entry = {
            "operation_id": operation_id,
            "article_url": operation["url"],
            "publish_date": operation["publish_date"],
            "message_sha256": operation["message_sha256"],
        }
        operations[operation_id] = entry
    entry.update({"stage": stage, "updated_at": now_iso(), **values})
    journal["updated_at"] = now_iso()
    write_json(journal_path, journal)
    return entry


def saved_photo_token(
    mutation_client: VkApiClient,
    upload_payload: dict[str, Any],
) -> str:
    response = mutation_client._call(
        "photos.saveWallPhoto",
        params={
            "group_id": COMMUNITY_ID,
            "photo": str(upload_payload["photo"]),
            "server": int(upload_payload["server"]),
            "hash": str(upload_payload["hash"]),
        },
    )
    photos = (
        [item for item in response if isinstance(item, dict)]
        if isinstance(response, list)
        else []
    )
    if len(photos) != 1:
        raise RuntimeError(f"photos.saveWallPhoto returned {len(photos)} photos")
    token = photo_token(photos[0])
    if not token:
        raise RuntimeError("photos.saveWallPhoto returned no usable photo token")
    if photos[0].get("owner_id") != OWNER_ID:
        raise RuntimeError(
            f"Saved wall photo has unexpected owner: {photos[0].get('owner_id')!r}"
        )
    return token


def prepare_photo_token(
    *,
    operation: dict[str, Any],
    jpeg: bytes,
    read_client: VkApiClient,
    mutation_client: VkApiClient,
    journal: dict[str, Any],
    journal_path: Path,
) -> str:
    operation_id = str(operation["operation_id"])
    entry = journal["operations"].get(operation_id)
    entry = entry if isinstance(entry, dict) else {}
    stage = str(entry.get("stage") or "")
    existing_token = str(entry.get("photo_token") or "").strip()

    if stage in RESUMABLE_WITH_PHOTO and existing_token:
        return existing_token
    if stage in BLOCKING_JOURNAL_STAGES:
        raise RuntimeError(f"Cannot prepare photo from blocking journal stage: {stage}")
    if stage == "photo_uploaded":
        upload_payload = entry.get("upload_payload")
        if not isinstance(upload_payload, dict):
            raise RuntimeError("photo_uploaded journal entry lacks upload payload")
    else:
        set_journal_stage(
            journal,
            journal_path,
            operation,
            "photo_upload_intent",
            asset_sha256=bytes_sha(jpeg),
        )
        server = read_client._call(
            "photos.getWallUploadServer",
            params={"group_id": COMMUNITY_ID},
        )
        upload_url = (
            str(server.get("upload_url") or "").strip()
            if isinstance(server, dict)
            else ""
        )
        parsed = urlsplit(upload_url)
        if parsed.scheme != "https" or not parsed.netloc:
            set_journal_stage(
                journal,
                journal_path,
                operation,
                "photo_upload_failed",
                error="no usable HTTPS upload URL",
            )
            raise RuntimeError("photos.getWallUploadServer returned no usable HTTPS URL")
        try:
            upload_payload = upload_photo_bytes(
                upload_url,
                operation_id=operation_id,
                jpeg=jpeg,
            )
        except Exception as exc:
            set_journal_stage(
                journal,
                journal_path,
                operation,
                "photo_upload_failed",
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        set_journal_stage(
            journal,
            journal_path,
            operation,
            "photo_uploaded",
            upload_payload=upload_payload,
        )

    set_journal_stage(
        journal,
        journal_path,
        operation,
        "photo_save_intent",
    )
    try:
        token = saved_photo_token(mutation_client, upload_payload)
    except VkApiError as exc:
        stage = (
            "photo_save_rejected"
            if exc.code is not None and not exc.retryable
            else "photo_save_unknown"
        )
        set_journal_stage(
            journal,
            journal_path,
            operation,
            stage,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise RuntimeError(
            f"Photo save outcome is {stage}; do not retry blindly: {operation_id}"
        ) from exc
    except Exception as exc:
        set_journal_stage(
            journal,
            journal_path,
            operation,
            "photo_save_unknown",
            error=f"{type(exc).__name__}: {exc}",
        )
        raise RuntimeError(
            f"Photo save outcome is unknown; do not retry blindly: {operation_id}"
        ) from exc

    set_journal_stage(
        journal,
        journal_path,
        operation,
        "photo_saved",
        photo_token=token,
    )
    return token


def response_post_id(response: object) -> int:
    value = (
        response
        if isinstance(response, int)
        else response.get("post_id")
        if isinstance(response, dict)
        else None
    )
    if isinstance(value, int) and value > 0:
        return value
    raise RuntimeError(f"wall.post returned no positive post ID: {response!r}")


def find_exact_post(
    client: VkApiClient,
    operation: dict[str, Any],
    *,
    expected_photo_token: str | None,
    expected_post_id: int | None = None,
) -> dict[str, Any] | None:
    _, postponed = wall_snapshot(client)
    for raw_post in postponed:
        if expected_post_id is not None and raw_post.get("id") != expected_post_id:
            continue
        reference = post_reference(raw_post, "postponed")
        if exact_reference(
            operation,
            reference,
            expected_photo_token=expected_photo_token,
        ):
            return reference
    return None


def wait_for_exact_post(
    client: VkApiClient,
    operation: dict[str, Any],
    *,
    post_id: int,
    photo_token_value: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + POST_WAIT_SECONDS
    last: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        _, postponed = wall_snapshot(client)
        for raw_post in postponed:
            if raw_post.get("owner_id") != OWNER_ID or raw_post.get("id") != post_id:
                continue
            reference = post_reference(raw_post, "postponed")
            last = reference
            if reference["message"] != canonical_text(operation["message"]):
                raise RuntimeError(f"Accepted post text differs: {operation['operation_id']}")
            if reference["date"] != operation["publish_date"]:
                raise RuntimeError(f"Accepted post time differs: {operation['operation_id']}")
            if normalize_url(operation["url"]) not in reference["text_urls"]:
                raise RuntimeError(
                    f"Accepted post text lacks article URL: {operation['operation_id']}"
                )
            if photo_token_value not in reference["photo_tokens"]:
                raise RuntimeError(
                    f"Accepted post has a different wall photo: {operation['operation_id']}"
                )
            return reference
        time.sleep(3)
    if last is None:
        raise RuntimeError(f"Accepted postponed post is not visible after {POST_WAIT_SECONDS}s")
    raise RuntimeError(f"Accepted postponed post is not exact after {POST_WAIT_SECONDS}s")


def submit_wall_post(
    *,
    operation: dict[str, Any],
    photo_token_value: str,
    read_client: VkApiClient,
    mutation_client: VkApiClient,
    journal: dict[str, Any],
    journal_path: Path,
) -> tuple[int, dict[str, Any]]:
    operation_id = str(operation["operation_id"])
    set_journal_stage(
        journal,
        journal_path,
        operation,
        "wall_post_intent",
        photo_token=photo_token_value,
    )
    try:
        response = mutation_client._call(
            "wall.post",
            params={
                "owner_id": OWNER_ID,
                "from_group": True,
                "message": str(operation["message"]),
                "attachments": photo_token_value,
                "publish_date": int(operation["publish_date"]),
                "guid": operation_id,
            },
        )
    except VkApiError as exc:
        explicit = exc.code is not None and not exc.retryable
        stage = "wall_post_rejected" if explicit else "wall_post_unknown"
        set_journal_stage(
            journal,
            journal_path,
            operation,
            stage,
            photo_token=photo_token_value,
            error=f"{type(exc).__name__}: {exc}",
        )
        if not explicit:
            reconciled = find_exact_post(
                read_client,
                operation,
                expected_photo_token=photo_token_value,
            )
            if reconciled and isinstance(reconciled.get("post_id"), int):
                post_id = int(reconciled["post_id"])
                set_journal_stage(
                    journal,
                    journal_path,
                    operation,
                    "verified",
                    photo_token=photo_token_value,
                    post_id=post_id,
                    reconciled_from="wall_post_unknown",
                )
                return post_id, reconciled
        raise RuntimeError(
            f"wall.post outcome is {stage}; do not retry blindly: {operation_id}"
        ) from exc
    except Exception as exc:
        set_journal_stage(
            journal,
            journal_path,
            operation,
            "wall_post_unknown",
            photo_token=photo_token_value,
            error=f"{type(exc).__name__}: {exc}",
        )
        reconciled = find_exact_post(
            read_client,
            operation,
            expected_photo_token=photo_token_value,
        )
        if reconciled and isinstance(reconciled.get("post_id"), int):
            post_id = int(reconciled["post_id"])
            set_journal_stage(
                journal,
                journal_path,
                operation,
                "verified",
                photo_token=photo_token_value,
                post_id=post_id,
                reconciled_from="wall_post_unknown",
            )
            return post_id, reconciled
        raise RuntimeError(
            f"wall.post outcome is unknown; do not retry blindly: {operation_id}"
        ) from exc

    post_id = response_post_id(response)
    set_journal_stage(
        journal,
        journal_path,
        operation,
        "wall_post_accepted",
        photo_token=photo_token_value,
        post_id=post_id,
    )
    try:
        reference = wait_for_exact_post(
            read_client,
            operation,
            post_id=post_id,
            photo_token_value=photo_token_value,
        )
    except Exception as exc:
        set_journal_stage(
            journal,
            journal_path,
            operation,
            "wall_post_accepted_unverified",
            photo_token=photo_token_value,
            post_id=post_id,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise RuntimeError(f"Accepted post requires inspection: {operation_id}") from exc

    set_journal_stage(
        journal,
        journal_path,
        operation,
        "verified",
        photo_token=photo_token_value,
        post_id=post_id,
    )
    return post_id, reference


def review_markdown(policy: dict[str, Any], report: dict[str, Any]) -> str:
    states = {item["operation_id"]: item["state"] for item in report["states"]}
    lines = [
        "# Господь Бог — Сила Моя: 10 ежедневных статей",
        "",
        "- Время: ежедневно в 14:00 UTC+03:00.",
        "- Интервал до другого отложенного поста: не менее двух часов.",
        "- Изображение: отдельная проверенная фотография стены из OG-изображения.",
        "- Ссылка: точный публичный URL находится в тексте поста.",
        "- Порядок: Plan → Canary → ручная проверка → Apply.",
        "",
    ]
    for operation in policy["operations"]:
        lines.extend(
            [
                f"## {operation['ordinal']}. {operation['title']}",
                "",
                f"- Время: `{operation['publish_at']}`",
                f"- Статус: `{states[operation['operation_id']]}`",
                f"- Статья: {operation['url']}",
                f"- Изображение: {operation['image_url']}",
                f"- Источник: `{operation['source_path']}`",
                "",
                str(operation["message"]),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def execute_scope(
    *,
    mode: str,
    policy: dict[str, Any],
    read_client: VkApiClient,
    mutation_client: VkApiClient,
    settings: Any,
    report: dict[str, Any],
    journal: dict[str, Any],
    journal_path: Path,
    assets_manifest: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    if os.environ.get("VCM_ALLOW_WALL_POSTS") != "1":
        raise RuntimeError("Execution requires VCM_ALLOW_WALL_POSTS=1")

    states = {item["operation_id"]: item["state"] for item in report["states"]}
    canary = policy["operations"][0]
    canary_id = str(canary["operation_id"])
    if mode == "canary":
        selected = [canary]
        result_path = output_dir / "canary-result.json"
    elif mode == "apply":
        if states.get(canary_id) != "already_applied":
            raise RuntimeError("Apply requires the verified canary article post")
        selected = policy["operations"][1:]
        result_path = output_dir / "result.json"
    else:
        raise ValueError(f"Unsupported execution mode: {mode}")

    assets_by_id = {
        str(item["operation_id"]): item
        for item in assets_manifest["items"]
        if isinstance(item, dict)
    }
    result: dict[str, Any] = {
        "schema_name": "video-manager.vk-lord-god-article-wave-result",
        "schema_version": 3,
        "mode": mode,
        "status": "running",
        "policy_sha256": policy["policy_sha256"],
        "asset_manifest_sha256": assets_manifest["manifest_sha256"],
        "started_at": now_iso(),
        "operations": [],
    }
    write_json(result_path, result)

    lock_path = settings.data_dir / "locks" / f"vk-wall-{COMMUNITY_ID}.lock"
    with local_vk_write_lock(
        lock_path,
        account=ACCOUNT_ALIAS,
        community_id=COMMUNITY_ID,
        operation=f"{DECISION_SET_ID}-{mode}",
    ):
        locked_published, locked_postponed = wall_snapshot(read_client)
        locked = preflight(policy, locked_published, locked_postponed, journal)
        if locked["conflicts"] or state_fingerprint(locked) != state_fingerprint(report):
            raise RuntimeError("Locked preflight differs from reviewed preflight")
        locked_states = {item["operation_id"]: item["state"] for item in locked["states"]}

        for operation in selected:
            operation_id = str(operation["operation_id"])
            if locked_states[operation_id] == "already_applied":
                result["operations"].append(
                    {"operation_id": operation_id, "status": "already_applied"}
                )
                write_json(result_path, result)
                continue
            if locked_states[operation_id] != "ready":
                raise RuntimeError(f"Operation is not ready: {operation_id}")

            jpeg = validate_materialized_asset(operation, assets_by_id)
            photo = prepare_photo_token(
                operation=operation,
                jpeg=jpeg,
                read_client=read_client,
                mutation_client=mutation_client,
                journal=journal,
                journal_path=journal_path,
            )
            post_id, reference = submit_wall_post(
                operation=operation,
                photo_token_value=photo,
                read_client=read_client,
                mutation_client=mutation_client,
                journal=journal,
                journal_path=journal_path,
            )
            result["operations"].append(
                {
                    "operation_id": operation_id,
                    "post_id": post_id,
                    "photo_token": photo,
                    "status": "verified",
                    "publish_at": operation["publish_at"],
                    "article_url_in_text": True,
                    "wall_photo_verified": bool(reference["has_photo"]),
                }
            )
            write_json(result_path, result)
            print(
                f"SCHEDULED {operation['ordinal']}/10 "
                f"post={OWNER_ID}_{post_id} photo=yes url=yes"
            )
            time.sleep(1)

        final_published, final_postponed = wall_snapshot(read_client)
        final = preflight(
            policy,
            final_published,
            final_postponed,
            journal,
            minimum_future_seconds=0,
        )
        postflight_path = (
            output_dir / "canary-postflight.json"
            if mode == "canary"
            else output_dir / "postflight.json"
        )
        write_json(postflight_path, final)
        expected_applied = 1 if mode == "canary" else 10
        if final["conflicts"] or final["already_applied"] != expected_applied:
            raise RuntimeError(
                f"{mode.capitalize()} postflight verified "
                f"{final['already_applied']} of {expected_applied}"
            )
        if mode == "canary" and final["ready"] != 9:
            raise RuntimeError("Canary did not leave exactly nine ready posts")
        if mode == "apply" and final["ready"] != 0:
            raise RuntimeError("Apply left unscheduled article posts")

        uploaded_now = sum(
            1 for item in result["operations"] if item.get("status") == "verified"
        )
        result.update(
            {
                "status": "completed",
                "completed_at": now_iso(),
                "verified_operations": expected_applied,
                "verified_postponed": expected_applied,
                "verified_posts_with_wall_photos": expected_applied,
                "uploaded_wall_photos_this_run": uploaded_now,
                "verified_article_urls_in_text": expected_applied,
                "conflicts": 0,
                "first_publish_at": policy["summary"]["first_publish_at"],
                "last_publish_at": (
                    canary["publish_at"]
                    if mode == "canary"
                    else policy["summary"]["last_publish_at"]
                ),
            }
        )
        write_json(result_path, result)
    return result


def run(repo: Path, *, mode: str) -> int:
    repo = repo.resolve()
    output_dir = repo / "data" / "vk-wall" / DECISION_SET_ID
    assets_dir = output_dir / "assets"
    output_dir.mkdir(parents=True, exist_ok=True)

    policy = load_policy(repo)
    validate_policy(policy)
    write_json(output_dir / "plan.json", policy)

    source_rows, assets_manifest = materialize_and_verify_sources(
        policy,
        assets_dir=assets_dir,
    )
    write_json(output_dir / "source-audit.json", assets_manifest)
    write_json(output_dir / "asset-manifest.json", assets_manifest)

    settings = get_settings()
    read_client = VkApiClient(
        token_store=VkTokenStore(settings.data_dir),
        account_alias=ACCOUNT_ALIAS,
        api_version=settings.vk_api_version,
        max_attempts=4,
    )
    mutation_client = VkApiClient(
        token_store=VkTokenStore(settings.data_dir),
        account_alias=ACCOUNT_ALIAS,
        api_version=settings.vk_api_version,
        max_attempts=1,
    )
    community = read_client.get_community(COMMUNITY_ID)
    if (
        community.ref.remote_id != str(COMMUNITY_ID)
        or not community.metadata.get("managed_by_token")
    ):
        raise RuntimeError("Stored token does not manage VK community 60805374")

    upload_server_check = verify_upload_server(read_client)
    write_json(output_dir / "vk-photo-preflight.json", upload_server_check)

    journal_path = output_dir / "journal.json"
    journal = load_journal(journal_path, policy)
    write_json(journal_path, journal)

    published, postponed = wall_snapshot(read_client)
    report = preflight(policy, published, postponed, journal)
    write_json(output_dir / "preflight.json", report)
    (output_dir / "plan-review.md").write_text(
        review_markdown(policy, report),
        encoding="utf-8",
    )

    summary = {
        "mode": mode,
        "policy_sha256": policy["policy_sha256"],
        "external_urls_checked": assets_manifest["external_urls_checked"],
        "source_pages_verified": assets_manifest["article_pages_verified"],
        "source_images_verified": assets_manifest["source_images_verified"],
        "pinned_source_files_verified": assets_manifest[
            "pinned_source_files_verified"
        ],
        "prepared_jpeg_assets": len(source_rows),
        "vk_wall_photo_upload_server_verified": upload_server_check["verified"],
        "operations": report["total_operations"],
        "ready": report["ready"],
        "already_applied": report["already_applied"],
        "conflicts": report["conflicts"],
        "postponed_wall_posts_seen": report["postponed_wall_posts"],
        "minimum_gap_minutes": report["minimum_gap_minutes"],
        "first_publish_at": policy["summary"]["first_publish_at"],
        "last_publish_at": policy["summary"]["last_publish_at"],
        "plan_review": str(output_dir / "plan-review.md"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if report["conflicts"]:
        raise RuntimeError("Article queue blocked: " + "; ".join(report["global_conflicts"]))

    if mode == "plan":
        print(
            "READ-ONLY ARTICLE PLAN COMPLETE. "
            "No photo upload, photo save, or wall post was sent."
        )
        return 0

    result = execute_scope(
        mode=mode,
        policy=policy,
        read_client=read_client,
        mutation_client=mutation_client,
        settings=settings,
        report=report,
        journal=journal,
        journal_path=journal_path,
        assets_manifest=assets_manifest,
        output_dir=output_dir,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "mode": mode,
                "verified_operations": result["verified_operations"],
                "verified_posts_with_wall_photos": result[
                    "verified_posts_with_wall_photos"
                ],
                "result_path": str(
                    output_dir
                    / ("canary-result.json" if mode == "canary" else "result.json")
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--canary", action="store_true")
    modes.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    selected_mode = "canary" if args.canary else "apply" if args.execute else "plan"
    return run(args.repo, mode=selected_mode)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        httpx.HTTPError,
        json.JSONDecodeError,
        OSError,
        RuntimeError,
        ValueError,
        VkApiError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
