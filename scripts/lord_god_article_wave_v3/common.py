from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

PROJECT_KEY = "lord-god-strength"
COMMUNITY_ID = 60805374
OWNER_ID = -60805374
ACCOUNT_ALIAS = "legendary-poet"  # Shared credential alias only.
DECISION_SET_ID = "lord-god-article-wave-v3-202608"
POLICY_PATH = Path("content/policies/lord-god-article-wave-v3-202608.json")
EXPECTED_POLICY_SHA = "sha256:5592f3e9089fdc6395cd2b2f0d10fb275a30aa5791041a18f1e9003f6c588ebf"
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
PHOTO_TOKEN_RE = re.compile(r"^(photo-?\d+_\d+)(?:_.+)?$")
TRAILING_URL_PUNCTUATION = ".,;:!?)]}»”\""
BLOCKING_JOURNAL_STAGES = frozenset(
    {
        "photo_save_intent",
        "photo_save_rejected",
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
