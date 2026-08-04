from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from video_channel_manager.wave_engine import (
    EvidenceArtifact,
    MutationClass,
    OperationStatus,
    ProjectBinding,
    WaveApplyIntent,
    WaveEngine,
    WaveFaultStage,
    WaveOperation,
    WaveOperationResult,
    WaveOperationSpec,
    WavePlan,
    WaveReconciliationRequest,
    WaveResult,
    WaveSourceEvidence,
    WaveStatus,
)
from video_channel_manager.wave_engine.canonical import file_sha256, write_json_atomic

_SOURCE_BYTES = b'{"source":1}\n'


class CrashAt(RuntimeError):
    pass


class RecordingAdapter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def execute(self, operation: WaveOperation) -> dict[str, object]:
        self.calls.append(operation.operation_id)
        return {"remote_identity": f"remote-{operation.sequence}"}


class RecordingReconciliationAdapter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def reconcile(self, operation: WaveOperation) -> dict[str, object]:
        self.calls.append(operation.operation_id)
        return {"remote_identity": f"reconciled-{operation.sequence}"}


def _clear_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CI", "GITHUB_ACTIONS", "TF_BUILD"):
        monkeypatch.delenv(name, raising=False)


def _source() -> WaveSourceEvidence:
    return WaveSourceEvidence.build(
        project=ProjectBinding(
            project_key="legendary-poet",
            community_id=235216998,
            owner_id=-235216998,
        ),
        policy_version="wave-policy-v1",
        artifacts=(
            EvidenceArtifact(
                path="data/source.json",
                sha256=hashlib.sha256(_SOURCE_BYTES).hexdigest(),
            ),
        ),
    )


def _plan() -> WavePlan:
    return WavePlan.build(
        source=_source(),
        specs=(
            WaveOperationSpec(
                order_key="000000",
                operation_kind="ambiguous-write",
                mutation_class=MutationClass.AMBIGUOUS_MUTATION,
                payload={"value": 1},
            ),
        ),
    )


def _prepare(tmp_path: Path) -> tuple[WaveSourceEvidence, WavePlan, WaveApplyIntent, Path, Path]:
    source = _source()
    plan = _plan()
    artifact = tmp_path / "data" / "source.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(_SOURCE_BYTES)
    source_path = tmp_path / "source-evidence.json"
    plan_path = tmp_path / "plan.json"
    write_json_atomic(source_path, source.model_dump(mode="json"))
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
    return source, plan, intent, source_path, plan_path


def _unknown_result(plan: WavePlan) -> WaveResult:
    operation = plan.operations[0]
    return WaveResult.build(
        plan=plan,
        status=WaveStatus.UNKNOWN_REQUIRES_RECONCILIATION,
        operations=(
            WaveOperationResult(
                operation_id=operation.operation_id,
                status=OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION,
                attempt_count=1,
                retry_safe=False,
                unknown_requires_reconciliation=True,
                evidence={},
                error_kind="unknown_provider_outcome",
                error_message="response lost after dispatch",
            ),
        ),
    )


def _journal_stage(journal: Path) -> str | None:
    operation_files = sorted(journal.glob("000000-*.json"))
    if not operation_files:
        return None
    payload = json.loads(operation_files[0].read_text(encoding="utf-8"))
    return str(payload["stage"])


@pytest.mark.parametrize(
    ("fault_stage", "expected_calls", "expected_journal_stage", "expected_final_result"),
    [
        (WaveFaultStage.BEFORE_PREFLIGHT_COMMIT, 0, None, False),
        (WaveFaultStage.AFTER_PREFLIGHT_COMMIT, 0, None, False),
        (WaveFaultStage.BEFORE_OPERATION_INTENT_COMMIT, 0, None, False),
        (WaveFaultStage.AFTER_OPERATION_INTENT_COMMIT, 0, "intent_committed", False),
        (WaveFaultStage.AFTER_OPERATION_DISPATCH_STARTED_COMMIT, 0, "dispatch_started", False),
        (
            WaveFaultStage.AFTER_OPERATION_OUTCOME_BEFORE_RESULT_COMMIT,
            1,
            "dispatch_started",
            False,
        ),
        (WaveFaultStage.AFTER_OPERATION_RESULT_COMMIT, 1, "result_committed", False),
        (WaveFaultStage.BEFORE_FINAL_RESULT_COMMIT, 1, "result_committed", False),
        (WaveFaultStage.AFTER_FINAL_RESULT_COMMIT, 1, "result_committed", True),
    ],
)
def test_apply_fault_boundaries_preserve_durable_replay_barrier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault_stage: WaveFaultStage,
    expected_calls: int,
    expected_journal_stage: str | None,
    expected_final_result: bool,
) -> None:
    _clear_ci(monkeypatch)
    source, plan, intent, source_path, plan_path = _prepare(tmp_path)
    journal = tmp_path / "journal"
    adapter = RecordingAdapter()

    def crash(stage: WaveFaultStage, operation: WaveOperation | None) -> None:
        del operation
        if stage is fault_stage:
            raise CrashAt(stage.value)

    with pytest.raises(CrashAt, match=fault_stage.value):
        WaveEngine().apply(
            source=source,
            plan=plan,
            intent=intent,
            adapter=adapter,
            repository_root=tmp_path,
            source_file_path=source_path,
            plan_file_path=plan_path,
            journal_directory=journal,
            provider_writes_enabled=True,
            fault_hook=crash,
        )

    assert len(adapter.calls) == expected_calls
    assert journal.exists() is (fault_stage is not WaveFaultStage.BEFORE_PREFLIGHT_COMMIT)
    if journal.exists():
        assert (journal / "preflight-summary.json").is_file()
        assert _journal_stage(journal) == expected_journal_stage
        assert (journal / "result.json").exists() is expected_final_result

        with pytest.raises(ValueError, match="automatic replay is prohibited"):
            WaveEngine().apply(
                source=source,
                plan=plan,
                intent=intent,
                adapter=adapter,
                repository_root=tmp_path,
                source_file_path=source_path,
                plan_file_path=plan_path,
                journal_directory=journal,
                provider_writes_enabled=True,
            )
        assert len(adapter.calls) == expected_calls


