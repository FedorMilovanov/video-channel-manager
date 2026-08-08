from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from video_channel_manager.telegram_multichannel_outcome import GenericProviderOutcome
from video_channel_manager.telegram_multichannel_state import GenericDispatchEnvelope

ARTIFACT_NAME_PREFIX = "svodka-provider-outcome-"


class ProviderWorkflowContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event: str
    persist_step: str
    send_step: str
    archive_step: str
    final_state_step: str


PROVIDER_WORKFLOWS: dict[str, ProviderWorkflowContract] = {
    ".github/workflows/svodka-canary.yml": ProviderWorkflowContract(
        event="workflow_dispatch",
        persist_step="Persist intent before Telegram mutation",
        send_step="Send exactly one canary payload",
        archive_step="Archive exact provider outcome before state mutation",
        final_state_step="Apply and persist exact provider outcome",
    ),
    ".github/workflows/svodka-scheduled-publisher.yml": ProviderWorkflowContract(
        event="schedule",
        persist_step="Persist scheduled intent before Telegram mutation",
        send_step="Send exactly one scheduled payload",
        archive_step="Archive exact provider outcome before state mutation",
        final_state_step="Apply and persist exact scheduled provider outcome",
    ),
}


class ProviderOutcomeArtifactProof(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: str = "video-channel-manager.telegram-provider-outcome-artifact-proof"
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


def _safe_github_json(url: str, *, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "video-channel-manager-svodka-outcome-reconciler",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except Exception as exc:
        raise RuntimeError(f"GitHub provider-outcome proof unavailable: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub provider-outcome proof returned a non-object response")
    return cast(dict[str, Any], payload)


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
        raise ValueError("GitHub jobs proof has no jobs list")
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
        raise ValueError(f"cannot prove unique source step: {name}")
    return matches[0]


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
    expected_artifact_name = artifact_name(source_run_id, source_run_attempt)

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
    contract = PROVIDER_WORKFLOWS.get(workflow_path)
    if contract is None:
        raise ValueError(f"source run is not a recognized Svodka provider workflow: {workflow_path}")
    if run_payload.get("event") != contract.event:
        raise ValueError("source provider run event does not match workflow contract")

    if dispatch.workflow_run_id != source_run_id:
        raise ValueError("persisted dispatch run id differs from archived-outcome recovery request")
    if dispatch.workflow_run_attempt != source_run_attempt:
        raise ValueError("persisted dispatch run attempt differs from archived-outcome recovery request")
    if dispatch.publication_id != requested_publication_id:
        raise ValueError("persisted dispatch publication differs from archived-outcome recovery request")
    head_sha = str(run_payload.get("head_sha") or "")
    if head_sha != dispatch.github_sha:
        raise ValueError("source run head SHA differs from persisted dispatch provenance")

    persist_step = _single_named_step(jobs_payload, contract.persist_step)
    send_step = _single_named_step(jobs_payload, contract.send_step)
    archive_step = _single_named_step(jobs_payload, contract.archive_step)
    final_step = _single_named_step(jobs_payload, contract.final_state_step)
    if persist_step.get("conclusion") != "success":
        raise ValueError("source durable intent step was not successful")
    if send_step.get("conclusion") != "success":
        raise ValueError("source provider send step was not executed to completion")
    if archive_step.get("conclusion") != "success":
        raise ValueError("source provider outcome artifact was not archived successfully")
    if final_step.get("conclusion") == "success":
        raise ValueError("source final state-persistence step already succeeded; recovery is inconsistent")

    artifacts = artifacts_payload.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("GitHub artifact proof has no artifacts list")
    matches = [
        cast(dict[str, Any], candidate)
        for candidate in artifacts
        if isinstance(candidate, dict) and candidate.get("name") == expected_artifact_name
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one archived provider outcome artifact for source run")
    artifact = matches[0]
    if artifact.get("expired") is True:
        raise ValueError("archived provider outcome artifact has expired")
    try:
        artifact_id = int(artifact.get("id", 0))
        artifact_size = int(artifact.get("size_in_bytes", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("archived provider outcome artifact metadata is invalid") from exc
    if artifact_id <= 0 or artifact_size <= 0:
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
        event=contract.event,
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
    return prove_provider_outcome_artifact(
        run_payload=run_payload,
        jobs_payload=jobs_payload,
        artifacts_payload=artifacts_payload,
        dispatch=dispatch,
        source_run_id=source_run_id,
        source_run_attempt=source_run_attempt,
        requested_publication_id=requested_publication_id,
    )


def validate_recovered_outcome(
    dispatch: GenericDispatchEnvelope,
    outcome: GenericProviderOutcome,
    *,
    requested_publication_id: str,
) -> None:
    if outcome.publication_id != dispatch.publication_id:
        raise ValueError("archived provider outcome publication differs from persisted dispatch")
    if outcome.provider_payload_sha256 != dispatch.provider_payload_sha256:
        raise ValueError("archived provider outcome payload digest differs from persisted dispatch")
    if outcome.publication_id != requested_publication_id:
        raise ValueError("archived provider outcome publication differs from recovery request")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Prove and validate archived Svodka Telegram provider outcomes")
    sub = root.add_subparsers(dest="command", required=True)

    prove = sub.add_parser("prove")
    prove.add_argument("--dispatch", type=Path, required=True)
    prove.add_argument("--source-run-id", required=True)
    prove.add_argument("--source-run-attempt", required=True)
    prove.add_argument("--publication-id", required=True)
    prove.add_argument("--proof-output", type=Path, required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("--dispatch", type=Path, required=True)
    validate.add_argument("--outcome", type=Path, required=True)
    validate.add_argument("--publication-id", required=True)
    return root


def main() -> int:
    args = parser().parse_args()
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
        print(
            json.dumps(
                {
                    "valid": True,
                    "publication_id": outcome.publication_id,
                    "provider_effect": outcome.provider_effect,
                    "retryable": outcome.retryable,
                },
                ensure_ascii=False,
            )
        )
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
