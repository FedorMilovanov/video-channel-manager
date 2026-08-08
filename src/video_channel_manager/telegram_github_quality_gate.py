from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any, cast

ALLOWED_QUALITY_EVENTS = frozenset({"push", "workflow_dispatch"})


def _safe_github_json(url: str, *, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "video-channel-manager-svodka-quality-gate",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except Exception as exc:
        raise RuntimeError(f"GitHub quality proof unavailable: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub quality proof returned a non-object response")
    return cast(dict[str, Any], payload)


def select_successful_quality_run(
    payload: dict[str, Any],
    *,
    workflow_file: str,
    head_sha: str,
) -> dict[str, Any]:
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        raise ValueError("GitHub quality proof has no workflow_runs list")

    expected_path = f".github/workflows/{workflow_file}"
    allowed_paths = {expected_path, f"{expected_path}@main"}
    matching: list[dict[str, Any]] = []
    for candidate in runs:
        if not isinstance(candidate, dict):
            continue
        if (
            candidate.get("head_sha") == head_sha
            and candidate.get("head_branch") == "main"
            and candidate.get("status") == "completed"
            and candidate.get("conclusion") == "success"
            and candidate.get("event") in ALLOWED_QUALITY_EVENTS
            and candidate.get("path") in allowed_paths
        ):
            matching.append(cast(dict[str, Any], candidate))
    if not matching:
        raise ValueError("no successful Svodka quality run proves the exact current main SHA")

    def run_number(value: dict[str, Any]) -> int:
        raw = value.get("id", 0)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    return max(matching, key=run_number)


def require_successful_quality_run(
    *,
    api_url: str,
    repository: str,
    token: str,
    workflow_file: str,
    head_sha: str,
) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", head_sha) is None:
        raise ValueError("quality gate requires an exact 40-character GitHub SHA")
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is None:
        raise ValueError("quality gate requires an exact owner/repository name")
    if re.fullmatch(r"[A-Za-z0-9_.-]+\.ya?ml", workflow_file) is None:
        raise ValueError("quality gate requires an exact workflow filename")
    if not token.strip():
        raise ValueError("quality gate requires GitHub Actions read credentials")

    encoded_workflow = urllib.parse.quote(workflow_file, safe="")
    query = urllib.parse.urlencode(
        {
            "head_sha": head_sha,
            "status": "success",
            "per_page": "100",
        }
    )
    url = (
        f"{api_url.rstrip('/')}/repos/{repository}/actions/workflows/"
        f"{encoded_workflow}/runs?{query}"
    )
    payload = _safe_github_json(url, token=token)
    return select_successful_quality_run(payload, workflow_file=workflow_file, head_sha=head_sha)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Require an exact-SHA successful GitHub Actions quality proof")
    root.add_argument("--workflow", required=True)
    root.add_argument("--sha", required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    run = require_successful_quality_run(
        api_url=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
        repository=os.environ.get("GITHUB_REPOSITORY", ""),
        token=os.environ.get("GH_TOKEN", ""),
        workflow_file=args.workflow,
        head_sha=args.sha,
    )
    print(
        json.dumps(
            {
                "quality_proven": True,
                "workflow": args.workflow,
                "head_sha": args.sha,
                "run_id": run.get("id"),
                "run_attempt": run.get("run_attempt"),
                "event": run.get("event"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
