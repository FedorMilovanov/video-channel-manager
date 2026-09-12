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
from video_channel_manager.wave_engine.models import (
    MutationClass,
    OperationStatus,
    WaveApplyIntent,
    WaveOperationResult,
    WaveOperationSpec,
    WavePlan,
    WaveResult,
    WaveStatus,
)


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


def _wall_retry_documents(tmp_path: Path) -> tuple[WaveSourceEvidence, WavePlan, WaveApplyIntent]:
    source_path = tmp_path / "source-evidence.json"
    source = _source(source_path, tmp_path)
    plan = WavePlan.build(
        source=source,
        specs=(
            WaveOperationSpec(
                order_key="000001",
                operation_kind=wave_cli.VK_VIDEO_WALL_OPERATION_KIND,
                mutation_class=MutationClass.AMBIGUOUS_MUTATION,
                payload={"test": "wall"},
            ),
        ),
    )
    plan_path = tmp_path / "plan.json"
    write_json_atomic(plan_path, plan.model_dump(mode="json"))
    intent = WaveApplyIntent.build(
        source=source,
        source_path="source-evidence.json",
        source_file_sha256=file_sha256(source_path),
        plan=plan,
        plan_path="plan.json",
        plan_file_sha256=file_sha256(plan_path),
        enable_provider_writes=True,
    )
    return source, plan, intent


def _write_wall_retry_journal(
    journal: Path,
    plan: WavePlan,
    intent: WaveApplyIntent,
    *,
    retry_safe: bool = True,
    error_kind: str = "rejected_before_dispatch",
    error_message: str = "test failure",
) -> WaveResult:
    journal.mkdir(parents=True)
    operation = plan.operations[0]
    operation_result = WaveOperationResult(
        operation_id=operation.operation_id,
        status=OperationStatus.FAILED,
        attempt_count=1,
        retry_safe=retry_safe,
        unknown_requires_reconciliation=False,
        evidence={},
        error_kind=error_kind,
        error_message=error_message,
    )
    result = WaveResult.build(
        plan=plan,
        status=WaveStatus.FAILED,
        operations=(operation_result,),
    )
    write_json_atomic(
        journal / "preflight-summary.json",
        {
            "schema_name": "video-manager.wave-preflight",
            "schema_version": 1,
            "status": "passed",
            "plan_self_digest": plan.self_digest,
            "apply_intent_self_digest": intent.self_digest,
            "source_snapshot_id": plan.source_snapshot_id,
            "operation_set_digest": plan.operation_set_digest,
            "operation_count": 1,
        },
    )
    write_json_atomic(
        journal / f"{operation.sequence:06d}-{operation.operation_id}.json",
        {
            "schema_name": "video-manager.wave-operation-journal",
            "schema_version": 1,
            "stage": "result_committed",
            "plan_self_digest": plan.self_digest,
            "apply_intent_self_digest": intent.self_digest,
            "operation": operation.model_dump(mode="json"),
            "result": operation_result.model_dump(mode="json"),
        },
    )
    write_json_atomic(journal / "result.json", result.model_dump(mode="json"))
    return result


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


def test_video_wall_retry_safe_journal_uses_fresh_sibling_and_preserves_evidence(tmp_path: Path) -> None:
    _source, plan, intent = _wall_retry_documents(tmp_path)
    journal = tmp_path / "journal"
    _write_wall_retry_journal(journal, plan, intent)
    before = {path.name: path.read_bytes() for path in journal.iterdir() if path.is_file()}

    resolved = wave_cli._resolve_video_wall_apply_journal(
        requested_journal_directory=journal,
        repository_root=tmp_path,
        plan=plan,
        intent=intent,
    )

    assert resolved == tmp_path / "journal-retry-001"
    assert not resolved.exists()
    after = {path.name: path.read_bytes() for path in journal.iterdir() if path.is_file()}
    assert after == before


def test_video_wall_retry_safe_journal_advances_only_across_valid_failed_attempts(tmp_path: Path) -> None:
    _source, plan, intent = _wall_retry_documents(tmp_path)
    journal = tmp_path / "journal"
    _write_wall_retry_journal(journal, plan, intent)
    _write_wall_retry_journal(tmp_path / "journal-retry-001", plan, intent)

    resolved = wave_cli._resolve_video_wall_apply_journal(
        requested_journal_directory=journal,
        repository_root=tmp_path,
        plan=plan,
        intent=intent,
    )

    assert resolved == tmp_path / "journal-retry-002"


def test_video_wall_retry_safe_journal_accepts_legacy_wall_get_flood_result(tmp_path: Path) -> None:
    _source, plan, intent = _wall_retry_documents(tmp_path)
    journal = tmp_path / "journal"
    _write_wall_retry_journal(journal, plan, intent)
    _write_wall_retry_journal(
        tmp_path / "journal-retry-001",
        plan,
        intent,
        retry_safe=False,
        error_kind="provider_rejected",
        error_message=wave_cli.VK_VIDEO_WALL_LEGACY_PREFLIGHT_FLOOD_ERROR,
    )

    resolved = wave_cli._resolve_video_wall_apply_journal(
        requested_journal_directory=journal,
        repository_root=tmp_path,
        plan=plan,
        intent=intent,
    )

    assert resolved == tmp_path / "journal-retry-002"


