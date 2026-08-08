from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from video_channel_manager.telegram_lordchrist_outcome import LordchristProviderOutcome
from video_channel_manager.telegram_models import DispatchEnvelope
from video_channel_manager.telegram_state import load_dispatch, save_model

ARTIFACT_NAME_PREFIX = "lordchrist-provider-outcome-"
OUTCOME_FILENAME = "lordchrist-outcome.json"
SOURCE_WORKFLOW = ".github/workflows/lordchrist-telegram-poster.yml"
PERSIST_STEP = "Persist intent and rendered payload before sendMessage"
SEND_STEP = "Send exactly one prepared message"
ARCHIVE_STEP = "Archive exact Lordchrist provider outcome before state mutation"
FINAL_STATE_STEP = "Persist exact Telegram result"
MAX_OUTCOME_ARCHIVE_BYTES = 1_000_000
MAX_OUTCOME_JSON_BYTES = 256_000
USER_AGENT = "video-channel-manager-lordchrist-outcome-reconciler"
REDIRECT_CODES = {301, 302, 303, 307, 308}


class LordchristProviderOutcomeArtifactProof(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: str = "video-channel-manager.telegram-lordchrist-provider-outcome-artifact-proof"
    schema_version: int = 1
    source_run_id: str
    source_run_attempt: str
    workflow_path: str
    event: str
    run_status: str
    run_conclusion: str | None
    head_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    publication_id: str
    artifact_id: int = Field(gt=0)
    artifact_name: str
    artifact_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    artifact_size_in_bytes: int = Field(gt=0)
    persist_step_conclusion: str
    send_step_conclusion: str
    archive_step_conclusion: str
    final_state_step_conclusion: str | None
    checked_at_utc: datetime


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    }


def _safe_github_json(url: str, *, token: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=_github_headers(token))
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except Exception as exc:
        raise RuntimeError(f"GitHub Lordchrist outcome proof unavailable: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub Lordchrist outcome proof returned a non-object response")
    return cast(dict[str, Any], payload)


def _bounded_read(response: Any, *, max_bytes: int) -> bytes:
    payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError("downloaded Lordchrist outcome artifact exceeds the allowed size")
    return cast(bytes, payload)


