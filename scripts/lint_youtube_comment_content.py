from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.youtube.comment_content import (
    CONTENT_SCHEMA_NAME,
    render_comment_content,
    validate_comment_content,
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and preview sourced YouTube channel-comment records without calling YouTube."
    )
    parser.add_argument("--content-dir", type=Path, default=Path("content/youtube-comments"))
    parser.add_argument("--channel")
    parser.add_argument("--video-id")
    parser.add_argument("--show", action="store_true", help="Print rendered comments after validation")
    args = parser.parse_args()

    paths = sorted(args.content_dir.rglob("*.json"))
    if args.video_id:
        paths = [path for path in paths if path.stem == args.video_id]
    if not paths:
        print("ERROR: no YouTube comment content records found.", file=sys.stderr)
        return 2

    failures: list[str] = []
    variation_paths: dict[str, Path] = {}
    rendered_paths: dict[str, Path] = {}
    approved = 0
    legacy = 0
    structured = 0

    for path in paths:
        try:
            payload = _read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            failures.append(f"{path}: {exc}")
            continue
        if payload.get("schema_name") != CONTENT_SCHEMA_NAME:
            continue
        errors = validate_comment_content(payload, expected_channel_id=args.channel)
        failures.extend(f"{path}: {error}" for error in errors)
        if errors:
            continue

        version = payload.get("schema_version")
        if version == 1:
            legacy += 1
        elif version == 2:
            structured += 1
        if payload.get("status") == "approved":
            approved += 1

        variation_key = str(payload.get("variation_key") or "").strip()
        if variation_key:
            previous = variation_paths.get(variation_key)
            if previous is not None:
                failures.append(f"{path}: duplicate variation_key also used by {previous}")
            variation_paths[variation_key] = path

        rendered = render_comment_content(payload)
        previous_rendered = rendered_paths.get(rendered)
        if previous_rendered is not None:
            failures.append(f"{path}: duplicate rendered comment also used by {previous_rendered}")
        rendered_paths[rendered] = path

        if args.show:
            print(f"\n=== {path.stem} — {payload.get('video_title') or ''} ===\n")
            print(rendered)
            print()

    print("YouTube comment content lint:")
    print(f"  records checked: {len(paths)}")
    print(f"  approved: {approved}")
    print(f"  structured v2: {structured}")
    print(f"  legacy v1: {legacy}")
    print(f"  errors: {len(failures)}")
    for failure in failures:
        print(f"  ERROR {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
