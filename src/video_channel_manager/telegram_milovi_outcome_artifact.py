from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import urllib.parse
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, cast

from video_channel_manager.telegram_github_outcome_artifact import (
    MAX_OUTCOME_ARCHIVE_BYTES,
    MAX_OUTCOME_JSON_BYTES,
    ProviderOutcomeArtifactProof,
    _positive_integer,
    _safe_github_bytes,
    _safe_github_json,
    _single_named_step,
    validate_recovered_outcome,
)
from video_channel_manager.telegram_multichannel_outcome import GenericProviderOutcome
from video_channel_manager.telegram_multichannel_state import GenericDispatchEnvelope

WORKFLOW_PATH = ".github/workflows/milovi-telegram-feed-publisher.yml"
EVENT = "workflow_dispatch"
ARTIFACT_NAME_PREFIX = "milovi-provider-outcome-"
OUTCOME_FILENAME = "milovi-feed-outcome.json"
PERSIST_STEP = "Persist exact intent in release ledger and channel-wide index before mutation"
SEND_STEP = "Send exactly once through the canonical generic Telegram runtime"
ARCHIVE_STEP = "Archive exact provider outcome before state mutation"
FINAL_STATE_STEP = "Apply exact outcome and persist terminal or blocking state"


def artifact_name(run_id: str, run_attempt: str) -> str:
    _positive_integer(run_id, field_name="source_run_id")
    _positive_integer(run_attempt, field_name="source_run_attempt")
    return f"{ARTIFACT_NAME_PREFIX}{run_id}-{run_attempt}"


