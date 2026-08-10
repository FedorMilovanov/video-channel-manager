from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from video_channel_manager.youtube_release_execution import (
    execute_child,
    execute_next,
    metadata_verdict,
    processing_verdict,
    reconcile,
)
from video_channel_manager.youtube_release_plan import (
    ABSENCE_EVIDENCE_SCHEMA,
    ABSENCE_EVIDENCE_VERSION,
    EXECUTION_APPROVAL_SCHEMA,
    EXECUTION_APPROVAL_VERSION,
    build_release_plan,
    execution_approval_digest,
    validate_absence_evidence,
)
from video_channel_manager.youtube_release_provider import ReleaseProviderResult
from video_channel_manager.youtube_release_state import (
    build_release_state,
    child_by_id,
    mark_existing_target_absent,
    prepare_child,
    transition_child,
)
from video_channel_manager.youtube_stable_state import read_json, write_json_atomic
from video_channel_manager.youtube_upload_plan import (
    UploadPlanError,
    build_intent,
    journal_path,
    planned_journal,
)

CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"
SHA_X = "sha256:" + "f" * 64
SESSION = "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=fixture"


def _fixture(tmp_path: Path, *, playlists: list[str] | None = None) -> tuple[dict, Path, Path, str]:
    media = tmp_path / "release.mp4"
    media.write_bytes(b"guarded-release-fixture")
    media_sha = "sha256:" + hashlib.sha256(media.read_bytes()).hexdigest()
    spec = {
        "schema_name": "video-manager.youtube-video-upload-spec",
        "schema_version": "2.0",
        "project_key": "legendary-poet",
        "account_alias": "legendary-poet",
        "target_channel_id": CHANNEL_ID,
        "expected_media_sha256": media_sha,
        "title": "Black Man",
        "description": "Exact release",
        "tags": ["Есенин", "Black Man"],
        "privacy_status": "private",
        "contains_synthetic_media": True,
        "self_declared_made_for_kids": False,
    }
    intent = build_intent(spec, media, created_at="2026-08-10T12:00:00+00:00")
    plan = build_release_plan(intent, playlist_ids=playlists or [], final_privacy_status="public")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    data_dir = tmp_path / "state"
    stable = journal_path(data_dir, plan["upload_key_sha256"])
    absence = {
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
    absence_sha = validate_absence_evidence(absence, plan=plan)
    release = mark_existing_target_absent(
        build_release_state(
            upload_key_sha256=plan["upload_key_sha256"],
            release_plan_sha256=plan["release_plan_sha256"],
            playlist_ids=list(plan["playlist_ids"]),
        ),
        evidence=absence,
    )
    journal = planned_journal(intent)
    journal["release"] = release
    journal["release_plan_sha256"] = plan["release_plan_sha256"]
    journal["release_absence_evidence_sha256"] = absence_sha
    write_json_atomic(stable, journal)
    return plan, plan_path, stable, absence_sha


def _approval(plan: dict, child_id: str, absence_sha: str) -> dict:
    approval = {
        "schema_name": EXECUTION_APPROVAL_SCHEMA,
        "schema_version": EXECUTION_APPROVAL_VERSION,
        "approval_id": "test-execution-approval",
        "release_plan_sha256": plan["release_plan_sha256"],
        "project_key": plan["project_key"],
        "account_alias": plan["account_alias"],
        "target_channel_id": plan["target_channel_id"],
        "upload_key_sha256": plan["upload_key_sha256"],
        "approved_child_ids": [child_id],
        "existing_target_absence_evidence_sha256": absence_sha,
        "provider_writes_authorized": True,
        "reviewed_by": "FedorMilovanov",
        "reviewed_at": "2026-08-10T12:20:00+00:00",
    }
    approval["approval_sha256"] = execution_approval_digest(approval)
    return approval


def _write_approval(tmp_path: Path, approval: dict) -> Path:
    path = tmp_path / "approval.json"
    path.write_text(json.dumps(approval), encoding="utf-8")
    return path


def _advance(
    release: dict,
    child_id: str,
    *,
    remote_id: str | None = None,
    runtime: dict[str, Any] | None = None,
) -> dict:
    release = prepare_child(release, child_id=child_id, payload={"fixture": child_id})
    return transition_child(
        release,
        child_id=child_id,
        provider_effect="verified",
        remote_id=remote_id,
        evidence={"fixture": True},
        runtime_updates=runtime,
    )


def _release(stable: Path) -> dict:
    return read_json(stable)["release"]


class FakeProvider:
    def __init__(self) -> None:
        self.closed = False
        self.readbacks: list[dict[str, Any]] = []
        self.playlist_answers: list[bool] = []
        self.session_result = ReleaseProviderResult(
            provider_effect="verified",
            evidence={"session": True},
            runtime={"session_url": SESSION, "session_url_sha256": SHA_X},
        )
        self.upload_result = ReleaseProviderResult(
            provider_effect="verified",
            remote_id="video123",
            evidence={"upload": True},
            runtime={"next_offset": 23, "resume_requires_status_query": False},
        )
        self.status_result = ReleaseProviderResult(
            provider_effect="confirmed_absent",
            evidence={"range": "bytes=0-9"},
            runtime={"next_offset": 10, "resume_requires_status_query": False},
        )
        self.metadata_result = ReleaseProviderResult(
            provider_effect="may_exist",
            remote_id="video123",
            evidence={"accepted_response": True},
            runtime={"accepted_response": True},
        )
        self.thumbnail_result = ReleaseProviderResult(
            provider_effect="verified", remote_id="video123", evidence={"thumbnail": True}
        )
        self.playlist_result = ReleaseProviderResult(
            provider_effect="may_exist",
            remote_id="membership-1",
            evidence={"accepted_response": True},
        )
        self.visibility_result = ReleaseProviderResult(
            provider_effect="may_exist",
            remote_id="video123",
            evidence={"accepted_response": True},
        )
        self.comment_result = ReleaseProviderResult(
            provider_effect="verified", remote_id="comment-1", evidence={"comment": True}
        )
        self.calls: list[str] = []

    def close(self) -> None:
        self.closed = True

    def read_video(self, video_id: str) -> dict[str, Any]:
        self.calls.append("read_video")
        assert video_id == "video123"
        if not self.readbacks:
            raise AssertionError("missing fake readback")
        return self.readbacks.pop(0)

    def playlist_contains_video(self, playlist_id: str, video_id: str) -> bool:
        self.calls.append("playlist_contains")
        assert playlist_id.startswith("PL")
        assert video_id == "video123"
        return self.playlist_answers.pop(0)

    def start_upload_session(self, **kwargs) -> ReleaseProviderResult:
        self.calls.append("start_upload_session")
        return self.session_result

    def upload_media(self, **kwargs) -> ReleaseProviderResult:
        self.calls.append("upload_media")
        return self.upload_result

    def query_upload_status(self, **kwargs) -> ReleaseProviderResult:
        self.calls.append("query_upload_status")
        return self.status_result

    def update_metadata_status(self, **kwargs) -> ReleaseProviderResult:
        self.calls.append("update_metadata_status")
        return self.metadata_result

    def set_thumbnail(self, **kwargs) -> ReleaseProviderResult:
        self.calls.append("set_thumbnail")
        return self.thumbnail_result

    def insert_playlist_item(self, **kwargs) -> ReleaseProviderResult:
        self.calls.append("insert_playlist_item")
        return self.playlist_result

    def update_visibility(self, **kwargs) -> ReleaseProviderResult:
        self.calls.append("update_visibility")
        return self.visibility_result

    def create_top_level_comment(self, **kwargs) -> ReleaseProviderResult:
        self.calls.append("create_top_level_comment")
        return self.comment_result


def test_metadata_verdict_accepts_tag_reordering_but_requires_observed_boolean(tmp_path: Path) -> None:
    plan, _, _, _ = _fixture(tmp_path)
    raw = {
        "snippet": {
            "title": plan["snippet"]["title"],
            "description": plan["snippet"]["description"],
            "categoryId": plan["snippet"]["categoryId"],
            "tags": list(reversed(plan["snippet"]["tags"])),
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
        },
    }
    verified, evidence = metadata_verdict(plan, raw)
    assert verified is True
    assert evidence["contains_synthetic_media_verdict"] == "verified"
    del raw["status"]["containsSyntheticMedia"]
    verified, evidence = metadata_verdict(plan, raw)
    assert verified is False
    assert evidence["contains_synthetic_media_verdict"] == "unobserved"


def test_metadata_verdict_preserves_tag_multiplicity(tmp_path: Path) -> None:
    plan, _, _, _ = _fixture(tmp_path)
    raw = {
        "snippet": {
            "title": plan["snippet"]["title"],
            "description": plan["snippet"]["description"],
            "categoryId": plan["snippet"]["categoryId"],
            "tags": [plan["snippet"]["tags"][0], plan["snippet"]["tags"][0]],
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
        },
    }
    assert metadata_verdict(plan, raw)[0] is False


def test_processing_verdict_requires_target_private_and_succeeded(tmp_path: Path) -> None:
    plan, _, _, _ = _fixture(tmp_path)
    good = {
        "snippet": {"channelId": CHANNEL_ID},
        "status": {"privacyStatus": "private"},
        "processingDetails": {"processingStatus": "succeeded"},
    }
    assert processing_verdict(plan, good)[0] == "verified"
    good["processingDetails"]["processingStatus"] = "processing"
    assert processing_verdict(plan, good)[0] == "not_ready"
    good["processingDetails"]["processingStatus"] = "failed"
    assert processing_verdict(plan, good)[0] == "blocked"


def test_execute_requires_explicit_flag_before_provider_builder(tmp_path: Path) -> None:
    plan, plan_path, _, absence_sha = _fixture(tmp_path)
    approval_path = _write_approval(tmp_path, _approval(plan, "upload-session", absence_sha))
    called = False

    def builder(_alias: str):
        nonlocal called
        called = True
        raise AssertionError("provider must not be built")

    with pytest.raises(UploadPlanError, match="explicit --execute"):
        execute_next(
            argparse.Namespace(
                execute=False,
                plan=plan_path,
                approval=approval_path,
                data_dir=tmp_path / "state",
            ),
            provider_builder=builder,
        )
    assert called is False


def test_wrong_approval_is_rejected_before_provider_builder(tmp_path: Path) -> None:
    plan, plan_path, _, absence_sha = _fixture(tmp_path)
    approval_path = _write_approval(tmp_path, _approval(plan, "upload", absence_sha))
    called = False

    def builder(_alias: str):
        nonlocal called
        called = True
        raise AssertionError("provider must not be built")

    with pytest.raises(UploadPlanError, match="does not authorize release child upload-session"):
        execute_next(
            argparse.Namespace(
                execute=True,
                plan=plan_path,
                approval=approval_path,
                data_dir=tmp_path / "state",
            ),
            provider_builder=builder,
        )
    assert called is False


def test_upload_session_is_pessimistically_may_exist_before_provider_call(tmp_path: Path) -> None:
    plan, plan_path, stable, absence_sha = _fixture(tmp_path)
    approval_path = _write_approval(tmp_path, _approval(plan, "upload-session", absence_sha))

    class InspectingProvider(FakeProvider):
        def start_upload_session(self, **kwargs) -> ReleaseProviderResult:
            assert child_by_id(_release(stable), "upload-session")["provider_effect"] == "may_exist"
            return super().start_upload_session(**kwargs)

    fake = InspectingProvider()
    assert (
        execute_next(
            argparse.Namespace(
                execute=True,
                plan=plan_path,
                approval=approval_path,
                data_dir=tmp_path / "state",
            ),
            provider_builder=lambda _alias: fake,
        )
        == 0
    )
    child = child_by_id(_release(stable), "upload-session")
    assert child["provider_effect"] == "verified"
    assert child["runtime"]["session_url"] == SESSION
    assert fake.closed is True


def test_ambiguous_upload_blocks_next_until_reconcile(tmp_path: Path) -> None:
    plan, _, stable, _ = _fixture(tmp_path)
    journal = read_json(stable)
    release = _advance(
        journal["release"],
        "upload-session",
        runtime={"session_url": SESSION, "session_url_sha256": SHA_X},
    )
    journal["release"] = release
    write_json_atomic(stable, journal)
    fake = FakeProvider()
    fake.upload_result = ReleaseProviderResult(
        provider_effect="may_exist",
        evidence={"timeout": True},
        runtime={"resume_requires_status_query": True},
    )
    release = execute_child(
        child_id="upload",
        plan=plan,
        journal=journal,
        release=release,
        stable_journal=stable,
        provider=fake,
    )
    assert child_by_id(release, "upload")["provider_effect"] == "may_exist"
    assert child_by_id(release, "upload")["runtime"]["resume_requires_status_query"] is True


def test_reconcile_upload_uses_status_query_and_persists_exact_offset(tmp_path: Path) -> None:
    plan, plan_path, stable, _ = _fixture(tmp_path)
    journal = read_json(stable)
    release = _advance(
        journal["release"],
        "upload-session",
        runtime={"session_url": SESSION, "session_url_sha256": SHA_X},
    )
    release = prepare_child(release, child_id="upload", payload={"fixture": "upload"})
    release = transition_child(
        release,
        child_id="upload",
        provider_effect="may_exist",
        runtime_updates={"resume_requires_status_query": True},
    )
    journal["release"] = release
    write_json_atomic(stable, journal)
    fake = FakeProvider()
    assert (
        reconcile(
            argparse.Namespace(plan=plan_path, data_dir=tmp_path / "state"),
            provider_builder=lambda _alias: fake,
        )
        == 0
    )
    upload = child_by_id(_release(stable), "upload")
    assert upload["provider_effect"] == "confirmed_absent"
    assert upload["runtime"]["next_offset"] == 10
    assert fake.calls == ["query_upload_status"]


def test_metadata_exact_readback_skips_mutation(tmp_path: Path) -> None:
    plan, _, stable, _ = _fixture(tmp_path)
    journal = read_json(stable)
    release = _advance(
        journal["release"],
        "upload-session",
        runtime={"session_url": SESSION, "session_url_sha256": SHA_X},
    )
    release = _advance(release, "upload", remote_id="video123")
    release = _advance(release, "processing-private", remote_id="video123")
    journal["release"] = release
    fake = FakeProvider()
    fake.readbacks = [
        {
            "snippet": {
                **plan["snippet"],
                "tags": list(reversed(plan["snippet"]["tags"])),
            },
            "status": {**plan["initial_status"]},
        }
    ]
    release = execute_child(
        child_id="metadata-status",
        plan=plan,
        journal=journal,
        release=release,
        stable_journal=stable,
        provider=fake,
    )
    assert child_by_id(release, "metadata-status")["provider_effect"] == "verified"
    assert fake.calls == ["read_video"]


def test_metadata_accepted_but_unobserved_synthetic_stays_may_exist(tmp_path: Path) -> None:
    plan, _, stable, _ = _fixture(tmp_path)
    journal = read_json(stable)
    release = _advance(
        journal["release"],
        "upload-session",
        runtime={"session_url": SESSION, "session_url_sha256": SHA_X},
    )
    release = _advance(release, "upload", remote_id="video123")
    release = _advance(release, "processing-private", remote_id="video123")
    journal["release"] = release
    readback = {
        "snippet": dict(plan["snippet"]),
        "status": {**plan["initial_status"]},
    }
    del readback["status"]["containsSyntheticMedia"]
    fake = FakeProvider()
    fake.readbacks = [readback, readback]
    release = execute_child(
        child_id="metadata-status",
        plan=plan,
        journal=journal,
        release=release,
        stable_journal=stable,
        provider=fake,
    )
    assert child_by_id(release, "metadata-status")["provider_effect"] == "may_exist"
    assert fake.calls == ["read_video", "update_metadata_status", "read_video"]


def test_playlist_insert_is_verified_only_after_readback(tmp_path: Path) -> None:
    plan, _, stable, _ = _fixture(tmp_path, playlists=["PL-one"])
    journal = read_json(stable)
    release = _advance(
        journal["release"],
        "upload-session",
        runtime={"session_url": SESSION, "session_url_sha256": SHA_X},
    )
    release = _advance(release, "upload", remote_id="video123")
    release = _advance(release, "processing-private", remote_id="video123")
    release = _advance(release, "metadata-status", remote_id="video123")
    release = _advance(release, "thumbnail", remote_id="video123")
    journal["release"] = release
    fake = FakeProvider()
    fake.playlist_answers = [False, True]
    release = execute_child(
        child_id="playlist:PL-one",
        plan=plan,
        journal=journal,
        release=release,
        stable_journal=stable,
        provider=fake,
    )
    child = child_by_id(release, "playlist:PL-one")
    assert child["provider_effect"] == "verified"
    assert child["remote_id"] == "membership-1"
    assert fake.calls == ["playlist_contains", "insert_playlist_item", "playlist_contains"]


def test_preexisting_playlist_membership_skips_insert(tmp_path: Path) -> None:
    plan, _, stable, _ = _fixture(tmp_path, playlists=["PL-one"])
    journal = read_json(stable)
    release = _advance(
        journal["release"],
        "upload-session",
        runtime={"session_url": SESSION, "session_url_sha256": SHA_X},
    )
    for child in ("upload", "processing-private", "metadata-status", "thumbnail"):
        release = _advance(release, child, remote_id="video123")
    journal["release"] = release
    fake = FakeProvider()
    fake.playlist_answers = [True]
    release = execute_child(
        child_id="playlist:PL-one",
        plan=plan,
        journal=journal,
        release=release,
        stable_journal=stable,
        provider=fake,
    )
    assert child_by_id(release, "playlist:PL-one")["provider_effect"] == "verified"
    assert fake.calls == ["playlist_contains"]


def test_visibility_preexisting_target_state_skips_mutation(tmp_path: Path) -> None:
    plan, _, stable, _ = _fixture(tmp_path)
    journal = read_json(stable)
    release = _advance(
        journal["release"],
        "upload-session",
        runtime={"session_url": SESSION, "session_url_sha256": SHA_X},
    )
    for child in ("upload", "processing-private", "metadata-status", "thumbnail"):
        release = _advance(release, child, remote_id="video123")
    journal["release"] = release
    fake = FakeProvider()
    fake.readbacks = [{"status": {"privacyStatus": "public"}}]
    release = execute_child(
        child_id="visibility-publication",
        plan=plan,
        journal=journal,
        release=release,
        stable_journal=stable,
        provider=fake,
    )
    assert child_by_id(release, "visibility-publication")["provider_effect"] == "verified"
    assert fake.calls == ["read_video"]


def test_visibility_update_requires_converged_readback(tmp_path: Path) -> None:
    plan, _, stable, _ = _fixture(tmp_path)
    journal = read_json(stable)
    release = _advance(
        journal["release"],
        "upload-session",
        runtime={"session_url": SESSION, "session_url_sha256": SHA_X},
    )
    for child in ("upload", "processing-private", "metadata-status", "thumbnail"):
        release = _advance(release, child, remote_id="video123")
    journal["release"] = release
    fake = FakeProvider()
    fake.readbacks = [
        {"status": {"privacyStatus": "private"}},
        {"status": {"privacyStatus": "public"}},
    ]
    release = execute_child(
        child_id="visibility-publication",
        plan=plan,
        journal=journal,
        release=release,
        stable_journal=stable,
        provider=fake,
    )
    assert child_by_id(release, "visibility-publication")["provider_effect"] == "verified"
    assert fake.calls == ["read_video", "update_visibility", "read_video"]


def test_optional_thumbnail_and_comment_are_verified_without_provider_write(tmp_path: Path) -> None:
    plan, _, stable, _ = _fixture(tmp_path)
    journal = read_json(stable)
    release = _advance(
        journal["release"],
        "upload-session",
        runtime={"session_url": SESSION, "session_url_sha256": SHA_X},
    )
    for child in ("upload", "processing-private", "metadata-status"):
        release = _advance(release, child, remote_id="video123")
    fake = FakeProvider()
    release = execute_child(
        child_id="thumbnail",
        plan=plan,
        journal=journal,
        release=release,
        stable_journal=stable,
        provider=fake,
    )
    release = _advance(release, "visibility-publication", remote_id="video123")
    release = execute_child(
        child_id="top-level-comment",
        plan=plan,
        journal=journal,
        release=release,
        stable_journal=stable,
        provider=fake,
    )
    assert child_by_id(release, "thumbnail")["provider_effect"] == "verified"
    assert child_by_id(release, "top-level-comment")["provider_effect"] == "verified"
    assert "set_thumbnail" not in fake.calls
    assert "create_top_level_comment" not in fake.calls


def test_manual_pin_required_never_calls_provider(tmp_path: Path) -> None:
    plan, _, stable, _ = _fixture(tmp_path)
    plan["manual_pin_evidence_required"] = True
    journal = read_json(stable)
    release = _advance(
        journal["release"],
        "upload-session",
        runtime={"session_url": SESSION, "session_url_sha256": SHA_X},
    )
    for child in (
        "upload",
        "processing-private",
        "metadata-status",
        "thumbnail",
        "visibility-publication",
        "top-level-comment",
    ):
        release = _advance(release, child, remote_id="video123")
    fake = FakeProvider()
    with pytest.raises(UploadPlanError, match="Manual pin evidence is required"):
        execute_child(
            child_id="manual-pin-evidence",
            plan=plan,
            journal=journal,
            release=release,
            stable_journal=stable,
            provider=fake,
        )
    assert fake.calls == []


def test_reconcile_refuses_unsafe_child_instead_of_replaying_mutation(tmp_path: Path) -> None:
    plan, plan_path, stable, _ = _fixture(tmp_path)
    journal = read_json(stable)
    release = _advance(
        journal["release"],
        "upload-session",
        runtime={"session_url": SESSION, "session_url_sha256": SHA_X},
    )
    for child in ("upload", "processing-private", "metadata-status"):
        release = _advance(release, child, remote_id="video123")
    release = prepare_child(release, child_id="thumbnail", payload={"thumbnail": True})
    release = transition_child(release, child_id="thumbnail", provider_effect="may_exist")
    journal["release"] = release
    write_json_atomic(stable, journal)
    fake = FakeProvider()
    with pytest.raises(UploadPlanError, match="cannot be safely auto-reconciled"):
        reconcile(
            argparse.Namespace(plan=plan_path, data_dir=tmp_path / "state"),
            provider_builder=lambda _alias: fake,
        )
    assert fake.calls == []
    assert child_by_id(_release(stable), "thumbnail")["provider_effect"] == "may_exist"
