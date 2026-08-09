from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import video_channel_manager.youtube_release_cli as release_cli
from video_channel_manager.youtube_release_state import (
    YouTubeReleaseStateError,
    build_release_state,
    mark_existing_target_adopted,
    next_release_child,
    prepare_child,
    transition_child,
    validate_release_state,
)
from video_channel_manager.youtube_upload_plan import (
    UploadPlanError,
    build_intent,
    journal_path,
    require_new_plan_allowed,
    validate_live_state_evidence,
)

CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"


def _evidence(
    *,
    media_sha256: str,
    title: str = "Existing target",
    channel_id: str = CHANNEL_ID,
    account_alias: str = "legendary-poet",
) -> dict:
    return {
        "schema_name": "video-manager.youtube-live-state-evidence",
        "schema_version": 1,
        "project_key": "legendary-poet",
        "account_alias": account_alias,
        "channel_id": channel_id,
        "video": {
            "video_id": "VID-EXISTING",
            "title": title,
            "uploaded_media_sha256": media_sha256,
            "privacy_status": "public",
        },
        "execution_authority": False,
        "provider_writes_authorized": False,
    }


class _FakeReadClient:
    def __init__(
        self,
        *,
        title: str = "Existing target",
        revision: str = "sha256:" + "a" * 64,
    ) -> None:
        self.title = title
        self.revision = revision
        self.closed = False
        self.calls = 0

    def get_video(self, video_id: str):
        self.calls += 1
        return SimpleNamespace(
            title=self.title,
            privacy_status="public",
            revision=self.revision,
            ref=SimpleNamespace(channel_id=CHANNEL_ID, remote_id=video_id),
        )

    def close(self) -> None:
        self.closed = True


def test_identity_mismatch_fails_before_oauth_material_is_loaded(monkeypatch, tmp_path: Path) -> None:
    evidence = _evidence(media_sha256="sha256:" + "b" * 64, channel_id="UC-wrong")
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    called = False

    def forbidden_builder(account_alias: str):
        nonlocal called
        called = True
        raise AssertionError(account_alias)

    monkeypatch.setattr(release_cli, "_build_readonly_client", forbidden_builder)
    with pytest.raises(ValueError, match="channel differs from canonical project identity"):
        release_cli.adopt_existing(
            argparse.Namespace(
                evidence=evidence_path,
                data_dir=tmp_path / "data",
                output=tmp_path / "result.json",
            )
        )
    assert called is False


def test_adoption_persists_verified_stable_journal_and_blocks_replan(monkeypatch, tmp_path: Path) -> None:
    media = tmp_path / "album.mp4"
    media.write_bytes(b"same-media-stable-identity")
    media_sha = "sha256:" + hashlib.sha256(media.read_bytes()).hexdigest()
    evidence = _evidence(media_sha256=media_sha)
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    fake = _FakeReadClient()
    monkeypatch.setattr(release_cli, "_build_readonly_client", lambda alias: fake)

    data_dir = tmp_path / "data"
    output = tmp_path / "adoption.json"
    assert release_cli.adopt_existing(argparse.Namespace(evidence=evidence_path, data_dir=data_dir, output=output)) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    stable = journal_path(data_dir, result["upload_key_sha256"])
    journal = json.loads(stable.read_text(encoding="utf-8"))

    assert fake.calls == 1
    assert fake.closed is True
    assert result["provider_writes"] == 0
    assert journal["state"] == "verified"
    assert journal["provider_effect"] == "verified"
    assert journal["adopted_existing_target"] is True
    assert journal["remote_video_id"] == "VID-EXISTING"
    assert journal["release"]["children"][0]["provider_effect"] == "verified"
    assert journal["release"]["children"][1]["provider_effect"] == "verified"

    spec = {
        "schema_name": "video-manager.youtube-video-upload-spec",
        "schema_version": "2.0",
        "project_key": "legendary-poet",
        "account_alias": "legendary-poet",
        "target_channel_id": CHANNEL_ID,
        "expected_media_sha256": media_sha,
        "title": "Would duplicate existing target",
        "description": "blocked",
        "tags": ["Есенин"],
        "privacy_status": "private",
    }
    intent = build_intent(spec, media, created_at="2026-08-09T00:00:00+00:00")
    with pytest.raises(UploadPlanError, match="blocks a new plan"):
        require_new_plan_allowed(journal, intent=intent)


