from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
import warnings
from typing import Any

import pytest


REPOSITORY = "FedorMilovanov/video-channel-manager"
WINDOW_START = "2026-08-18T13:15:00Z"
WINDOW_END = "2026-08-18T14:10:00Z"
WORKFLOWS = (
    "milovi-telegram-oneoff-canary-dispatch.yml",
    "milovi-telegram-oneoff-canary.yml",
    "ci.yml",
    "milovi-telegram-oneoff-canary-quality.yml",
    "milovi-telegram-bootstrap-media-proof.yml",
)


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "video-channel-manager-milovi-forensics",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310
        payload = json.load(response)
    assert isinstance(payload, dict)
    return payload


def _workflow_runs(workflow: str) -> dict[str, Any]:
    encoded = urllib.parse.quote(workflow, safe="")
    url = (
        f"https://api.github.com/repos/{REPOSITORY}/actions/workflows/{encoded}/runs"
        "?per_page=100"
    )
    payload = _get_json(url)
    runs = []
    for run in payload.get("workflow_runs", []):
        created_at = str(run.get("created_at") or "")
        if WINDOW_START <= created_at <= WINDOW_END:
            runs.append(
                {
                    "id": run.get("id"),
                    "run_number": run.get("run_number"),
                    "event": run.get("event"),
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "head_sha": run.get("head_sha"),
                    "head_branch": run.get("head_branch"),
                    "created_at": created_at,
                    "updated_at": run.get("updated_at"),
                }
            )
    return {"workflow": workflow, "runs": runs}


def test_emit_exact_milovi_canary_actions_forensics() -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        pytest.skip("GitHub Actions-only read-only forensic probe")

    evidence = {
        "window_utc": [WINDOW_START, WINDOW_END],
        "provider_access_performed": False,
        "provider_write_performed": False,
        "workflows": [_workflow_runs(workflow) for workflow in WORKFLOWS],
    }
    warnings.warn(
        "MILOVI_CANARY_FORENSICS=" + json.dumps(evidence, sort_keys=True),
        RuntimeWarning,
        stacklevel=1,
    )
