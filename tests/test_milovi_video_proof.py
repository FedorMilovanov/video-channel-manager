"""Real-git tests for the Milovi video release proof.

The shell block this replaces could not be tested, and its first real execution happened
after merge, on `main`, where it failed for a reason nobody could read. These tests run the
actual git plumbing — a real commit, real blob ids, a real fetch by SHA — so the guard is
exercised before it is trusted.

They also pin the distinction the lane depends on: an encoder that changed is reported, a
build that is nondeterministic with the same encoder fails.
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
ACCEPTED_ENCODER = "sha256:" + "a" * 64
ACCEPTED_PROBE = "sha256:" + "b" * 64
OTHER_ENCODER = "sha256:" + "c" * 64
OTHER_PROBE = "sha256:" + "d" * 64


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
        self.accepted_evidence = self.repo / "accepted-evidence.json"
        self.evidence = self.repo / "evidence.json"
        self.rebuilt_encoder = ACCEPTED_ENCODER
        self.rebuilt_probe = ACCEPTED_PROBE
        self.publications: dict[str, dict[str, object]] = {}
        self.write_metadata()

        _git(self.repo, ["clone", "--quiet", "--bare", str(self.repo), str(self.origin)])
        _git(self.origin, ["config", "uploadpack.allowAnySHA1InWant", "true"])
        _git(self.repo, ["remote", "add", "origin", str(self.origin)])
        _git(self.repo, ["update-ref", "refs/heads/agent/milovi-video-accepted-73c578eff825", self.commit])

    def _artifact_rows(self) -> list[dict[str, object]]:
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

    def _output_rows(self) -> list[dict[str, object]]:
        """Evidence rows describe the bytes that are on disk *now*, as the builder writes them."""

        rows = []
        for name in self.payloads:
            rebuilt = (self.output_dir / name).read_bytes()
            rows.append(
                {
                    "media_id": name.split("-")[1].split(".")[0],
                    "output_path": f"{VIDEO_DIR}/{name}",
                    "output_sha256": _sha256(rebuilt),
                    "output_byte_size": len(rebuilt),
                }
            )
        return rows

    @staticmethod
    def _toolchain(encoder: str, probe: str) -> dict[str, object]:
        return {
            "ffmpeg_executable_sha256": encoder,
            "ffprobe_executable_sha256": probe,
            "ffmpeg_version": "ffmpeg version pinned-by-test",
        }

    def write_metadata(self) -> None:
        artifacts = self._artifact_rows()
        outputs = self._output_rows()
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
                    "toolchain": self._toolchain(ACCEPTED_ENCODER, ACCEPTED_PROBE),
                    "outputs": outputs,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self.evidence.write_text(
            json.dumps(
                {
                    "evidence_sha256": "sha256:rebuilt-identity",
                    "toolchain": self._toolchain(self.rebuilt_encoder, self.rebuilt_probe),
                    "outputs": outputs,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def use_a_different_encoder(self) -> None:
        self.rebuilt_encoder = OTHER_ENCODER
        self.rebuilt_probe = OTHER_PROBE
        self.write_metadata()

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


def test_rebuild_of_the_accepted_bytes_proves_the_release(fixture: Fixture) -> None:
    result = fixture.verify()

    assert result.artifact_count == 2  # type: ignore[attr-defined]
    assert result.accepted_commit == fixture.commit  # type: ignore[attr-defined]
    assert result.byte_identical is True  # type: ignore[attr-defined]
    assert result.encoder_changed is False  # type: ignore[attr-defined]
    # The rebuilt identity is expected to differ: toolchain metadata is part of it.
    assert result.identity_matches_accepted is False  # type: ignore[attr-defined]
    assert fixture.verify() == result


def test_same_encoder_with_different_bytes_is_a_nondeterminism_failure(fixture: Fixture) -> None:
    """Same binary, different output: that is our bug, and it must stop the lane."""

    (fixture.output_dir / "milovi-v02.mp4").write_bytes(b"v02-bytes-tampered")
    fixture.write_metadata()

    with pytest.raises(ProofFailure) as raised:
        fixture.verify()

    assert "nondeterminism in our own build" in str(raised.value)
    report = " | ".join(raised.value.details)
    assert "artifacts/milovi-telegram/video/milovi-v02.mp4" in report
    assert "accepted sha256:" in report and "rebuilt sha256:" in report


def test_a_changed_encoder_is_reported_and_the_release_still_passes(fixture: Fixture) -> None:
    """An Ubuntu FFmpeg update is not artifact drift: the release bytes did not move."""

    (fixture.output_dir / "milovi-v01.mp4").write_bytes(b"re-encoded-by-a-newer-ffmpeg")
    fixture.use_a_different_encoder()

    result = fixture.verify()

    assert result.byte_identical is False  # type: ignore[attr-defined]
    assert result.encoder_changed is True  # type: ignore[attr-defined]
    assert [drift.path for drift in result.drifted] == ["artifacts/milovi-telegram/video/milovi-v01.mp4"]  # type: ignore[attr-defined]
    assert result.accepted_toolchain["ffmpeg_executable_sha256"] == ACCEPTED_ENCODER  # type: ignore[attr-defined]
    assert result.rebuilt_toolchain["ffmpeg_executable_sha256"] == OTHER_ENCODER  # type: ignore[attr-defined]


def test_rebuild_evidence_without_encoder_identity_is_not_certifiable(fixture: Fixture) -> None:
    payload = json.loads(fixture.evidence.read_text(encoding="utf-8"))
    payload["toolchain"].pop("ffmpeg_executable_sha256")
    fixture.evidence.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(ProofFailure) as raised:
        fixture.verify()

    assert "ffmpeg_executable_sha256" in str(raised.value)
    assert "not certifiable" in str(raised.value)


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


def test_cli_fails_the_lane_on_nondeterminism(
    fixture: Fixture, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(fixture.repo)
    (fixture.output_dir / "milovi-v01.mp4").write_bytes(b"drifted")
    fixture.write_metadata()

    exit_code = main(
        [
            "--output-dir",
            str(fixture.output_dir),
            "--reservoir",
            str(fixture.reservoir),
            "--evidence",
            str(fixture.evidence),
            "--report",
            str(fixture.root / "report.json"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    assert "::error title=Milovi video release proof::" in captured.out
    assert "nondeterminism" in captured.err
    assert not (fixture.root / "report.json").exists()


def test_cli_reports_an_encoder_change_and_writes_the_proof_report(
    fixture: Fixture,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fixture.repo)
    (fixture.output_dir / "milovi-v01.mp4").write_bytes(b"re-encoded")
    fixture.use_a_different_encoder()
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

    written = output.read_text(encoding="utf-8")
    assert "branch=agent/milovi-video-accepted-73c578eff825" in written
    assert f"artifact_commit={fixture.commit}" in written
    assert "byte_identical=false" in written
    assert "drifted_count=1" in written

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["release_integrity"] == "verified"
    assert payload["rebuild_conclusion"] == "encoder_changed"
    assert payload["provider_access_performed"] is False
    assert payload["repository_write_performed"] is False
    assert payload["byte_identical_count"] == 1
    assert payload["drifted"][0]["path"] == f"{VIDEO_DIR}/milovi-v01.mp4"
    assert payload["toolchain"]["accepted"]["ffmpeg_executable_sha256"] == ACCEPTED_ENCODER
    assert payload["toolchain"]["rebuilt"]["ffmpeg_executable_sha256"] == OTHER_ENCODER


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

    assert "git push" not in text
    assert "contents: write" not in text
    # The proof reads the accepted commit from the reservoir, never from the rebuild.
    assert "git fetch --depth=1" not in text
    assert "refs/remotes/accepted" not in text
    # A failed proof still ships its report, otherwise the next difference is unreadable.
    assert text.count("if: always()") == 2
    assert text.count("video-rebuild-proof.json") == 2
