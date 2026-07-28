from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore
from video_channel_manager.platforms.vk.wall_content_audit import (
    build_wall_content_audit,
    fetch_wall_posts,
    render_wall_content_audit_markdown,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only audit of published and postponed VK wall posts.")
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--community", type=int, default=235216998)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _package(bundle_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(bundle_dir.iterdir(), key=lambda item: item.name):
            if path.is_file():
                archive.write(path, arcname=path.name)


def _manifest(bundle_dir: Path, *, community_id: int, audit: dict[str, Any]) -> dict[str, Any]:
    files = []
    for path in sorted(bundle_dir.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != "manifest.json":
            files.append(
                {
                    "name": path.name,
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256_file(path),
                }
            )
    return {
        "schema_name": "video-manager.vk-wall-content-audit-handoff",
        "schema_version": 1,
        "status": audit["status"],
        "mode": "read-only",
        "community_id": community_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "audit_sha256": audit["audit_sha256"],
        "summary": audit["summary"],
        "files": files,
    }


def run(args: argparse.Namespace) -> Path:
    if args.community <= 0:
        raise ValueError("--community must be a positive VK community ID")

    settings = get_settings()
    output_dir = args.output_dir or settings.data_dir / "handoffs"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    bundle_name = f"vk-wall-content-audit-{stamp}"
    bundle_dir = output_dir / bundle_name
    zip_path = output_dir / f"{bundle_name}.zip"
    bundle_dir.mkdir(parents=True, exist_ok=False)

    store = VkTokenStore(settings.data_dir)
    client = VkApiClient(
        token_store=store,
        account_alias=args.account,
        api_version=settings.vk_api_version,
    )
    community = client.get_community(args.community)
    if int(community.ref.channel_id) != args.community or not bool(community.metadata.get("managed_by_token")):
        raise ValueError("The VK token does not manage the requested community")

    videos = [item.model_dump(mode="json") for item in client.list_videos(args.community)]
    published_posts = fetch_wall_posts(client, community_id=args.community, filter_name="owner")
    postponed_posts = fetch_wall_posts(client, community_id=args.community, filter_name="postponed")
    audit = build_wall_content_audit(
        community_id=args.community,
        videos=videos,
        published_posts=published_posts,
        postponed_posts=postponed_posts,
    )

    _write_json(bundle_dir / "00-videos.json", videos)
    _write_json(bundle_dir / "01-published-wall-posts.json", published_posts)
    _write_json(bundle_dir / "02-postponed-wall-posts.json", postponed_posts)
    _write_json(bundle_dir / "03-wall-content-audit.json", audit)
    (bundle_dir / "04-wall-content-audit.md").write_text(
        render_wall_content_audit_markdown(audit),
        encoding="utf-8",
    )
    (bundle_dir / "README.txt").write_text(
        "Read-only VK wall audit. No posts were created, edited, deleted, or scheduled.\n",
        encoding="utf-8",
    )
    _write_json(bundle_dir / "manifest.json", _manifest(bundle_dir, community_id=args.community, audit=audit))
    _package(bundle_dir, zip_path)

    summary = audit["summary"]
    print(
        "VK WALL CONTENT AUDIT\n"
        f"  status: {audit['status']}\n"
        f"  videos: {summary['videos']}\n"
        f"  already published: {summary['published_videos']}\n"
        f"  already scheduled: {summary['scheduled_videos']}\n"
        f"  confirmed unposted: {summary['unposted_videos']}\n"
        f"  review required: {summary['wall_marker_only_review'] + summary['published_and_scheduled_conflicts']}"
    )
    return zip_path


def main() -> int:
    args = _parse_args()
    try:
        path = run(args)
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
