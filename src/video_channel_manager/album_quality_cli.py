from __future__ import annotations

import argparse
import json
from pathlib import Path

from video_channel_manager.album import (
    AlbumError,
    bind_quality_master,
    load_album_manifest,
    load_or_initialize_quality_master_manifest,
    quality_master_path_from_manifest_path,
    require_complete_quality_masters,
    save_quality_master_manifest,
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Bind exact local quality masters to an album without provider writes")
    root.add_argument("--manifest", type=Path, required=True)
    sub = root.add_subparsers(dest="command", required=True)

    bind = sub.add_parser("bind-master")
    bind.add_argument("--track", type=int, required=True)
    bind.add_argument("--path", type=Path, required=True)
    bind.add_argument("--ffprobe", default="ffprobe")

    validate = sub.add_parser("validate")
    validate.add_argument("--no-byte-check", action="store_true")
    return root


def main() -> int:
    args = parser().parse_args()
    manifest_path = args.manifest.expanduser().resolve()
    manifest = load_album_manifest(manifest_path)
    quality_path = quality_master_path_from_manifest_path(manifest_path)

    try:
        quality = load_or_initialize_quality_master_manifest(quality_path, manifest)
        if args.command == "bind-master":
            quality = bind_quality_master(
                manifest,
                quality,
                ordinal=args.track,
                path=args.path,
                ffprobe=args.ffprobe,
            )
            quality = save_quality_master_manifest(quality_path, quality)
            entry = next(item for item in quality.entries if item.ordinal == args.track)
            print(
                json.dumps(
                    {
                        "bound": True,
                        "track": entry.ordinal,
                        "source_sha256": entry.source_sha256,
                        "master_path": entry.master_path,
                        "master_sha256": entry.master_sha256,
                        "duration_seconds": entry.duration_seconds,
                        "quality_master_sha256": quality.quality_master_sha256,
                        "provider_write_performed": False,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if args.command == "validate":
            require_complete_quality_masters(manifest, quality, verify_bytes=not args.no_byte_check)
            print(
                json.dumps(
                    {
                        "valid": True,
                        "track_count": len(quality.entries),
                        "quality_master_sha256": quality.quality_master_sha256,
                        "provider_write_performed": False,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
    except (AlbumError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
