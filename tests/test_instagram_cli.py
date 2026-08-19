from __future__ import annotations

import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from video_channel_manager.cli.app import app
from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef, VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage


CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"
runner = CliRunner()


def _write_audit(path: Path) -> bytes:
    channel_ref = RemoteRef(platform=PlatformName.YOUTUBE, channel_id=CHANNEL_ID, remote_id=CHANNEL_ID)
    video_ref = RemoteRef(platform=PlatformName.YOUTUBE, channel_id=CHANNEL_ID, remote_id="AAAAAAAAAAA")
    audit = AuditPackage(
        channel=ChannelRecord(ref=channel_ref, title="The Legendary Poet", kind=ChannelKind.VIDEO_CHANNEL),
        videos=[VideoRecord(ref=video_ref, title="One video", duration_seconds=55, revision="sha256:revision")],
    )
    raw = audit.model_dump_json(indent=2).encode("utf-8")
    path.write_bytes(raw)
    return raw


def _write_supporting_sources(mapping_path: Path, reviewed_dir: Path) -> tuple[bytes, bytes]:
    mapping_raw = json.dumps({"AAAAAAAAAAA": "-235216998_1"}, ensure_ascii=False).encode("utf-8")
    mapping_path.write_bytes(mapping_raw)
    reviewed_dir.mkdir()
    reviewed_raw = json.dumps(
        {
            "video_id": "AAAAAAAAAAA",
            "channel_id": CHANNEL_ID,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    (reviewed_dir / "AAAAAAAAAAA.json").write_bytes(reviewed_raw)
    return mapping_raw, reviewed_raw


def test_video_intake_cli_builds_project_bound_hashed_artifact(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.json"
    mapping_path = tmp_path / "mapping.json"
    reviewed_dir = tmp_path / "reviewed"
    output_path = tmp_path / "intake.json"
    audit_raw = _write_audit(audit_path)
    mapping_raw, reviewed_raw = _write_supporting_sources(mapping_path, reviewed_dir)

    result = runner.invoke(
        app,
        [
            "instagram",
            "video-intake",
            str(audit_path),
            "--project",
            "legendary-poet",
            "--mapping",
            str(mapping_path),
            "--reviewed-dir",
            str(reviewed_dir),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["project_key"] == "legendary-poet"
    assert payload["channel_id"] == CHANNEL_ID
    assert payload["provider_effect"] == "impossible"
    assert payload["provider_writes_authorized"] is False
    assert payload["counts"]["current_videos"] == 1
    assert payload["counts"]["format_unknown"] == 1
    assert payload["records"][0]["exact_vk_video_id"] == "-235216998_1"
    assert payload["source_evidence"]["audit_package_sha256"] == (
        f"sha256:{hashlib.sha256(audit_raw).hexdigest()}"
    )
    assert payload["source_evidence"]["frozen_mapping_sha256"] == (
        f"sha256:{hashlib.sha256(mapping_raw).hexdigest()}"
    )

    corpus = hashlib.sha256()
    corpus.update(b"AAAAAAAAAAA.json")
    corpus.update(b"\0")
    corpus.update(reviewed_raw)
    corpus.update(b"\0")
    assert payload["source_evidence"]["reviewed_corpus_sha256"] == f"sha256:{corpus.hexdigest()}"


def test_video_intake_cli_rejects_cross_project_channel(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.json"
    output_path = tmp_path / "intake.json"
    _write_audit(audit_path)

    result = runner.invoke(
        app,
        [
            "instagram",
            "video-intake",
            str(audit_path),
            "--project",
            "lord-god-strength",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 2
    assert "unexpected YouTube channel" in result.output
    assert not output_path.exists()


def test_video_intake_cli_rejects_reviewed_record_filename_mismatch(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.json"
    mapping_path = tmp_path / "mapping.json"
    reviewed_dir = tmp_path / "reviewed"
    output_path = tmp_path / "intake.json"
    _write_audit(audit_path)
    mapping_path.write_text("{}", encoding="utf-8")
    reviewed_dir.mkdir()
    (reviewed_dir / "AAAAAAAAAAA.json").write_text(
        json.dumps({"video_id": "BBBBBBBBBBB", "channel_id": CHANNEL_ID}),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "instagram",
            "video-intake",
            str(audit_path),
            "--project",
            "legendary-poet",
            "--mapping",
            str(mapping_path),
            "--reviewed-dir",
            str(reviewed_dir),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 2
    assert "does not match filename" in result.output
    assert not output_path.exists()
