from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin

import httpx

from .common import (
    HTTP_TIMEOUT_SECONDS,
    JPEG_HEIGHT,
    JPEG_WIDTH,
    PageMetadata,
    bytes_sha,
    canonical_sha,
    canonical_text,
    contract_identity,
    convert_webp_to_jpeg,
    find_ffmpeg,
    metadata_raw_url,
    normalize_url,
    now_iso,
    source_raw_url,
)


def _conflict(row: dict[str, Any], code: str, detail: str) -> None:
    conflicts = row.setdefault("conflicts", [])
    if isinstance(conflicts, list):
        conflicts.append({"code": code, "detail": detail})


def _response_or_conflict(
    http: httpx.Client,
    *,
    url: str,
    row: dict[str, Any],
    stage: str,
    checked_urls: list[str],
) -> httpx.Response | None:
    checked_urls.append(url)
    try:
        response = http.get(url)
        response.raise_for_status()
        return response
    except httpx.HTTPError as exc:
        _conflict(row, f"{stage}_http_error", str(exc))
        return None


def _decode_utf8(
    payload: bytes,
    *,
    row: dict[str, Any],
    stage: str,
) -> str | None:
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        _conflict(row, f"{stage}_not_utf8", str(exc))
        return None


def _metadata_from_text(
    text: str,
    *,
    row: dict[str, Any],
    stage: str,
) -> PageMetadata | None:
    metadata = PageMetadata()
    try:
        metadata.feed(text)
    except Exception as exc:  # HTMLParser can surface malformed authored markup.
        _conflict(row, f"{stage}_parse_error", str(exc))
        return None
    return metadata


def _verify_metadata(
    metadata: PageMetadata,
    *,
    article_url: str,
    image_url: str,
    row: dict[str, Any],
    stage: str,
) -> bool:
    valid = True
    canonical = normalize_url(
        urljoin(article_url, metadata.canonical or metadata.og_url or article_url)
    )
    og_url = normalize_url(urljoin(article_url, metadata.og_url or canonical))
    og_image = normalize_url(urljoin(article_url, metadata.og_image))

    row[f"{stage}_canonical_url"] = canonical
    row[f"{stage}_og_url"] = og_url
    row[f"{stage}_og_image"] = og_image
    row[f"{stage}_og_title"] = metadata.og_title
    row[f"{stage}_og_description"] = metadata.og_description
    row[f"{stage}_og_description_length"] = len(metadata.og_description)

    if canonical != article_url:
        _conflict(
            row,
            f"{stage}_canonical_mismatch",
            f"{canonical} != {article_url}",
        )
        valid = False
    if og_url != article_url:
        _conflict(row, f"{stage}_og_url_mismatch", f"{og_url} != {article_url}")
        valid = False
    if og_image != image_url:
        _conflict(row, f"{stage}_og_image_mismatch", f"{og_image} != {image_url}")
        valid = False
    if not metadata.og_title or len(metadata.og_title.strip()) < 12:
        _conflict(row, f"{stage}_missing_og_title", "No usable og:title")
        valid = False
    if not metadata.og_description or len(metadata.og_description.strip()) < 60:
        _conflict(
            row,
            f"{stage}_missing_og_description",
            "No usable og:description",
        )
        valid = False
    if any("noindex" in directive for directive in metadata.robots):
        _conflict(row, f"{stage}_noindex", "Page metadata contains noindex")
        valid = False
    return valid


def _compare_live_and_pinned_metadata(
    live: PageMetadata,
    pinned: PageMetadata,
    *,
    row: dict[str, Any],
) -> bool:
    valid = True
    comparisons = {
        "og_title": (
            canonical_text(live.og_title),
            canonical_text(pinned.og_title),
        ),
        "og_description": (
            canonical_text(live.og_description),
            canonical_text(pinned.og_description),
        ),
    }
    for name, (live_value, pinned_value) in comparisons.items():
        if live_value != pinned_value:
            _conflict(
                row,
                f"live_metadata_{name}_differs_from_pinned_source",
                f"live={live_value!r}; pinned={pinned_value!r}",
            )
            valid = False
    return valid


def _verify_markers(
    text: str,
    markers: list[str],
    *,
    row: dict[str, Any],
    stage: str,
) -> bool:
    missing = [marker for marker in markers if marker not in text]
    row[f"{stage}_markers_expected"] = markers
    row[f"{stage}_markers_missing"] = missing
    if missing:
        _conflict(row, f"{stage}_markers_missing", repr(missing))
        return False
    return True


