from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

import video_channel_manager.telegram_github_outcome_artifact as outcome_artifact
from video_channel_manager.telegram_github_outcome_artifact import (
    PROVIDER_WORKFLOWS,
    artifact_name,
    fetch_provider_outcome_artifact_proof,
    prove_provider_outcome_artifact,
    validate_recovered_outcome,
)
from video_channel_manager.telegram_multichannel_outcome import GenericProviderOutcome
from video_channel_manager.telegram_multichannel_state import GenericDispatchEnvelope
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof

RUN_ID = "31260000001"
ATTEMPT = "1"
PUBLICATION_ID = "svodka-provider-outcome-recovery-test"
HEAD_SHA = "1" * 40
WORKFLOW_SHA = "2" * 40
PAYLOAD_SHA = "sha256:" + "3" * 64
PROFILE_SHA = "sha256:" + "4" * 64
RELEASE_SHA = "sha256:" + "5" * 64
ARTIFACT_SHA = "sha256:" + "6" * 64
NOW = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)


def _dispatch(*, mode: str = "manual") -> GenericDispatchEnvelope:
    target = GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key="svodka",
        channel_username="@deep_info_life",
        profile_sha256=PROFILE_SHA,
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
        chat_id=-1003527567039,
        chat_username="deep_info_life",
        chat_title="СВОДКА",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=NOW,
    )
    return GenericDispatchEnvelope(
        schema_name="video-channel-manager.telegram-generic-dispatch",
        schema_version=1,
        release_digest=RELEASE_SHA,
        release_id="svodka-pilot-2026-08",
        project_key="svodka",
        channel_username="@deep_info_life",
        profile_sha256=PROFILE_SHA,
        publication_id=PUBLICATION_ID,
        sequence=1,
        provider_payload_sha256=PAYLOAD_SHA,
        intent_id="intent-provider-outcome-test",
        dispatch_mode=mode,
        workflow_run_id=RUN_ID,
        workflow_run_attempt=ATTEMPT,
        github_sha=HEAD_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        target=target,
        prepared_at_utc=NOW,
    )


def _run(
    path: str,
    event: str,
    *,
    head_sha: str = HEAD_SHA,
    conclusion: str = "failure",
) -> dict[str, Any]:
    return {
        "run_attempt": 1,
        "head_branch": "main",
        "head_sha": head_sha,
        "status": "completed",
        "conclusion": conclusion,
        "path": f"{path}@main",
        "event": event,
    }


def _jobs(path: str, *, final_conclusion: str = "failure") -> dict[str, Any]:
    contract = PROVIDER_WORKFLOWS[path]
    return {
        "jobs": [
            {
                "steps": [
                    {"name": contract.persist_step, "conclusion": "success"},
                    {"name": contract.send_step, "conclusion": "success"},
                    {"name": contract.archive_step, "conclusion": "success"},
                    {"name": contract.final_state_step, "conclusion": final_conclusion},
                ]
            }
        ]
    }


def _artifacts(*, expired: bool = False, duplicates: int = 1) -> dict[str, Any]:
    artifact = {
        "id": 991,
        "name": artifact_name(RUN_ID, ATTEMPT),
        "expired": expired,
        "digest": ARTIFACT_SHA,
        "size_in_bytes": 512,
        "workflow_run": {"id": int(RUN_ID), "head_sha": HEAD_SHA},
    }
    return {"artifacts": [dict(artifact) for _ in range(duplicates)]}


@pytest.mark.parametrize(
    ("workflow_path", "event", "mode"),
    [
        (".github/workflows/svodka-canary.yml", "workflow_dispatch", "manual"),
        (".github/workflows/svodka-scheduled-publisher.yml", "schedule", "scheduled"),
        (".github/workflows/svodka-scheduled-publisher.yml", "workflow_dispatch", "scheduled"),
    ],
)
def test_provider_outcome_artifact_proof_accepts_exact_svodka_source_run(
    workflow_path: str,
    event: str,
    mode: str,
) -> None:
    proof = prove_provider_outcome_artifact(
        run_payload=_run(workflow_path, event),
        jobs_payload=_jobs(workflow_path),
        artifacts_payload=_artifacts(),
        dispatch=_dispatch(mode=mode),
        source_run_id=RUN_ID,
        source_run_attempt=ATTEMPT,
        requested_publication_id=PUBLICATION_ID,
        now=NOW,
    )

    assert proof.workflow_path == workflow_path
    assert proof.event == event
    assert proof.head_sha == HEAD_SHA
    assert proof.artifact_name == artifact_name(RUN_ID, ATTEMPT)
    assert proof.artifact_digest == ARTIFACT_SHA
    assert proof.send_step_conclusion == "success"
    assert proof.archive_step_conclusion == "success"
    assert proof.final_state_step_conclusion == "failure"


