from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

from .common import (
    HTTP_TIMEOUT_SECONDS,
    JPEG_HEIGHT,
    JPEG_WIDTH,
    PageMetadata,
    bytes_sha,
    canonical_sha,
    convert_webp_to_jpeg,
    find_ffmpeg,
    normalize_url,
    now_iso,
    source_raw_url,
)


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
