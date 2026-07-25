#!/usr/bin/env python3
"""Run YouTube→VK sync with mandatory text rendering, media QC, and writer locking."""

from __future__ import annotations

import os
import sys
from contextlib import nullcontext
from pathlib import Path
from typing import ContextManager

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import sync_youtube_to_vk as sync  # noqa: E402
from video_channel_manager.config import get_settings  # noqa: E402
from video_channel_manager.local_media.quality import MediaQualityError, probe_media  # noqa: E402
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore  # noqa: E402
from video_channel_manager.platforms.vk.lock import local_vk_write_lock  # noqa: E402
from video_channel_manager.platforms.vk.publishing import (  # noqa: E402
    render_vk_publication_description,
    render_vk_publication_title,
)

_ORIGINAL_DOWNLOAD = sync._download_video


def _vk_title(source_title: str) -> str:
    return render_vk_publication_title(source_title)


def _vk_description(source_description: str) -> str:
    return render_vk_publication_description(source_description).text


def _download_video(*, yt_dlp: str, video_id: str, cache_dir: Path) -> Path:
    path = _ORIGINAL_DOWNLOAD(yt_dlp=yt_dlp, video_id=video_id, cache_dir=cache_dir)
    report = probe_media(
        path,
        ffprobe=os.environ.get("VCM_FFPROBE", "ffprobe"),
        timeout_seconds=float(os.environ.get("VCM_MEDIA_QC_TIMEOUT", "180")),
    )
    print(
        "Media QC passed: "
        f"{path.name} | {report.duration_seconds:.3f}s | "
        f"{report.video_codec or '?'}+{report.audio_codec or '?'} | {report.sha256}"
    )
    return path


def _write_lock(args: object) -> ContextManager[None]:
    if not bool(getattr(args, "execute", False)):
        return nullcontext()
    settings = get_settings()
    account = str(getattr(args, "account"))
    community_value = str(getattr(args, "community"))
    store = VkTokenStore(settings.data_dir)
    reader = VkApiClient(
        token_store=store,
        account_alias=account,
        api_version=settings.vk_api_version,
    )
    community = reader.get_community(community_value)
    community_id = int(community.ref.channel_id)
    lock_path = settings.data_dir / "locks" / f"vk-{account}-{community_id}.lock"
    return local_vk_write_lock(
        lock_path,
        account=account,
        community_id=community_id,
        operation="sync-youtube-to-vk-textsafe",
    )


def main() -> int:
    args = sync._parser().parse_args()
    sync._vk_title = _vk_title
    sync._vk_description = _vk_description
    sync._download_video = _download_video
    print(
        "Safe VK publishing profile enabled: plain-text descriptions, centralized title policy, "
        "ffprobe A/V validation, SHA-256 media fingerprints, and a single-writer community lock."
    )
    with _write_lock(args):
        return sync.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, MediaQualityError, sync.VkWriteError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
