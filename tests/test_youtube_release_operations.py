from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from video_channel_manager.youtube_release_operations import (
    adopt_existing,
    initialize_release,
    prepare_plan,
    record_manual_evidence,
    release_from_journal,
    status,
    verify_remote_against_evidence,
    video_id_from_release,
)
from video_channel_manager.youtube_release_plan import (
    ABSENCE_EVIDENCE_SCHEMA,
    ABSENCE_EVIDENCE_VERSION,
    build_release_plan,
)
from video_channel_manager.youtube_release_state import (
    build_release_state,
    child_by_id,
    mark_existing_target_adopted,
    prepare_child,
    transition_child,
)
from video_channel_manager.youtube_stable_state import read_json, write_json_atomic
from video_channel_manager.youtube_upload_plan import (
    LIVE_STATE_EVIDENCE_SCHEMA,
    UploadPlanError,
    adopted_journal,
    build_intent,
    canonical_sha256,
    journal_path,
    planned_journal,
    stable_upload_key,
)

CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"
VIDEO_ID = "x-puy27S2qs"
REMOTE_REVISION = "sha256:" + "d" * 64


def _intent(tmp_path: Path) -> dict:
    media = tmp_path / "release.mp4"
    media.write_bytes(b"release-operations-fixture")
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


def _plan(tmp_path: Path, *, manual_pin: bool = False) -> dict:
    return build_release_plan(
        _intent(tmp_path),
        final_privacy_status="public",
        manual_pin_evidence_required=manual_pin,
    )


def _live_evidence(plan: dict) -> dict:
    return {
        "schema_name": LIVE_STATE_EVIDENCE_SCHEMA,
        "schema_version": 1,
        "project_key": plan["project_key"],
        "account_alias": plan["account_alias"],
        "channel_id": plan["target_channel_id"],
        "execution_authority": False,
        "provider_writes_authorized": False,
        "video": {
            "video_id": VIDEO_ID,
            "title": "Black Man",
            "privacy_status": "public",
            "uploaded_media_sha256": plan["media"]["sha256"],
        },
    }


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


class FakeReadClient:
    def __init__(self, *, channel_id: str = CHANNEL_ID, video_id: str = VIDEO_ID) -> None:
        self.closed = False
        self.video = SimpleNamespace(
            title="Black Man",
            privacy_status="public",
            revision=REMOTE_REVISION,
            ref=SimpleNamespace(channel_id=channel_id, remote_id=video_id),
        )

    def get_video(self, video_id: str):
        assert video_id == VIDEO_ID
        return self.video

    def close(self) -> None:
        self.closed = True


