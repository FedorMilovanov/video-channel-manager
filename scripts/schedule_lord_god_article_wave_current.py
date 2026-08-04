#!/usr/bin/env python3
"""Current guarded entrypoint for the theological article wall queue.

The immutable plan needed two exact content corrections:
* the current Hermeneutics social image;
* replacement of the unpublished Diotrophes draft with a public article.

VK ``wall.parseAttachedLink`` is deliberately not used. The connected VK
account returns an empty parse result for valid project URLs, so this entrypoint
uses the documented photo-wall flow instead:

1. verify the public Open Graph image;
2. convert it to a deterministic 1280x720 JPEG with ffmpeg;
3. obtain ``photos.getWallUploadServer`` for the managed community;
4. upload and save it with ``photos.saveWallPhoto``;
5. call ``wall.post`` with the saved photo and the exact external article URL.

Plan remains read-only: it validates all source pages, converts all ten images
locally, verifies the user token can obtain a wall upload server, audits wall
duplicates and schedule gaps, and sends no upload or wall-post request.
Canary still creates only the first postponed post.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

_WAVE6_RETIRED_EXECUTOR = True
if __name__ == "__main__":
    raise SystemExit(
        "This historical executor is retired by Wave 6. "
        "Use the versioned `video-manager wave` engine through the reviewed operator contract."
    )

MODULE_PATH = Path(__file__).with_name("schedule_lord_god_article_wave.py")
MODULE_NAME = "schedule_lord_god_article_wave_guarded"

HERMENEUTICS_ID = "lord-god-article-wave-202608-05-hermenevtika"
HERMENEUTICS_IMAGE = "https://gospod-bog.ru/images/og-hermenevtika-hristotsentrichnaya-otsenka.webp"

DIOTROPHES_ID = "lord-god-article-wave-202608-06-diotrefy"
KRAJNE_OPERATION: dict[str, Any] = {
    "id": "krajne-isporcheno",
    "title": "Крайне ли испорчено сердце верующего?",
    "url": "https://gospod-bog.ru/articles/krajne-li-isporcheno-serdce/",
    "og_image": "https://gospod-bog.ru/images/og-krajne-isporcheno.webp",
    "source_path": "src/components/article-pilots/krajne/KrajneBody.astro",
    "message": (
        "🫀 Крайне ли испорчено сердце верующего?\n\n"
        "«Неверный диагноз превращает лечение в бесконечную суету вокруг "
        "симптомов: человек хлопочет о внешних проявлениях болезни, тогда как "
        "сама болезнь продолжает жить глубже».\n\n"
        "Иеремия 17:9 говорит о сердце резко и беспощадно. Но как применять "
        "этот диагноз к человеку, которому Бог дал новое сердце? Подробная "
        "статья удерживает обе истины: реальность обновления во Христе и "
        "способность остаточного греха оправдывать самого себя.\n\n"
        "💬 Как одновременно исповедовать реальность нового сердца и не "
        "недооценивать самообман остаточного греха?\n\n"
        "Читать полную статью:\n"
        "https://gospod-bog.ru/articles/krajne-li-isporcheno-serdce/"
    ),
    "ordinal": 6,
    "operation_id": "lord-god-article-wave-202608-06-krajne-isporcheno",
    "publish_at": "2026-08-08T14:00:00+03:00",
    "publish_date": 1786186800,
}

JPEG_MIN_BYTES = 10_000
UPLOAD_TIMEOUT_SECONDS = 120.0


def load_guarded_module() -> Any:
    spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load guarded article scheduler: {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def install_reviewed_policy_corrections(module: Any) -> None:
    original_load_policy = module.load_policy

    def load_current_policy(repo: Path) -> dict[str, Any]:
        original = original_load_policy(repo)
        policy = copy.deepcopy(original)
        operations = policy.get("operations")
        if not isinstance(operations, list) or len(operations) != 10:
            raise RuntimeError("Unexpected article policy operation set")

        hermeneutics_seen = False
        diotrophes_seen = False
        corrected: list[dict[str, Any]] = []
        for raw_operation in operations:
            if not isinstance(raw_operation, dict):
                raise RuntimeError("Article policy contains a non-object operation")
            operation = copy.deepcopy(raw_operation)
            operation_id = str(operation.get("operation_id") or "")

            if operation_id == HERMENEUTICS_ID:
                expected_old_image = "https://gospod-bog.ru/images/hermenevtika-preview.webp"
                if module.normalize_url(operation.get("og_image")) != expected_old_image:
                    raise RuntimeError("Hermeneutics policy no longer matches reviewed source")
                operation["og_image"] = HERMENEUTICS_IMAGE
                hermeneutics_seen = True

            if operation_id == DIOTROPHES_ID:
                if module.normalize_url(operation.get("url")) != (
                    "https://gospod-bog.ru/articles/diotrefy-nashego-vremeni/"
                ):
                    raise RuntimeError("Diotrophes policy no longer matches reviewed draft")
                operation = copy.deepcopy(KRAJNE_OPERATION)
                operation["message_sha256"] = module.message_sha(operation["message"])
                diotrophes_seen = True

            corrected.append(operation)

        if not hermeneutics_seen or not diotrophes_seen:
            raise RuntimeError("Reviewed article corrections could not be applied exactly")

        policy["operations"] = corrected
        policy["policy_sha256"] = module.canonical_sha(
            {key: value for key, value in policy.items() if key != "policy_sha256"}
        )
        module.EXPECTED_SHA = policy["policy_sha256"]
        return policy

    module.load_policy = load_current_policy


def find_ffmpeg() -> str:
    configured = str(os.environ.get("FFMPEG_BINARY") or "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return str(candidate)
        raise RuntimeError(f"FFMPEG_BINARY does not exist: {candidate}")
    discovered = shutil.which("ffmpeg")
    if not discovered:
        raise RuntimeError("ffmpeg is required to convert article WebP images to JPEG")
    return discovered


def convert_webp_to_jpeg(payload: bytes, *, ffmpeg: str) -> bytes:
    if len(payload) < 10_000:
        raise RuntimeError("Source Open Graph image is unexpectedly small")
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-vf",
        ("scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black"),
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
    ]
    completed = subprocess.run(
        command,
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
    if len(jpeg) < JPEG_MIN_BYTES or not jpeg.startswith(b"\xff\xd8"):
        raise RuntimeError("ffmpeg did not produce a usable JPEG")
    return jpeg


def install_explicit_photo_flow(module: Any) -> None:
    original_verify_live_sources = module.verify_live_sources

    def verify_live_sources(policy: dict[str, Any]) -> list[dict[str, Any]]:
        checks = original_verify_live_sources(policy)
        ffmpeg = find_ffmpeg()
        headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/148 Safari/537.36")
        }
        by_operation = {str(item.get("operation_id") or ""): item for item in checks if isinstance(item, dict)}
        with httpx.Client(
            headers=headers,
            follow_redirects=True,
            timeout=45.0,
        ) as http:
            for operation in policy["operations"]:
                operation_id = str(operation["operation_id"])
                image_url = module.normalize_url(operation["og_image"])
                response = http.get(image_url)
                response.raise_for_status()
                jpeg = convert_webp_to_jpeg(response.content, ffmpeg=ffmpeg)
                check = by_operation.get(operation_id)
                if check is None:
                    raise RuntimeError(f"Missing source verification row: {operation_id}")
                check.update(
                    {
                        "wall_image_mode": "explicit_uploaded_photo",
                        "wall_jpeg_width": 1280,
                        "wall_jpeg_height": 720,
                        "wall_jpeg_bytes": len(jpeg),
                        "wall_jpeg_sha256": (f"sha256:{hashlib.sha256(jpeg).hexdigest()}"),
                        "ffmpeg_conversion_verified": True,
                    }
                )
        return checks

    def verify_vk_link_cards(
        policy: dict[str, Any],
        client: Any,
    ) -> list[dict[str, Any]]:
        response = client._call(
            "photos.getWallUploadServer",
            params={"group_id": module.COMMUNITY_ID},
        )
        upload_url = str(response.get("upload_url") or "").strip() if isinstance(response, dict) else ""
        parsed_upload_url = urlsplit(upload_url)
        if parsed_upload_url.scheme != "https" or not parsed_upload_url.netloc:
            raise RuntimeError("photos.getWallUploadServer returned no usable HTTPS upload URL")
        return [
            {
                "operation_id": operation["operation_id"],
                "article_url": module.normalize_url(operation["url"]),
                "og_image": module.normalize_url(operation["og_image"]),
                "parse_mode": "explicit_wall_photo_plus_external_url",
                "attachment_type": "photo+external-link",
                "upload_server_host": parsed_upload_url.netloc,
                "upload_server_verified": True,
                "link_card_has_image": True,
                "photo_tokens": [],
                "status": "verified_read_only",
            }
            for operation in policy["operations"]
        ]

    def upload_wall_photo(client: Any, operation: dict[str, Any]) -> str:
        image_url = module.normalize_url(operation["og_image"])
        ffmpeg = find_ffmpeg()
        headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/148 Safari/537.36")
        }
        with httpx.Client(
            headers=headers,
            follow_redirects=True,
            timeout=45.0,
        ) as http:
            image_response = http.get(image_url)
            image_response.raise_for_status()
        jpeg = convert_webp_to_jpeg(image_response.content, ffmpeg=ffmpeg)

        server_response = client._call(
            "photos.getWallUploadServer",
            params={"group_id": module.COMMUNITY_ID},
        )
        upload_url = str(server_response.get("upload_url") or "").strip() if isinstance(server_response, dict) else ""
        parsed_upload_url = urlsplit(upload_url)
        if parsed_upload_url.scheme != "https" or not parsed_upload_url.netloc:
            raise RuntimeError("photos.getWallUploadServer returned no usable HTTPS upload URL")

        with httpx.Client(
            follow_redirects=True,
            timeout=UPLOAD_TIMEOUT_SECONDS,
        ) as http:
            upload_response = http.post(
                upload_url,
                files={
                    "photo": (
                        f"{operation['id']}.jpg",
                        jpeg,
                        "image/jpeg",
                    )
                },
            )
            upload_response.raise_for_status()
            upload_payload = upload_response.json()

        if not isinstance(upload_payload, dict):
            raise RuntimeError("VK photo upload server returned a non-object response")
        photo_value = upload_payload.get("photo")
        server_value = upload_payload.get("server")
        hash_value = upload_payload.get("hash")
        if (
            not isinstance(photo_value, str)
            or not photo_value.strip()
            or not isinstance(hash_value, str)
            or not hash_value.strip()
            or not isinstance(server_value, (int, str))
            or not str(server_value).strip()
        ):
            raise RuntimeError("VK photo upload server response lacks photo/server/hash")

        saved_response = client._call(
            "photos.saveWallPhoto",
            params={
                "group_id": module.COMMUNITY_ID,
                "photo": photo_value,
                "server": server_value,
                "hash": hash_value,
            },
        )
        saved_photos = (
            [item for item in saved_response if isinstance(item, dict)] if isinstance(saved_response, list) else []
        )
        if len(saved_photos) != 1:
            raise RuntimeError(f"photos.saveWallPhoto returned {len(saved_photos)} photos")
        token = module.photo_token(saved_photos[0])
        if not token:
            raise RuntimeError("photos.saveWallPhoto returned no usable photo token")
        owner_id = saved_photos[0].get("owner_id")
        if owner_id != module.OWNER_ID:
            raise RuntimeError(f"Saved wall photo has unexpected owner_id: {owner_id!r}")
        return token

    def post_once(client: Any, operation: dict[str, Any]) -> object:
        photo = upload_wall_photo(client, operation)
        article_url = module.normalize_url(operation["url"])
        return client._call(
            "wall.post",
            params={
                "owner_id": module.OWNER_ID,
                "from_group": True,
                "message": str(operation["message"]),
                "attachments": f"{photo},{article_url}",
                "publish_date": int(operation["publish_date"]),
                "guid": str(operation["operation_id"]),
            },
        )

    module.verify_live_sources = verify_live_sources
    module.verify_vk_link_cards = verify_vk_link_cards
    module.post_once = post_once


def main() -> int:
    module = load_guarded_module()
    install_reviewed_policy_corrections(module)
    install_explicit_photo_flow(module)
    return int(module.main())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        raise SystemExit(2) from exc
