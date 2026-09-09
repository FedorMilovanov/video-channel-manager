from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import pytest
from pydantic import ValidationError

from video_channel_manager.telegram_historical_archival_revision import (
    HistoricalRevisionArchivalMediaV2,
    HistoricalRevisionPackageV2,
    _probe_image,
    _verify_binary_identity,
)
from video_channel_manager.telegram_historical_revision import HistoricalRevisionGitBlobRef


def _git_blob(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()  # noqa: S324


def _png(width: int = 640, height: int = 480) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", width, height)


def _media(*, slot: str = "hero", asset_id: str = "img-example-archival-hero") -> dict[str, object]:
    return {
        "asset_id": asset_id,
        "slot": slot,
        "source_id": "src-example-archive",
        "acquisition_asset_id": "img-example-acquired-source",
        "exhibit_kind": "primary_document_facsimile",
        "accepted_file": {"path": f"content/example-{slot}.png", "git_blob_sha": "a" * 40},
        "accepted_mime": "image/png",
        "accepted_byte_length": 100,
        "accepted_width": 640,
        "accepted_height": 480,
        "accepted_sha256": "sha256:" + "b" * 64,
        "placement_after": "evidence",
        "depicts": "Exact archival source exhibit selected for the historical post.",
        "purpose": "Show the bound historical document without reconstructing it.",
        "claim_boundary": "The image evidences only the bound document and is not a reconstruction of unstated events.",
        "rights_basis": "Public-domain or archive-authorized historical source with explicit attribution.",
        "attribution_text": "Example Archive, exact historical source exhibit.",
        "transport_ready": False,
        "provider_write_performed": False,
    }


def _package() -> dict[str, object]:
    ref = {"path": "content/example.json", "git_blob_sha": "c" * 40}
    return {
        "schema_name": "video-channel-manager.telegram-historical-revision-package",
        "schema_version": 2,
        "revision_id": "historical-revision-example-archival-v2",
        "owning_issue": 561,
        "checked_on": "2026-09-09",
        "project_key": "lord-god-strength",
        "channel_username": "@lordchrist",
        "publication_id": "lordchrist-history-example-topic-v3",
        "state": "provider_inert",
        "provider_writes_authorized": False,
        "live_eligible": False,
        "post": {"path": "content/post.json", "git_blob_sha": "1" * 40},
        "verification": {"path": "content/verification.json", "git_blob_sha": "2" * 40},
        "theology_profile": {"path": "content/theology.json", "git_blob_sha": "3" * 40},
        "source_shards": [
            {"path": "content/source-a.json", "git_blob_sha": "4" * 40},
            {"path": "content/source-b.json", "git_blob_sha": "5" * 40},
        ],
        "acquisition_manifest": {"path": "content/acquisition.json", "git_blob_sha": "6" * 40},
        "render_receipt": ref,
        "archival_media": [_media()],
    }


def test_archival_revision_probe_accepts_png_dimensions() -> None:
    assert _probe_image(_png(321, 123)) == ("image/png", 321, 123)


def test_archival_revision_binary_identity_binds_git_blob_sha256_size_and_dimensions(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    path = repo / "content/example.png"
    path.parent.mkdir(parents=True)
    data = _png(800, 600)
    path.write_bytes(data)
    ref = HistoricalRevisionGitBlobRef(path="content/example.png", git_blob_sha=_git_blob(data))

    _verify_binary_identity(
        ref,
        repo_root=repo,
        sha256="sha256:" + hashlib.sha256(data).hexdigest(),
        byte_length=len(data),
        mime="image/png",
        width=800,
        height=600,
    )

    with pytest.raises(ValueError, match="SHA-256 differs"):
        _verify_binary_identity(
            ref,
            repo_root=repo,
            sha256="sha256:" + "0" * 64,
            byte_length=len(data),
            mime="image/png",
            width=800,
            height=600,
        )


def test_archival_media_cannot_be_promoted_to_transport_ready() -> None:
    payload = _media()
    payload["transport_ready"] = True
    with pytest.raises(ValidationError):
        HistoricalRevisionArchivalMediaV2.model_validate(payload)


def test_archival_media_suffix_must_match_accepted_mime() -> None:
    payload = _media()
    accepted_file = payload["accepted_file"]
    assert isinstance(accepted_file, dict)
    accepted_file["path"] = "content/example.jpg"
    with pytest.raises(ValidationError, match="suffix"):
        HistoricalRevisionArchivalMediaV2.model_validate(payload)


def test_archival_package_rejects_duplicate_visual_slots() -> None:
    payload = _package()
    first = _media(slot="hero", asset_id="img-example-archival-one")
    second = _media(slot="hero", asset_id="img-example-archival-two")
    second_file = second["accepted_file"]
    assert isinstance(second_file, dict)
    second_file["path"] = "content/example-hero-two.png"
    payload["archival_media"] = [first, second]
    with pytest.raises(ValidationError, match="slots must be unique"):
        HistoricalRevisionPackageV2.model_validate(payload)


def test_archival_package_stays_provider_inert() -> None:
    package = HistoricalRevisionPackageV2.model_validate(_package())
    assert package.schema_version == 2
    assert package.provider_writes_authorized is False
    assert package.live_eligible is False
    assert all(media.transport_ready is False for media in package.archival_media)
