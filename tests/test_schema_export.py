from __future__ import annotations

import json
from pathlib import Path

from video_channel_manager.cli.app import schema_export


def test_schema_export_includes_instagram_reel_artifact_binding(tmp_path: Path) -> None:
    output_dir = tmp_path / "schemas"

    schema_export(output_dir=output_dir)

    schema_path = output_dir / "instagram-reel-artifact-binding-v1.schema.json"
    payload = json.loads(schema_path.read_text(encoding="utf-8"))
    properties = payload["properties"]

    assert properties["schema_name"]["const"] == "video-manager.instagram-reel-artifact-binding"
    assert properties["schema_version"]["default"] == "1.0"
    assert properties["ruleset_version"]["default"] == "meta-instagram-reels-2026-09-v2"
    assert properties["ruleset_version"]["enum"] == [
        "meta-instagram-reels-2026-09-v1",
        "meta-instagram-reels-2026-09-v2",
        "meta-instagram-reels-2026-09-v3",
    ]
    assert "pixel_format" in properties
    assert "field_order" in properties
    assert "closed_gop_verified" in properties
    assert "media_sha256" in properties
    assert "media_size_bytes" in properties
    assert "media_content_type" in properties