def prove_provider_outcome_artifact(
    *,
    run_payload: dict[str, Any],
    jobs_payload: dict[str, Any],
    artifacts_payload: dict[str, Any],
    dispatch: GenericDispatchEnvelope,
    source_run_id: str,
    source_run_attempt: str,
    requested_publication_id: str,
    now: datetime | None = None,
) -> ProviderOutcomeArtifactProof:
    attempt = _positive_integer(source_run_attempt, field_name="source_run_attempt")
    _positive_integer(source_run_id, field_name="source_run_id")

    try:
        run_attempt = int(run_payload.get("run_attempt", 0))
    except (TypeError, ValueError):
        run_attempt = 0
    if run_attempt != attempt:
        raise ValueError("GitHub run attempt differs from archived-outcome recovery request")
    if run_payload.get("head_branch") != "main":
        raise ValueError("source provider run was not executed from main")
    if run_payload.get("status") != "completed":
        raise ValueError("source provider run is not completed")
    if run_payload.get("conclusion") == "success":
        raise ValueError("source provider run already succeeded; archived-outcome recovery is inconsistent")

    workflow_path = str(run_payload.get("path") or "").split("@", 1)[0]
    if workflow_path != WORKFLOW_PATH:
        raise ValueError(f"source run is not the permanent Milovi provider workflow: {workflow_path}")
    source_event = str(run_payload.get("event") or "")
    if source_event != EVENT:
        raise ValueError("source provider run event does not match Milovi workflow contract")

    if dispatch.project_key != "milovi-cake" or dispatch.channel_username.casefold() != "@milovicake".casefold():
        raise ValueError("persisted dispatch is not exact Milovi Cake publication evidence")
    if dispatch.workflow_run_id != source_run_id:
        raise ValueError("persisted dispatch run id differs from archived-outcome recovery request")
    if dispatch.workflow_run_attempt != source_run_attempt:
        raise ValueError("persisted dispatch run attempt differs from archived-outcome recovery request")
    if dispatch.publication_id != requested_publication_id:
        raise ValueError("persisted dispatch publication differs from recovery request")

    head_sha = str(run_payload.get("head_sha") or "")
    if head_sha != dispatch.github_sha:
        raise ValueError("source run head SHA differs from persisted dispatch provenance")

    persist_step = _single_named_step(jobs_payload, PERSIST_STEP)
    send_step = _single_named_step(jobs_payload, SEND_STEP)
    archive_step = _single_named_step(jobs_payload, ARCHIVE_STEP)
    final_step = _single_named_step(jobs_payload, FINAL_STATE_STEP)
    if persist_step.get("conclusion") != "success":
        raise ValueError("source durable intent step was not successful")
    if send_step.get("conclusion") != "success":
        raise ValueError("source provider send step was not executed to completion")
    if archive_step.get("conclusion") != "success":
        raise ValueError("source provider outcome artifact was not archived successfully")
    if final_step.get("conclusion") == "success":
        raise ValueError("source final state-persistence step already succeeded; recovery is inconsistent")

    expected_name = artifact_name(source_run_id, source_run_attempt)
    artifacts = artifacts_payload.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("GitHub artifact proof has no artifacts list")
    matches = [
        cast(dict[str, Any], candidate)
        for candidate in artifacts
        if isinstance(candidate, dict) and candidate.get("name") == expected_name
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one archived Milovi provider outcome artifact")
    artifact = matches[0]
    if artifact.get("expired") is True:
        raise ValueError("archived provider outcome artifact has expired")
    try:
        artifact_id = int(artifact.get("id", 0))
        artifact_size = int(artifact.get("size_in_bytes", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("archived provider outcome artifact metadata is invalid") from exc
    if artifact_id <= 0 or artifact_size <= 0 or artifact_size > MAX_OUTCOME_ARCHIVE_BYTES:
        raise ValueError("archived provider outcome artifact metadata is invalid")
    artifact_digest = str(artifact.get("digest") or "")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", artifact_digest) is None:
        raise ValueError("archived provider outcome artifact has no exact sha256 digest")
    artifact_run = artifact.get("workflow_run")
    if not isinstance(artifact_run, dict):
        raise ValueError("archived provider outcome artifact has no workflow-run provenance")
    if str(artifact_run.get("id") or "") != source_run_id:
        raise ValueError("artifact workflow run id differs from source provider run")
    if str(artifact_run.get("head_sha") or "") != dispatch.github_sha:
        raise ValueError("artifact head SHA differs from persisted dispatch provenance")

    checked_at = now or datetime.now(tz=UTC)
    if checked_at.tzinfo is None:
        raise ValueError("proof timestamp must be timezone-aware")
    return ProviderOutcomeArtifactProof(
        source_run_id=source_run_id,
        source_run_attempt=source_run_attempt,
        workflow_path=workflow_path,
        event=source_event,
        run_status="completed",
        run_conclusion=str(run_payload.get("conclusion")) if run_payload.get("conclusion") is not None else None,
        head_sha=head_sha,
        publication_id=requested_publication_id,
        artifact_id=artifact_id,
        artifact_name=expected_name,
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


def fetch_provider_outcome_artifact_proof(
    *,
    api_url: str,
    repository: str,
    token: str,
    dispatch: GenericDispatchEnvelope,
    source_run_id: str,
    source_run_attempt: str,
    requested_publication_id: str,
) -> ProviderOutcomeArtifactProof:
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is None:
        raise ValueError("outcome recovery requires an exact owner/repository name")
    if not token.strip():
        raise ValueError("outcome recovery requires GitHub Actions read credentials")
    attempt = _positive_integer(source_run_attempt, field_name="source_run_attempt")
    _positive_integer(source_run_id, field_name="source_run_id")
    base = api_url.rstrip("/")
    run_payload = _safe_github_json(
        f"{base}/repos/{repository}/actions/runs/{source_run_id}/attempts/{attempt}", token=token
    )
    jobs_payload = _safe_github_json(
        f"{base}/repos/{repository}/actions/runs/{source_run_id}/attempts/{attempt}/jobs?per_page=100", token=token
    )
    query = urllib.parse.urlencode({"name": artifact_name(source_run_id, source_run_attempt), "per_page": "100"})
    artifacts_payload = _safe_github_json(
        f"{base}/repos/{repository}/actions/runs/{source_run_id}/artifacts?{query}", token=token
    )
    return prove_provider_outcome_artifact(
        run_payload=run_payload,
        jobs_payload=jobs_payload,
        artifacts_payload=artifacts_payload,
        dispatch=dispatch,
        source_run_id=source_run_id,
        source_run_attempt=source_run_attempt,
        requested_publication_id=requested_publication_id,
    )


def verify_provider_outcome_archive(archive_bytes: bytes, proof: ProviderOutcomeArtifactProof) -> bytes:
    if len(archive_bytes) != proof.artifact_size_in_bytes:
        raise ValueError("downloaded provider-outcome artifact size differs from proved GitHub metadata")
    if "sha256:" + hashlib.sha256(archive_bytes).hexdigest() != proof.artifact_digest:
        raise ValueError("downloaded provider-outcome artifact digest differs from proved GitHub metadata")
    try:
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes))
    except zipfile.BadZipFile as exc:
        raise ValueError("downloaded provider-outcome artifact is not a valid ZIP archive") from exc
    with archive:
        files = [member for member in archive.infolist() if not member.is_dir()]
        if len(files) != 1:
            raise ValueError("provider-outcome artifact must contain exactly one file")
        member = files[0]
        path = PurePosixPath(member.filename)
        if path.is_absolute() or ".." in path.parts or path.name != OUTCOME_FILENAME:
            raise ValueError("provider-outcome artifact contains an unexpected file path")
        if member.file_size <= 0 or member.file_size > MAX_OUTCOME_JSON_BYTES:
            raise ValueError("provider-outcome JSON has an invalid size")
        outcome_bytes = archive.read(member)
    if len(outcome_bytes) != member.file_size:
        raise ValueError("provider-outcome JSON size differs from ZIP metadata")
    try:
        GenericProviderOutcome.model_validate_json(outcome_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("provider-outcome artifact does not contain a valid outcome JSON") from exc
    return outcome_bytes


def download_verified_provider_outcome(
    *, api_url: str, repository: str, token: str, proof: ProviderOutcomeArtifactProof, output: Path
) -> None:
    archive_url = f"{api_url.rstrip('/')}/repos/{repository}/actions/artifacts/{proof.artifact_id}/zip"
    archive_bytes = _safe_github_bytes(archive_url, token=token, max_bytes=MAX_OUTCOME_ARCHIVE_BYTES)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(verify_provider_outcome_archive(archive_bytes, proof))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Prove and validate archived Milovi Telegram provider outcomes")
    sub = root.add_subparsers(dest="command", required=True)
    prove = sub.add_parser("prove")
    prove.add_argument("--dispatch", type=Path, required=True)
    prove.add_argument("--source-run-id", required=True)
    prove.add_argument("--source-run-attempt", required=True)
    prove.add_argument("--publication-id", required=True)
    prove.add_argument("--proof-output", type=Path, required=True)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("--proof", type=Path, required=True)
    fetch.add_argument("--outcome-output", type=Path, required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--dispatch", type=Path, required=True)
    validate.add_argument("--outcome", type=Path, required=True)
    validate.add_argument("--publication-id", required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    if args.command == "fetch":
        proof = ProviderOutcomeArtifactProof.model_validate_json(args.proof.read_text(encoding="utf-8"))
        if proof.workflow_path != WORKFLOW_PATH or not proof.artifact_name.startswith(ARTIFACT_NAME_PREFIX):
            raise ValueError("proof is not an exact Milovi provider-outcome proof")
        download_verified_provider_outcome(
            api_url=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
            repository=os.environ.get("GITHUB_REPOSITORY", ""),
            token=os.environ.get("GH_TOKEN", ""),
            proof=proof,
            output=args.outcome_output,
        )
        return 0

    dispatch = GenericDispatchEnvelope.model_validate_json(args.dispatch.read_text(encoding="utf-8"))
    if args.command == "prove":
        proof = fetch_provider_outcome_artifact_proof(
            api_url=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
            repository=os.environ.get("GITHUB_REPOSITORY", ""),
            token=os.environ.get("GH_TOKEN", ""),
            dispatch=dispatch,
            source_run_id=args.source_run_id,
            source_run_attempt=args.source_run_attempt,
            requested_publication_id=args.publication_id,
        )
        args.proof_output.parent.mkdir(parents=True, exist_ok=True)
        args.proof_output.write_text(proof.model_dump_json(indent=2) + "\n", encoding="utf-8")
        print(proof.model_dump_json())
        return 0
    if args.command == "validate":
        outcome = GenericProviderOutcome.model_validate_json(args.outcome.read_text(encoding="utf-8"))
        validate_recovered_outcome(dispatch, outcome, requested_publication_id=args.publication_id)
        print(json.dumps({"valid": True, "publication_id": outcome.publication_id}, ensure_ascii=False))
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
