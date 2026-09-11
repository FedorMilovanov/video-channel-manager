from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer
from typer.testing import CliRunner

import video_channel_manager.wave_engine.cli as wave_cli
from video_channel_manager.cli.app import app
from video_channel_manager.wave_engine import EvidenceArtifact, ProjectBinding, WaveSourceEvidence
from video_channel_manager.wave_engine.canonical import file_sha256, write_json_atomic


runner = CliRunner()


def _source(path: Path, repository_root: Path) -> WaveSourceEvidence:
    artifact = repository_root / "source.json"
    artifact.write_text('{"source":true}\n', encoding="utf-8")
    source = WaveSourceEvidence.build(
        project=ProjectBinding(project_key="legendary-poet", community_id=235216998, owner_id=-235216998),
        policy_version="policy-v1",
        artifacts=(EvidenceArtifact(path="source.json", sha256=file_sha256(artifact)),),
    )
    write_json_atomic(path, source.model_dump(mode="json"))
    return source


def test_wave_cli_build_validate_preview_and_source_verify(tmp_path: Path) -> None:
    source_path = tmp_path / "source-evidence.json"
    _source(source_path, tmp_path)
    operations_path = tmp_path / "operations.json"
    operations_path.write_text(
        json.dumps(
            [
                {
                    "order_key": "000001",
                    "operation_kind": "inventory.read",
                    "mutation_class": "safe_read",
                    "payload": {"scope": "videos"},
                }
            ]
        ),
        encoding="utf-8",
    )
    plan_path = tmp_path / "plan.json"

    verify = runner.invoke(
        app,
        ["wave", "source", "verify", str(source_path), "--repository-root", str(tmp_path)],
    )
    build = runner.invoke(
        app,
        [
            "wave",
            "plan",
            "build",
            "--source",
            str(source_path),
            "--operations",
            str(operations_path),
            "--output",
            str(plan_path),
            "--repository-root",
            str(tmp_path),
        ],
    )
    validate = runner.invoke(app, ["wave", "plan", "validate", str(plan_path)])
    preview = runner.invoke(app, ["wave", "preview", str(plan_path)])

    assert verify.exit_code == 0, verify.output
    assert build.exit_code == 0, build.output
    assert validate.exit_code == 0, validate.output
    assert preview.exit_code == 0, preview.output
    assert "legendary-poet" in preview.output
    assert "Operations" in preview.output


def test_wave_cli_rejects_tampered_source_artifact_and_plan(tmp_path: Path) -> None:
    source_path = tmp_path / "source-evidence.json"
    _source(source_path, tmp_path)
    (tmp_path / "source.json").write_text('{"tampered":true}\n', encoding="utf-8")
    verify = runner.invoke(
        app,
        ["wave", "source", "verify", str(source_path), "--repository-root", str(tmp_path)],
    )
    assert verify.exit_code != 0
    assert "SHA-256 mismatch" in verify.output

    _source(source_path, tmp_path)
    operations_path = tmp_path / "operations.json"
    operations_path.write_text(
        '[{"order_key":"000001","operation_kind":"inventory.read","mutation_class":"safe_read","payload":{}}]',
        encoding="utf-8",
    )
    plan_path = tmp_path / "plan.json"
    build = runner.invoke(
        app,
        [
            "wave",
            "plan",
            "build",
            "--source",
            str(source_path),
            "--operations",
            str(operations_path),
            "--output",
            str(plan_path),
            "--repository-root",
            str(tmp_path),
        ],
    )
    assert build.exit_code == 0, build.output
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    payload["source_snapshot_id"] = "0" * 64
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    result = runner.invoke(app, ["wave", "plan", "validate", str(plan_path)])
    assert result.exit_code != 0
    assert "Invalid WavePlan" in result.output


def test_wave_apply_exception_after_new_journal_is_unknown_not_retry_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    journal = tmp_path / "journal"
    plan = SimpleNamespace(
        operations=(SimpleNamespace(operation_kind=wave_cli.VK_VIDEO_OPERATION_KIND),),
    )
    monkeypatch.setattr(
        wave_cli,
        "_validated_apply_documents",
        lambda **_kwargs: (object(), plan, object()),
    )

    class DummyAdapter:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def close(self) -> None:
            pass

    class FailingEngine:
        def apply(self, **kwargs: object) -> None:
            journal_directory = kwargs["journal_directory"]
            assert isinstance(journal_directory, Path)
            journal_directory.mkdir()
            raise OSError("result commit failed")

    monkeypatch.setattr(wave_cli, "VkNativeVideoUploadAdapter", DummyAdapter)
    monkeypatch.setattr(wave_cli, "WaveEngine", FailingEngine)

    with pytest.raises(typer.Exit) as exc_info:
        wave_cli.apply(
            source_path=tmp_path / "source.json",
            plan_path=tmp_path / "plan.json",
            intent_path=tmp_path / "intent.json",
            repository_root=tmp_path,
            journal_directory=journal,
            vk_account="legendary-poet",
            enable_provider_writes=True,
        )

    assert exc_info.value.exit_code == 4


def test_wave_apply_rejection_before_journal_remains_known_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    journal = tmp_path / "journal"
    plan = SimpleNamespace(
        operations=(SimpleNamespace(operation_kind=wave_cli.VK_VIDEO_OPERATION_KIND),),
    )
    monkeypatch.setattr(
        wave_cli,
        "_validated_apply_documents",
        lambda **_kwargs: (object(), plan, object()),
    )

    class DummyAdapter:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def close(self) -> None:
            pass

    class RejectingEngine:
        def apply(self, **_kwargs: object) -> None:
            raise ValueError("preflight rejected")

    monkeypatch.setattr(wave_cli, "VkNativeVideoUploadAdapter", DummyAdapter)
    monkeypatch.setattr(wave_cli, "WaveEngine", RejectingEngine)

    with pytest.raises(typer.Exit) as exc_info:
        wave_cli.apply(
            source_path=tmp_path / "source.json",
            plan_path=tmp_path / "plan.json",
            intent_path=tmp_path / "intent.json",
            repository_root=tmp_path,
            journal_directory=journal,
            vk_account="legendary-poet",
            enable_provider_writes=True,
        )

    assert exc_info.value.exit_code == 3
    assert not journal.exists()

