from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

import video_channel_manager.youtube_album_description_cli as cli
from video_channel_manager.youtube_album_description import (
    AlbumDescriptionError,
    _package_digest,
    render_album_description,
    validate_album_package,
)


CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"


def _package() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_name": "video-manager.album-package",
        "schema_version": "1.0",
        "project_key": "legendary-poet",
        "album_key": "black-man",
        "display_title": "Black Man",
        "expected_channel_id": CHANNEL_ID,
        "source_manifest_sha256": "sha256:" + "1" * 64,
        "timing_sha256": "sha256:" + "2" * 64,
        "final_media_path": "/tmp/black-man.mp4",
        "final_media_sha256": "sha256:" + "3" * 64,
        "chapters": ["00:00 Version 1", "04:00 Version 2", "08:20 Version 3"],
        "provider_write_authorized": False,
        "quality_master_sha256": "sha256:" + "4" * 64,
    }
    payload["package_sha256"] = _package_digest(payload)
    return payload


def test_render_replaces_exact_marker_from_digest_bound_package() -> None:
    rendered = render_album_description(
        "Intro\n\n[[CHAPTERS_FROM_EXACT_VERIFIED_TIMING]]\n\nFooter",
        _package(),
        project_key="legendary-poet",
    )
    assert "[[" not in rendered
    assert "00:00 Version 1\n04:00 Version 2\n08:20 Version 3" in rendered


def test_tampered_package_fails_closed() -> None:
    package = _package()
    package["chapters"] = ["00:00 Changed"]
    with pytest.raises(AlbumDescriptionError, match="package SHA-256"):
        validate_album_package(package, project_key="legendary-poet")


def test_package_requires_quality_master_provenance() -> None:
    package = _package()
    package.pop("quality_master_sha256")
    package["package_sha256"] = _package_digest(package)
    with pytest.raises(AlbumDescriptionError, match="quality_master_sha256"):
        validate_album_package(package, project_key="legendary-poet")


def test_chapters_must_start_at_zero_and_increase() -> None:
    package = _package()
    package["chapters"] = ["00:10 Version 1", "00:05 Version 2"]
    package["package_sha256"] = _package_digest(package)
    with pytest.raises(AlbumDescriptionError, match="first album chapter"):
        validate_album_package(package, project_key="legendary-poet")


def test_provider_authorization_cannot_be_smuggled_into_package() -> None:
    package = _package()
    package["provider_write_authorized"] = True
    package["package_sha256"] = _package_digest(package)
    with pytest.raises(AlbumDescriptionError, match="provider_write_authorized=false"):
        validate_album_package(package, project_key="legendary-poet")


def test_cli_writes_immutable_text_and_evidence(tmp_path: Path) -> None:
    body = tmp_path / "body.txt"
    body.write_text("Intro\n\n[[CHAPTERS_FROM_EXACT_VERIFIED_TIMING]]\n\nFooter\n", encoding="utf-8")
    package_path = tmp_path / "package.json"
    package = _package()
    package_path.write_text(json.dumps(package), encoding="utf-8")
    output = tmp_path / "description.txt"
    evidence = tmp_path / "description.evidence.json"
    args = argparse.Namespace(
        project="legendary-poet",
        body=body,
        package=package_path,
        output=output,
        evidence=evidence,
    )

    assert cli.render(args) == 0
    rendered = output.read_text(encoding="utf-8")
    proof = json.loads(evidence.read_text(encoding="utf-8"))
    assert proof["provider_write_authorized"] is False
    assert proof["album_package_sha256"] == package["package_sha256"]
    assert proof["rendered_description_sha256"] == "sha256:" + hashlib.sha256(rendered.rstrip("\n").encode()).hexdigest()

    with pytest.raises(AlbumDescriptionError, match="overwrite immutable"):
        cli.render(args)
