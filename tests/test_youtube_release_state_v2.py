from __future__ import annotations

import copy

import pytest

from video_channel_manager.youtube_release_state import (
    YouTubeReleaseStateError,
    build_release_state,
    child_by_id,
    mark_existing_target_absent,
    mark_existing_target_adopted,
    next_release_child,
    prepare_child,
    transition_child,
    validate_release_state,
)

SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64


def _state(*, playlists: list[str] | None = None) -> dict:
    return build_release_state(
        upload_key_sha256=SHA_A,
        release_plan_sha256=SHA_B,
        playlist_ids=playlists,
        now="2026-08-10T12:00:00+00:00",
    )


def test_release_state_has_exact_order_and_playlist_binding() -> None:
    state = _state(playlists=["PL-one", "PL-two"])
    assert [child["child_id"] for child in state["children"]] == [
        "existing-target",
        "upload-session",
        "upload",
        "processing-private",
        "metadata-status",
        "thumbnail",
        "playlist:PL-one",
        "playlist:PL-two",
        "visibility-publication",
        "top-level-comment",
        "manual-pin-evidence",
    ]
    assert child_by_id(state, "playlist:PL-two")["target_id"] == "PL-two"


def test_duplicate_playlist_is_rejected() -> None:
    with pytest.raises(YouTubeReleaseStateError, match="unique"):
        _state(playlists=["PL-x", "PL-x"])


def test_effect_cannot_exist_without_persisted_payload() -> None:
    state = _state()
    with pytest.raises(YouTubeReleaseStateError, match="immutable payload"):
        transition_child(
            state,
            child_id="existing-target",
            provider_effect="may_exist",
        )


def test_terminal_effect_requires_proof_evidence() -> None:
    state = prepare_child(_state(), child_id="existing-target", payload={"probe": 1})
    with pytest.raises(YouTubeReleaseStateError, match="proof evidence"):
        transition_child(
            state,
            child_id="existing-target",
            provider_effect="confirmed_absent",
        )


def test_existing_target_absence_unlocks_upload_session_only() -> None:
    state = mark_existing_target_absent(_state(), evidence={"reviewed": True})
    assert child_by_id(state, "existing-target")["provider_effect"] == "confirmed_absent"
    assert next_release_child(state)["child_id"] == "upload-session"
    with pytest.raises(YouTubeReleaseStateError, match="blocked by upload-session"):
        prepare_child(state, child_id="upload", payload={"bytes": SHA_A})


def test_may_exist_blocks_entire_release_until_reconciled() -> None:
    state = mark_existing_target_absent(_state(), evidence={"reviewed": True})
    state = prepare_child(state, child_id="upload-session", payload={"start": True})
    state = transition_child(
        state,
        child_id="upload-session",
        provider_effect="may_exist",
    )
    with pytest.raises(YouTubeReleaseStateError, match="unresolved provider effect"):
        next_release_child(state)
    with pytest.raises(YouTubeReleaseStateError, match="blocked by upload-session"):
        prepare_child(state, child_id="upload", payload={"offset": 0})


def test_confirmed_absent_upload_session_can_be_retried_with_same_payload() -> None:
    state = mark_existing_target_absent(_state(), evidence={"reviewed": True})
    payload = {"start": True}
    state = prepare_child(state, child_id="upload-session", payload=payload)
    state = transition_child(
        state,
        child_id="upload-session",
        provider_effect="confirmed_absent",
        evidence={"connect_failed_before_dispatch": True},
    )
    state = prepare_child(state, child_id="upload-session", payload=payload)
    state = transition_child(
        state,
        child_id="upload-session",
        provider_effect="verified",
        evidence={"session": "created"},
        runtime_updates={"session_url_sha256": SHA_A},
    )
    assert child_by_id(state, "upload-session")["provider_effect"] == "verified"
    assert next_release_child(state)["child_id"] == "upload"


