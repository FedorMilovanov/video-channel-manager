from __future__ import annotations

import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from video_channel_manager.cli.app import app


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "content" / "instagram" / "legendary-poet-reels-factory.json"
runner = CliRunner()


def test_reel_queue_cli_builds_exact_provider_inert_baseline(tmp_path: Path) -> None:
    output = tmp_path / "reel-queue.json"
    registry_bytes = REGISTRY.read_bytes()

    result = runner.invoke(
        app,
        [
            "instagram",
            "reel-queue",
            str(REGISTRY),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_name"] == "video-manager.instagram-reel-queue"
    assert payload["schema_version"] == 1
    assert payload["project_key"] == "legendary-poet"
    assert payload["provider_effect"] == "impossible"
    assert payload["provider_writes_authorized"] is False
    assert payload["source_registry_sha256"] == f"sha256:{hashlib.sha256(registry_bytes).hexdigest()}"
    assert payload["source_media_route_sha256"] is None
    assert payload["counts"] == {
        "total": 59,
        "source_led_ready": 40,
        "exact_text_binding_required": 8,
        "source_binding_required": 8,
        "materialization_required": 3,
        "timing_selection_required": 0,
        "media_edit_ready": 0,
        "editorial_rebuild_required": 0,
        "hold": 0,
    }
    assert len(payload["records"]) == 59
    assert len({record["reel_id"] for record in payload["records"]}) == 59
