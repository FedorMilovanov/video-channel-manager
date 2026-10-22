"""Prove that rebuilt Milovi Telegram artifacts reproduce the accepted evidence commit.

This module replaces the shell block that used to live in the artifact workflow. It exists
because that block had two defects that only surfaced in production:

1. It was exercised **after** merge. The pull-request job built the artifacts but never
   proved them, so the guard around `main` ran for the first time when `main` was already
   merged — and its failure was invisible in the build log.
2. It named its evidence ref after the rebuilt digest. A rebuild legitimately produces a
   different evidence identity (runner toolchain metadata is part of the identity), so a
   digest-derived name can never equal the accepted ref. Anchoring the proof on the
   reservoir's `artifact_commit` removes that class of mistake entirely.

The proof is deliberately a rebuild-proof, not a release event: it writes nothing, pushes
nothing, and never derives a ref name from a rebuild.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from video_channel_manager.milovi_telegram_video_artifacts import _evidence_identity

DEFAULT_OUTPUT_DIR = Path("artifacts/milovi-telegram/video")
DEFAULT_RESERVOIR = Path("content/telegram/milovi-cake/accepted-video-reservoir-2026-08.json")
DEFAULT_EVIDENCE = Path("content/telegram/milovi-cake/video-conversion-evidence-2026-08.json")

# Local, throw-away pointer for the accepted commit inside the build workspace. It is not a
# repository ref and must never be named like a binding, so it is deliberately not called
# `*_REF`/`*_BRANCH`: nothing durable is allowed to depend on it.
LOCAL_PROOF_POINTER = "refs/milovi-accepted/evidence"

COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
GIT_CONFIG_HINT = "docs/operations/protected-evidence-refs.json"


class ProofFailure(RuntimeError):
    """The rebuilt artifacts do not reproduce the accepted evidence commit."""

    def __init__(self, message: str, *, details: Iterable[str] = ()) -> None:
        super().__init__(message)
        self.details = tuple(details)


@dataclass(frozen=True)
class ProofResult:
    accepted_ref: str
    accepted_commit: str
    artifact_count: int
    rebuilt_evidence_sha256: str
    accepted_evidence_sha256: str
    blob_ids: dict[str, str] = field(default_factory=dict)

    @property
    def identity_matches_accepted(self) -> bool:
        return self.rebuilt_evidence_sha256 == self.accepted_evidence_sha256


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ProofFailure(f"expected a JSON object: {path}")
    return payload


def _git(argv: Sequence[str], *, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        ["git", *argv],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "no output"
        raise ProofFailure(f"git {' '.join(argv)} failed: {message}")
    return completed.stdout.strip()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _file_blob_sha1(path: Path, *, cwd: Path | None = None) -> str:
    return _git(["hash-object", "--no-filters", str(path)], cwd=cwd)


def _worktree_root(*, cwd: Path | None = None) -> Path:
    return Path(_git(["rev-parse", "--show-toplevel"], cwd=cwd)).resolve()


def fetch_accepted_commit(commit: str, *, remote: str = "origin", cwd: Path | None = None) -> str:
    """Fetch the accepted commit by SHA and return the local pointer that now holds it.

    Fetching by SHA — never by branch name — is the point: a rebuild cannot reach a ref it
    did not name, and a rewritten ref cannot masquerade as the accepted bytes.
    """

    if not COMMIT_PATTERN.fullmatch(commit):
        raise ProofFailure(f"accepted artifact_commit is not a full commit id: {commit!r}")
    _git(
        ["fetch", "--depth=1", "--no-tags", "--force", remote, f"+{commit}:{LOCAL_PROOF_POINTER}"],
        cwd=cwd,
    )
    return LOCAL_PROOF_POINTER


def _blob_in_commit(pointer: str, path: str, *, cwd: Path | None = None) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", f"{pointer}:{path}"],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _rebuilt_paths(output_dir: Path, root: Path) -> dict[str, Path]:
    if not output_dir.is_dir():
        raise ProofFailure(f"rebuilt output directory is missing: {output_dir}")
    rebuilt: dict[str, Path] = {}
    for path in sorted(output_dir.glob("*.mp4")):
        rebuilt[path.resolve().relative_to(root).as_posix()] = path
    if not rebuilt:
        raise ProofFailure(f"no rebuilt artifacts found under {output_dir}")
    return rebuilt


def _expected_paths(reservoir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    artifacts = reservoir.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ProofFailure("reservoir does not list the accepted artifacts")
    expected: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ProofFailure("reservoir artifact entry is not an object")
        path = str(artifact.get("artifact_path") or "")
        if not path.endswith(".mp4"):
            raise ProofFailure(f"reservoir artifact path is not an MP4: {path!r}")
        if path in expected:
            raise ProofFailure(f"reservoir lists {path} more than once")
        if not COMMIT_PATTERN.fullmatch(str(artifact.get("git_blob_sha1") or "")):
            raise ProofFailure(f"reservoir blob id for {path} is not a full object id")
        if not str(artifact.get("sha256") or "").startswith("sha256:"):
            raise ProofFailure(f"reservoir content digest for {path} is not a sha256 digest")
        expected[path] = artifact
    declared = reservoir.get("accepted_output_count")
    if isinstance(declared, int) and declared != len(expected):
        raise ProofFailure(f"reservoir declares {declared} outputs but lists {len(expected)}")
    return expected


def verify(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    reservoir_path: Path = DEFAULT_RESERVOIR,
    evidence_path: Path = DEFAULT_EVIDENCE,
    remote: str = "origin",
    cwd: Path | None = None,
    fetch: bool = True,
) -> ProofResult:
    """Compare the rebuilt bytes with the accepted bytes, failure by failure.

    Every mismatch is collected instead of raised on the first one, so a single run reports
    the whole truth: one drifted artifact is a rebuild bug, sixteen are a different
    question, and the difference matters when reading a failed run.
    """

    root = _worktree_root(cwd=cwd)
    reservoir = _json(reservoir_path)
    evidence = _json(evidence_path)

    accepted_ref = str(reservoir.get("artifact_ref") or "")
    accepted_commit = str(reservoir.get("artifact_commit") or "")
    accepted_identity = str(reservoir.get("evidence_sha256") or "")
    expected = _expected_paths(reservoir)

    outputs = evidence.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise ProofFailure(f"rebuilt evidence has no outputs: {evidence_path}")
    evidence_by_path = {str(output.get("output_path") or ""): output for output in outputs if isinstance(output, dict)}

    rebuilt = _rebuilt_paths(output_dir, root)
    details: list[str] = []

    missing = sorted(set(expected) - set(rebuilt))
    unexpected = sorted(set(rebuilt) - set(expected))
    for path in missing:
        details.append(f"rebuilt output is missing {path}; the accepted commit has it")
    for path in unexpected:
        details.append(
            f"rebuilt output {path} is not part of the accepted artifact set; refusing an unreviewed artifact"
        )

    blob_ids: dict[str, str] = {}
    for path in sorted(set(expected) & set(rebuilt)):
        artifact = expected[path]
        local = rebuilt[path]
        accepted_sha256 = str(artifact["sha256"])
        accepted_blob = str(artifact["git_blob_sha1"])

        actual_sha256 = _file_sha256(local)
        if actual_sha256 != accepted_sha256:
            details.append(
                f"artifact drift on {path}: accepted content digest {accepted_sha256} "
                f"rebuilt {actual_sha256} ({local.stat().st_size} bytes)"
            )
        output = evidence_by_path.get(path)
        if output is not None and str(output.get("output_sha256")) != actual_sha256:
            details.append(
                f"rebuild evidence disagrees with its own artifact on {path}: "
                f"recorded {output.get('output_sha256')} actual {actual_sha256}"
            )

        actual_blob = _file_blob_sha1(local, cwd=cwd)
        if actual_blob != accepted_blob:
            details.append(f"artifact drift on {path}: accepted blob {accepted_blob} rebuilt blob {actual_blob}")
        blob_ids[path] = actual_blob

    if not COMMIT_PATTERN.fullmatch(accepted_commit):
        raise ProofFailure(f"reservoir artifact_commit is not a full commit id: {accepted_commit!r}")
    if not accepted_ref:
        raise ProofFailure("reservoir does not name the accepted artifact ref")

    if fetch:
        pointer = fetch_accepted_commit(accepted_commit, remote=remote, cwd=cwd)
    else:
        pointer = LOCAL_PROOF_POINTER
    for path, artifact in sorted(expected.items()):
        pinned = _blob_in_commit(pointer, path, cwd=cwd)
        if pinned is None:
            details.append(
                f"accepted commit {accepted_commit} does not contain {path}; "
                f"restore the accepted ref from {GIT_CONFIG_HINT} before rebuilding"
            )
        elif pinned != artifact["git_blob_sha1"]:
            details.append(
                f"accepted commit {accepted_commit} holds blob {pinned} for {path} but the reservoir "
                f"records {artifact['git_blob_sha1']}; one of them is stale"
            )

    if details:
        raise ProofFailure(
            f"rebuilt artifacts do not reproduce {accepted_ref}@{accepted_commit}; refusing to publish. "
            "Different bytes are a new release decision: update the reservoir "
            f"({reservoir_path}) and {GIT_CONFIG_HINT} before materializing a new accepted ref.",
            details=details,
        )

    rebuilt_identity = str(evidence.get("evidence_sha256") or "") or _evidence_identity(evidence)
    return ProofResult(
        accepted_ref=accepted_ref,
        accepted_commit=accepted_commit,
        artifact_count=len(expected),
        rebuilt_evidence_sha256=rebuilt_identity,
        accepted_evidence_sha256=accepted_identity,
        blob_ids=blob_ids,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prove rebuilt Milovi artifacts reproduce the accepted commit")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--reservoir", type=Path, default=DEFAULT_RESERVOIR)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--github-output", type=Path, default=None)
    return parser


def _annotate(message: str, *, title: str) -> None:
    """Emit a GitHub annotation so a failed run is readable from the checks API.

    The run that exposed this defect could not be diagnosed at all: the job log was not
    reachable, and the shell step only wrote to stderr. An annotation is part of the check
    run, so the next failure explains itself where it can be read.
    """

    print(f"::error title={title}::{message}", flush=True)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = verify(
            output_dir=args.output_dir,
            reservoir_path=args.reservoir,
            evidence_path=args.evidence,
            remote=args.remote,
        )
    except ProofFailure as failure:
        for detail in failure.details:
            _annotate(detail, title="Milovi artifact proof")
        _annotate(str(failure), title="Milovi artifact proof")
        print(str(failure), file=sys.stderr, flush=True)
        return 3

    print(
        f"rebuilt {result.artifact_count} artifacts reproduce "
        f"{result.accepted_ref}@{result.accepted_commit} byte-for-byte"
    )
    if result.identity_matches_accepted:
        print(f"rebuilt evidence identity {result.rebuilt_evidence_sha256} equals the accepted identity")
    else:
        print(
            f"rebuilt evidence identity {result.rebuilt_evidence_sha256} differs from the accepted "
            f"identity {result.accepted_evidence_sha256}: runner toolchain metadata is part of the "
            "identity, and the artifact bytes above are what the release is bound to"
        )

    if args.github_output is not None:
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"branch={result.accepted_ref}\n")
            handle.write(f"evidence_sha256={result.rebuilt_evidence_sha256}\n")
            handle.write(f"artifact_commit={result.accepted_commit}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