@pytest.mark.parametrize(
    ("fault_stage", "expected_calls", "expected_journal_stage", "expected_output"),
    [
        (WaveFaultStage.BEFORE_RECONCILIATION_INTENT_COMMIT, 0, None, False),
        (WaveFaultStage.AFTER_RECONCILIATION_INTENT_COMMIT, 0, "intent_committed", False),
        (
            WaveFaultStage.AFTER_RECONCILIATION_DISPATCH_STARTED_COMMIT,
            0,
            "dispatch_started",
            False,
        ),
        (
            WaveFaultStage.AFTER_RECONCILIATION_OUTCOME_BEFORE_RESULT_COMMIT,
            1,
            "dispatch_started",
            False,
        ),
        (
            WaveFaultStage.AFTER_RECONCILIATION_OPERATION_RESULT_COMMIT,
            1,
            "operation_result_committed",
            False,
        ),
        (
            WaveFaultStage.BEFORE_RECONCILIATION_RESULT_COMMIT,
            1,
            "operation_result_committed",
            False,
        ),
        (WaveFaultStage.AFTER_RECONCILIATION_RESULT_COMMIT, 1, "completed", True),
    ],
)
def test_reconciliation_fault_boundaries_preserve_durable_replay_barrier(
    tmp_path: Path,
    fault_stage: WaveFaultStage,
    expected_calls: int,
    expected_journal_stage: str | None,
    expected_output: bool,
) -> None:
    plan = _plan()
    result = _unknown_result(plan)
    request = WaveReconciliationRequest.build(plan=plan, result=result)
    output = tmp_path / "reconciliation-result.json"
    journal = tmp_path / ".reconciliation-result.json.journal.json"
    adapter = RecordingReconciliationAdapter()

    def crash(stage: WaveFaultStage, operation: WaveOperation | None) -> None:
        del operation
        if stage is fault_stage:
            raise CrashAt(stage.value)

    with pytest.raises(CrashAt, match=fault_stage.value):
        WaveEngine().reconcile(
            plan=plan,
            result=result,
            request=request,
            adapter=adapter,
            output_path=output,
            fault_hook=crash,
        )

    assert len(adapter.calls) == expected_calls
    assert journal.exists() is (fault_stage is not WaveFaultStage.BEFORE_RECONCILIATION_INTENT_COMMIT)
    assert output.exists() is expected_output
    if journal.exists():
        journal_payload = json.loads(journal.read_text(encoding="utf-8"))
        assert journal_payload["stage"] == expected_journal_stage
        with pytest.raises(ValueError, match="(automatic replay|overwrite) is prohibited"):
            WaveEngine().reconcile(
                plan=plan,
                result=result,
                request=request,
                adapter=adapter,
                output_path=output,
            )
        assert len(adapter.calls) == expected_calls


def test_fault_hook_is_explicit_and_success_path_emits_ordered_stages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_ci(monkeypatch)
    source, plan, intent, source_path, plan_path = _prepare(tmp_path)
    observed: list[tuple[WaveFaultStage, str | None]] = []

    def observe(stage: WaveFaultStage, operation: WaveOperation | None) -> None:
        observed.append((stage, None if operation is None else operation.operation_id))

    result = WaveEngine().apply(
        source=source,
        plan=plan,
        intent=intent,
        adapter=RecordingAdapter(),
        repository_root=tmp_path,
        source_file_path=source_path,
        plan_file_path=plan_path,
        journal_directory=tmp_path / "journal",
        provider_writes_enabled=True,
        fault_hook=observe,
    )

    assert result.status.value == "succeeded"
    assert [stage for stage, _ in observed] == [
        WaveFaultStage.BEFORE_PREFLIGHT_COMMIT,
        WaveFaultStage.AFTER_PREFLIGHT_COMMIT,
        WaveFaultStage.BEFORE_OPERATION_INTENT_COMMIT,
        WaveFaultStage.AFTER_OPERATION_INTENT_COMMIT,
        WaveFaultStage.AFTER_OPERATION_DISPATCH_STARTED_COMMIT,
        WaveFaultStage.AFTER_OPERATION_OUTCOME_BEFORE_RESULT_COMMIT,
        WaveFaultStage.AFTER_OPERATION_RESULT_COMMIT,
        WaveFaultStage.BEFORE_FINAL_RESULT_COMMIT,
        WaveFaultStage.AFTER_FINAL_RESULT_COMMIT,
    ]
