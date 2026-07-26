#!/usr/bin/env python3
"""Prefetch YouTube media into the VK transfer cache with guarded fallbacks.

The downloader always tries the highest-quality separate video/audio streams first.
When YouTube returns HTTP 403 for one player client, it retries with alternative
clients. A progressive MP4 is used only as the final compatibility fallback.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DownloadStrategy:
    name: str
    format_selector: str
    extractor_args: str | None = None


_STRATEGIES = (
    DownloadStrategy("default-max-quality", "bv*+ba/b"),
    DownloadStrategy(
        "embedded-max-quality",
        "bv*+ba/b",
        "youtube:player_client=web_embedded",
    ),
    DownloadStrategy(
        "alternate-clients-max-quality",
        "bv*+ba/b",
        "youtube:player_client=android_vr,web_safari",
    ),
    DownloadStrategy(
        "progressive-mp4-fallback",
        "best[ext=mp4]/best",
        "youtube:player_client=web_embedded",
    ),
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video_ids", nargs="+", help="One or more exact YouTube video IDs")
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--yt-dlp", default="yt-dlp", help="yt-dlp executable name or path")
    parser.add_argument(
        "--cookies-from-browser",
        help="Optional yt-dlp browser spec, e.g. edge or chrome:Default",
    )
    parser.add_argument("--between-videos-delay", type=float, default=5.0)
    return parser


def _resolve_executable(value: str) -> str:
    resolved = shutil.which(value)
    if resolved is not None:
        return resolved
    candidate = Path(value)
    if candidate.is_file():
        return str(candidate)
    raise ValueError(f"Required executable not found: {value}")


def _completed_mp4(cache_dir: Path, video_id: str) -> Path | None:
    candidates = sorted(
        path for path in cache_dir.glob(f"{video_id}*.mp4") if path.is_file() and path.stat().st_size > 0
    )
    return candidates[0] if candidates else None


def _remove_partial_files(cache_dir: Path, video_id: str) -> None:
    for pattern in (f"{video_id}*.part", f"{video_id}*.ytdl", f"{video_id}*.temp"):
        for path in cache_dir.glob(pattern):
            try:
                path.unlink()
            except FileNotFoundError:
                pass


def _command(
    *,
    yt_dlp: str,
    cache_dir: Path,
    video_id: str,
    strategy: DownloadStrategy,
    cookies_from_browser: str | None,
) -> list[str]:
    output_template = str(cache_dir / f"{video_id}.%(ext)s")
    command = [
        yt_dlp,
        "--no-playlist",
        "--no-progress",
        "--newline",
        "--merge-output-format",
        "mp4",
        "--remux-video",
        "mp4",
        "--retries",
        "10",
        "--fragment-retries",
        "10",
        "--retry-sleep",
        "exp=1:20",
        "--concurrent-fragments",
        "1",
        "--sleep-requests",
        "2",
        "--sleep-interval",
        "3",
        "--max-sleep-interval",
        "7",
        "--format",
        strategy.format_selector,
        "--output",
        output_template,
        "--print",
        "after_move:filepath",
    ]
    if strategy.extractor_args is not None:
        command.extend(["--extractor-args", strategy.extractor_args])
    if cookies_from_browser:
        command.extend(["--cookies-from-browser", cookies_from_browser])
    command.append(f"https://www.youtube.com/watch?v={video_id}")
    return command


def _download_one(
    *,
    yt_dlp: str,
    cache_dir: Path,
    video_id: str,
    cookies_from_browser: str | None,
) -> Path:
    existing = _completed_mp4(cache_dir, video_id)
    if existing is not None:
        print(f"CACHED {video_id} → {existing}")
        return existing

    failures: list[str] = []
    for strategy in _STRATEGIES:
        _remove_partial_files(cache_dir, video_id)
        print(f"TRY {video_id}: {strategy.name}")
        completed = subprocess.run(
            _command(
                yt_dlp=yt_dlp,
                cache_dir=cache_dir,
                video_id=video_id,
                strategy=strategy,
                cookies_from_browser=cookies_from_browser,
            ),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        media = _completed_mp4(cache_dir, video_id)
        if completed.returncode == 0 and media is not None:
            print(f"READY {video_id} → {media} ({media.stat().st_size / 1024 / 1024:.1f} MiB)")
            return media
        tail = (completed.stderr or completed.stdout).strip()[-1600:]
        failures.append(f"{strategy.name}: {tail or f'exit {completed.returncode}'}")
        print(f"FAILED {video_id}: {strategy.name}")

    details = "\n\n".join(failures)
    raise RuntimeError(f"All yt-dlp strategies failed for {video_id}:\n{details}")


def main() -> int:
    args = _parser().parse_args()
    if args.between_videos_delay < 0:
        raise SystemExit("--between-videos-delay cannot be negative")

    yt_dlp = _resolve_executable(args.yt_dlp)
    _resolve_executable("ffmpeg")
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    for index, video_id in enumerate(args.video_ids, start=1):
        try:
            print(f"[{index}/{len(args.video_ids)}] Prefetching {video_id}")
            _download_one(
                yt_dlp=yt_dlp,
                cache_dir=args.cache_dir,
                video_id=video_id,
                cookies_from_browser=args.cookies_from_browser,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            failures.append(f"{video_id}: {exc}")
            print(f"ERROR {video_id}: {exc}", file=sys.stderr)
        if index < len(args.video_ids) and args.between_videos_delay > 0:
            time.sleep(args.between_videos_delay)

    if failures:
        print("Prefetch completed with failures:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 2

    print(f"Prefetch completed: {len(args.video_ids)} video(s) ready in {args.cache_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
