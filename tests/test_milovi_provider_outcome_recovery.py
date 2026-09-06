from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from video_channel_manager.telegram_milovi_outcome_artifact import (
    ARCHIVE_STEP,
    FINAL_STATE_STEP,
    PERSIST_STEP,
    SEND_STEP,
    WORKFLOW_PATH,
    artifact_name,
    prove_provider_outcome_artifact,
)
from video_channel_manager.telegram_multichannel_state import GenericDispatchEnvelope
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof

RUN_ID = "33990000001"
ATTEMPT = "1"
PUBLICATION_ID = "milovi-feed-20260906-001"
HEAD_SHA = "1" * 40
WORKFLOW_SHA = "2" * 40
PAYLOAD_SHA = "sha256:" + "3" * 64
PROFILE_SHA = "sha256:" + "4" * 64
RELEASE_SHA = "sha256:" + "5" * 64
ARTIFACT_SHA = "sha256:" + "6" * 64
NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)


def _dispatch() -> GenericDispatchEnvelope:
    target = GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key="milovi-cake",
        channel_username="@MiloviCake",
        profile_sha256=PROFILE_SHA,
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
        chat_id=-1002215328390,
        chat_username="MiloviCake",
        chat_title="Milovi Cake",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=NOW,
    )
    return GenericDispatchEnvelope(
        schema_name="video-channel-manager.telegram-generic-dispatch",
        schema_version=1,
        release_digest=RELEASE_SHA,
        release_id=PUBLICATION_ID,
        project_key="milovi-cake",
        channel_username="@MiloviCake",
        profile_sha256=PROFILE_SHA,
        publication_id=PUBLICATION_ID,
        sequence=1,
        provider_payload_sha256=PAYLOAD_SHA,
        intent_id="intent-milovi-provider-outcome-test",
        dispatch_mode="manual",
        workflow_run_id=RUN_ID,
        workflow_run_attempt=ATTEMPT,
        github_sha=HEAD_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        target=target,
        prepared_at_utc=NOW,
    )


def _run(*, path: str = WORKFLOW_PATH, event: str = "workflow_dispatch", conclusion: str = "failure") -> dict[str, Any]:
    return {
        "run_attempt": 1,
        "head_branch": "main",
        "head_sha": HEAD_SHA,
        "status": "completed",
        "conclusion": conclusion,
        "path": f"{path}@main",
        "event": event,
    }


def _jobs(*, final_conclusion: str = "failure") -> dict[str, Any]:
    return {
        "jobs": [
            {
                "steps": [
                    {"name": PERSIST_STEP, "conclusion": "success"},
                    {"name": SEND_STEP, "conclusion": "success"},
                    {"name": ARCHIVE_STEP, "conclusion": "success"},
                    {"name": FINAL_STATE_STEP, "conclusion": final_conclusion},
                ]
            }
        ]
    }


def _artifacts() -> dict[str, Any]:
    return {
        "artifacts": [
            {
                "id": 991,
                "name": artifact_name(RUN_ID, ATTEMPT),
                "expired": False,
                "digest": ARTIFACT_SHA,
                "size_in_bytes": 512,
                "workflow_run": {"id": int(RUN_ID), "head_sha": HEAD_SHA},
            }
        ]
    }


def test_milovi_provider_outcome_proof_accepts_only_exact_archived_source() -> None:
    proof = prove_provider_outcome_artifact(
        run_payload=_run(),
        jobs_payload=_jobs(),
        artifacts_payload=_artifacts(),
        dispatch=_dispatch(),
        source_run_id=RUN_ID,
        source_run_attempt=ATTEMPT,
        requested_publication_id=PUBLICATION_ID,
        now=NOW,
    )

    assert proof.workflow_path == WORKFLOW_PATH
    assert proof.event == "workflow_dispatch"
    assert proof.head_sha == HEAD_SHA
    assert proof.artifact_name == f"milovi-provider-outcome-{RUN_ID}-{ATTEMPT}"
    assert proof.archive_step_conclusion == "success"
    assert proof.final_state_step_conclusion == "failure"


@pytest.mark.parametrize(
    ("run_payload", "jobs_payload", "message"),
    [
        (_run(event="push"), _jobs(), "event does not match"),
        (_run(path=".github/workflows/svodka-canary.yml"), _jobs(), "permanent Milovi provider workflow"),
        (_run(conclusion="success"), _jobs(), "run already succeeded"),
        (_run(), _jobs(final_conclusion="success"), "already succeeded"),
    ],
)
def test_milovi_provider_outcome_proof_rejects_wrong_authority(
    run_payload: dict[str, Any], jobs_payload: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        prove_provider_outcome_artifact(
            run_payload=run_payload,
            jobs_payload=jobs_payload,
            artifacts_payload=_artifacts(),
            dispatch=_dispatch(),
            source_run_id=RUN_ID,
            source_run_attempt=ATTEMPT,
            requested_publication_id=PUBLICATION_ID,
            now=NOW,
        )


def test_milovi_archive_precedes_state_apply_and_recovery_is_provider_free() -> None:
    publisher = Path(".github/workflows/milovi-telegram-feed-publisher.yml").read_text(encoding="utf-8")
    recovery = Path(".github/workflows/milovi-reconcile-provider-outcome.yml").read_text(encoding="utf-8")

    send = publisher.index("- name: Send exactly once through the canonical generic Telegram runtime")
    archive = publisher.index("- name: Archive exact provider outcome before state mutation")
    apply = publisher.index("- name: Apply exact outcome and persist terminal or blocking state")
    assert send < archive < apply
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in publisher
    assert "name: milovi-provider-outcome-${{ github.run_id }}-${{ github.run_attempt }}" in publisher
    assert "if-no-files-found: error" in publisher

    assert "workflow_dispatch:" in recovery
    assert "group: milovi-cake-telegram-publisher" in recovery
    assert "actions: read" in recovery
    assert "contents: write" in recovery
    assert "telegram_multichannel_cli verify-intent" in recovery
    assert "telegram_multichannel_cli apply-outcome" in recovery
    assert "telegram_milovi_outcome_artifact prove" in recovery
    assert "telegram_milovi_outcome_artifact fetch" in recovery
    assert "MILOVI_STATE_BASE_SHA" in recovery
    assert "current_main_sha" in recovery
    for forbidden in (
        "LORDCHRIST_TELEGRAM_BOT_TOKEN",
        "MILOVI_CAKE_TELEGRAM_BOT_TOKEN",
        "telegram_channel_cli preflight",
        "telegram_multichannel_cli send-once",
        "sendMessage",
        "sendPhoto",
        "sendVideo",
    ):
        assert forbidden not in recovery
