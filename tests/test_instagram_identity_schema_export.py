from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from video_channel_manager.cli.app import app


runner = CliRunner()


def test_schema_export_includes_exact_instagram_contracts(tmp_path: Path) -> None:
    result = runner.invoke(app, ["schema", "export", "--output-dir", str(tmp_path)])

    assert result.exit_code == 0, result.output
    expected = {
        "instagram-account-observation-v1.schema.json": "InstagramAccountObservation",
        "instagram-project-binding-v1.schema.json": "InstagramProjectBinding",
        "instagram-project-binding-registry-v1.schema.json": "InstagramProjectBindingRegistry",
        "instagram-launch-pack-v1.schema.json": "InstagramLaunchPack",
        "instagram-launch-preview-v1.schema.json": "InstagramLaunchPreviewArtifact",
        "instagram-analytics-snapshot-v1.schema.json": "InstagramAnalyticsSnapshot",
    }
    for filename, title in expected.items():
        path = tmp_path / filename
        assert path.is_file(), filename
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["title"] == title
        assert schema["additionalProperties"] is False
