from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from video_channel_manager.cli.app import app

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = "snapshot/comments-20260725.json"
SNAPSHOT_SHA256 = "sha256:" + "a" * 64
SNAPSHOT_TIME = "2026-07-25T20:30:00+00:00"
PROJECT_KEY = "legendary-poet"


def _example_path() -> Path:
    return ROOT / "content" / "editorial" / "examples" / "tyutchev-night-sea.json"


def _manifest() -> dict[str, object]:
    return {
        "project_key": PROJECT_KEY,
        "source_snapshot": SNAPSHOT,
        "source_snapshot_sha256": SNAPSHOT_SHA256,
        "source_snapshot_generated_at": SNAPSHOT_TIME,
        "operations": [
            {
                "content_id": "tyutchev-night-sea",
                "action": "create",
                "target_id": "RQIlUvFf1KQ",
            }
        ],
    }


def _normalized_stdout(result: Any) -> str:
    stdout = result.stdout
    assert isinstance(stdout, str)
    return " ".join(stdout.split())


def _build(tmp_path: Path) -> tuple[Path, object]:
    manifest_path = tmp_path / "targets.json"
    output_path = tmp_path / "plan.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "content",
            "plan",
            "build",
            "--platform",
            "youtube",
            "--surface",
            "comment",
            "--input",
            str(_example_path()),
            "--targets",
            str(manifest_path),
            "--output",
            str(output_path),
        ],
    )
    return output_path, result


def test_strict_cli_builds_project_and_provenance_bound_plan(tmp_path: Path) -> None:
    output_path, result = _build(tmp_path)
    assert result.exit_code == 0, result.stdout
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    operation = payload["operations"][0]
    assert payload["schema_version"] == 2
    assert payload["project_key"] == PROJECT_KEY
    assert operation["project_key"] == PROJECT_KEY
    assert operation["reviewed_target_id"] == "RQIlUvFf1KQ"
    assert operation["source_ids_sha256"].startswith("sha256:")


def test_strict_cli_rejects_manifest_without_project_identity(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest.pop("project_key")
    manifest_path = tmp_path / "no-project.json"
    output_path = tmp_path / "no-project-plan.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "content",
            "plan",
            "build",
            "--platform",
            "youtube",
            "--surface",
            "comment",
            "--input",
            str(_example_path()),
            "--targets",
            str(manifest_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 2
    assert "manifest.project_key must be a nonblank string" in _normalized_stdout(result)
    assert not output_path.exists()


def test_strict_cli_rejects_wrong_project_before_rendering(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["project_key"] = "lord-god-strength"
    manifest_path = tmp_path / "wrong-project.json"
    output_path = tmp_path / "wrong-project-plan.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "content",
            "plan",
            "build",
            "--platform",
            "youtube",
            "--surface",
            "comment",
            "--input",
            str(_example_path()),
            "--targets",
            str(manifest_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 2
    assert "does not match requested project" in _normalized_stdout(result)
    assert not output_path.exists()


def test_strict_cli_requires_exact_content_coverage(tmp_path: Path) -> None:
    input_dir = tmp_path / "content"
    input_dir.mkdir()
    first = json.loads(_example_path().read_text(encoding="utf-8"))
    second = dict(first)
    second["content_id"] = "tyutchev-night-sea-second"
    second["variation_key"] = "tyutchev-night-sea-second"
    (input_dir / "first.json").write_text(json.dumps(first), encoding="utf-8")
    (input_dir / "second.json").write_text(json.dumps(second), encoding="utf-8")
    manifest_path = tmp_path / "partial-targets.json"
    output_path = tmp_path / "partial-plan.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "content",
            "plan",
            "build",
            "--platform",
            "youtube",
            "--surface",
            "comment",
            "--input",
            str(input_dir),
            "--targets",
            str(manifest_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 2
    assert "target manifest is missing content_id operations: tyutchev-night-sea-second" in _normalized_stdout(result)
    assert not output_path.exists()


def test_strict_cli_rejects_duplicate_content_operation(tmp_path: Path) -> None:
    manifest = _manifest()
    operations = manifest["operations"]
    assert isinstance(operations, list)
    operations.append(dict(operations[0]))
    manifest_path = tmp_path / "duplicate-targets.json"
    output_path = tmp_path / "duplicate-plan.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "content",
            "plan",
            "build",
            "--platform",
            "youtube",
            "--surface",
            "comment",
            "--input",
            str(_example_path()),
            "--targets",
            str(manifest_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 2
    assert "target manifest repeats content_id: tyutchev-night-sea" in _normalized_stdout(result)
    assert not output_path.exists()


def test_strict_cli_rejects_manifest_scalar_coercion(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["source_snapshot"] = 123
    operations = manifest["operations"]
    assert isinstance(operations, list)
    operation = operations[0]
    assert isinstance(operation, dict)
    operation["target_id"] = 456
    manifest_path = tmp_path / "invalid-targets.json"
    output_path = tmp_path / "invalid-plan.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "content",
            "plan",
            "build",
            "--platform",
            "youtube",
            "--surface",
            "comment",
            "--input",
            str(_example_path()),
            "--targets",
            str(manifest_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 2
    assert "manifest.source_snapshot must be a nonblank string" in _normalized_stdout(result)
    assert not output_path.exists()


def test_strict_cli_preflight_binds_snapshot_timestamp(tmp_path: Path) -> None:
    plan_path, build_result = _build(tmp_path)
    assert build_result.exit_code == 0, build_result.stdout
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "source_snapshot": SNAPSHOT,
                "source_snapshot_sha256": SNAPSHOT_SHA256,
                "source_snapshot_generated_at": "2026-07-25T20:31:00+00:00",
                "targets": [
                    {
                        "platform": "youtube",
                        "surface": "comment",
                        "target_id": "RQIlUvFf1KQ",
                        "exists": False,
                        "current_text": None,
                        "current_revision": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "content",
            "plan",
            "preflight",
            str(plan_path),
            "--state",
            str(state_path),
        ],
    )

    assert result.exit_code == 2
    assert "state source_snapshot_generated_at does not match the signed plan" in result.stdout
