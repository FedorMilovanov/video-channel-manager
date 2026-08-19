from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from video_channel_manager.cli.app import app
from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef, VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.exchange.instagram_video import InstagramMediaReview
from video_channel_manager.local_media import (
    MediaAcquisitionEvidence,
    MediaArtifactEvidence,
    MediaCompatibilityProfile,
    MediaProbeEvidence,
    MediaSourceIdentity,
    calculate_media_manifest_sha256,
    write_media_artifact_manifest,
)


CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"
VIDEO_ID = "AAAAAAAAAAA"
MEDIA_SHA = "sha256:" + "2" * 64
runner = CliRunner()


def _write_audit(path: Path) -> bytes:
    channel_ref = RemoteRef(platform=PlatformName.YOUTUBE, channel_id=CHANNEL_ID, remote_id=CHANNEL_ID)
    video_ref = RemoteRef(platform=PlatformName.YOUTUBE, channel_id=CHANNEL_ID, remote_id=VIDEO_ID)
    audit = AuditPackage(
        channel=ChannelRecord(ref=channel_ref, title="The Legendary Poet", kind=ChannelKind.VIDEO_CHANNEL),
        videos=[VideoRecord(ref=video_ref, title="One video", duration_seconds=55, revision="sha256:revision")],
    )
    raw = audit.model_dump_json(indent=2).encode("utf-8")
    path.write_bytes(raw)
    return raw


def _write_supporting_sources(mapping_path: Path, reviewed_dir: Path) -> tuple[bytes, bytes]:
    mapping_raw = json.dumps({VIDEO_ID: "-235216998_1"}, ensure_ascii=False).encode("utf-8")
    mapping_path.write_bytes(mapping_raw)
    reviewed_dir.mkdir()
    reviewed_raw = json.dumps(
        {
            "video_id": VIDEO_ID,
            "channel_id": CHANNEL_ID,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    (reviewed_dir / f"{VIDEO_ID}.json").write_bytes(reviewed_raw)
    return mapping_raw, reviewed_raw


def _write_intake(tmp_path: Path) -> Path:
    audit_path = tmp_path / "audit.json"
    mapping_path = tmp_path / "mapping.json"
    reviewed_dir = tmp_path / "reviewed"
    output_path = tmp_path / "intake.json"
    _write_audit(audit_path)
    _write_supporting_sources(mapping_path, reviewed_dir)
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
    return output_path


def _media_evidence(tmp_path: Path) -> MediaArtifactEvidence:
    master_path = (tmp_path / "master.mp4").resolve()
    provisional = MediaArtifactEvidence(
        source=MediaSourceIdentity(
            project_key="legendary-poet",
            platform=PlatformName.YOUTUBE,
            source_channel_id=CHANNEL_ID,
            source_id=VIDEO_ID,
            expected_duration_seconds=55.0,
        ),
        acquisition=MediaAcquisitionEvidence(
            method="controlled_master",
            path_authority="controlled_master",
            requested_output_path=str(master_path),
            authoritative_final_path=str(master_path),
            tool_name="controlled-master",
        ),
        profile=MediaCompatibilityProfile(),
        probe=MediaProbeEvidence(
            path=str(master_path),
            size_bytes=1_000_000,
            sha256=MEDIA_SHA,
            duration_seconds=55.0,
            format_names=("mp4",),
            video_stream_count=1,
            audio_stream_count=1,
            video_codec="h264",
            audio_codec="aac",
            width=1080,
            height=1920,
            sample_rate_hz=48_000,
            audio_channels=2,
        ),
        manifest_sha256="sha256:" + "0" * 64,
    )
    return provisional.model_copy(update={"manifest_sha256": calculate_media_manifest_sha256(provisional)})


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
    assert payload["source_evidence"]["audit_package_sha256"] == (f"sha256:{hashlib.sha256(audit_raw).hexdigest()}")
    assert payload["source_evidence"]["frozen_mapping_sha256"] == (f"sha256:{hashlib.sha256(mapping_raw).hexdigest()}")

    corpus = hashlib.sha256()
    corpus.update(f"{VIDEO_ID}.json".encode())
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
    (reviewed_dir / f"{VIDEO_ID}.json").write_text(
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
    assert "reviewed editorial video_id does not match" in result.output
    assert "filename:" in result.output
    assert not output_path.exists()


def test_media_route_cli_builds_direct_remaster_from_exact_evidence(tmp_path: Path) -> None:
    intake_path = _write_intake(tmp_path)
    manifest_dir = tmp_path / "media-manifests"
    review_dir = tmp_path / "media-reviews"
    route_path = tmp_path / "route.json"
    manifest_dir.mkdir()
    review_dir.mkdir()

    evidence = _media_evidence(tmp_path)
    write_media_artifact_manifest(evidence, manifest_dir / f"{VIDEO_ID}.json")
    review = InstagramMediaReview(
        project_key="legendary-poet",
        youtube_channel_id=CHANNEL_ID,
        youtube_video_id=VIDEO_ID,
        media_manifest_sha256=evidence.manifest_sha256,
        rights_status="cleared",
        master_provenance="project_owned_clean_master",
        reviewed_at=datetime(2026, 8, 20, tzinfo=UTC),
        reviewed_by="test-reviewer",
    )
    (review_dir / f"{VIDEO_ID}.json").write_text(review.model_dump_json(indent=2), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "instagram",
            "media-route",
            str(intake_path),
            "--media-manifest-dir",
            str(manifest_dir),
            "--media-review-dir",
            str(review_dir),
            "--output",
            str(route_path),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(route_path.read_text(encoding="utf-8"))
    assert payload["provider_effect"] == "impossible"
    assert payload["counts"]["direct_remaster"] == 1
    assert payload["records"][0]["route"] == "direct_remaster"
    assert payload["records"][0]["media_manifest_sha256"] == evidence.manifest_sha256
