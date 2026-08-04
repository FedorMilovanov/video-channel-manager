#!/usr/bin/env python3
"""Supported YouTube→VK sync entrypoint with explicit project-safe dependencies."""

from __future__ import annotations

import argparse
import os
import sys
from contextlib import nullcontext
from pathlib import Path
from typing import ContextManager

_WAVE6_RETIRED_EXECUTOR = True
if __name__ == "__main__":
    raise SystemExit(
        "This historical executor is retired by Wave 6. "
        "Use the versioned `video-manager wave` engine through the reviewed operator contract."
    )

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import sync_youtube_to_vk as sync  # noqa: E402
from video_channel_manager.config import get_settings  # noqa: E402
from video_channel_manager.editorial._project_profiles import resolve_project_key  # noqa: E402
from video_channel_manager.local_media.quality import MediaQualityError, probe_media  # noqa: E402
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore  # noqa: E402
from video_channel_manager.platforms.vk.lock import local_vk_write_lock  # noqa: E402
from video_channel_manager.platforms.vk.publishing import (  # noqa: E402
    render_vk_publication_description,
    render_vk_publication_title,
)


def _render_title(source_title: str, *, project_key: str) -> str:
    return render_vk_publication_title(source_title, project_key=project_key)


def _render_description(source_description: str, *, project_key: str) -> str:
    return render_vk_publication_description(source_description, project_key=project_key).text


def _download_video(*, yt_dlp: str, video_id: str, cache_dir: Path) -> Path:
    path = sync.download_media_file(yt_dlp=yt_dlp, video_id=video_id, cache_dir=cache_dir)
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


def _provider_identity(args: argparse.Namespace) -> tuple[int, str, str]:
    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    reader = VkApiClient(
        token_store=store,
        account_alias=str(args.account),
        api_version=settings.vk_api_version,
    )
    community = reader.get_community(str(args.community))
    community_id = int(community.ref.channel_id)
    source = sync.load_audit(Path(args.source))
    source_channel_id = str(source.channel.ref.channel_id)
    project_key = resolve_project_key(
        {
            "channel_id": source_channel_id,
            "community_id": community_id,
        }
    )
    if project_key is None:
        raise ValueError(
            "Source YouTube channel and target VK community do not resolve to one registered project; "
            "sync is blocked before rendering or mutation"
        )
    return community_id, source_channel_id, project_key


def _write_lock(args: argparse.Namespace, community_id: int) -> ContextManager[None]:
    if not args.execute:
        return nullcontext()
    settings = get_settings()
    account = str(args.account)
    lock_path = settings.data_dir / "locks" / f"vk-{account}-{community_id}.lock"
    return local_vk_write_lock(
        lock_path,
        account=account,
        community_id=community_id,
        operation="sync-youtube-to-vk-textsafe",
    )


def main(argv: list[str] | None = None) -> int:
    args = sync.build_parser().parse_args(argv)
    community_id, source_channel_id, project_key = _provider_identity(args)
    runtime = sync.SyncRuntime(
        project_key=project_key,
        expected_source_channel_id=source_channel_id,
        expected_community_id=community_id,
        render_title=lambda value: _render_title(value, project_key=project_key),
        render_description=lambda value: _render_description(value, project_key=project_key),
        download_media=_download_video,
    )
    print(
        "Safe VK publishing profile enabled: "
        f"project={project_key}, source={source_channel_id}, community={community_id}, "
        "plain-text project rendering, ffprobe A/V validation, SHA-256 media fingerprints, "
        "journaled upload recovery, and a single-writer community lock."
    )
    with _write_lock(args, community_id):
        return sync.run(args, runtime=runtime)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, MediaQualityError, sync.VkWriteError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