def _safe_github_bytes(url: str, *, token: str, max_bytes: int) -> bytes:
    request = urllib.request.Request(url, headers=_github_headers(token))
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=30) as response:
            return _bounded_read(response, max_bytes=max_bytes)
    except urllib.error.HTTPError as exc:
        if exc.code not in REDIRECT_CODES:
            raise RuntimeError(f"GitHub Lordchrist outcome artifact unavailable: HTTP {exc.code}") from exc
        location = exc.headers.get("Location")
        exc.close()
        if not location:
            raise RuntimeError("GitHub Lordchrist outcome artifact redirect has no location") from exc
    except Exception as exc:
        raise RuntimeError(f"GitHub Lordchrist outcome artifact unavailable: {type(exc).__name__}") from exc

    redirect_url = urllib.parse.urljoin(url, location)
    parsed = urllib.parse.urlsplit(redirect_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ValueError("GitHub Lordchrist outcome artifact redirect is not a safe HTTPS URL")

    storage_request = urllib.request.Request(redirect_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(storage_request, timeout=30) as response:
            return _bounded_read(response, max_bytes=max_bytes)
    except Exception as exc:
        raise RuntimeError(f"GitHub Lordchrist outcome artifact unavailable: {type(exc).__name__}") from exc


def _positive_integer(value: str, *, field_name: str) -> int:
    if re.fullmatch(r"[1-9][0-9]*", value) is None:
        raise ValueError(f"{field_name} must be a positive integer")
    return int(value)


def artifact_name(run_id: str, run_attempt: str) -> str:
    _positive_integer(run_id, field_name="source_run_id")
    _positive_integer(run_attempt, field_name="source_run_attempt")
    return f"{ARTIFACT_NAME_PREFIX}{run_id}-{run_attempt}"


def _single_named_step(jobs_payload: dict[str, Any], name: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    jobs = jobs_payload.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("GitHub Lordchrist jobs proof has no jobs list")
    for job in jobs:
        if not isinstance(job, dict):
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            if isinstance(step, dict) and step.get("name") == name:
                matches.append(cast(dict[str, Any], step))
    if len(matches) != 1:
        raise ValueError(f"cannot prove unique Lordchrist source step: {name}")
    return matches[0]


def prove_lordchrist_provider_outcome_artifact(
    *,
    run_payload: dict[str, Any],
    jobs_payload: dict[str, Any],
    artifacts_payload: dict[str, Any],
    dispatch: DispatchEnvelope,
    source_run_id: str,
    source_run_attempt: str,
    requested_publication_id: str,
    now: datetime | None = None,
) -> LordchristProviderOutcomeArtifactProof:
    attempt = _positive_integer(source_run_attempt, field_name="source_run_attempt")
    _positive_integer(source_run_id, field_name="source_run_id")
    expected_artifact_name = artifact_name(source_run_id, source_run_attempt)

    try:
        run_attempt = int(run_payload.get("run_attempt", 0))
    except (TypeError, ValueError):
        run_attempt = 0
    if run_attempt != attempt:
        raise ValueError("GitHub run attempt differs from Lordchrist recovery request")
    if run_payload.get("head_branch") != "main":
        raise ValueError("source Lordchrist provider run was not executed from main")
    if run_payload.get("status") != "completed":
        raise ValueError("source Lordchrist provider run is not completed")
    if run_payload.get("conclusion") == "success":
        raise ValueError("source Lordchrist provider run already succeeded; recovery is inconsistent")

    workflow_path = str(run_payload.get("path") or "").split("@", 1)[0]
    if workflow_path != SOURCE_WORKFLOW:
        raise ValueError(f"source run is not the Lordchrist provider workflow: {workflow_path}")
    expected_event = "schedule" if dispatch.dispatch_mode == "scheduled" else "workflow_dispatch"
    if run_payload.get("event") != expected_event:
        raise ValueError("source Lordchrist run event differs from durable dispatch mode")

    if dispatch.workflow_run_id != source_run_id:
        raise ValueError("persisted Lordchrist dispatch run id differs from recovery request")
    if dispatch.workflow_run_attempt != source_run_attempt:
        raise ValueError("persisted Lordchrist dispatch attempt differs from recovery request")
    if dispatch.publication_id != requested_publication_id:
        raise ValueError("persisted Lordchrist dispatch publication differs from recovery request")
    head_sha = str(run_payload.get("head_sha") or "")
    if head_sha != dispatch.github_sha:
        raise ValueError("source Lordchrist run head SHA differs from persisted dispatch provenance")

    persist_step = _single_named_step(jobs_payload, PERSIST_STEP)
    send_step = _single_named_step(jobs_payload, SEND_STEP)
    archive_step = _single_named_step(jobs_payload, ARCHIVE_STEP)
    final_step = _single_named_step(jobs_payload, FINAL_STATE_STEP)
    if persist_step.get("conclusion") != "success":
        raise ValueError("source Lordchrist durable intent step was not successful")
    if send_step.get("conclusion") != "success":
        raise ValueError("source Lordchrist provider send step did not execute to completion")
    if archive_step.get("conclusion") != "success":
        raise ValueError("source Lordchrist provider outcome artifact was not archived successfully")
    if final_step.get("conclusion") == "success":
        raise ValueError("source Lordchrist final state persistence already succeeded; recovery is inconsistent")

    artifacts = artifacts_payload.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("GitHub Lordchrist artifact proof has no artifacts list")
    matches = [
        cast(dict[str, Any], candidate)
        for candidate in artifacts
        if isinstance(candidate, dict) and candidate.get("name") == expected_artifact_name
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one archived Lordchrist provider outcome artifact")
    artifact = matches[0]
    if artifact.get("expired") is True:
        raise ValueError("archived Lordchrist provider outcome artifact has expired")
    try:
        artifact_id = int(artifact.get("id", 0))
        artifact_size = int(artifact.get("size_in_bytes", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("archived Lordchrist provider outcome artifact metadata is invalid") from exc
    if artifact_id <= 0 or artifact_size <= 0 or artifact_size > MAX_OUTCOME_ARCHIVE_BYTES:
        raise ValueError("archived Lordchrist provider outcome artifact metadata is invalid")
    artifact_digest = str(artifact.get("digest") or "")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", artifact_digest) is None:
        raise ValueError("archived Lordchrist provider outcome artifact has no exact sha256 digest")
    artifact_run = artifact.get("workflow_run")
    if not isinstance(artifact_run, dict):
        raise ValueError("archived Lordchrist provider outcome artifact has no workflow-run provenance")
    if str(artifact_run.get("id") or "") != source_run_id:
        raise ValueError("Lordchrist artifact workflow run id differs from source provider run")
    if str(artifact_run.get("head_sha") or "") != dispatch.github_sha:
        raise ValueError("Lordchrist artifact head SHA differs from persisted dispatch provenance")

    checked_at = now or datetime.now(tz=UTC)
    if checked_at.tzinfo is None:
        raise ValueError("Lordchrist outcome proof timestamp must be timezone-aware")
    return LordchristProviderOutcomeArtifactProof(
        source_run_id=source_run_id,
        source_run_attempt=source_run_attempt,
        workflow_path=workflow_path,
        event=expected_event,
        run_status="completed",
        run_conclusion=str(run_payload.get("conclusion")) if run_payload.get("conclusion") is not None else None,
        head_sha=head_sha,
        publication_id=requested_publication_id,
        artifact_id=artifact_id,
        artifact_name=expected_artifact_name,
        artifact_digest=artifact_digest,
        artifact_size_in_bytes=artifact_size,
        persist_step_conclusion=str(persist_step.get("conclusion")),
        send_step_conclusion=str(send_step.get("conclusion")),
        archive_step_conclusion=str(archive_step.get("conclusion")),
        final_state_step_conclusion=(
            str(final_step.get("conclusion")) if final_step.get("conclusion") is not None else None
        ),
        checked_at_utc=checked_at,
    )


def fetch_lordchrist_provider_outcome_artifact_proof(
    *,
    api_url: str,
    repository: str,
    token: str,
    dispatch: DispatchEnvelope,
    source_run_id: str,
    source_run_attempt: str,
    requested_publication_id: str,
) -> LordchristProviderOutcomeArtifactProof:
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is None:
        raise ValueError("Lordchrist outcome recovery requires an exact owner/repository name")
    if not token.strip():
        raise ValueError("Lordchrist outcome recovery requires GitHub Actions read credentials")
    attempt = _positive_integer(source_run_attempt, field_name="source_run_attempt")
    _positive_integer(source_run_id, field_name="source_run_id")
    base = api_url.rstrip("/")
    run_payload = _safe_github_json(
        f"{base}/repos/{repository}/actions/runs/{source_run_id}/attempts/{attempt}",
        token=token,
    )
    jobs_payload = _safe_github_json(
        f"{base}/repos/{repository}/actions/runs/{source_run_id}/attempts/{attempt}/jobs?per_page=100",
        token=token,
    )
    query = urllib.parse.urlencode({"name": artifact_name(source_run_id, source_run_attempt), "per_page": "100"})
    artifacts_payload = _safe_github_json(
        f"{base}/repos/{repository}/actions/runs/{source_run_id}/artifacts?{query}",
        token=token,
    )
    return prove_lordchrist_provider_outcome_artifact(
        run_payload=run_payload,
        jobs_payload=jobs_payload,
        artifacts_payload=artifacts_payload,
        dispatch=dispatch,
        source_run_id=source_run_id,
        source_run_attempt=source_run_attempt,
        requested_publication_id=requested_publication_id,
    )


def verify_lordchrist_provider_outcome_archive(
    archive_bytes: bytes,
    proof: LordchristProviderOutcomeArtifactProof,
) -> bytes:
    if len(archive_bytes) != proof.artifact_size_in_bytes:
        raise ValueError("downloaded Lordchrist outcome artifact size differs from proved GitHub metadata")
    actual_digest = "sha256:" + hashlib.sha256(archive_bytes).hexdigest()
    if actual_digest != proof.artifact_digest:
        raise ValueError("downloaded Lordchrist outcome artifact digest differs from proved GitHub metadata")

    try:
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes))
    except zipfile.BadZipFile as exc:
        raise ValueError("downloaded Lordchrist outcome artifact is not a valid ZIP archive") from exc
    with archive:
        files = [member for member in archive.infolist() if not member.is_dir()]
        if len(files) != 1:
            raise ValueError("Lordchrist outcome artifact must contain exactly one file")
        member = files[0]
        path = PurePosixPath(member.filename)
        if path.is_absolute() or ".." in path.parts or path.as_posix() != OUTCOME_FILENAME:
            raise ValueError("Lordchrist outcome artifact contains an unexpected file path")
        if member.file_size <= 0 or member.file_size > MAX_OUTCOME_JSON_BYTES:
            raise ValueError("Lordchrist provider outcome JSON has an invalid size")
        outcome_bytes = archive.read(member)

    if len(outcome_bytes) != member.file_size:
        raise ValueError("Lordchrist provider outcome JSON size differs from ZIP metadata")
    try:
        LordchristProviderOutcome.model_validate_json(outcome_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Lordchrist outcome artifact does not contain a valid outcome JSON") from exc
    return outcome_bytes


def download_verified_lordchrist_provider_outcome(
    *,
    api_url: str,
    repository: str,
    token: str,
    proof: LordchristProviderOutcomeArtifactProof,
) -> bytes:
    archive_url = f"{api_url.rstrip('/')}/repos/{repository}/actions/artifacts/{proof.artifact_id}/zip"
    archive_bytes = _safe_github_bytes(archive_url, token=token, max_bytes=MAX_OUTCOME_ARCHIVE_BYTES)
    return verify_lordchrist_provider_outcome_archive(archive_bytes, proof)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Recover exact archived Lordchrist provider outcomes")
    root.add_argument("--dispatch", type=Path, required=True)
    root.add_argument("--source-run-id", required=True)
    root.add_argument("--source-run-attempt", required=True)
    root.add_argument("--publication-id", required=True)
    root.add_argument("--proof-output", type=Path, required=True)
    root.add_argument("--outcome-output", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    dispatch = load_dispatch(args.dispatch)
    proof = fetch_lordchrist_provider_outcome_artifact_proof(
        api_url=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
        repository=os.environ.get("GITHUB_REPOSITORY", ""),
        token=os.environ.get("GH_TOKEN", ""),
        dispatch=dispatch,
        source_run_id=args.source_run_id,
        source_run_attempt=args.source_run_attempt,
        requested_publication_id=args.publication_id,
    )
    outcome_bytes = download_verified_lordchrist_provider_outcome(
        api_url=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
        repository=os.environ.get("GITHUB_REPOSITORY", ""),
        token=os.environ.get("GH_TOKEN", ""),
        proof=proof,
    )
    args.proof_output.parent.mkdir(parents=True, exist_ok=True)
    save_model(args.proof_output, proof)
    args.outcome_output.parent.mkdir(parents=True, exist_ok=True)
    args.outcome_output.write_bytes(outcome_bytes)
    print(
        json.dumps(
            {
                "recovered": True,
                "publication_id": proof.publication_id,
                "source_run_id": proof.source_run_id,
                "source_run_attempt": proof.source_run_attempt,
                "artifact_id": proof.artifact_id,
                "artifact_digest": proof.artifact_digest,
                "outcome": str(args.outcome_output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
