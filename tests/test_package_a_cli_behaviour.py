"""`video-manager-package-a` is a declared supported entry point; these tests execute it.

`docs/operations/package-a-release-checklist.md` lists `video-manager-package-a` as the supported
entrypoint and `package-a-wave9-wave10-runbook.md` gives the operator three commands to run. The
only test that touched the module asserted the path string and the `pyproject.toml` line, so the
console application itself had 0% coverage: a broken `run`, `verify` or `schema` would have been
discovered by an operator, not by CI.

Provider access is impossible here by construction: Package A is a read-only reconciliation board.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from video_channel_manager.wave_engine import package_a_cli
from video_channel_manager.wave_engine.canonical import file_sha256
from video_channel_manager.wave_engine.models import EvidenceArtifact, ProjectBinding
from video_channel_manager.wave_engine.package_a import PackageAInputMode, PackageARunRequest
from video_channel_manager.wave_engine.reconciliation import (
    BoundedSourceSnapshot,
    BoundedTargetSnapshot,
    LocalMutationStage,
    LocalReconciliationRecord,
    TargetCoverageKind,
)

NOW = datetime(2026, 10, 22, 6, 0, tzinfo=UTC)
CAPTURED = NOW - timedelta(minutes=5)
PROJECT = ProjectBinding(project_key="lord-god-strength", community_id=60805374, owner_id=-60805374)
RUNNER = CliRunner()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _artifact(root: Path, path: Path) -> EvidenceArtifact:
    return EvidenceArtifact(path=path.relative_to(root).as_posix(), sha256=file_sha256(path))


def _request(root: Path) -> PackageARunRequest:
    source_ids = ("alpha", "beta")
    _write_json(
        root / "inputs" / "source-snapshot.json",
        BoundedSourceSnapshot.build(
            project=PROJECT,
            channel_id="UCeSJsC6go2c9pdJCuUI1BYA",
            captured_at=CAPTURED,
            bounded_source_video_ids=source_ids,
        ).model_dump(mode="json"),
    )
    _write_json(
        root / "inputs" / "target-snapshot.json",
        BoundedTargetSnapshot.build(
            project=PROJECT,
            captured_at=CAPTURED,
            coverage_kind=TargetCoverageKind.COMPLETE_OWNER_CATALOG,
            bounded_source_video_ids=source_ids,
            observations=(),
        ).model_dump(mode="json"),
    )
    records = (
        LocalReconciliationRecord(source_video_id="alpha", stage=LocalMutationStage.NEVER_DISPATCHED),
        LocalReconciliationRecord(source_video_id="beta", stage=LocalMutationStage.INVENTORY_ONLY),
    )
    _write_json(root / "inputs" / "local-records.json", [item.model_dump(mode="json") for item in records])
    return PackageARunRequest.build(
        project=PROJECT,
        source_snapshot=_artifact(root, root / "inputs" / "source-snapshot.json"),
        target_snapshot=_artifact(root, root / "inputs" / "target-snapshot.json"),
        input_mode=PackageAInputMode.CANONICAL_JSON,
        local_records_json=_artifact(root, root / "inputs" / "local-records.json"),
        maximum_snapshot_age_seconds=3600,
    )


def _request_file(tmp_path: Path) -> Path:
    request = _request(tmp_path)
    path = tmp_path / "package-a-request.json"
    _write_json(path, request.model_dump(mode="json"))
    return path


def test_help_lists_the_three_supported_commands() -> None:
    result = RUNNER.invoke(package_a_cli.app, ["--help"])

    assert result.exit_code == 0
    for command in ("run", "verify", "schema"):
        assert command in result.stdout


def test_run_writes_the_board_and_verify_accepts_it(tmp_path: Path) -> None:
    request_path = _request_file(tmp_path)
    output = tmp_path / "output"

    produced = RUNNER.invoke(
        package_a_cli.app,
        ["run", str(request_path), "--input-root", str(tmp_path), "--output-directory", str(output)],
    )

    assert produced.exit_code == 0, produced.stdout
    assert "Provider writes" in produced.stdout
    for name in ("reconciliation-evidence.json", "recovery-decisions.json", "operator-board.json", "run-summary.json"):
        assert (output / name).is_file(), name
    summary = json.loads((output / "run-summary.json").read_text(encoding="utf-8"))
    assert summary["provider_queries"] == 0
    assert summary["provider_writes"] == 0
    assert summary["write_plan_created"] is False

    verified = RUNNER.invoke(package_a_cli.app, ["verify", str(output)])

    assert verified.exit_code == 0, verified.stdout
    assert "Verified Package A run" in verified.stdout


def test_verify_rejects_a_tampered_output_directory(tmp_path: Path) -> None:
    request_path = _request_file(tmp_path)
    output = tmp_path / "output"
    RUNNER.invoke(
        package_a_cli.app,
        ["run", str(request_path), "--input-root", str(tmp_path), "--output-directory", str(output)],
    )
    board = output / "operator-board.json"
    board.write_text(board.read_text(encoding="utf-8").replace("lord-god-strength", "other-project"), encoding="utf-8")

    result = RUNNER.invoke(package_a_cli.app, ["verify", str(output)])

    assert result.exit_code == 2
    assert "verification failed" in result.stdout


def test_run_reports_a_rejected_request_as_exit_two(tmp_path: Path) -> None:
    bad = tmp_path / "package-a-request.json"
    _write_json(bad, {"schema_name": "video-channel-manager.package-a-run-request", "schema_version": 1})

    result = RUNNER.invoke(
        package_a_cli.app,
        ["run", str(bad), "--input-root", str(tmp_path), "--output-directory", str(tmp_path / "output")],
    )

    assert result.exit_code == 2
    assert "Package A rejected" in result.stdout
    assert not (tmp_path / "output" / "run-summary.json").exists()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-22T06:00:00", "must include a timezone"),
        ("not-a-date", "must be a valid ISO-8601 timestamp"),
        (" 2026-10-22T06:00:00+00:00", "must be a normalized ISO-8601 timestamp"),
    ],
)
def test_run_refuses_an_evaluated_at_without_exact_time_identity(tmp_path: Path, value: str, expected: str) -> None:
    request_path = _request_file(tmp_path)

    result = RUNNER.invoke(
        package_a_cli.app,
        [
            "run",
            str(request_path),
            "--input-root",
            str(tmp_path),
            "--output-directory",
            str(tmp_path / "output"),
            "--evaluated-at",
            value,
        ],
    )

    assert result.exit_code == 2
    assert expected in (result.stderr or "")
    assert not (tmp_path / "output" / "run-summary.json").exists()


def test_schema_exports_every_declared_model(tmp_path: Path) -> None:
    result = RUNNER.invoke(package_a_cli.app, ["schema", "--output-directory", str(tmp_path / "schemas")])

    assert result.exit_code == 0, result.stdout
    exported = sorted(path.name for path in (tmp_path / "schemas").glob("*-v1.schema.json"))
    assert len(exported) == len(package_a_cli.PACKAGE_A_SCHEMA_MODELS)
    for name in exported:
        payload = json.loads((tmp_path / "schemas" / name).read_text(encoding="utf-8"))
        assert "properties" in payload


def test_explicit_evaluated_at_is_normalized_to_utc() -> None:
    parsed = package_a_cli._parse_evaluated_at("2026-10-22T09:00:00+03:00")

    assert parsed == datetime(2026, 10, 22, 6, 0, tzinfo=UTC)
    assert parsed.utcoffset() == timedelta(0)


def test_module_entry_point_runs_the_application(monkeypatch: pytest.MonkeyPatch) -> None:
    """`video-manager-package-a` resolves to `run`, so the wrapper itself is exercised."""

    monkeypatch.setattr(sys, "argv", ["video-manager-package-a", "--help"])

    with pytest.raises(SystemExit) as excinfo:
        package_a_cli.run()

    assert excinfo.value.code == 0