def test_fetch_proof_uses_exact_attempt_run_metadata_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    path = ".github/workflows/svodka-canary.yml"
    seen_urls: list[str] = []

    def fake_github_json(url: str, *, token: str) -> dict[str, Any]:
        assert token == "test-token"
        seen_urls.append(url)
        if url.endswith(f"/actions/runs/{RUN_ID}/attempts/{ATTEMPT}"):
            return _run(path, "workflow_dispatch")
        if url.endswith(f"/actions/runs/{RUN_ID}/attempts/{ATTEMPT}/jobs?per_page=100"):
            return _jobs(path)
        if f"/actions/runs/{RUN_ID}/artifacts?" in url:
            return _artifacts()
        raise AssertionError(f"unexpected GitHub URL: {url}")

    monkeypatch.setattr(outcome_artifact, "_safe_github_json", fake_github_json)
    proof = fetch_provider_outcome_artifact_proof(
        api_url="https://api.github.test",
        repository="owner/repository",
        token="test-token",
        dispatch=_dispatch(),
        source_run_id=RUN_ID,
        source_run_attempt=ATTEMPT,
        requested_publication_id=PUBLICATION_ID,
    )

    assert proof.source_run_attempt == ATTEMPT
    assert seen_urls[0].endswith(f"/actions/runs/{RUN_ID}/attempts/{ATTEMPT}")
    assert not any(url.endswith(f"/actions/runs/{RUN_ID}") for url in seen_urls)


def test_provider_outcome_artifact_proof_rejects_already_successful_state_persistence() -> None:
    path = ".github/workflows/svodka-canary.yml"
    with pytest.raises(ValueError, match="already succeeded"):
        prove_provider_outcome_artifact(
            run_payload=_run(path, "workflow_dispatch"),
            jobs_payload=_jobs(path, final_conclusion="success"),
            artifacts_payload=_artifacts(),
            dispatch=_dispatch(),
            source_run_id=RUN_ID,
            source_run_attempt=ATTEMPT,
            requested_publication_id=PUBLICATION_ID,
            now=NOW,
        )


def test_provider_outcome_artifact_proof_rejects_successful_source_run() -> None:
    path = ".github/workflows/svodka-canary.yml"
    with pytest.raises(ValueError, match="run already succeeded"):
        prove_provider_outcome_artifact(
            run_payload=_run(path, "workflow_dispatch", conclusion="success"),
            jobs_payload=_jobs(path),
            artifacts_payload=_artifacts(),
            dispatch=_dispatch(),
            source_run_id=RUN_ID,
            source_run_attempt=ATTEMPT,
            requested_publication_id=PUBLICATION_ID,
            now=NOW,
        )


@pytest.mark.parametrize(
    ("run_payload", "artifacts_payload", "message"),
    [
        (
            _run(".github/workflows/svodka-canary.yml", "schedule"),
            _artifacts(),
            "event does not match",
        ),
        (
            _run(".github/workflows/svodka-scheduled-publisher.yml", "push"),
            _artifacts(),
            "event does not match",
        ),
        (
            _run(".github/workflows/svodka-canary.yml", "workflow_dispatch", head_sha="9" * 40),
            _artifacts(),
            "head SHA differs",
        ),
        (
            _run(".github/workflows/svodka-canary.yml", "workflow_dispatch"),
            _artifacts(expired=True),
            "has expired",
        ),
        (
            _run(".github/workflows/svodka-canary.yml", "workflow_dispatch"),
            _artifacts(duplicates=2),
            "exactly one archived",
        ),
    ],
)
def test_provider_outcome_artifact_proof_rejects_inexact_provenance(
    run_payload: dict[str, Any],
    artifacts_payload: dict[str, Any],
    message: str,
) -> None:
    path = str(run_payload["path"]).split("@", 1)[0]
    with pytest.raises(ValueError, match=message):
        prove_provider_outcome_artifact(
            run_payload=run_payload,
            jobs_payload=_jobs(path),
            artifacts_payload=artifacts_payload,
            dispatch=_dispatch(mode="scheduled" if path.endswith("svodka-scheduled-publisher.yml") else "manual"),
            source_run_id=RUN_ID,
            source_run_attempt=ATTEMPT,
            requested_publication_id=PUBLICATION_ID,
            now=NOW,
        )


def test_recovered_outcome_must_match_persisted_dispatch_exactly() -> None:
    dispatch = _dispatch()
    outcome = GenericProviderOutcome(
        schema_name="video-channel-manager.telegram-generic-provider-outcome",
        schema_version=1,
        publication_id=PUBLICATION_ID,
        provider_payload_sha256=PAYLOAD_SHA,
        provider_effect="may_exist",
        retryable=False,
        error="provider response was ambiguous",
        receipt=None,
    )

    validate_recovered_outcome(dispatch, outcome, requested_publication_id=PUBLICATION_ID)

    wrong_payload = outcome.model_copy(update={"provider_payload_sha256": "sha256:" + "7" * 64})
    with pytest.raises(ValueError, match="payload digest differs"):
        validate_recovered_outcome(dispatch, wrong_payload, requested_publication_id=PUBLICATION_ID)

    with pytest.raises(ValueError, match="differs from recovery request"):
        validate_recovered_outcome(dispatch, outcome, requested_publication_id="svodka-other-publication")
