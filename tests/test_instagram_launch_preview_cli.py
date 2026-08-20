from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from video_channel_manager.cli.app import app
from video_channel_manager.exchange.instagram_content import InstagramLaunchPreviewArtifact


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "instagram"
runner = CliRunner()


@pytest.mark.parametrize(
    ("filename", "project_key"),
    [
        ("legendary-poet-launch-candidates.json", "legendary-poet"),
        ("lord-god-strength-launch-candidates.json", "lord-god-strength"),
    ],
)
def test_launch_preview_cli_renders_exact_repository_pack(
    tmp_path: Path,
    filename: str,
    project_key: str,
) -> None:
    source = CONTENT / filename
    raw = source.read_bytes()
    output = tmp_path / f"{project_key}-preview.json"

    result = runner.invoke(
        app,
        ["instagram", "launch-preview", str(source), "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    artifact = InstagramLaunchPreviewArtifact.model_validate_json(output.read_bytes())
    assert artifact.project_key == project_key
    assert artifact.source_pack_sha256 == f"sha256:{hashlib.sha256(raw).hexdigest()}"
    assert artifact.provider_effect == "impossible"
    assert artifact.provider_writes_authorized is False
    assert artifact.counts.total == 9
    assert artifact.counts.errors == 0


def test_launch_preview_cli_rejects_unknown_fields(tmp_path: Path) -> None:
    source = CONTENT / "legendary-poet-launch-candidates.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["unexpected_runtime_target"] = "@some-handle"
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = runner.invoke(app, ["instagram", "launch-preview", str(invalid)])

    assert result.exit_code == 2
    assert "extra_forbidden" in result.output
