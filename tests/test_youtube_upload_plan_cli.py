from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

import video_channel_manager.youtube_upload_plan_cli as cli
from video_channel_manager.youtube_upload_plan import UploadPlanError, intent_digest, journal_path


CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"


def _fixture(tmp_path: Path, *, title: str = "Black Man") -> tuple[Path, Path]:
    media = tmp_path / "album.mp4"
    if not media.exists():
        media.write_bytes(b"exact-private-upload-fixture")
    media_sha = "sha256:" + hashlib.sha256(media.read_bytes()).hexdigest()
    spec = tmp_path / f"spec-{title.replace(' ', '-')}.json"
    spec.write_text(
        json.dumps(
            {
                "schema_name": "video-manager.youtube-video-upload-spec",
                "schema_version": "2.0",
                "project_key": "legendary-poet",
                "account_alias": "legendary-poet",
                "target_channel_id": CHANNEL_ID,
                "expected_media_sha256": media_sha,
                "title": title,
                "description": "Local-only planning fixture",
                "tags": ["Есенин"],
                "privacy_status": "private",
            }
        ),
        encoding="utf-8",
    )
    return media, spec


def _plan_args(*, spec: Path, media: Path, data_dir: Path, output: Path) -> argparse.Namespace:
    return argparse.Namespace(spec=spec, video=media, data_dir=data_dir, output=output)


def test_plan_persists_stable_journal_and_blocks_duplicate_replan(tmp_path: Path) -> None:
    media, first_spec = _fixture(tmp_path, title="First")
    _, second_spec = _fixture(tmp_path, title="Changed")
    data_dir = tmp_path / "state"
    first_output = tmp_path / "intent-first.json"
    second_output = tmp_path / "intent-second.json"

    assert cli.plan(_plan_args(spec=first_spec, media=media, data_dir=data_dir, output=first_output)) == 0
    first_intent = json.loads(first_output.read_text(encoding="utf-8"))
    stable_journal = journal_path(data_dir, first_intent["upload_key_sha256"])
    journal = json.loads(stable_journal.read_text(encoding="utf-8"))

    assert journal["state"] == "planned"
    assert journal["provider_effect"] == "not_dispatched"
    assert journal["active_intent_sha256"] == first_intent["intent_sha256"]

    with pytest.raises(UploadPlanError, match="blocks a new plan"):
        cli.plan(_plan_args(spec=second_spec, media=media, data_dir=data_dir, output=second_output))
    assert not second_output.exists()


def test_abandon_exact_immutable_intent_allows_safe_local_replan(tmp_path: Path) -> None:
    media, first_spec = _fixture(tmp_path, title="First")
    _, second_spec = _fixture(tmp_path, title="Changed")
    data_dir = tmp_path / "state"
    first_output = tmp_path / "intent-first.json"
    second_output = tmp_path / "intent-second.json"

    cli.plan(_plan_args(spec=first_spec, media=media, data_dir=data_dir, output=first_output))
    assert cli.abandon(argparse.Namespace(intent=first_output, data_dir=data_dir)) == 0

    first_intent = json.loads(first_output.read_text(encoding="utf-8"))
    stable_journal = journal_path(data_dir, first_intent["upload_key_sha256"])
    abandoned = json.loads(stable_journal.read_text(encoding="utf-8"))
    assert abandoned["state"] == "abandoned"
    assert abandoned["provider_effect"] == "confirmed_absent"

    assert cli.plan(_plan_args(spec=second_spec, media=media, data_dir=data_dir, output=second_output)) == 0
    second_intent = json.loads(second_output.read_text(encoding="utf-8"))
    assert second_intent["upload_key_sha256"] == first_intent["upload_key_sha256"]
    assert second_intent["intent_sha256"] != first_intent["intent_sha256"]


def test_abandon_rejects_different_attempt_for_same_stable_key(tmp_path: Path) -> None:
    media, spec = _fixture(tmp_path)
    data_dir = tmp_path / "state"
    output = tmp_path / "intent.json"
    cli.plan(_plan_args(spec=spec, media=media, data_dir=data_dir, output=output))

    intent = json.loads(output.read_text(encoding="utf-8"))
    intent["created_at"] = "2099-01-01T00:00:00+00:00"
    intent["intent_sha256"] = intent_digest(intent)
    other_attempt = tmp_path / "other-attempt.json"
    other_attempt.write_text(json.dumps(intent), encoding="utf-8")

    with pytest.raises(UploadPlanError, match="Journal active intent differs"):
        cli.abandon(argparse.Namespace(intent=other_attempt, data_dir=data_dir))


def test_existing_stable_key_lock_blocks_local_mutation(tmp_path: Path) -> None:
    media, spec = _fixture(tmp_path)
    data_dir = tmp_path / "state"
    output = tmp_path / "intent.json"
    spec_payload = json.loads(spec.read_text(encoding="utf-8"))
    from video_channel_manager.youtube_upload_plan import build_intent

    intent = build_intent(spec_payload, media)
    stable_journal = journal_path(data_dir, intent["upload_key_sha256"])
    lock_path = stable_journal.with_suffix(stable_journal.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("existing writer\n", encoding="utf-8")

    with pytest.raises(UploadPlanError, match="already locked"):
        cli.plan(_plan_args(spec=spec, media=media, data_dir=data_dir, output=output))

    assert not output.exists()
    assert lock_path.exists()


def test_planner_has_no_provider_execute_command() -> None:
    root = cli.parser()
    subparser_action = next(action for action in root._actions if isinstance(action, argparse._SubParsersAction))
    assert set(subparser_action.choices) == {"plan", "status", "abandon"}


def test_plan_rolls_back_orphan_intent_if_journal_persist_fails(monkeypatch, tmp_path: Path) -> None:
    media, spec = _fixture(tmp_path)
    output = tmp_path / "intent.json"

    def fail_journal(*args, **kwargs) -> None:
        raise OSError("durable state unavailable")

    monkeypatch.setattr(cli, "_write_json_atomic", fail_journal)
    with pytest.raises(OSError, match="durable state unavailable"):
        cli.plan(_plan_args(spec=spec, media=media, data_dir=tmp_path / "state", output=output))

    assert not output.exists()
