"""Real-git tests for the Milovi video release proof.

The shell block this replaces could not be tested, and its first real execution happened
after merge, on `main`, where it failed for a reason nobody could read. These tests run the
actual git plumbing — a real commit, real blob ids, a real fetch by SHA — so the guard is
exercised before it is trusted.

They also pin the distinction the lane depends on. A second build of the same pinned inputs
is what attributes a difference: if two builds agree, the difference against the accepted
bytes cannot be our pipeline's fault; if they disagree, the pipeline is at fault and the job
fails. An earlier version inferred this from an encoder binary digest recorded in the
evidence, which does not identify the encoder — `libavcodec`/`libx264` carry the behaviour and
apt updates them separately — and it accused the pipeline of nondeterminism that was not there.
"""

from __future__ import annotations

import hashlib
import json
import shutil
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
SECOND_DIR = "artifacts/milovi-telegram/rebuild"


def _git(repo: Path, argv: Sequence[str]) -> str:
    completed = subprocess.run(["git", *argv], cwd=repo, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _blob(repo: Path, path: Path) -> str:
    return _git(repo, ["hash-object", "--no-filters", str(path)])


class Fixture:
    """A repository with an accepted artifact commit, a rebuild of it, and a second build."""

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
        self.second_dir = self.repo / SECOND_DIR
        self.output_dir.mkdir(parents=True)
        for name, payload in payloads.items():
            (self.output_dir / name).write_bytes(payload)
        self.sync_second_build()

        # The accepted bytes are committed: that commit is what publication is bound to.
        _git(self.repo, ["add", "--all"])
        _git(self.repo, ["commit", "--quiet", "-m", "accepted artifacts"])
        self.commit = _git(self.repo, ["rev-parse", "HEAD"])
        self.blobs = {f"{VIDEO_DIR}/{name}": _blob(self.repo, self.output_dir / name) for name in payloads}

        self.reservoir = self.repo / "reservoir.json"
        self.accepted_evidence = self.repo / "accepted-evidence.json"
        self.evidence = self.repo / "evidence.json"
        self.write_metadata()

        _git(self.repo, ["clone", "--quiet", "--bare", str(self.repo), str(self.origin)])
        _git(self.origin, ["config", "uploadpack.allowAnySHA1InWant", "true"])
        _git(self.repo, ["remote", "add", "origin", str(self.origin)])
        _git(self.repo, ["update-ref", "refs/heads/agent/milovi-video-accepted-73c578eff825", self.commit])

    def sync_second_build(self) -> None:
        """Model a deterministic second build: the same bytes, produced independently."""

        if self.second_dir.exists():
            shutil.rmtree(self.second_dir)
        self.second_dir.mkdir(parents=True)
        for name in self.payloads:
            shutil.copyfile(self.output_dir / name, self.second_dir / name)

    def _artifact_rows(self) -> list[dict[str, object]]:
        """Accepted rows are frozen at construction: they describe the accepted bytes."""

        rows = []
        for name, payload in self.payloads.items():
            path = f"{VIDEO_DIR}/{name}"
            rows.append(
                {
                    "media_id": name.split("-")[1].split(".")[0],
                    "artifact_path": path,
                    "sha256": _sha256(payload),
                    "byte_size": len(payload),
                    "git_blob_sha1": self.blobs[path],
                }
            )
        return rows

    def _output_rows(self, directory: Path) -> list[dict[str, object]]:
        """Evidence rows describe the bytes on disk now, as the builder writes them."""

        rows = []
        for name in self.payloads:
            rebuilt = (directory / name).read_bytes()
            rows.append(
                {
                    "media_id": name.split("-")[1].split(".")[0],
                    "output_path": f"{VIDEO_DIR}/{name}",
                    "output_sha256": _sha256(rebuilt),
                    "output_byte_size": len(rebuilt),
                }
            )
        return rows

    def write_metadata(self) -> None:
        artifacts = self._artifact_rows()
        self.reservoir.write_text(
            json.dumps(
                {
                    "artifact_ref": "agent/milovi-video-accepted-73c578eff825",
                    "artifact_commit": self.commit,
                    "evidence_path": self.accepted_evidence.name,
                    "evidence_sha256": "sha256:accepted-identity",
                    "accepted_output_count": len(artifacts),
                    "artifacts": artifacts,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self.accepted_evidence.write_text(
            json.dumps(
                {
                    "evidence_sha256": "sha256:accepted-identity",
                    "toolchain": {"ffmpeg_executable_sha256": "sha256:accepted-encoder"},
                    "outputs": self._output_rows(self.output_dir),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self.evidence.write_text(
            json.dumps(
                {
                    "evidence_sha256": "sha256:rebuilt-identity",
                    "toolchain": {"ffmpeg_executable_sha256": "sha256:rebuilt-encoder"},
                    "outputs": self._output_rows(self.output_dir),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def rebuild(self, name: str, payload: bytes) -> None:
        """Rebuild one artifact: new bytes plus the evidence the builder would write."""

        (self.output_dir / name).write_bytes(payload)
        self.write_metadata()
        self.sync_second_build()

    def verify(self, *, determinism: bool = True) -> object:
        return verify(
            output_dir=self.output_dir,
            reservoir_path=self.reservoir,
            evidence_path=self.evidence,
            cwd=self.repo,
            determinism_dir=self.second_dir if determinism else None,
        )


@pytest.fixture
def fixture(tmp_path: Path) -> Fixture:
    return Fixture(tmp_path, {"milovi-v01.mp4": b"\x00\x00\x00\x18ftypmp42v01", "milovi-v02.mp4": b"v02-bytes"})


def test_rebuild_of_the_accepted_bytes_proves_the_release(fixture: Fixture) -> None:
    result = fixture.verify()

    assert result.artifact_count == 2  # type: ignore[attr-defined]
    assert result.accepted_commit == fixture.commit  # type: ignore[attr-defined]
    assert result.byte_identical is True  # type: ignore[attr-defined]
    assert result.determinism_verified is True  # type: ignore[attr-defined]
    # The rebuilt identity is expected to differ: toolchain metadata is part of it.
    assert result.identity_matches_accepted is False  # type: ignore[attr-defined]
    assert fixture.verify() == result


def test_deterministic_rebuild_differing_from_the_accepted_bytes_is_reported(fixture: Fixture) -> None:
    """An archive update is not artifact drift: the two builds agree, so our pipeline is fine."""

    fixture.rebuild("milovi-v01.mp4", b"re-encoded-by-a-newer-ffmpeg")

    result = fixture.verify()

    assert result.byte_identical is False  # type: ignore[attr-defined]
    assert result.determinism_verified is True  # type: ignore[attr-defined]
    assert [drift.path for drift in result.drifted] == [f"{VIDEO_DIR}/milovi-v01.mp4"]  # type: ignore[attr-defined]


def test_nondeterministic_second_build_fails_the_lane(fixture: Fixture) -> None:
    """Same inputs, same runner, different bytes: that is our defect, and nothing is published."""

    (fixture.second_dir / "milovi-v02.mp4").write_bytes(b"different-on-the-second-build")

    with pytest.raises(ProofFailure) as raised:
        fixture.verify()

    assert "nondeterminism in our own pipeline" in str(raised.value)
    report = " | ".join(raised.value.details)
    assert "milovi-v02.mp4" in report
    assert "first build sha256:" in report and "second build sha256:" in report


def test_second_build_with_a_different_artifact_set_fails(fixture: Fixture) -> None:
    (fixture.second_dir / "milovi-v02.mp4").unlink()

    with pytest.raises(ProofFailure) as raised:
        fixture.verify()

    assert "did not produce milovi-v02.mp4" in " | ".join(raised.value.details)


def test_without_a_second_build_the_difference_is_reported_without_attribution(fixture: Fixture) -> None:
    fixture.rebuild("milovi-v01.mp4", b"re-encoded")

    result = fixture.verify(determinism=False)

    assert result.determinism_verified is False  # type: ignore[attr-defined]
    assert result.byte_identical is False  # type: ignore[attr-defined]
    assert result.as_report()["determinism"] == "not_measured_on_a_second_build"  # type: ignore[attr-defined]


def test_unexpected_rebuilt_artifact_is_refused(fixture: Fixture) -> None:
    (fixture.output_dir / "milovi-v03.mp4").write_bytes(b"unreviewed")

    with pytest.raises(ProofFailure) as raised:
        fixture.verify(determinism=False)

    assert "not part of the accepted artifact set" in " | ".join(raised.value.details)


def test_missing_rebuilt_artifact_is_reported(fixture: Fixture) -> None:
    (fixture.output_dir / "milovi-v02.mp4").unlink()

    with pytest.raises(ProofFailure) as raised:
        fixture.verify(determinism=False)

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
        fixture.verify(determinism=False)

    report = " | ".join(raised.value.details)
    assert "does not contain artifacts/milovi-telegram/video/milovi-v03.mp4" in report
    assert "restore the accepted ref from docs/operations/protected-evidence-refs.json" in report


def test_stale_reservoir_blob_id_is_reported_instead_of_being_trusted(fixture: Fixture) -> None:
    payload = json.loads(fixture.reservoir.read_text(encoding="utf-8"))
    payload["artifacts"][0]["git_blob_sha1"] = "0" * 40
    fixture.reservoir.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(ProofFailure) as raised:
        fixture.verify(determinism=False)

    report = " | ".join(raised.value.details)
    assert "but the reservoir records" in report
    assert "one of them is stale" in report


def test_evidence_that_disagrees_with_its_own_bytes_is_reported(fixture: Fixture) -> None:
    payload = json.loads(fixture.evidence.read_text(encoding="utf-8"))
    payload["outputs"][0]["output_sha256"] = "sha256:" + "0" * 64
    fixture.evidence.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(ProofFailure) as raised:
        fixture.verify(determinism=False)

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
        fixture.verify(determinism=False)

    assert "git fetch" in str(raised.value)


def test_cli_fails_the_lane_on_nondeterminism(
    fixture: Fixture, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(fixture.repo)
    (fixture.second_dir / "milovi-v01.mp4").write_bytes(b"unstable")

    exit_code = main(
        [
            "--output-dir",
            str(fixture.output_dir),
            "--reservoir",
            str(fixture.reservoir),
            "--evidence",
            str(fixture.evidence),
            "--determinism-dir",
            str(fixture.second_dir),
            "--report",
            str(fixture.root / "report.json"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    assert "::error title=Milovi video release proof::" in captured.out
    assert "nondeterminism" in captured.err
    assert not (fixture.root / "report.json").exists()


def test_cli_reports_a_rebuild_difference_and_writes_the_proof_report(
    fixture: Fixture,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fixture.repo)
    fixture.rebuild("milovi-v01.mp4", b"re-encoded")
    output = tmp_path / "github-output.txt"
    output.write_text("", encoding="utf-8")
    report = tmp_path / "report.json"

    exit_code = main(
        [
            "--output-dir",
            str(fixture.output_dir),
            "--reservoir",
            str(fixture.reservoir),
            "--evidence",
            str(fixture.evidence),
            "--determinism-dir",
            str(fixture.second_dir),
            "--github-output",
            str(output),
            "--report",
            str(report),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "::warning title=Milovi rebuild differs from the accepted encoding::" in captured.out
    assert "::warning title=Milovi rebuild drift::" in captured.out
    assert "two builds of the same pinned inputs on this runner agree byte-for-byte" in captured.out

    written = output.read_text(encoding="utf-8")
    assert "branch=agent/milovi-video-accepted-73c578eff825" in written
    assert f"artifact_commit={fixture.commit}" in written
    assert "byte_identical=false" in written
    assert "drifted_count=1" in written
    assert "determinism_verified=true" in written

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["release_integrity"] == "verified"
    assert payload["determinism"] == "verified"
    assert payload["rebuild_conclusion"] == "environment_changed"
    assert payload["provider_access_performed"] is False
    assert payload["repository_write_performed"] is False
    assert payload["byte_identical_count"] == 1
    assert payload["drifted"][0]["path"] == f"{VIDEO_DIR}/milovi-v01.mp4"


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
                "--determinism-dir",
                str(fixture.second_dir),
                "--github-output",
                str(output),
                "--report",
                str(tmp_path / "report.json"),
            ]
        )
        == 0
    )

    written = output.read_text(encoding="utf-8")
    assert "branch=agent/milovi-video-accepted-73c578eff825" in written
    assert f"artifact_commit={fixture.commit}" in written
    assert "byte_identical=true" in written
    assert "runner toolchain metadata is part of the identity" in capsys.readouterr().out


def test_workflow_proves_in_both_jobs_and_can_never_write() -> None:
    """A guard that only runs after merge is not a guard."""

    text = WORKFLOW.read_text(encoding="utf-8")

    assert text.count("python -m video_channel_manager.milovi_telegram_video_proof") == 2
    pull_request_job, main_job = text.split("  build-provider-free-artifacts:", 1)
    assert "milovi_telegram_video_proof" in pull_request_job
    assert "milovi_telegram_video_proof" in main_job

    # Both jobs measure determinism with a second build of the same pinned inputs.
    assert text.count("Rebuild the same pinned inputs a second time to measure determinism") == 2
    assert text.count('--determinism-dir "$DETERMINISM_DIR"') == 2

    assert "git push" not in text
    assert "contents: write" not in text
    # The proof reads the accepted commit from the reservoir, never from the rebuild.
    assert "git fetch --depth=1" not in text
    assert "refs/remotes/accepted" not in text
    # A failed proof still ships its report, otherwise the next difference is unreadable.
    assert text.count("if: always()") == 2
    assert text.count("video-rebuild-proof.json") == 2