def test_adoption_is_idempotent_for_same_existing_video(monkeypatch, tmp_path: Path) -> None:
    media_sha = "sha256:" + "c" * 64
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_evidence(media_sha256=media_sha)), encoding="utf-8")
    monkeypatch.setattr(release_cli, "_build_readonly_client", lambda alias: _FakeReadClient())
    data_dir = tmp_path / "data"

    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    release_cli.adopt_existing(argparse.Namespace(evidence=evidence_path, data_dir=data_dir, output=first))
    release_cli.adopt_existing(argparse.Namespace(evidence=evidence_path, data_dir=data_dir, output=second))

    assert json.loads(first.read_text(encoding="utf-8"))["journal_write_performed"] is True
    assert json.loads(second.read_text(encoding="utf-8"))["journal_write_performed"] is False


def test_same_video_revision_drift_is_not_silently_idempotent(monkeypatch, tmp_path: Path) -> None:
    media_sha = "sha256:" + "c" * 64
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_evidence(media_sha256=media_sha)), encoding="utf-8")
    data_dir = tmp_path / "data"

    monkeypatch.setattr(
        release_cli,
        "_build_readonly_client",
        lambda alias: _FakeReadClient(revision="sha256:" + "a" * 64),
    )
    release_cli.adopt_existing(
        argparse.Namespace(evidence=evidence_path, data_dir=data_dir, output=tmp_path / "first.json")
    )

    monkeypatch.setattr(
        release_cli,
        "_build_readonly_client",
        lambda alias: _FakeReadClient(revision="sha256:" + "b" * 64),
    )
    with pytest.raises(UploadPlanError, match="conflicts with existing-target adoption"):
        release_cli.adopt_existing(
            argparse.Namespace(evidence=evidence_path, data_dir=data_dir, output=tmp_path / "second.json")
        )


def test_same_video_evidence_drift_is_not_silently_idempotent(monkeypatch, tmp_path: Path) -> None:
    media_sha = "sha256:" + "c" * 64
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_evidence(media_sha256=media_sha)), encoding="utf-8")
    data_dir = tmp_path / "data"
    monkeypatch.setattr(release_cli, "_build_readonly_client", lambda alias: _FakeReadClient())
    release_cli.adopt_existing(
        argparse.Namespace(evidence=evidence_path, data_dir=data_dir, output=tmp_path / "first.json")
    )

    changed = _evidence(media_sha256=media_sha)
    changed["recorded_at"] = "2026-08-09T23:59:59+03:00"
    evidence_path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(UploadPlanError, match="different immutable evidence"):
        release_cli.adopt_existing(
            argparse.Namespace(evidence=evidence_path, data_dir=data_dir, output=tmp_path / "second.json")
        )


def test_planned_journal_conflicts_with_adoption(monkeypatch, tmp_path: Path) -> None:
    media = tmp_path / "album.mp4"
    media.write_bytes(b"planned-before-adoption")
    media_sha = "sha256:" + hashlib.sha256(media.read_bytes()).hexdigest()
    spec = {
        "schema_name": "video-manager.youtube-video-upload-spec",
        "schema_version": "2.0",
        "project_key": "legendary-poet",
        "account_alias": "legendary-poet",
        "target_channel_id": CHANNEL_ID,
        "expected_media_sha256": media_sha,
        "title": "Plan",
        "description": "desc",
        "tags": ["tag"],
        "privacy_status": "private",
    }
    intent = build_intent(spec, media)
    from video_channel_manager.youtube_stable_state import write_json_atomic
    from video_channel_manager.youtube_upload_plan import planned_journal

    stable = journal_path(tmp_path / "data", intent["upload_key_sha256"])
    write_json_atomic(stable, planned_journal(intent))
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_evidence(media_sha256=media_sha)), encoding="utf-8")
    monkeypatch.setattr(release_cli, "_build_readonly_client", lambda alias: _FakeReadClient())

    with pytest.raises(UploadPlanError, match="conflicts with existing-target adoption"):
        release_cli.adopt_existing(
            argparse.Namespace(evidence=evidence_path, data_dir=tmp_path / "data", output=tmp_path / "out.json")
        )


