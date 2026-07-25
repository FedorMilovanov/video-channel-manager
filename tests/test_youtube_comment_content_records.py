from __future__ import annotations

import json
from pathlib import Path

from video_channel_manager.platforms.youtube.comment_content import (
    CONTENT_SCHEMA_NAME,
    validate_comment_content,
)

_CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"


def test_all_youtube_comment_content_records_are_sourced_and_valid() -> None:
    root = Path(__file__).resolve().parents[1] / "content" / "youtube-comments"
    paths = sorted(root.glob("*.json"))
    assert len(paths) >= 15

    video_ids: set[str] = set()
    failures: list[str] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_name") != CONTENT_SCHEMA_NAME:
            continue
        video_id = str(payload.get("video_id") or "")
        if video_id in video_ids:
            failures.append(f"{path}: duplicate video_id {video_id}")
        video_ids.add(video_id)
        errors = validate_comment_content(payload, expected_channel_id=_CHANNEL_ID)
        failures.extend(f"{path}: {error}" for error in errors)

    assert failures == []
