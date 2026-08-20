from __future__ import annotations

import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from video_channel_manager.cli.app import app


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "content" / "instagram" / "legendary-poet-reels-factory.json"
MAPPING = ROOT / "content" / "mappings" / "youtube-vk-reviewed-20260727.json"
COMMENTS = ROOT / "content" / "youtube-comments"
runner = CliRunner()


def _reviewed_corpus_sha256() -> str:
    digest = hashlib.sha256()
    for path in sorted(COMMENTS.glob("*.json"), key=lambda item: item.name):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def test_historical_backlog_cli_builds_exact_repository_floor(tmp_path: Path) -> None:
    output = tmp_path / "historical-backlog.json"

    result = runner.invoke(
        app,
        [
            "instagram",
            "historical-backlog",
            str(REGISTRY),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_name"] == "video-manager.instagram-historical-factory-backlog"
    assert payload["schema_version"] == 1
    assert payload["evidence_scope"] == "historical_floor_not_current_provider_state"
    assert payload["project_key"] == "legendary-poet"
    assert payload["youtube_channel_id"] == "UC-78ys2S3cQ3lpqgXfo-SvQ"
    assert payload["provider_effect"] == "impossible"
    assert payload["provider_writes_authorized"] is False
    assert payload["source_mapping_sha256"] == f"sha256:{hashlib.sha256(MAPPING.read_bytes()).hexdigest()}"
    assert payload["source_reviewed_corpus_sha256"] == _reviewed_corpus_sha256()
    assert payload["source_registry_sha256"] == f"sha256:{hashlib.sha256(REGISTRY.read_bytes()).hexdigest()}"
    assert payload["counts"] == {
        "already_covered": 9,
        "build_editorial_record": 96,
        "design_reel_jobs": 6,
        "factory_youtube_sources_outside_historical_floor": 0,
        "reviewed_ids_outside_historical_floor": 0,
        "total_historical_floor_ids": 111,
    }
    assert len(payload["records"]) == 111
    assert [record["youtube_video_id"] for record in payload["records"]] == sorted(
        record["youtube_video_id"] for record in payload["records"]
    )