def test_release_state_blocks_may_exist_and_preserves_verified_parent() -> None:
    state = build_release_state(upload_key_sha256="sha256:" + "d" * 64, playlist_ids=["PL1", "PL2"])
    state = prepare_child(state, child_id="existing-target", payload={"video_id": "VID"})
    state = transition_child(
        state,
        child_id="existing-target",
        provider_effect="confirmed_absent",
        evidence={"exact_video_lookup": "absent"},
    )
    state = prepare_child(state, child_id="upload", payload={"media_sha256": "sha256:" + "e" * 64})
    state = transition_child(
        state,
        child_id="upload",
        provider_effect="verified",
        remote_id="VID",
        evidence={"upload_readback": "verified"},
    )
    parent_snapshot = dict(state["children"][1])
    state = prepare_child(state, child_id="processing-private", payload={"video_id": "VID"})
    state = transition_child(state, child_id="processing-private", provider_effect="may_exist")

    with pytest.raises(YouTubeReleaseStateError, match="reconcile read-only first"):
        next_release_child(state)
    assert state["children"][1] == parent_snapshot


def test_release_state_requires_durable_payload_before_provider_effect() -> None:
    state = build_release_state(upload_key_sha256="sha256:" + "f" * 64)
    with pytest.raises(YouTubeReleaseStateError, match="must persist its immutable payload"):
        transition_child(state, child_id="existing-target", provider_effect="verified", remote_id="VID")
    with pytest.raises(YouTubeReleaseStateError, match="must persist its immutable payload"):
        transition_child(state, child_id="existing-target", provider_effect="confirmed_absent")


def test_release_state_requires_proof_for_terminal_effect() -> None:
    state = build_release_state(upload_key_sha256="sha256:" + "4" * 64)
    state = prepare_child(state, child_id="existing-target", payload={"video_id": "VID"})
    with pytest.raises(YouTubeReleaseStateError, match="must persist immutable proof evidence"):
        transition_child(state, child_id="existing-target", provider_effect="confirmed_absent")


def test_release_state_rejects_tampered_child_kind_and_playlist_shape() -> None:
    state = build_release_state(upload_key_sha256="sha256:" + "3" * 64, playlist_ids=["PL1"])

    wrong_kind = json.loads(json.dumps(state))
    wrong_kind["children"][1]["kind"] = "playlist_membership"
    with pytest.raises(YouTubeReleaseStateError, match="fixed child identity/kind order"):
        validate_release_state(wrong_kind)

    wrong_playlist_target = json.loads(json.dumps(state))
    playlist_child = next(child for child in wrong_playlist_target["children"] if child["child_id"] == "playlist:PL1")
    playlist_child["target_id"] = "PL2"
    with pytest.raises(YouTubeReleaseStateError, match="must bind target_id"):
        validate_release_state(wrong_playlist_target)

    arbitrary_middle = json.loads(json.dumps(state))
    playlist_index = next(
        index for index, child in enumerate(arbitrary_middle["children"]) if child["child_id"] == "playlist:PL1"
    )
    arbitrary_middle["children"][playlist_index] = {
        "child_id": "surprise-operation",
        "kind": "metadata_description",
        "provider_effect": "not_dispatched",
        "payload_sha256": None,
        "remote_id": None,
        "evidence_sha256": None,
        "updated_at": None,
    }
    with pytest.raises(YouTubeReleaseStateError, match="middle children must be exact playlist"):
        validate_release_state(arbitrary_middle)


def test_adopted_release_state_skips_upload_forever() -> None:
    state = build_release_state(upload_key_sha256="sha256:" + "1" * 64)
    state = mark_existing_target_adopted(
        state,
        video_id="VID",
        remote_revision="sha256:" + "2" * 64,
        evidence={"proof": "exact"},
    )
    next_child = next_release_child(state)
    assert next_child is not None
    assert next_child["child_id"] == "processing-private"
    assert state["children"][0]["provider_effect"] == "verified"
    assert state["children"][1]["provider_effect"] == "verified"


def test_actual_black_man_live_state_binds_expected_stable_identity() -> None:
    evidence_path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "operations"
        / "black-man-youtube-live-state-2026-08-09.json"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    identity = validate_live_state_evidence(evidence)

    assert identity == {
        "project_key": "legendary-poet",
        "account_alias": "legendary-poet",
        "target_channel_id": CHANNEL_ID,
        "video_id": "x-puy27S2qs",
        "media_sha256": "sha256:e5450342249e95882136af35976ee3ab08bc85bba626a061be9944b28d8310a0",
        "upload_key_sha256": "sha256:8717dbba1face5b69941587a66a35a5644e3fb7cf7babe260fcfbf2df5f7e73f",
    }
