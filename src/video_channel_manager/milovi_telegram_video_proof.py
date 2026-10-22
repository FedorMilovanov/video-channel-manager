"""Prove the Milovi Telegram video release, and explain any rebuild difference.

The lane has two claims, and they are not the same claim:

1. **Release integrity** — the 16 accepted MP4s live on the content-addressed evidence ref
   named by the reservoir, at the exact commit it records, with exactly the blob ids it
   records. This is checkable without an encoder, and it is what publication depends on.
   It is blocking.
2. **Rebuild reproduction** — the current runner's FFmpeg rebuilds those bytes. This is a
   supply-chain observation about a *third-party encoder build*, not a property of the
   release: `apt-get install ffmpeg` follows a moving Ubuntu archive, and on 2026-10-22 the
   archive shipped an FFmpeg whose encode differs from the accepted one by a few hundred
   bytes per file. The release did not change; the encoder did.

Conflating the two is what kept `main` red: the previous step demanded byte equality from a
moving encoder, so a normal archive update was reported as artifact drift.

The proof therefore compares the encoder binary digests recorded in both evidence files:

* same encoder, different bytes — our own build is nondeterministic, which is a real defect:
  blocking;
* different encoder, different bytes — the toolchain moved, which the release is not bound
  to: reported, with both digests and every file that differs, and never published.

The proof writes nothing and pushes nothing. It never derives a ref name from a rebuild: a
rebuild legitimately produces a different evidence identity, because that identity includes
toolchain metadata.
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
DEFAULT_REPORT = Path("artifacts/milovi-telegram/video-rebuild-proof.json")

# Local, throw-away pointer for the accepted commit inside the build workspace. It is not a
# repository ref and must never be named like a binding, so it is deliberately not called
# `*_REF`/`*_BRANCH`: nothing durable is allowed to depend on it.
LOCAL_PROOF_POINTER = "refs/milovi-accepted/evidence"

COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
ENCODER_KEYS = ("ffmpeg_executable_sha256", "ffprobe_executable_sha256")
GIT_CONFIG_HINT = "docs/operations/protected-evidence-refs.json"


class ProofFailure(RuntimeError):
    """The release cannot be proven, or the same encoder produced different bytes."""

    def __init__(self, message: str, *, details: Iterable[str] = ()) -> None:
        super().__init__(message)
        self.details = tuple(details)


@dataclass(frozen=True)
class Drift:
    path: str
    accepted_sha256: str
    rebuilt_sha256: str
    accepted_blob: str
    rebuilt_blob: str
    accepted_size: int
    rebuilt_size: int

    def describe(self) -> str:
        return (
            f"{self.path}: accepted {self.accepted_sha256} ({self.accepted_size} bytes, "
            f"blob {self.accepted_blob}) rebuilt {self.rebuilt_sha256} "
            f"({self.rebuilt_size} bytes, blob {self.rebuilt_blob})"
        )


@dataclass(frozen=True)
class ProofResult:
    accepted_ref: str
    accepted_commit: str
    artifact_count: int
    rebuilt_evidence_sha256: str
    accepted_evidence_sha256: str
    accepted_toolchain: dict[str, Any]
    rebuilt_toolchain: dict[str, Any]
    drifted: tuple[Drift, ...] = field(default_factory=tuple)

    @property
    def byte_identical(self) -> bool:
        return not self.drifted

    @property
    def encoder_changed(self) -> bool:
        return any(
            str(self.accepted_toolchain.get(key)) != str(self.rebuilt_toolchain.get(key)) for key in ENCODER_KEYS
        )

    @property
    def identity_matches_accepted(self) -> bool:
        return self.rebuilt_evidence_sha256 == self.accepted_evidence_sha256

    def as_report(self) -> dict[str, Any]:
        return {
            "schema_name": "video-channel-manager.milovi-video-rebuild-proof",
            "schema_version": 1,
            "provider_access_performed": False,
            "provider_write_performed": False,
            "repository_write_performed": False,
            "release_integrity": "verified",
            "accepted_ref": self.accepted_ref,
            "accepted_commit": self.accepted_commit,
            "accepted_evidence_sha256": self.accepted_evidence_sha256,
            "rebuilt_evidence_sha256": self.rebuilt_evidence_sha256,
            "artifact_count": self.artifact_count,
            "byte_identical_count": self.artifact_count - len(self.drifted),
            "rebuild_conclusion": "byte_identical"
            if self.byte_identical
            else ("encoder_changed" if self.encoder_changed else "nondeterministic"),
            "encoder_changed": self.encoder_changed,
            "toolchain": {
                "accepted": {key: self.accepted_toolchain.get(key) for key in ENCODER_KEYS},
                "rebuilt": {key: self.rebuilt_toolchain.get(key) for key in ENCODER_KEYS},
            },
            "drifted": [
                {
                    "path": drift.path,
                    "accepted_sha256": drift.accepted_sha256,
                    "rebuilt_sha256": drift.rebuilt_sha256,
                    "accepted_blob": drift.accepted_blob,
                    "rebuilt_blob": drift.rebuilt_blob,
                    "accepted_byte_size": drift.accepted_size,
                    "rebuilt_byte_size": drift.rebuilt_size,
                }
                for drift in self.drifted
            ],
        }


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


def _accepted_evidence_path(reservoir: dict[str, Any], *, root: Path, reservoir_path: Path) -> Path:
    """Resolve the accepted evidence file named by the reservoir.

    The reservoir records a repository-relative path. Resolving it against the worktree keeps
    the proof independent of the directory the job happens to run from, and falls back to the
    reservoir's own directory so a relocated copy still resolves.
    """

    raw = str(reservoir.get("evidence_path") or "").strip()
    if not raw:
        raise ProofFailure(f"reservoir does not name the accepted evidence path: {reservoir_path}")
    candidate = Path(raw)
    if not candidate.is_absolute():
        rooted = root / candidate
        candidate = rooted if rooted.is_file() else reservoir_path.parent / candidate.name
    if not candidate.is_file():
        raise ProofFailure(f"accepted evidence file is missing: {candidate}")
    return candidate


def _toolchain(evidence: dict[str, Any], *, label: str) -> dict[str, Any]:
    toolchain = evidence.get("toolchain")
    if not isinstance(toolchain, dict):
        raise ProofFailure(f"{label} evidence does not record its toolchain; the encoder cannot be identified")
    missing = [key for key in ENCODER_KEYS if not str(toolchain.get(key) or "").startswith("sha256:")]
    if missing:
        raise ProofFailure(
            f"{label} evidence does not record {', '.join(missing)}: without the encoder binary digest an "
            "artifact difference cannot be attributed to the toolchain or to nondeterminism, so it is not certifiable"
        )
    return toolchain


def verify(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    reservoir_path: Path = DEFAULT_RESERVOIR,
    evidence_path: Path = DEFAULT_EVIDENCE,
    remote: str = "origin",
    cwd: Path | None = None,
) -> ProofResult:
    """Prove the release, then attribute any rebuild difference to its actual cause.

    Every mismatch is collected instead of raised on the first one, so a single run reports
    the whole truth: one drifted artifact is a build bug, sixteen are a different question,
    and the difference matters when reading a failed run.
    """

    root = _worktree_root(cwd=cwd)
    reservoir = _json(reservoir_path)
    evidence = _json(evidence_path)

    accepted_ref = str(reservoir.get("artifact_ref") or "")
    accepted_commit = str(reservoir.get("artifact_commit") or "")
    accepted_evidence_sha256 = str(reservoir.get("evidence_sha256") or "")
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

    drift: list[Drift] = []
    for path in sorted(set(expected) & set(rebuilt)):
        artifact = expected[path]
        local = rebuilt[path]
        accepted_sha256 = str(artifact["sha256"])
        accepted_blob = str(artifact["git_blob_sha1"])

        actual_sha256 = _file_sha256(local)
        output = evidence_by_path.get(path)
        if output is not None and str(output.get("output_sha256")) != actual_sha256:
            details.append(
                f"rebuild evidence disagrees with its own artifact on {path}: "
                f"recorded {output.get('output_sha256')} actual {actual_sha256}"
            )

        actual_blob = _file_blob_sha1(local, cwd=cwd)
        if actual_sha256 != accepted_sha256 or actual_blob != accepted_blob:
            drift.append(
                Drift(
                    path=path,
                    accepted_sha256=accepted_sha256,
                    rebuilt_sha256=actual_sha256,
                    accepted_blob=accepted_blob,
                    rebuilt_blob=actual_blob,
                    accepted_size=int(artifact.get("byte_size") or 0),
                    rebuilt_size=local.stat().st_size,
                )
            )

    if not COMMIT_PATTERN.fullmatch(accepted_commit):
        raise ProofFailure(f"reservoir artifact_commit is not a full commit id: {accepted_commit!r}")
    if not accepted_ref:
        raise ProofFailure("reservoir does not name the accepted artifact ref")

    # Release integrity: the accepted commit must exist and hold exactly the recorded bytes.
    pointer = fetch_accepted_commit(accepted_commit, remote=remote, cwd=cwd)
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
            f"the accepted Milovi video release {accepted_ref}@{accepted_commit} cannot be proven; "
            f"nothing may be published from this workspace. Update the reservoir ({reservoir_path}) and "
            f"{GIT_CONFIG_HINT}, or restore the accepted ref, before rebuilding.",
            details=details,
        )

    accepted_toolchain = _toolchain(
        _json(_accepted_evidence_path(reservoir, root=root, reservoir_path=reservoir_path)),
        label="accepted",
    )
    rebuilt_toolchain = _toolchain(evidence, label="rebuilt")

    result = ProofResult(
        accepted_ref=accepted_ref,
        accepted_commit=accepted_commit,
        artifact_count=len(expected),
        rebuilt_evidence_sha256=str(evidence.get("evidence_sha256") or "") or _evidence_identity(evidence),
        accepted_evidence_sha256=accepted_evidence_sha256,
        accepted_toolchain=accepted_toolchain,
        rebuilt_toolchain=rebuilt_toolchain,
        drifted=tuple(drift),
    )

    if result.drifted and not result.encoder_changed:
        raise ProofFailure(
            "the same encoder binary produced different bytes: this is nondeterminism in our own build, "
            "not an archive update. The accepted release is unchanged, but the build pipeline must be fixed "
            "before its output can be trusted again.",
            details=[drift.describe() for drift in result.drifted],
        )

    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prove the Milovi video release and report rebuild differences")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--reservoir", type=Path, default=DEFAULT_RESERVOIR)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--github-output", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser


def _annotate(message: str, *, title: str, level: str = "error") -> None:
    """Emit a GitHub annotation so a run is readable from the checks API.

    The run that exposed this defect could not be diagnosed at all: the job log was not
    reachable and the shell step only wrote to stderr. An annotation is part of the check
    run, so the next difference explains itself where it can be read.
    """

    print(f"::{level} title={title}::{message}", flush=True)


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
            _annotate(detail, title="Milovi video release proof")
        _annotate(str(failure), title="Milovi video release proof")
        print(str(failure), file=sys.stderr, flush=True)
        return 3

    print(
        f"release proven: {result.artifact_count} accepted artifacts at {result.accepted_ref}@{result.accepted_commit}"
    )
    if result.byte_identical:
        print(f"rebuild reproduces every accepted byte; evidence identity {result.rebuilt_evidence_sha256}")
    else:
        _annotate(
            f"the runner rebuilt {len(result.drifted)} of {result.artifact_count} artifacts with different bytes "
            f"because its FFmpeg binary changed (accepted {result.accepted_toolchain['ffmpeg_executable_sha256']} "
            f"rebuilt {result.rebuilt_toolchain['ffmpeg_executable_sha256']}). The accepted release is unchanged and "
            "nothing is published from the rebuild; re-accepting the new encoding is a separate release decision.",
            title="Milovi rebuild differs from the accepted encoding",
            level="warning",
        )
        for drift in result.drifted:
            _annotate(drift.describe(), title="Milovi rebuild drift", level="warning")
        print(
            f"rebuild differs from the accepted encoding on {len(result.drifted)} artifacts; "
            f"encoder changed: {result.accepted_toolchain['ffmpeg_executable_sha256']} -> "
            f"{result.rebuilt_toolchain['ffmpeg_executable_sha256']}"
        )

    if result.identity_matches_accepted:
        print(f"rebuilt evidence identity {result.rebuilt_evidence_sha256} equals the accepted identity")
    else:
        print(
            f"rebuilt evidence identity {result.rebuilt_evidence_sha256} differs from the accepted identity "
            f"{result.accepted_evidence_sha256}: runner toolchain metadata is part of the identity"
        )

    report_path = args.report
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result.as_report(), indent=2) + "\n", encoding="utf-8")
        print(f"rebuild proof report: {report_path}")

    if args.github_output is not None:
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"branch={result.accepted_ref}\n")
            handle.write(f"evidence_sha256={result.rebuilt_evidence_sha256}\n")
            handle.write(f"artifact_commit={result.accepted_commit}\n")
            handle.write(f"byte_identical={'true' if result.byte_identical else 'false'}\n")
            handle.write(f"drifted_count={len(result.drifted)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