def test_video_wall_retry_safe_journal_rejects_provider_dispatched_failure(tmp_path: Path) -> None:
    _source, plan, intent = _wall_retry_documents(tmp_path)
    journal = tmp_path / "journal"
    _write_wall_retry_journal(
        journal,
        plan,
        intent,
        retry_safe=False,
        error_kind="provider_rejected",
    )

    with pytest.raises(ValueError, match="not explicitly retry-safe before provider dispatch"):
        wave_cli._resolve_video_wall_apply_journal(
            requested_journal_directory=journal,
            repository_root=tmp_path,
            plan=plan,
            intent=intent,
        )


def test_video_wall_retry_safe_journal_rejects_tampered_operation_binding(tmp_path: Path) -> None:
    _source, plan, intent = _wall_retry_documents(tmp_path)
    journal = tmp_path / "journal"
    _write_wall_retry_journal(journal, plan, intent)
    operation = plan.operations[0]
    operation_path = journal / f"{operation.sequence:06d}-{operation.operation_id}.json"
    payload = json.loads(operation_path.read_text(encoding="utf-8"))
    payload["apply_intent_self_digest"] = "0" * 64
    operation_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="incomplete or does not bind"):
        wave_cli._resolve_video_wall_apply_journal(
            requested_journal_directory=journal,
            repository_root=tmp_path,
            plan=plan,
            intent=intent,
        )


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


def test_wave_apply_routes_lord_god_wall_plan_to_lord_god_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    journal = tmp_path / "journal"
    plan = SimpleNamespace(
        operations=(SimpleNamespace(operation_kind=wave_cli.LORD_GOD_WALL_OPERATION_KIND),),
    )
    monkeypatch.setattr(
        wave_cli,
        "_validated_apply_documents",
        lambda **_kwargs: (object(), plan, object()),
    )
    constructed: list[dict[str, object]] = []

    class DummyLordGodAdapter:
        def __init__(self, **kwargs: object) -> None:
            constructed.append(kwargs)

        def close(self) -> None:
            pass

    class WrongAdapter:
        def __init__(self, **_kwargs: object) -> None:
            raise AssertionError("Legendary Poet wall adapter must not be selected")

    class SuccessfulEngine:
        def apply(self, **_kwargs: object) -> object:
            return SimpleNamespace(
                status=wave_cli.WaveStatus.SUCCEEDED,
                operations=(object(),),
            )

    monkeypatch.setattr(wave_cli, "LordGodPostponedWallAdapter", DummyLordGodAdapter)
    monkeypatch.setattr(wave_cli, "VkPostponedVideoWallAdapter", WrongAdapter)
    monkeypatch.setattr(wave_cli, "WaveEngine", SuccessfulEngine)

    wave_cli.apply(
        source_path=tmp_path / "source.json",
        plan_path=tmp_path / "plan.json",
        intent_path=tmp_path / "intent.json",
        repository_root=tmp_path,
        journal_directory=journal,
        vk_account="legendary-poet",
        enable_provider_writes=True,
    )

    assert constructed == [{"account_alias": "legendary-poet"}]


def test_wave_reconcile_routes_lord_god_wall_plan_to_lord_god_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = SimpleNamespace(
        operations=(SimpleNamespace(operation_kind=wave_cli.LORD_GOD_WALL_OPERATION_KIND),),
    )
    request = SimpleNamespace(
        self_digest="request-digest",
        assert_matches=lambda _plan, _result: None,
    )
    result = object()

    def fake_read_model(_path: Path, model: object) -> object:
        if model is wave_cli.WaveReconciliationRequest:
            return request
        if model is wave_cli.WavePlan:
            return plan
        if model is wave_cli.WaveResult:
            return result
        raise AssertionError(f"unexpected model: {model}")

    constructed: list[dict[str, object]] = []

    class DummyLordGodAdapter:
        def __init__(self, **kwargs: object) -> None:
            constructed.append(kwargs)

        def close(self) -> None:
            pass

    class WrongAdapter:
        def __init__(self, **_kwargs: object) -> None:
            raise AssertionError("Legendary Poet wall adapter must not be selected")

    class SuccessfulEngine:
        def reconcile(self, **_kwargs: object) -> object:
            return SimpleNamespace(self_digest="reconciliation-digest")

    monkeypatch.setattr(wave_cli, "_read_model", fake_read_model)
    monkeypatch.setattr(wave_cli, "LordGodPostponedWallAdapter", DummyLordGodAdapter)
    monkeypatch.setattr(wave_cli, "VkPostponedVideoWallAdapter", WrongAdapter)
    monkeypatch.setattr(wave_cli, "WaveEngine", SuccessfulEngine)

    wave_cli.reconcile(
        request_path=tmp_path / "request.json",
        plan_path=tmp_path / "plan.json",
        result_path=tmp_path / "result.json",
        output_path=tmp_path / "reconciliation.json",
        repository_root=tmp_path,
        vk_account="legendary-poet",
    )

    assert constructed == [{"account_alias": "legendary-poet"}]
