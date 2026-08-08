from __future__ import annotations

import hashlib
import io
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import video_channel_manager.telegram_lordchrist_outcome_artifact as artifact_module
from video_channel_manager.telegram_lordchrist_outcome import LordchristProviderOutcome
from video_channel_manager.telegram_lordchrist_outcome_artifact import (
    LordchristProviderOutcomeArtifactProof,
    download_verified_lordchrist_provider_outcome,
    prove_lordchrist_provider_outcome_artifact,
    verify_lordchrist_provider_outcome_archive,
)
from video_channel_manager.telegram_models import LedgerEntry, TargetProof
from video_channel_manager.telegram_publisher import load_queue
from video_channel_manager.telegram_state import initialize_ledger, prepare_next

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "content/telegram/lordchrist/verified-30-posts.json"


def outcome_bytes() -> bytes:
    outcome = LordchristProviderOutcome(
        schema_name="video-channel-manager.telegram-lordchrist-provider-outcome",
        schema_version=1,
        queue_digest="sha256:" + "1" * 64,
        publication_id="lordchrist-artifact-proof",
        dispatch_intent_id="a" * 32,
        workflow_run_id="12345",
        workflow_run_attempt="1",
        github_sha="b" * 40,
        github_workflow_sha="c" * 40,
        source_payload_sha256="sha256:" + "2" * 64,
        provider_payload_sha256="sha256:" + "3" * 64,
        presentation_policy_id="lordchrist-editorial-v2",
        presentation_policy_sha256="sha256:" + "4" * 64,
        entry=LedgerEntry(
            publication_id="lordchrist-artifact-proof",
            payload_sha256="sha256:" + "2" * 64,
            state="published",
            provider_effect="verified",
            intent_id="a" * 32,
            dispatch_mode="scheduled",
            workflow_run_id="12345",
            workflow_run_attempt="1",
            github_sha="b" * 40,
            github_workflow_sha="c" * 40,
            attempted_at_utc=datetime(2026, 8, 9, 6, 17, tzinfo=UTC),
            published_at_utc=datetime(2026, 8, 9, 6, 17, 3, tzinfo=UTC),
            message_id=1555,
            message_url="https://t.me/lordchrist/1555",
            actual_chat_id=-1001295216957,
            actual_chat_username="lordchrist",
            bot_id=8716602202,
            bot_username="preaching_mp3_bot",
        ),
    )
    return (outcome.model_dump_json(indent=2) + "\n").encode("utf-8")


