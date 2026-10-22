"""Real-git tests for the Milovi artifact reproduction proof.

The shell block this replaces could not be tested, and its first real execution happened
after merge, on `main`, where it failed for a reason nobody could read. These tests run the
actual git plumbing — a real commit, real blob ids, a real fetch by SHA — so the guard is
executed before it is trusted.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from video_channel_manager.milovi_telegram_video_proof import (
    LOCAL_PROOF_POINTER,
    ProofFailure,
    fetch_accepted_commit,
    main,
    verify,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "milovi-telegram-video-artifacts.yml"
VIDEO_DIR = "artifacts/milovi-telegram/video"


def _git(repo: Path, argv: Sequence[str]) -> str:
    completed = subprocess.run(["git", *argv], cwd=repo, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _blob(repo: Path, path: Path) -> str:
    return _git(repo, ["hash-object", "--no-filters", str(path)])


class Fixture:
    """A repository that holds an accepted artifact commit and a rebuild of it."""

    def __init__(self, root: Path, payloads: dict[str, bytes]) -> None:
        self.root = root
        self.repo = root / "repo"
        self.origin = root / "origin.git"
        self.payloads = payloads
        self.repo.mkdir(parents=True)
        _git(self.repo, ["init", "--quiet", "--initial-branch=main"])
        _git(self.repo, ["config", "user.name", "proof-fixture"])
        _git(self.repo, ["config", "user.email", "proof-fixture@example.invalid"])

        self.output_dir = self.repo / VIDEO_DIR
        self.output_dir.mkdir(parents=True)
        for name, payload in payloads.items():
            (self.output_dir / name).write_bytes(payload)

        _git(self.repo, ["add", "--all"])
        _git(self.repo, ["commit", "--quiet", "-m", "accepted artifacts"])
        self.commit = _git(self.repo, ["rev-parse", "HEAD"])

        self.blobs = {f"{VIDEO_DIR}/{name}": _blob(self.repo, self.output_dir / name) for name in payloads}
        self.reservoir = self.repo / "reservoir.json"
        self.evidence = self.repo / "evidence.json"
        self.write_metadata()

        _git(self.repo, ["clone", "--quiet", "--bare", str(self.repo), str(self.origin)])
        _git(self.origin, ["config", "uploadpack.allowAnySHA1InWant", "true"])
        _git(self.repo, ["remote", "add", "origin", str(self.origin)])
        _git(self.repo, ["update-ref", "refs/heads/agent/milovi-video-accepted-73c578eff825", self.commit])

    def write_metadata(self) -> None:
        artifacts = []
        outputs = []
        for name, payload in self.payloads.items():
            path = f"{VIDEO_DIR}/{name}"
            media_id = name.split("-")[1].split(".")[0]
            artifacts.append(
                {
                    "media_id": media_id,
                    "artifact_path": path,
                    "sha256": _sha256(payload),
                    "byte_size": len(payload),
                    "git_blob_sha1": self.blobs[path],
                }
            )
            outputs.append(
                {
                    "media_id": media_id,
                    "output_path": path,
                    "output_sha256": _sha256(payload),
                    "output_byte_size": len(payload),
                }
            )
        self.reservoir.write_text(
            json.dumps(
                {
                    "artifact_ref": "agent/milovi-video-accepted-73c578eff825",
                    "artifact_commit": self.commit,
                    "evidence_sha256": "sha256:accepted-identity",
                    "accepted_output_count": len(artifacts),
                    "artifacts": artifacts,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self.evidence.write_text(
            json.dumps(
                {"evidence_sha256": "sha256:rebuilt-identity", "outputs": outputs},
                indent=2,
            ),
            encoding="utf-8",
        )

    def verify(self) -> object:
        return verify(
            output_dir=self.output_dir,
            reservoir_path=self.reservoir,
            evidence_path=self.evidence,
            cwd=self.repo,
        )


@pytest.fixture
def fixture(tmp_path: Path) -> Fixture:
    return Fixture(tmp_path, {"milovi-v01.mp4": b"\x00\x00\x00\x18ftypmp42v01", "milovi-v02.mp4": b"v02-bytes"})


def test_rebuild_of_the_accepted_bytes_passes_and_reports_both_identities(fixture: Fixture) -> None:
    result = fixture.verify()

    assert result.artifact_count == 2  # type: ignore[attr-defined]
    assert result.accepted_commit == fixture.commit  # type: ignore[attr-defined]
    assert result.blob_ids  # type: ignore[attr-defined]
    # The rebuilt identity is expected to differ: toolchain metadata is part of it.
    assert result.identity_matches_accepted is False  # type: ignore[attr-defined]
    assert fixture.verify() == result


def test_one_changed_byte_is_reported_with_both_digests(fixture: Fixture) -> None:
    (fixture.output_dir / "milovi-v02.mp4").write_bytes(b"v02-bytes-tampered")

    with pytest.raises(ProofFailure) as raised:
        fixture.verify()

    report = " | ".join(raised.value.details)
    assert "artifact drift on artifacts/milovi-telegram/video/milovi-v02.mp4" in report
    assert "accepted blob" in report and "rebuilt blob" in report
    assert "refusing to publish" in str(raised.value)


def test_unexpected_rebuilt_artifact_is_refused(fixture: Fixture) -> None:
    (fixture.output_dir / "milovi-v03.mp4").write_bytes(b"unreviewed")

    with pytest.raises(ProofFailure) as raised:
        fixture.verify()

    assert "not part of the accepted artifact set" in " | ".join(raised.value.details)


def test_missing_rebuilt_artifact_is_reported(fixture: Fixture) -> None:
    (fixture.output_dir / "milovi-v02.mp4").unlink()

    with pytest.raises(ProofFailure) as raised:
        fixture.verify()

    assert "rebuilt output is missing" in " | ".join(raised.value.details)


def test_rebuilt_artifact_absent_from_the_accepted_commit_is_reported(fixture: Fixture) -> None:
    extra = fixture.output_dir / "milovi-v03.mp4"
    extra.write_bytes(b"not-in-the-accepted-commit")
    payload = json.loads(fixture.reservoir.read_text(encoding="utf-8"))
    payload["artifacts"].append(
        {
            "media_id": "v03",
            "artifact_path": f"{VIDEO_DIR}/milovi-v03.mp4",
            "sha256": _sha256(b"not-in-the-accepted-commit"),
            "byte_size": len(b"not-in-the-accepted-commit"),
            "git_blob_sha1": _blob(fixture.repo, extra),
        }
    )
    payload["accepted_output_count"] = 3
    fixture.reservoir.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    evidence = json.loads(fixture.evidence.read_text(encoding="utf-8"))
    evidence["outputs"].append(
        {
            "media_id": "v03",
            "output_path": f"{VIDEO_DIR}/milovi-v03.mp4",
            "output_sha256": _sha256(b"not-in-the-accepted-commit"),
            "output_byte_size": len(b"not-in-the-accepted-commit"),
        }
    )
    fixture.evidence.write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    with pytest.raises(ProofFailure) as raised:
        fixture.verify()

    report = " | ".join(raised.value.details)
    assert "does not contain artifacts/milovi-telegram/video/milovi-v03.mp4" in report
    assert "restore the accepted ref from docs/operations/protected-evidence-refs.json" in report


def test_stale_reservoir_blob_id_is_reported_instead_of_being_trusted(fixture: Fixture) -> None:
    payload = json.loads(fixture.reservoir.read_text(encoding="utf-8"))
    payload["artifacts"][0]["git_blob_sha1"] = "0" * 40
    fixture.reservoir.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(ProofFailure) as raised:
        fixture.verify()

    report = " | ".join(raised.value.details)
    assert "but the reservoir records" in report
    assert "one of them is stale" in report


def test_evidence_that_disagrees_with_its_own_bytes_is_reported(fixture: Fixture) -> None:
    payload = json.loads(fixture.evidence.read_text(encoding="utf-8"))
    payload["outputs"][0]["output_sha256"] = "sha256:" + "0" * 64
    fixture.evidence.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(ProofFailure) as raised:
        fixture.verify()

    assert "rebuild evidence disagrees with its own artifact" in " | ".join(raised.value.details)


def test_fetch_uses_the_pinned_commit_and_refuses_a_branch_name(fixture: Fixture) -> None:
    assert fetch_accepted_commit(fixture.commit, cwd=fixture.repo) == LOCAL_PROOF_POINTER

    with pytest.raises(ProofFailure) as raised:
        fetch_accepted_commit("agent/milovi-video-accepted-73c578eff825", cwd=fixture.repo)

    assert "not a full commit id" in str(raised.value)


def test_missing_accepted_commit_fails_loudly(fixture: Fixture) -> None:
    payload = json.loads(fixture.reservoir.read_text(encoding="utf-8"))
    payload["artifact_commit"] = "1" * 40
    fixture.reservoir.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(ProofFailure) as raised:
        fixture.verify()

    assert "git fetch" in str(raised.value)


def test_cli_exits_three_and_annotates_the_failure(
    fixture: Fixture, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(fixture.repo)
    (fixture.output_dir / "milovi-v01.mp4").write_bytes(b"drifted")

    exit_code = main(
        [
            "--output-dir",
            str(fixture.output_dir),
            "--reservoir",
            str(fixture.reservoir),
            "--evidence",
            str(fixture.evidence),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    assert "::error title=Milovi artifact proof::" in captured.out
    assert "artifact drift" in captured.out
    assert "refusing to publish" in captured.err


def test_cli_writes_the_proven_binding_to_the_step_output_file(
    fixture: Fixture,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fixture.repo)
    output = tmp_path / "github-output.txt"
    output.write_text("", encoding="utf-8")

    assert (
        main(
            [
                "--output-dir",
                str(fixture.output_dir),
                "--reservoir",
                str(fixture.reservoir),
                "--evidence",
                str(fixture.evidence),
                "--github-output",
                str(output),
            ]
        )
        == 0
    )

    written = output.read_text(encoding="utf-8")
    assert "branch=agent/milovi-video-accepted-73c578eff825" in written
    assert f"artifact_commit={fixture.commit}" in written
    # The accepted identity is never overwritten by the rebuilt one.
    assert "evidence_sha256=sha256:rebuilt-identity" in written
    assert "runner toolchain metadata is part of the" in capsys.readouterr().out


def test_workflow_proves_in_both_jobs_and_can_never_write() -> None:
    """A guard that only runs after merge is not a guard."""

    text = WORKFLOW.read_text(encoding="utf-8")

    assert text.count("python -m video_channel_manager.milovi_telegram_video_proof") == 2
    pull_request_job, main_job = text.split("  build-provider-free-artifacts:", 1)
    assert "milovi_telegram_video_proof" in pull_request_job
    assert "milovi_telegram_video_proof" in main_job

    assert "git push" not in text
    assert "contents: write" not in text
    # The proof reads the accepted commit from the reservoir, never from the rebuild.
    assert "git fetch --depth=1" not in text
    assert "refs/remotes/accepted" not in text