def test_adoption_validates_identity_before_client_builder(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    evidence = _live_evidence(plan)
    evidence["channel_id"] = "UC-wrong"
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    called = False

    def builder(_alias: str):
        nonlocal called
        called = True
        raise AssertionError("client must not be built")

    with pytest.raises(ValueError):
        adopt_existing(
            argparse.Namespace(
                evidence=evidence_path,
                data_dir=tmp_path / "state",
                output=tmp_path / "result.json",
            ),
            client_builder=builder,
        )
    assert called is False


def test_adoption_reads_exact_target_and_writes_verified_stable_journal(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    evidence = _live_evidence(plan)
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    client = FakeReadClient()
    result_path = tmp_path / "result.json"
    assert (
        adopt_existing(
            argparse.Namespace(
                evidence=evidence_path,
                data_dir=tmp_path / "state",
                output=result_path,
            ),
            client_builder=lambda _alias: client,
        )
        == 0
    )
    assert client.closed is True
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["provider_writes"] == 0
    assert result["remote_video_id"] == VIDEO_ID
    stable = journal_path(tmp_path / "state", plan["upload_key_sha256"])
    journal = read_json(stable)
    assert journal["provider_effect"] == "verified"
    assert journal["adopted_existing_target"] is True


def test_adoption_is_idempotent_for_same_remote_revision(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    evidence = _live_evidence(plan)
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    first = FakeReadClient()
    second = FakeReadClient()
    for index, client in enumerate((first, second), start=1):
        assert (
            adopt_existing(
                argparse.Namespace(
                    evidence=evidence_path,
                    data_dir=tmp_path / "state",
                    output=tmp_path / f"result-{index}.json",
                ),
                client_builder=lambda _alias, client=client: client,
            )
            == 0
        )
    result = json.loads((tmp_path / "result-2.json").read_text(encoding="utf-8"))
    assert result["journal_write_performed"] is False


def test_adoption_refuses_provider_channel_mismatch(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    evidence = _live_evidence(plan)
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(UploadPlanError, match="Provider channel mismatch"):
        adopt_existing(
            argparse.Namespace(
                evidence=evidence_path,
                data_dir=tmp_path / "state",
                output=tmp_path / "result.json",
            ),
            client_builder=lambda _alias: FakeReadClient(channel_id="UC-other"),
        )


def test_verify_remote_against_evidence_checks_title_and_privacy(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    evidence = _live_evidence(plan)
    remote = FakeReadClient().video
    verify_remote_against_evidence(evidence=evidence, remote=remote)
    remote.title = "Wrong"
    with pytest.raises(UploadPlanError, match="title"):
        verify_remote_against_evidence(evidence=evidence, remote=remote)


def test_prepare_plan_writes_inert_exact_plan(tmp_path: Path) -> None:
    intent = _intent(tmp_path)
    intent_path = tmp_path / "intent.json"
    intent_path.write_text(json.dumps(intent), encoding="utf-8")
    output = tmp_path / "plan.json"
    assert (
        prepare_plan(
            argparse.Namespace(
                intent=intent_path,
                output=output,
                thumbnail=None,
                playlist=["PL-one"],
                final_privacy="public",
                comment_file=None,
                manual_pin=False,
            )
        )
        == 0
    )
    plan = json.loads(output.read_text(encoding="utf-8"))
    assert plan["provider_write_authorized"] is False
    assert plan["playlist_ids"] == ["PL-one"]


def test_initialize_new_upload_requires_reviewed_absence_evidence(tmp_path: Path) -> None:
    intent = _intent(tmp_path)
    plan = build_release_plan(intent)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    stable = journal_path(tmp_path / "state", plan["upload_key_sha256"])
    write_json_atomic(stable, planned_journal(intent))
    with pytest.raises(UploadPlanError, match="requires --intent"):
        initialize_release(
            argparse.Namespace(
                plan=plan_path,
                data_dir=tmp_path / "state",
                output=tmp_path / "init.json",
                intent=None,
                absence_evidence=None,
            )
        )


def test_initialize_new_upload_binds_absence_proof_and_unlocks_session(tmp_path: Path) -> None:
    intent = _intent(tmp_path)
    plan = build_release_plan(intent)
    plan_path = tmp_path / "plan.json"
    intent_path = tmp_path / "intent.json"
    absence_path = tmp_path / "absence.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    intent_path.write_text(json.dumps(intent), encoding="utf-8")
    absence = _absence(plan)
    absence_path.write_text(json.dumps(absence), encoding="utf-8")
    stable = journal_path(tmp_path / "state", plan["upload_key_sha256"])
    write_json_atomic(stable, planned_journal(intent))
    assert (
        initialize_release(
            argparse.Namespace(
                plan=plan_path,
                data_dir=tmp_path / "state",
                output=tmp_path / "init.json",
                intent=intent_path,
                absence_evidence=absence_path,
            )
        )
        == 0
    )
    journal = read_json(stable)
    assert journal["release_absence_evidence_sha256"] == canonical_sha256(absence)
    assert child_by_id(journal["release"], "existing-target")["provider_effect"] == "confirmed_absent"
    assert child_by_id(journal["release"], "upload-session")["provider_effect"] == "not_dispatched"


def test_initialize_adopted_target_skips_upload_children(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    evidence = _live_evidence(plan)
    journal = adopted_journal(
        evidence,
        remote_video_id=VIDEO_ID,
        remote_channel_id=CHANNEL_ID,
        remote_revision=REMOTE_REVISION,
    )
    stable = journal_path(tmp_path / "state", plan["upload_key_sha256"])
    write_json_atomic(stable, journal)
    assert (
        initialize_release(
            argparse.Namespace(
                plan=plan_path,
                data_dir=tmp_path / "state",
                output=tmp_path / "init.json",
                intent=None,
                absence_evidence=None,
            )
        )
        == 0
    )
    release = read_json(stable)["release"]
    assert child_by_id(release, "existing-target")["provider_effect"] == "verified"
    assert child_by_id(release, "upload-session")["provider_effect"] == "verified"
    assert child_by_id(release, "upload")["provider_effect"] == "verified"
    assert video_id_from_release(read_json(stable), release) == VIDEO_ID


def test_initialize_is_idempotent_for_same_release_plan(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    evidence = _live_evidence(plan)
    stable = journal_path(tmp_path / "state", plan["upload_key_sha256"])
    write_json_atomic(
        stable,
        adopted_journal(
            evidence,
            remote_video_id=VIDEO_ID,
            remote_channel_id=CHANNEL_ID,
            remote_revision=REMOTE_REVISION,
        ),
    )
    first = argparse.Namespace(
        plan=plan_path,
        data_dir=tmp_path / "state",
        output=tmp_path / "init-1.json",
        intent=None,
        absence_evidence=None,
    )
    second = argparse.Namespace(**{**vars(first), "output": tmp_path / "init-2.json"})
    initialize_release(first)
    before = read_json(stable)["release"]
    initialize_release(second)
    after = read_json(stable)["release"]
    assert after == before


def test_release_from_journal_rejects_wrong_plan_binding(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    journal = {
        "release": build_release_state(
            upload_key_sha256=plan["upload_key_sha256"],
            release_plan_sha256="sha256:" + "e" * 64,
        )
    }
    with pytest.raises(UploadPlanError, match="exact release plan"):
        release_from_journal(journal, plan=plan)


def _advance_to_manual_pin(plan: dict) -> dict:
    release = mark_existing_target_adopted(
        build_release_state(
            upload_key_sha256=plan["upload_key_sha256"],
            release_plan_sha256=plan["release_plan_sha256"],
        ),
        video_id=VIDEO_ID,
        remote_revision=REMOTE_REVISION,
        evidence={"adopted": True},
    )
    for child_id in (
        "processing-private",
        "metadata-status",
        "thumbnail",
        "visibility-publication",
        "top-level-comment",
    ):
        release = prepare_child(release, child_id=child_id, payload={"fixture": child_id})
        release = transition_child(
            release,
            child_id=child_id,
            provider_effect="verified",
            remote_id=VIDEO_ID,
            evidence={"fixture": True},
        )
    return release


def test_record_manual_pin_evidence_is_provider_free_and_terminal(tmp_path: Path) -> None:
    plan = _plan(tmp_path, manual_pin=True)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    stable = journal_path(tmp_path / "state", plan["upload_key_sha256"])
    journal = adopted_journal(
        _live_evidence(plan),
        remote_video_id=VIDEO_ID,
        remote_channel_id=CHANNEL_ID,
        remote_revision=REMOTE_REVISION,
    )
    journal["release"] = _advance_to_manual_pin(plan)
    journal["release_plan_sha256"] = plan["release_plan_sha256"]
    write_json_atomic(stable, journal)
    evidence = {
        "release_plan_sha256": plan["release_plan_sha256"],
        "child_id": "manual-pin-evidence",
        "provider_effect": "verified",
        "remote_id": VIDEO_ID,
        "reviewed_by": "FedorMilovanov",
        "reviewed_at": "2026-08-10T12:30:00+00:00",
        "manual_observation": "comment pinned in Studio",
    }
    evidence_path = tmp_path / "manual.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    assert (
        record_manual_evidence(
            argparse.Namespace(
                plan=plan_path,
                data_dir=tmp_path / "state",
                child="manual-pin-evidence",
                evidence=evidence_path,
            )
        )
        == 0
    )
    child = child_by_id(read_json(stable)["release"], "manual-pin-evidence")
    assert child["provider_effect"] == "verified"
    assert child["evidence_sha256"] == canonical_sha256(evidence)


def test_record_manual_evidence_rejects_unreviewed_or_wrong_child(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    evidence_path = tmp_path / "manual.json"
    evidence_path.write_text(
        json.dumps(
            {
                "release_plan_sha256": plan["release_plan_sha256"],
                "child_id": "upload",
                "provider_effect": "verified",
                "reviewed_by": "FedorMilovanov",
                "reviewed_at": "2026-08-10T12:30:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(UploadPlanError, match="not allowed"):
        record_manual_evidence(
            argparse.Namespace(
                plan=plan_path,
                data_dir=tmp_path / "state",
                child="upload",
                evidence=evidence_path,
            )
        )


def test_status_prints_exact_release_state(capsys, tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    stable = journal_path(tmp_path / "state", plan["upload_key_sha256"])
    journal = adopted_journal(
        _live_evidence(plan),
        remote_video_id=VIDEO_ID,
        remote_channel_id=CHANNEL_ID,
        remote_revision=REMOTE_REVISION,
    )
    journal["release"] = mark_existing_target_adopted(
        build_release_state(
            upload_key_sha256=plan["upload_key_sha256"],
            release_plan_sha256=plan["release_plan_sha256"],
        ),
        video_id=VIDEO_ID,
        remote_revision=REMOTE_REVISION,
        evidence={"adopted": True},
    )
    journal["release_plan_sha256"] = plan["release_plan_sha256"]
    write_json_atomic(stable, journal)
    assert status(argparse.Namespace(plan=plan_path, data_dir=tmp_path / "state")) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["release_plan_sha256"] == plan["release_plan_sha256"]


def test_stable_upload_key_for_live_evidence_matches_release_plan(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    assert plan["upload_key_sha256"] == stable_upload_key(
        project_key=plan["project_key"],
        target_channel_id=plan["target_channel_id"],
        media_sha256=plan["media"]["sha256"],
    )