def archive_bytes(
    *,
    filename: str = "lordchrist-outcome.json",
    extra_file: bool = False,
    payload: bytes | None = None,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(filename, payload if payload is not None else outcome_bytes())
        if extra_file:
            archive.writestr("unexpected.txt", b"unexpected")
    return buffer.getvalue()


def proof_for(archive: bytes) -> LordchristProviderOutcomeArtifactProof:
    return LordchristProviderOutcomeArtifactProof(
        source_run_id="12345",
        source_run_attempt="1",
        workflow_path=".github/workflows/lordchrist-telegram-poster.yml",
        event="schedule",
        run_status="completed",
        run_conclusion="failure",
        head_sha="b" * 40,
        publication_id="lordchrist-artifact-proof",
        artifact_id=999,
        artifact_name="lordchrist-provider-outcome-12345-1",
        artifact_digest="sha256:" + hashlib.sha256(archive).hexdigest(),
        artifact_size_in_bytes=len(archive),
        persist_step_conclusion="success",
        send_step_conclusion="success",
        archive_step_conclusion="success",
        final_state_step_conclusion="failure",
        checked_at_utc=datetime(2026, 8, 9, 7, 0, tzinfo=UTC),
    )


def source_dispatch():
    queue = load_queue(QUEUE)
    ledger = initialize_ledger(queue)
    now = datetime(2026, 8, 9, 6, 17, tzinfo=UTC)
    target = TargetProof(
        schema_name="video-channel-manager.telegram-target-proof",
        schema_version=2,
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
        chat_id=-1001295216957,
        chat_username="lordchrist",
        chat_title="Господь Бог — Сила Моя",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=now,
    )
    prepared = prepare_next(
        queue,
        ledger,
        run_id="12345",
        run_attempt="1",
        github_sha="b" * 40,
        github_workflow_sha="c" * 40,
        mode="scheduled",
        target=target,
        now=now,
    )
    assert prepared.envelope is not None
    return prepared.envelope


def source_proof_payloads():
    dispatch = source_dispatch()
    run_payload = {
        "run_attempt": 1,
        "head_branch": "main",
        "status": "completed",
        "conclusion": "failure",
        "path": ".github/workflows/lordchrist-telegram-poster.yml@refs/heads/main",
        "event": "schedule",
        "head_sha": dispatch.github_sha,
    }
    jobs_payload = {
        "jobs": [
            {
                "steps": [
                    {"name": artifact_module.PERSIST_STEP, "conclusion": "success"},
                    {"name": artifact_module.SEND_STEP, "conclusion": "success"},
                    {"name": artifact_module.ARCHIVE_STEP, "conclusion": "success"},
                    {"name": artifact_module.FINAL_STATE_STEP, "conclusion": "failure"},
                ]
            }
        ]
    }
    artifacts_payload = {
        "artifacts": [
            {
                "id": 999,
                "name": "lordchrist-provider-outcome-12345-1",
                "expired": False,
                "size_in_bytes": 321,
                "digest": "sha256:" + "d" * 64,
                "workflow_run": {"id": 12345, "head_sha": dispatch.github_sha},
            }
        ]
    }
    return dispatch, run_payload, jobs_payload, artifacts_payload


class BytesResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> BytesResponse:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self.payload if size < 0 else self.payload[:size]


def redirect_error(request: urllib.request.Request, location: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        request.full_url,
        302,
        "Found",
        {"Location": location},
        io.BytesIO(),
    )


def test_source_run_proof_binds_exact_attempt_event_steps_head_and_artifact() -> None:
    dispatch, run_payload, jobs_payload, artifacts_payload = source_proof_payloads()
    proof = prove_lordchrist_provider_outcome_artifact(
        run_payload=run_payload,
        jobs_payload=jobs_payload,
        artifacts_payload=artifacts_payload,
        dispatch=dispatch,
        source_run_id="12345",
        source_run_attempt="1",
        requested_publication_id=dispatch.publication_id,
        now=datetime(2026, 8, 9, 7, 0, tzinfo=UTC),
    )
    assert proof.source_run_id == "12345"
    assert proof.source_run_attempt == "1"
    assert proof.event == "schedule"
    assert proof.head_sha == dispatch.github_sha
    assert proof.artifact_id == 999


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("attempt", "attempt differs"),
        ("head", "head SHA differs"),
        ("event", "event differs"),
        ("send", "send step did not execute"),
        ("archive", "artifact was not archived"),
        ("final", "final state persistence already succeeded"),
    ],
)
def test_source_run_proof_rejects_mismatched_or_incomplete_provenance(mutation: str, error: str) -> None:
    dispatch, run_payload, jobs_payload, artifacts_payload = source_proof_payloads()
    if mutation == "attempt":
        run_payload["run_attempt"] = 2
    elif mutation == "head":
        run_payload["head_sha"] = "e" * 40
    elif mutation == "event":
        run_payload["event"] = "workflow_dispatch"
    elif mutation == "send":
        jobs_payload["jobs"][0]["steps"][1]["conclusion"] = "failure"
    elif mutation == "archive":
        jobs_payload["jobs"][0]["steps"][2]["conclusion"] = "failure"
    else:
        jobs_payload["jobs"][0]["steps"][3]["conclusion"] = "success"

    with pytest.raises(ValueError, match=error):
        prove_lordchrist_provider_outcome_artifact(
            run_payload=run_payload,
            jobs_payload=jobs_payload,
            artifacts_payload=artifacts_payload,
            dispatch=dispatch,
            source_run_id="12345",
            source_run_attempt="1",
            requested_publication_id=dispatch.publication_id,
        )


def test_verified_archive_returns_exact_valid_lordchrist_outcome_bytes() -> None:
    archive = archive_bytes()
    assert verify_lordchrist_provider_outcome_archive(archive, proof_for(archive)) == outcome_bytes()


