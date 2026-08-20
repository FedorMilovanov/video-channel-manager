from __future__ import annotations

import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from video_channel_manager.cli.app import app
from video_channel_manager.exchange.instagram_video import InstagramVideoIntakeArtifact


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "content" / "instagram" / "legendary-poet-reels-factory.json"
CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"
runner = CliRunner()


def _intake() -> InstagramVideoIntakeArtifact:
    return InstagramVideoIntakeArtifact.model_validate(
        {
            "project_key": "legendary-poet",
            "channel_id": CHANNEL_ID,
            "source_snapshot_id": "00000000-0000-0000-0000-000000000001",
            "source_generated_at": "2026-08-20T00:00:00+00:00",
            "source_evidence": {"audit_package_sha256": "sha256:" + "a" * 64},
            "counts": {
                "current_videos": 1,
                "frozen_mapping_ids": 1,
                "reviewed_editorial_ids": 1,
                "current_also_in_frozen_mapping": 1,
                "new_current_vs_frozen_mapping": 0,
                "historical_mapped_missing_from_current_snapshot": 0,
                "confirmed_short": 0,
                "confirmed_longform": 0,
                "format_unknown": 1,
                "short_candidates": 0,
                "file_details_available": 0,
                "source_geometry_known": 0,
            },
            "reconciliation": {
                "new_current_ids": [],
                "historical_mapped_missing_from_current_snapshot": [],
                "reviewed_missing_from_current_snapshot": [],
            },
            "classification_policy": {
                "shorts": "fail closed",
                "longform": "fail closed",
            },
            "records": [
                {
                    "youtube_video_id": "mw-dYETmPIE",
                    "title": "Чёрный человек",
                    "duration_seconds": 120,
                    "revision": "sha256:mw-dYETmPIE",
                    "present_in_frozen_mapping": True,
                    "reviewed_editorial_record": "content/youtube-comments/mw-dYETmPIE.json",
                    "youtube_format_status": "unknown",
                    "youtube_format_reason": "insufficient_exact_surface_evidence",
                }
            ],
        }
    )


def test_factory_coverage_cli_partitions_exact_current_intake(tmp_path: Path) -> None:
    intake_path = tmp_path / "intake.json"
    output = tmp_path / "coverage.json"
    intake_path.write_text(_intake().model_dump_json(indent=2), encoding="utf-8")
    intake_bytes = intake_path.read_bytes()
    registry_bytes = REGISTRY.read_bytes()

    result = runner.invoke(
        app,
        [
            "instagram",
            "factory-coverage",
            str(intake_path),
            str(REGISTRY),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_name"] == "video-manager.instagram-reel-factory-coverage"
    assert payload["schema_version"] == 1
    assert payload["project_key"] == "legendary-poet"
    assert payload["channel_id"] == CHANNEL_ID
    assert payload["provider_effect"] == "impossible"
    assert payload["provider_writes_authorized"] is False
    assert payload["source_intake_sha256"] == f"sha256:{hashlib.sha256(intake_bytes).hexdigest()}"
    assert payload["source_registry_sha256"] == f"sha256:{hashlib.sha256(registry_bytes).hexdigest()}"
    assert payload["counts"]["total_current_videos"] == 1
    assert payload["counts"]["covered_by_factory"] == 1
    assert payload["counts"]["reviewed_unexpanded"] == 0
    assert payload["counts"]["editorial_review_required"] == 0
    assert payload["counts"]["factory_reel_jobs"] == 59
    assert payload["counts"]["factory_youtube_sources"] == 9
    assert payload["counts"]["current_factory_sources"] == 1
    assert payload["counts"]["factory_sources_missing_from_current_snapshot"] == 8
    assert len(payload["records"]) == 1
    assert payload["records"][0]["youtube_video_id"] == "mw-dYETmPIE"
    assert payload["records"][0]["coverage_status"] == "covered_by_factory"
    assert len(payload["records"][0]["reel_ids"]) == 6
