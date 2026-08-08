from __future__ import annotations

import hashlib
import io
import json
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import video_channel_manager.telegram_github_outcome_artifact as outcome_artifact
from video_channel_manager.telegram_github_outcome_artifact import (
    ProviderOutcomeArtifactProof,
    download_verified_provider_outcome,
    verify_provider_outcome_archive,
)


def outcome_bytes() -> bytes:
    return (
        json.dumps(
            {
                "schema_name": "video-channel-manager.telegram-generic-provider-outcome",
                "schema_version": 1,
                "publication_id": "svodka-integrity-test",
                "provider_payload_sha256": "sha256:" + "1" * 64,
                "provider_effect": "not_dispatched",
                "retryable": True,
                "error": "test",
                "receipt": None,
            },
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def archive_bytes(*, filename: str = "svodka-outcome.json", extra_file: bool = False, payload: bytes | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(filename, payload if payload is not None else outcome_bytes())
        if extra_file:
            archive.writestr("unexpected.txt", b"unexpected")
    return buffer.getvalue()


def proof_for(archive: bytes) -> ProviderOutcomeArtifactProof:
    return ProviderOutcomeArtifactProof(
        source_run_id="12345",
        source_run_attempt="1",
        workflow_path=".github/workflows/svodka-canary.yml",
        event="workflow_dispatch",
        run_status="completed",
        run_conclusion="failure",
        head_sha="a" * 40,
        publication_id="svodka-integrity-test",
        artifact_id=999,
        artifact_name="svodka-provider-outcome-12345-1",
        artifact_digest="sha256:" + hashlib.sha256(archive).hexdigest(),
        artifact_size_in_bytes=len(archive),
        persist_step_conclusion="success",
        send_step_conclusion="success",
        archive_step_conclusion="success",
        final_state_step_conclusion="failure",
        checked_at_utc=datetime(2026, 8, 8, 12, 0, tzinfo=UTC),
    )


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


def test_verified_archive_returns_exact_valid_outcome_bytes() -> None:
    archive = archive_bytes()
    assert verify_provider_outcome_archive(archive, proof_for(archive)) == outcome_bytes()


def test_downloaded_archive_digest_mismatch_fails_closed() -> None:
    trusted = archive_bytes()
    tampered = archive_bytes(payload=outcome_bytes().replace(b"test", b"evil"))
    proof = proof_for(trusted)
    proof = proof.model_copy(update={"artifact_size_in_bytes": len(tampered)})
    with pytest.raises(ValueError, match="digest differs"):
        verify_provider_outcome_archive(tampered, proof)


def test_downloaded_archive_size_mismatch_fails_closed() -> None:
    archive = archive_bytes()
    proof = proof_for(archive).model_copy(update={"artifact_size_in_bytes": len(archive) + 1})
    with pytest.raises(ValueError, match="size differs"):
        verify_provider_outcome_archive(archive, proof)


def test_archive_rejects_extra_or_unsafe_paths() -> None:
    extra = archive_bytes(extra_file=True)
    with pytest.raises(ValueError, match="exactly one file"):
        verify_provider_outcome_archive(extra, proof_for(extra))

    traversal = archive_bytes(filename="../svodka-outcome.json")
    with pytest.raises(ValueError, match="unexpected file path"):
        verify_provider_outcome_archive(traversal, proof_for(traversal))


def test_archive_rejects_invalid_outcome_json() -> None:
    archive = archive_bytes(payload=b"{}")
    with pytest.raises(ValueError, match="valid outcome JSON"):
        verify_provider_outcome_archive(archive, proof_for(archive))


def test_artifact_redirect_sends_token_only_to_github_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = archive_bytes()
    proof = proof_for(archive)
    storage_url = "https://artifact-storage.example.test/signed/outcome.zip"
    initial_requests: list[urllib.request.Request] = []
    storage_requests: list[urllib.request.Request] = []

    class RedirectingOpener:
        def open(self, request: urllib.request.Request, timeout: int) -> BytesResponse:
            assert timeout == 30
            initial_requests.append(request)
            assert request.full_url.endswith(f"/actions/artifacts/{proof.artifact_id}/zip")
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

    monkeypatch.setattr(outcome_artifact.urllib.request, "build_opener", fake_build_opener)
    monkeypatch.setattr(outcome_artifact.urllib.request, "urlopen", fake_urlopen)

    output = tmp_path / "svodka-outcome.json"
    download_verified_provider_outcome(
        api_url="https://api.github.test",
        repository="owner/repository",
        token="top-secret",
        proof=proof,
        output=output,
    )

    assert len(initial_requests) == 1
    assert len(storage_requests) == 1
    assert output.read_bytes() == outcome_bytes()


def test_artifact_redirect_rejects_non_https_storage_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = archive_bytes()
    proof = proof_for(archive)

    class RedirectingOpener:
        def open(self, request: urllib.request.Request, timeout: int) -> BytesResponse:
            assert request.get_header("Authorization") == "Bearer top-secret"
            raise redirect_error(request, "http://artifact-storage.example.test/outcome.zip")

    monkeypatch.setattr(outcome_artifact.urllib.request, "build_opener", lambda *handlers: RedirectingOpener())

    with pytest.raises(ValueError, match="safe HTTPS URL"):
        download_verified_provider_outcome(
            api_url="https://api.github.test",
            repository="owner/repository",
            token="top-secret",
            proof=proof,
            output=tmp_path / "svodka-outcome.json",
        )