def materialize_and_verify_sources(
    policy: dict[str, Any],
    *,
    assets_dir: Path,
    client_factory: Callable[..., httpx.Client] = httpx.Client,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    assets_dir.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/148 Safari/537.36"
        )
    }
    rows: list[dict[str, Any]] = []
    checked_urls: list[str] = []
    global_conflicts: list[dict[str, str]] = []

    try:
        ffmpeg = find_ffmpeg()
    except RuntimeError as exc:
        ffmpeg = None
        global_conflicts.append({"code": "ffmpeg_unavailable", "detail": str(exc)})

    with client_factory(
        headers=headers,
        follow_redirects=True,
        timeout=HTTP_TIMEOUT_SECONDS,
    ) as http:
        for operation in policy["operations"]:
            operation_id = str(operation["operation_id"])
            article_url = normalize_url(operation["url"])
            image_url = normalize_url(operation["image_url"])
            content_url = source_raw_url(policy, operation)
            metadata_url = metadata_raw_url(policy, operation)
            source_markers = [str(value) for value in operation["source_markers"]]
            row: dict[str, Any] = {
                "operation_id": operation_id,
                "article_url": article_url,
                "image_url": image_url,
                "content_source_path": str(operation["source_path"]),
                "content_source_url": content_url,
                "metadata_source_path": str(operation["metadata_source_path"]),
                "metadata_source_url": metadata_url,
                "legacy_policy_image_url": operation.get("legacy_policy_image_url"),
                "legacy_policy_source_path": operation.get(
                    "legacy_policy_source_path"
                ),
                "legacy_policy_source_markers": operation.get(
                    "legacy_policy_source_markers"
                ),
                "conflicts": [],
                "checks": {
                    "live_page_verified": False,
                    "live_content_markers_verified": False,
                    "live_image_verified": False,
                    "content_source_verified": False,
                    "metadata_source_verified": False,
                    "live_metadata_matches_pinned_source": False,
                    "jpeg_asset_prepared": False,
                },
            }
            live_metadata: PageMetadata | None = None
            pinned_metadata: PageMetadata | None = None

            page_response = _response_or_conflict(
                http,
                url=article_url,
                row=row,
                stage="live_page",
                checked_urls=checked_urls,
            )
            if page_response is not None:
                content_type = page_response.headers.get("content-type", "")
                row["live_page_content_type"] = content_type
                if "text/html" not in content_type.lower():
                    _conflict(
                        row,
                        "live_page_not_html",
                        f"Unexpected content-type: {content_type}",
                    )
                else:
                    live_metadata = _metadata_from_text(
                        page_response.text,
                        row=row,
                        stage="live_page",
                    )
                    if live_metadata is not None and _verify_metadata(
                        live_metadata,
                        article_url=article_url,
                        image_url=image_url,
                        row=row,
                        stage="live_page",
                    ):
                        row["checks"]["live_page_verified"] = True
                    if _verify_markers(
                        page_response.text,
                        source_markers,
                        row=row,
                        stage="live_content",
                    ):
                        row["checks"]["live_content_markers_verified"] = True

            metadata_response = _response_or_conflict(
                http,
                url=metadata_url,
                row=row,
                stage="metadata_source",
                checked_urls=checked_urls,
            )
            if metadata_response is not None:
                row["metadata_source_bytes"] = len(metadata_response.content)
                row["metadata_source_sha256"] = bytes_sha(metadata_response.content)
                metadata_text = _decode_utf8(
                    metadata_response.content,
                    row=row,
                    stage="metadata_source",
                )
                if metadata_text is not None:
                    pinned_metadata = _metadata_from_text(
                        metadata_text,
                        row=row,
                        stage="metadata_source",
                    )
                    if pinned_metadata is not None and _verify_metadata(
                        pinned_metadata,
                        article_url=article_url,
                        image_url=image_url,
                        row=row,
                        stage="metadata_source",
                    ):
                        row["checks"]["metadata_source_verified"] = True

            if live_metadata is not None and pinned_metadata is not None:
                if _compare_live_and_pinned_metadata(
                    live_metadata,
                    pinned_metadata,
                    row=row,
                ):
                    row["checks"]["live_metadata_matches_pinned_source"] = True

            image_response = _response_or_conflict(
                http,
                url=image_url,
                row=row,
                stage="live_image",
                checked_urls=checked_urls,
            )
            if image_response is not None:
                image_content_type = image_response.headers.get("content-type", "")
                image_bytes = image_response.content
                row["image_content_type"] = image_content_type
                row["image_bytes"] = len(image_bytes)
                row["image_sha256"] = bytes_sha(image_bytes)
                if not image_content_type.lower().startswith("image/webp"):
                    _conflict(
                        row,
                        "live_image_not_webp",
                        f"Unexpected content-type: {image_content_type}",
                    )
                elif ffmpeg is None:
                    _conflict(
                        row,
                        "jpeg_conversion_unavailable",
                        "ffmpeg is unavailable",
                    )
                else:
                    try:
                        jpeg = convert_webp_to_jpeg(image_bytes, ffmpeg=ffmpeg)
                    except RuntimeError as exc:
                        _conflict(row, "jpeg_conversion_failed", str(exc))
                    else:
                        asset_path = assets_dir / f"{operation_id}.jpg"
                        temporary = asset_path.with_suffix(".jpg.tmp")
                        temporary.write_bytes(jpeg)
                        temporary.replace(asset_path)
                        row.update(
                            {
                                "asset_path": str(asset_path),
                                "asset_bytes": len(jpeg),
                                "asset_sha256": bytes_sha(jpeg),
                                "asset_width": JPEG_WIDTH,
                                "asset_height": JPEG_HEIGHT,
                            }
                        )
                        row["checks"]["live_image_verified"] = True
                        row["checks"]["jpeg_asset_prepared"] = True

            content_response = _response_or_conflict(
                http,
                url=content_url,
                row=row,
                stage="content_source",
                checked_urls=checked_urls,
            )
            if content_response is not None:
                source_bytes = content_response.content
                row["content_source_bytes"] = len(source_bytes)
                row["content_source_sha256"] = bytes_sha(source_bytes)
                if len(source_bytes) < 40:
                    _conflict(
                        row,
                        "content_source_too_small",
                        f"Only {len(source_bytes)} bytes",
                    )
                source_text = _decode_utf8(
                    source_bytes,
                    row=row,
                    stage="content_source",
                )
                if source_text is not None and _verify_markers(
                    source_text,
                    source_markers,
                    row=row,
                    stage="content_source",
                ):
                    if len(source_bytes) >= 40:
                        row["checks"]["content_source_verified"] = True

            row_conflicts = row["conflicts"]
            row["status"] = "verified" if not row_conflicts else "conflict"
            rows.append(row)

    expected_urls = {
        url
        for operation in policy["operations"]
        for url in (
            normalize_url(operation["url"]),
            normalize_url(operation["image_url"]),
            source_raw_url(policy, operation),
            metadata_raw_url(policy, operation),
        )
    }
    if len(expected_urls) != 40:
        global_conflicts.append(
            {
                "code": "external_resource_contract_not_unique",
                "detail": f"Expected 40 unique resources, found {len(expected_urls)}",
            }
        )
    checked_unique = len(set(checked_urls))
    if checked_unique != 40:
        global_conflicts.append(
            {
                "code": "external_resource_audit_incomplete",
                "detail": f"Attempted {checked_unique} of 40 unique resources",
            }
        )

    def verified(check: str) -> int:
        return sum(bool(row["checks"].get(check)) for row in rows)

    item_conflicts = sum(1 for row in rows if row["status"] == "conflict")
    finding_count = sum(len(row["conflicts"]) for row in rows) + len(
        global_conflicts
    )
    manifest: dict[str, Any] = {
        "schema_name": "video-manager.vk-lord-god-article-assets",
        "schema_version": 4,
        "generated_at": now_iso(),
        "policy_sha256": policy["policy_sha256"],
        "source_contract_sha256": policy["source_contract_sha256"],
        "execution_contract_sha256": contract_identity(policy),
        "status": "verified" if finding_count == 0 else "blocked",
        "expected_external_resources": 40,
        "external_urls_checked": checked_unique,
        "article_pages_verified": verified("live_page_verified"),
        "live_content_markers_verified": verified(
            "live_content_markers_verified"
        ),
        "source_images_verified": verified("live_image_verified"),
        "pinned_source_files_verified": verified("content_source_verified"),
        "pinned_metadata_files_verified": verified("metadata_source_verified"),
        "live_metadata_matches_pinned_source": verified(
            "live_metadata_matches_pinned_source"
        ),
        "prepared_jpeg_assets": verified("jpeg_asset_prepared"),
        "conflicts": finding_count,
        "conflicting_operations": item_conflicts,
        "global_conflicts": global_conflicts,
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
    if row.get("status") != "verified":
        raise RuntimeError(f"Prepared asset source audit is not verified: {operation_id}")
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
