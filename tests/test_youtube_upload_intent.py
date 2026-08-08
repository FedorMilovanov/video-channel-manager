from __future__ import annotations

import hashlib
from pathlib import Path

from video_channel_manager.youtube_upload_cli import _build_intent, _intent_digest


def test_upload_intent_is_private_and_digest_bound(tmp_path: Path) -> None:
    media = tmp_path / "album.mp4"
    media.write_bytes(b"exact bytes")
    media_sha = "sha256:" + hashlib.sha256(b"exact bytes").hexdigest()
    spec = {
        "schema_name": "video-manager.youtube-video-upload-spec",
        "schema_version": "1.0",
        "target_channel_id": "UC-78ys2S3cQ3lpqgXfo-SvQ",
        "expected_media_sha256": media_sha,
        "title": "Exact title",
        "description": "Description",
        "tags": ["tag"],
        "privacy_status": "private",
    }
    intent = _build_intent(spec, media, "legendary-poet")
    assert intent["status"]["privacyStatus"] == "private"
    assert intent["provider_effect"] == "not_dispatched"
    assert intent["intent_sha256"] == _intent_digest(intent)
