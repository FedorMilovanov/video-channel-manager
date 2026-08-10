from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from video_channel_manager.youtube_release_plan import (
    ABSENCE_EVIDENCE_SCHEMA,
    ABSENCE_EVIDENCE_VERSION,
    EXECUTION_APPROVAL_SCHEMA,
    EXECUTION_APPROVAL_VERSION,
    build_release_plan,
    execution_approval_digest,
    validate_absence_evidence,
    validate_execution_approval,
    validate_release_plan,
)
from video_channel_manager.youtube_upload_plan import UploadPlanError, build_intent, canonical_sha256

CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"


def _intent(tmp_path: Path) -> dict:
    media = tmp_path / "release.mp4"
    media.write_bytes(b"current-main-youtube-release")
    media_sha = "sha256:" + hashlib.sha256(media.read_bytes()).hexdigest()
    spec = {
        "schema_name": "video-manager.youtube-video-upload-spec",
        "schema_version": "2.0",
        "project_key": "legendary-poet",
        "account_alias": "legendary-poet",
        "target_channel_id": CHANNEL_ID,
        "expected_media_sha256": media_sha,
        "title": "Black Man",
        "description": "Exact release description",
        "tags": ["Есенин", "Black Man"],
        "privacy_status": "private",
        "contains_synthetic_media": True,
        "self_declared_made_for_kids": False,
    }
    return build_intent(spec, media, created_at="2026-08-10T12:00:00+00:00")


def _plan(tmp_path: Path, **kwargs) -> dict:
    return build_release_plan(_intent(tmp_path), **kwargs)


def _absence(plan: dict) -> dict:
    return {
        "schema_name": ABSENCE_EVIDENCE_SCHEMA,
        "schema_version": ABSENCE_EVIDENCE_VERSION,
        "project_key": plan["project_key"],
        "account_alias": plan["account_alias"],
        "target_channel_id": plan["target_channel_id"],
        "upload_key_sha256": plan["upload_key_sha256"],
        "media_sha256": plan["media"]["sha256"],
        "provider_effect": "confirmed_absent",
        "provider_writes_performed": 0,
        "reviewed_by": "FedorMilovanov",
        "reviewed_at": "2026-08-10T12:10:00+00:00",
    }


def _approval(plan: dict, *, children: list[str], absence_sha: str | None = None) -> dict:
    approval = {
        "schema_name": EXECUTION_APPROVAL_SCHEMA,
        "schema_version": EXECUTION_APPROVAL_VERSION,
        "approval_id": "reviewed-release-approval",
        "release_plan_sha256": plan["release_plan_sha256"],
        "project_key": plan["project_key"],
        "account_alias": plan["account_alias"],
        "target_channel_id": plan["target_channel_id"],
        "upload_key_sha256": plan["upload_key_sha256"],
        "approved_child_ids": children,
        "existing_target_absence_evidence_sha256": absence_sha,
        "provider_writes_authorized": True,
        "reviewed_by": "FedorMilovanov",
        "reviewed_at": "2026-08-10T12:20:00+00:00",
    }
    approval["approval_sha256"] = execution_approval_digest(approval)
    return approval


def test_release_plan_is_inert_and_byte_bound(tmp_path: Path) -> None:
    plan = _plan(tmp_path, playlist_ids=["PL-one", "PL-two"])
    assert plan["provider_write_authorized"] is False
    assert plan["media"]["sha256"].startswith("sha256:")
    assert plan["playlist_ids"] == ["PL-one", "PL-two"]
    validate_release_plan(plan)


def test_release_plan_binds_thumbnail_bytes(tmp_path: Path) -> None:
    thumbnail = tmp_path / "cover.jpg"
    thumbnail.write_bytes(b"jpeg-fixture")
    plan = _plan(tmp_path, thumbnail_path=thumbnail)
    assert plan["thumbnail"]["path"] == str(thumbnail.resolve())
    validate_release_plan(plan)
    thumbnail.write_bytes(b"tampered")
    with pytest.raises(UploadPlanError, match="Thumbnail SHA mismatch"):
        validate_release_plan(plan)


def test_release_plan_rejects_thumbnail_above_two_megabytes(tmp_path: Path) -> None:
    thumbnail = tmp_path / "cover.png"
    thumbnail.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    with pytest.raises(UploadPlanError, match="2 MB"):
        _plan(tmp_path, thumbnail_path=thumbnail)


