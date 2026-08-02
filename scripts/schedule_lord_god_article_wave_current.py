#!/usr/bin/env python3
"""Current guarded entrypoint for the theological article wall queue.

The immutable queue was reviewed with one earlier Open Graph image for the
Hermeneutics article. The live site and its current source now use a newer,
reviewed image. This wrapper accepts only that exact metadata transition while
preserving every other policy, schedule, text, VK-card, duplicate, and canary
guard from ``schedule_lord_god_article_wave.py``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

MODULE_PATH = Path(__file__).with_name("schedule_lord_god_article_wave.py")
MODULE_NAME = "schedule_lord_god_article_wave_guarded"

REVIEWED_OG_TRANSITIONS: dict[str, tuple[str, str]] = {
    "lord-god-article-wave-202608-05-hermenevtika": (
        "https://gospod-bog.ru/images/hermenevtika-preview.webp",
        "https://gospod-bog.ru/images/og-hermenevtika-hristotsentrichnaya-otsenka.webp",
    ),
}


def load_guarded_module() -> Any:
    spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load guarded article scheduler: {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def install_reviewed_source_verifier(module: Any) -> None:
    def verify_live_sources(policy: dict[str, Any]) -> list[dict[str, Any]]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/148 Safari/537.36"
        }
        checks: list[dict[str, Any]] = []
        with httpx.Client(headers=headers, follow_redirects=True, timeout=45.0) as http:
            for operation in policy["operations"]:
                operation_id = str(operation["operation_id"])
                expected_url = module.normalize_url(operation["url"])
                policy_image = module.normalize_url(operation["og_image"])

                page_response = http.get(expected_url)
                page_response.raise_for_status()
                content_type = page_response.headers.get("content-type", "").lower()
                if "text/html" not in content_type:
                    raise RuntimeError(f"Article is not HTML: {operation_id}")

                metadata = module.PageMetadata()
                metadata.feed(page_response.text)
                canonical = module.normalize_url(
                    urljoin(expected_url, metadata.canonical or metadata.og_url or expected_url)
                )
                og_url = module.normalize_url(urljoin(expected_url, metadata.og_url or canonical))
                live_image = module.normalize_url(urljoin(expected_url, metadata.og_image))

                if canonical != expected_url or og_url != expected_url:
                    raise RuntimeError(f"Live canonical metadata differs: {operation_id}")

                metadata_drift = live_image != policy_image
                reviewed_transition = REVIEWED_OG_TRANSITIONS.get(operation_id)
                if metadata_drift:
                    if reviewed_transition is None:
                        raise RuntimeError(f"Unreviewed live OG image differs: {operation_id}")
                    reviewed_from = module.normalize_url(reviewed_transition[0])
                    reviewed_to = module.normalize_url(reviewed_transition[1])
                    if policy_image != reviewed_from or live_image != reviewed_to:
                        raise RuntimeError(f"Live OG image differs from reviewed transition: {operation_id}")

                if not live_image.startswith("https://gospod-bog.ru/images/"):
                    raise RuntimeError(f"OG image is outside the project image host: {operation_id}")
                if not live_image.endswith(".webp"):
                    raise RuntimeError(f"OG image is not a WebP URL: {operation_id}")
                if not metadata.og_title or len(metadata.og_title.strip()) < 12:
                    raise RuntimeError(f"Missing usable og:title: {operation_id}")
                if not metadata.og_description or len(metadata.og_description.strip()) < 60:
                    raise RuntimeError(f"Missing usable og:description: {operation_id}")
                if any("noindex" in directive for directive in metadata.robots):
                    raise RuntimeError(f"Article is marked noindex: {operation_id}")

                image_response = http.get(live_image)
                image_response.raise_for_status()
                image_type = image_response.headers.get("content-type", "").lower()
                if not image_type.startswith("image/webp"):
                    raise RuntimeError(f"OG image is not served as WebP: {operation_id}")
                image_bytes = image_response.content
                if len(image_bytes) < 10_000:
                    raise RuntimeError(f"OG image is unexpectedly small: {operation_id}")
                dimensions = module.webp_dimensions(image_bytes)
                if dimensions is None:
                    raise RuntimeError(f"Cannot read WebP dimensions: {operation_id}")
                width, height = dimensions
                if width < 600 or height < 315:
                    raise RuntimeError(f"OG image is below 600x315: {operation_id}")
                ratio = width / height
                if not 1.45 <= ratio <= 2.15:
                    raise RuntimeError(f"OG image aspect ratio is unsuitable: {operation_id}")

                checks.append(
                    {
                        "operation_id": operation_id,
                        "article_url": expected_url,
                        "canonical_url": canonical,
                        "og_title": metadata.og_title,
                        "og_description_length": len(metadata.og_description),
                        "policy_og_image": policy_image,
                        "resolved_og_image": live_image,
                        "metadata_drift": metadata_drift,
                        "metadata_drift_reviewed": metadata_drift,
                        "og_image_width": width,
                        "og_image_height": height,
                        "og_image_bytes": len(image_bytes),
                        "og_image_sha256": f"sha256:{hashlib.sha256(image_bytes).hexdigest()}",
                        "status": (
                            "verified_with_reviewed_metadata_drift"
                            if metadata_drift
                            else "verified"
                        ),
                    }
                )
        return checks

    module.verify_live_sources = verify_live_sources


def main() -> int:
    module = load_guarded_module()
    install_reviewed_source_verifier(module)
    return int(module.main())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        raise SystemExit(2) from exc
