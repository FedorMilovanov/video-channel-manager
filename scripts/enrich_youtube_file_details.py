#!/usr/bin/env python3
"""Enrich an AuditPackage with owner-only YouTube file geometry.

The script performs read-only videos.list calls and writes a new local JSON file.
It never changes videos, playlists, or channel metadata.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.youtube import InstalledClientConfig, TokenStore, YouTubeApiClient


def chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit_package", type=Path)
    parser.add_argument("--account", "-a", default="default")
    parser.add_argument("--client-secret", type=Path)
    parser.add_argument("--output", "-o", type=Path)
    args = parser.parse_args()

    try:
        payload = json.loads(args.audit_package.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if not isinstance(payload, dict) or payload.get("schema_name") != "video-manager.audit-package":
        parser.error("Input is not a video-manager AuditPackage")

    videos = payload.get("videos")
    if not isinstance(videos, list):
        parser.error("AuditPackage videos field is missing")

    settings = get_settings()
    config = InstalledClientConfig.from_file(args.client_secret or settings.youtube_client_secret_file)
    store = TokenStore(settings.data_dir)
    client = YouTubeApiClient(client_config=config, token_store=store, account_alias=args.account)

    video_ids: list[str] = []
    for video in videos:
        if not isinstance(video, dict):
            continue
        ref = video.get("ref")
        if isinstance(ref, dict) and ref.get("remote_id"):
            video_ids.append(str(ref["remote_id"]))

    details_by_id: dict[str, dict[str, Any]] = {}
    for batch in chunks(video_ids, 50):
        response = client._get(  # noqa: SLF001 - temporary owner-only enrichment utility
            "videos",
            params={
                "part": "fileDetails,processingDetails",
                "id": ",".join(batch),
            },
        )
        items = response.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("id"):
                details_by_id[str(item["id"])] = item

    enriched = 0
    for video in videos:
        if not isinstance(video, dict):
            continue
        ref = video.get("ref")
        video_id = str(ref.get("remote_id") or "") if isinstance(ref, dict) else ""
        details = details_by_id.get(video_id)
        if details is None:
            continue
        metadata = video.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
            video["metadata"] = metadata
        for key in ("fileDetails", "processingDetails"):
            value = details.get(key)
            if isinstance(value, dict):
                metadata[key] = value
        if "fileDetails" in metadata:
            enriched += 1

    package_metadata = payload.setdefault("metadata", {})
    if not isinstance(package_metadata, dict):
        package_metadata = {}
        payload["metadata"] = package_metadata
    package_metadata["owner_file_details_enriched"] = True
    package_metadata["owner_file_details_count"] = enriched

    output = args.output or args.audit_package.with_name(f"{args.audit_package.stem}-file-details.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Enriched file details for {enriched}/{len(video_ids)} videos -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
