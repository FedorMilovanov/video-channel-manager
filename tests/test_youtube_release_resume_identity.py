from __future__ import annotations

from video_channel_manager.youtube_release_state import (
    build_release_state,
    child_by_id,
    mark_existing_target_absent,
    prepare_child,
    transition_child,
)

SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64


def _ready_for_upload() -> dict:
    state = build_release_state(
        upload_key_sha256=SHA_A,
        release_plan_sha256=SHA_B,
    )
    state = mark_existing_target_absent(state, evidence={"reviewed": True})
    state = prepare_child(
        state,
        child_id="upload-session",
        payload={"media_sha256": SHA_A},
    )
    return transition_child(
        state,
        child_id="upload-session",
        provider_effect="verified",
        evidence={"session": True},
        runtime_updates={
            "session_url_sha256": SHA_B,
            "session_url": "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=x",
        },
    )


def test_server_offset_does_not_change_immutable_upload_identity() -> None:
    state = _ready_for_upload()
    first_payload = {
        "session_url_sha256": SHA_B,
        "media_sha256": SHA_A,
        "media_size_bytes": 100,
        "offset": 0,
    }
    state = prepare_child(
        state,
        child_id="upload",
        payload=first_payload,
        runtime_updates={"next_offset": 0},
    )
    first_digest = child_by_id(state, "upload")["payload_sha256"]
    state = transition_child(
        state,
        child_id="upload",
        provider_effect="confirmed_absent",
        evidence={"http_status": 308, "range": "bytes=0-49"},
        runtime_updates={"next_offset": 50, "resume_requires_status_query": False},
    )

    resumed_payload = {
        "session_url_sha256": SHA_B,
        "media_sha256": SHA_A,
        "media_size_bytes": 100,
        "offset": 50,
    }
    state = prepare_child(
        state,
        child_id="upload",
        payload=resumed_payload,
        runtime_updates={"next_offset": 50},
    )
    assert child_by_id(state, "upload")["payload_sha256"] == first_digest


def test_resumable_identity_still_rejects_media_or_session_change() -> None:
    state = _ready_for_upload()
    state = prepare_child(
        state,
        child_id="upload",
        payload={
            "session_url_sha256": SHA_B,
            "media_sha256": SHA_A,
            "media_size_bytes": 100,
            "offset": 0,
        },
    )
    state = transition_child(
        state,
        child_id="upload",
        provider_effect="confirmed_absent",
        evidence={"http_status": 308},
        runtime_updates={"next_offset": 50},
    )

    try:
        prepare_child(
            state,
            child_id="upload",
            payload={
                "session_url_sha256": SHA_A,
                "media_sha256": SHA_A,
                "media_size_bytes": 100,
                "offset": 50,
            },
        )
    except Exception as exc:
        assert "different immutable payload digest" in str(exc)
    else:
        raise AssertionError("changing resumable session identity must fail closed")