def test_retry_cannot_change_immutable_payload_digest() -> None:
    state = mark_existing_target_absent(_state(), evidence={"reviewed": True})
    state = prepare_child(state, child_id="upload-session", payload={"start": 1})
    state = transition_child(
        state,
        child_id="upload-session",
        provider_effect="confirmed_absent",
        evidence={"not_dispatched": True},
    )
    with pytest.raises(YouTubeReleaseStateError, match="different immutable payload"):
        prepare_child(state, child_id="upload-session", payload={"start": 2})


def test_verified_child_remote_id_and_runtime_are_immutable() -> None:
    state = mark_existing_target_absent(_state(), evidence={"reviewed": True})
    state = prepare_child(state, child_id="upload-session", payload={"start": True})
    state = transition_child(
        state,
        child_id="upload-session",
        provider_effect="verified",
        remote_id="session-proof",
        evidence={"ok": True},
        runtime_updates={"session_url_sha256": SHA_A},
    )
    with pytest.raises(YouTubeReleaseStateError, match="remote_id is immutable"):
        transition_child(
            state,
            child_id="upload-session",
            provider_effect="verified",
            remote_id="different",
            evidence={"ok": True},
        )
    with pytest.raises(YouTubeReleaseStateError, match="runtime field"):
        transition_child(
            state,
            child_id="upload-session",
            provider_effect="verified",
            remote_id="session-proof",
            evidence={"ok": True},
            runtime_updates={"session_url_sha256": SHA_B},
        )


def test_adopted_target_marks_session_and_upload_verified() -> None:
    state = mark_existing_target_adopted(
        _state(),
        video_id="video123",
        remote_revision=SHA_A,
        evidence={"read_only_adoption": True},
    )
    assert child_by_id(state, "existing-target")["provider_effect"] == "verified"
    assert child_by_id(state, "upload-session")["provider_effect"] == "verified"
    upload = child_by_id(state, "upload")
    assert upload["provider_effect"] == "verified"
    assert upload["remote_id"] == "video123"
    assert next_release_child(state)["child_id"] == "processing-private"


def test_adoption_does_not_mark_later_children_verified() -> None:
    state = mark_existing_target_adopted(
        _state(playlists=["PL-x"]),
        video_id="video123",
        remote_revision=SHA_A,
        evidence={"read_only_adoption": True},
    )
    for child_id in (
        "processing-private",
        "metadata-status",
        "thumbnail",
        "playlist:PL-x",
        "visibility-publication",
        "top-level-comment",
        "manual-pin-evidence",
    ):
        assert child_by_id(state, child_id)["provider_effect"] == "not_dispatched"


def test_tampered_child_order_is_rejected() -> None:
    state = _state()
    state["children"][0], state["children"][1] = state["children"][1], state["children"][0]
    with pytest.raises(YouTubeReleaseStateError, match="fixed child"):
        validate_release_state(state)


def test_tampered_playlist_target_is_rejected() -> None:
    state = _state(playlists=["PL-x"])
    child_by_index = next(child for child in state["children"] if child["child_id"] == "playlist:PL-x")
    child_by_index["target_id"] = "PL-other"
    with pytest.raises(YouTubeReleaseStateError, match="bind target_id"):
        validate_release_state(state)


def test_child_by_id_returns_copy_not_mutable_state_reference() -> None:
    state = _state()
    child = child_by_id(state, "existing-target")
    child["provider_effect"] = "verified"
    assert child_by_id(state, "existing-target")["provider_effect"] == "not_dispatched"


def test_unknown_child_fails_closed() -> None:
    with pytest.raises(YouTubeReleaseStateError, match="Unknown release child"):
        child_by_id(_state(), "does-not-exist")


def test_invalid_state_schema_is_rejected() -> None:
    state = copy.deepcopy(_state())
    state["schema_version"] = 999
    with pytest.raises(YouTubeReleaseStateError, match="Unsupported"):
        validate_release_state(state)