def test_archive_digest_and_size_mismatch_fail_closed() -> None:
    trusted = archive_bytes()
    tampered = archive_bytes(payload=outcome_bytes().replace(b"1555", b"1556"))
    proof = proof_for(trusted).model_copy(update={"artifact_size_in_bytes": len(tampered)})
    with pytest.raises(ValueError, match="digest differs"):
        verify_lordchrist_provider_outcome_archive(tampered, proof)

    wrong_size = proof_for(trusted).model_copy(update={"artifact_size_in_bytes": len(trusted) + 1})
    with pytest.raises(ValueError, match="size differs"):
        verify_lordchrist_provider_outcome_archive(trusted, wrong_size)


def test_archive_rejects_extra_nested_traversal_and_invalid_json() -> None:
    extra = archive_bytes(extra_file=True)
    with pytest.raises(ValueError, match="exactly one file"):
        verify_lordchrist_provider_outcome_archive(extra, proof_for(extra))

    nested = archive_bytes(filename="nested/lordchrist-outcome.json")
    with pytest.raises(ValueError, match="unexpected file path"):
        verify_lordchrist_provider_outcome_archive(nested, proof_for(nested))

    traversal = archive_bytes(filename="../lordchrist-outcome.json")
    with pytest.raises(ValueError, match="unexpected file path"):
        verify_lordchrist_provider_outcome_archive(traversal, proof_for(traversal))

    invalid = archive_bytes(payload=b"{}")
    with pytest.raises(ValueError, match="valid outcome JSON"):
        verify_lordchrist_provider_outcome_archive(invalid, proof_for(invalid))


def test_artifact_redirect_sends_token_only_to_github_api(monkeypatch: pytest.MonkeyPatch) -> None:
    archive = archive_bytes()
    proof = proof_for(archive)
    storage_url = "https://artifact-storage.example.test/signed/outcome.zip"
    initial_requests: list[urllib.request.Request] = []
    storage_requests: list[urllib.request.Request] = []

    class RedirectingOpener:
        def open(self, request: urllib.request.Request, timeout: int) -> BytesResponse:
            assert timeout == 30
            initial_requests.append(request)
            assert request.get_header("Authorization") == "Bearer top-secret"
            raise redirect_error(request, storage_url)

    def fake_build_opener(*handlers: object) -> RedirectingOpener:
        assert len(handlers) == 1
        assert handlers[0].__class__.__name__ == "_NoRedirect"
        return RedirectingOpener()

    def fake_urlopen(request: urllib.request.Request, timeout: int) -> BytesResponse:
        assert timeout == 30
        storage_requests.append(request)
        assert request.full_url == storage_url
        assert request.get_header("Authorization") is None
        return BytesResponse(archive)

    monkeypatch.setattr(artifact_module.urllib.request, "build_opener", fake_build_opener)
    monkeypatch.setattr(artifact_module.urllib.request, "urlopen", fake_urlopen)

    recovered = download_verified_lordchrist_provider_outcome(
        api_url="https://api.github.test",
        repository="owner/repository",
        token="top-secret",
        proof=proof,
    )

    assert len(initial_requests) == 1
    assert len(storage_requests) == 1
    assert recovered == outcome_bytes()


def test_artifact_redirect_rejects_non_https_storage_url(monkeypatch: pytest.MonkeyPatch) -> None:
    archive = archive_bytes()
    proof = proof_for(archive)

    class RedirectingOpener:
        def open(self, request: urllib.request.Request, timeout: int) -> BytesResponse:
            assert request.get_header("Authorization") == "Bearer top-secret"
            raise redirect_error(request, "http://artifact-storage.example.test/outcome.zip")

    monkeypatch.setattr(artifact_module.urllib.request, "build_opener", lambda *handlers: RedirectingOpener())

    with pytest.raises(ValueError, match="safe HTTPS URL"):
        download_verified_lordchrist_provider_outcome(
            api_url="https://api.github.test",
            repository="owner/repository",
            token="top-secret",
            proof=proof,
        )
