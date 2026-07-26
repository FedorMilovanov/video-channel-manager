from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from video_channel_manager.cli.app import app
from video_channel_manager.editorial.content import parse_content_record
from video_channel_manager.editorial.content_plan import build_content_plan, make_content_operation
from video_channel_manager.platforms.youtube.renderers import YouTubeCommentRenderer

runner = CliRunner()


def _example_path() -> Path:
    return Path(__file__).resolve().parents[1] / "content" / "editorial" / "examples" / "tyutchev-night-sea.json"


def _record():
    payload = json.loads(_example_path().read_text(encoding="utf-8"))
    return parse_content_record(payload)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_content_preview_youtube_and_vk() -> None:
    youtube = runner.invoke(
        app,
        ["content", "preview", "--platform", "youtube", "--surface", "comment", "--input", str(_example_path())],
    )
    assert youtube.exit_code == 0, youtube.stdout
    assert "The Legendary Poet" in youtube.stdout

    vk = runner.invoke(
        app,
        ["content", "preview", "--platform", "vk", "--surface", "video_description", "--input", str(_example_path())],
    )
    assert vk.exit_code == 0, vk.stdout
    assert "Сообщество проекта VK: https://vk.com/thelegendarypoet" in vk.stdout
    assert "*Сообщество" not in vk.stdout


def test_content_validate_command() -> None:
    result = runner.invoke(app, ["content", "validate", "--input", str(_example_path())])
    assert result.exit_code == 0, result.stdout
    assert "Validated 1 editorial content record" in result.stdout


def test_content_plan_preflight_requires_complete_snapshot_bound_state(tmp_path: Path) -> None:
    record = _record()
    rendered = YouTubeCommentRenderer().render(record)
    operation = make_content_operation(
        record=record,
        rendered=rendered,
        target_id="RQIlUvFf1KQ",
        action="create",
    )
    snapshot = "artifacts/youtube-comment-audit.json"
    snapshot_sha256 = "sha256:" + "a" * 64
    plan = build_content_plan(
        source_snapshot=snapshot,
        source_snapshot_sha256=snapshot_sha256,
        source_snapshot_generated_at="2026-07-25T20:30:00+00:00",
        operations=[operation],
    )
    plan_path = tmp_path / "plan.json"
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "preflight.json"
    _write_json(plan_path, plan)

    valid_state = {
        "source_snapshot": snapshot,
        "source_snapshot_sha256": snapshot_sha256,
        "source_snapshot_generated_at": "2026-07-25T20:30:00+00:00",
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
    _write_json(state_path, valid_state)
    result = runner.invoke(
        app,
        ["content", "plan", "preflight", str(plan_path), "--state", str(state_path), "--json-output", str(report_path)],
    )
    assert result.exit_code == 0, result.stdout
    assert "ready=1" in result.stdout
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["source_snapshot"] == snapshot
    assert report["source_snapshot_sha256"] == snapshot_sha256
    assert report["counts"] == {"ready": 1}

    incomplete_state = dict(valid_state, targets=[])
    _write_json(state_path, incomplete_state)
    result = runner.invoke(app, ["content", "plan", "preflight", str(plan_path), "--state", str(state_path)])
    assert result.exit_code == 2
    assert "state snapshot is incomplete" in result.stdout

    wrong_snapshot_state = dict(valid_state, source_snapshot="artifacts/another-audit.json")
    _write_json(state_path, wrong_snapshot_state)
    result = runner.invoke(app, ["content", "plan", "preflight", str(plan_path), "--state", str(state_path)])
    assert result.exit_code == 2
    assert "does not match the signed plan" in result.stdout

    wrong_digest_state = dict(valid_state, source_snapshot_sha256="sha256:" + "b" * 64)
    _write_json(state_path, wrong_digest_state)
    result = runner.invoke(app, ["content", "plan", "preflight", str(plan_path), "--state", str(state_path)])
    assert result.exit_code == 2
    assert "source_snapshot_sha256 does not match" in result.stdout
