from __future__ import annotations

import json
from pathlib import Path

from video_channel_manager.cli.app import schema_export


def test_schema_export_includes_instagram_publish_manifest(tmp_path: Path) -> None:
    schema_export(tmp_path)

    schema_path = tmp_path / "instagram-publish-manifest-v1.schema.json"
    assert schema_path.is_file()
    payload = json.loads(schema_path.read_text(encoding="utf-8"))
    assert payload["additionalProperties"] is False
    assert set(payload["required"]) >= {
        "publication_key",
        "account_id",
        "video_url",
        "media_sha256",
        "media_size_bytes",
    }