def test_release_plan_rejects_unknown_thumbnail_type(tmp_path: Path) -> None:
    thumbnail = tmp_path / "cover.webp"
    thumbnail.write_bytes(b"webp")
    with pytest.raises(UploadPlanError, match="PNG or JPEG"):
        _plan(tmp_path, thumbnail_path=thumbnail)


def test_release_plan_rejects_duplicate_playlists(tmp_path: Path) -> None:
    with pytest.raises(UploadPlanError, match="unique"):
        _plan(tmp_path, playlist_ids=["PL-x", "PL-x"])


def test_release_plan_rejects_blank_comment(tmp_path: Path) -> None:
    with pytest.raises(UploadPlanError, match="cannot be blank"):
        _plan(tmp_path, top_level_comment="   ")


def test_tampered_plan_digest_is_rejected(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    plan["final_privacy_status"] = "unlisted"
    with pytest.raises(UploadPlanError, match="SHA-256"):
        validate_release_plan(plan, verify_files=False)


def test_tampered_media_bytes_are_rejected(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    Path(plan["media"]["path"]).write_bytes(b"changed")
    with pytest.raises(UploadPlanError, match="media SHA mismatch"):
        validate_release_plan(plan)


def test_canonical_plan_cannot_be_turned_into_write_authority(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    plan["provider_write_authorized"] = True
    plan["release_plan_sha256"] = canonical_sha256(
        {key: value for key, value in plan.items() if key != "release_plan_sha256"}
    )
    with pytest.raises(UploadPlanError, match="must remain provider_write_authorized=false"):
        validate_release_plan(plan, verify_files=False)


def test_absence_evidence_is_exact_identity_bound(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    evidence = _absence(plan)
    digest = validate_absence_evidence(evidence, plan=plan)
    assert digest == canonical_sha256(evidence)
    evidence["target_channel_id"] = "UC-wrong"
    with pytest.raises(UploadPlanError, match="target_channel_id"):
        validate_absence_evidence(evidence, plan=plan)


def test_absence_evidence_must_be_provider_read_only(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    evidence = _absence(plan)
    evidence["provider_writes_performed"] = 1
    with pytest.raises(UploadPlanError, match="provider-read-only"):
        validate_absence_evidence(evidence, plan=plan)


def test_execution_approval_binds_exact_plan_child_and_absence_proof(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    absence_sha = validate_absence_evidence(_absence(plan), plan=plan)
    approval = _approval(plan, children=["upload-session"], absence_sha=absence_sha)
    validate_execution_approval(
        approval,
        plan=plan,
        child_id="upload-session",
        absence_evidence_sha256=absence_sha,
    )
    with pytest.raises(UploadPlanError, match="does not authorize release child"):
        validate_execution_approval(
            approval,
            plan=plan,
            child_id="upload",
            absence_evidence_sha256=absence_sha,
        )


def test_execution_approval_cannot_bind_different_absence_evidence(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    approval = _approval(plan, children=["upload-session"], absence_sha="sha256:" + "f" * 64)
    with pytest.raises(UploadPlanError, match="does not bind"):
        validate_execution_approval(
            approval,
            plan=plan,
            child_id="upload-session",
            absence_evidence_sha256="sha256:" + "e" * 64,
        )


def test_execution_approval_requires_write_authorization(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    approval = _approval(plan, children=["upload-session"])
    approval["provider_writes_authorized"] = False
    approval["approval_sha256"] = execution_approval_digest(approval)
    with pytest.raises(UploadPlanError, match="does not authorize provider writes"):
        validate_execution_approval(approval, plan=plan, child_id="upload-session")


def test_execution_approval_digest_detects_tampering(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    approval = _approval(plan, children=["upload-session"])
    approval["approved_child_ids"] = ["upload"]
    with pytest.raises(UploadPlanError, match="approval SHA-256"):
        validate_execution_approval(approval, plan=plan, child_id="upload")


def test_release_plan_requires_private_initial_status(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    tampered = copy.deepcopy(plan)
    tampered["initial_status"]["privacyStatus"] = "public"
    tampered["release_plan_sha256"] = canonical_sha256(
        {key: value for key, value in tampered.items() if key != "release_plan_sha256"}
    )
    with pytest.raises(UploadPlanError, match="initial_status must be private"):
        validate_release_plan(tampered, verify_files=False)
