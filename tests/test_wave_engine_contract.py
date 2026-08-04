from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from video_channel_manager.wave_engine import (
    EvidenceArtifact,
    MutationClass,
    OperationStatus,
    ProjectBinding,
    UnknownProviderOutcomeError,
    WaveApplyIntent,
    WaveEngine,
    WaveOperation,
    WaveOperationResult,
    WaveOperationSpec,
    WavePlan,
    WaveReconciliationRequest,
    WaveResult,
    WaveSourceEvidence,
    WaveStatus,
)
from video_channel_manager.wave_engine.canonical import file_sha256, object_sha256, write_json_atomic


def _project() -> ProjectBinding:
    return ProjectBinding(project_key="legendary-poet", community_id=235216998, owner_id=-235216998)


_SOURCE_BYTES = b'{"source":1}\n'


def _source() -> WaveSourceEvidence:
    return WaveSourceEvidence.build(
        project=_project(),
        policy_version="wave-policy-v1",
        artifacts=(EvidenceArtifact(path="data/source.json", sha256=hashlib.sha256(_SOURCE_BYTES).hexdigest()),),
    )


def _plan(*classes: MutationClass) -> WavePlan:
    source = _source()
    specs = tuple(
        WaveOperationSpec(
            order_key=f"{index:06d}",
            operation_kind=f"operation-{index}",
            mutation_class=kind,
            payload={"index": index},
        )
        for index, kind in enumerate(classes)
    )
    return WavePlan.build(source=source, specs=specs)


def _write_plan(path: Path, plan: WavePlan) -> None:
    write_json_atomic(path, plan.model_dump(mode="json"))


def _intent(path: Path, plan: WavePlan, *, enabled: bool) -> WaveApplyIntent:
    root = path.parent
    artifact = root / "data" / "source.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(_SOURCE_BYTES)
    source = _source()
    source_path = root / "source-evidence.json"
    write_json_atomic(source_path, source.model_dump(mode="json"))
    _write_plan(path, plan)
    return WaveApplyIntent.build(
        source=source,
        source_path="source-evidence.json",
        source_file_sha256=file_sha256(source_path),
        plan=plan,
        plan_path="plan.json",
        plan_file_sha256=file_sha256(path),
        enable_provider_writes=enabled,
    )


def _clear_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CI", "GITHUB_ACTIONS", "TF_BUILD"):
        monkeypatch.delenv(name, raising=False)


def test_source_and_plan_builds_are_deterministic_self_digested_and_ordered() -> None:
    source = _source()
    specs = (
        WaveOperationSpec(
            order_key="b",
            operation_kind="second",
            mutation_class=MutationClass.AMBIGUOUS_MUTATION,
            payload={"value": 2},
        ),
        WaveOperationSpec(
            order_key="a",
            operation_kind="first",
            mutation_class=MutationClass.SAFE_READ,
            payload={"value": 1},
        ),
    )
    first = WavePlan.build(source=source, specs=specs)
    second = WavePlan.build(source=source, specs=tuple(reversed(specs)))

    assert first == second
    assert source.source_snapshot_id == source.compute_source_snapshot_id()
    assert first.self_digest == second.self_digest
    assert first.operation_set_digest == second.operation_set_digest
    assert [operation.order_key for operation in first.operations] == ["a", "b"]
    assert [operation.sequence for operation in first.operations] == [0, 1]
    assert all(operation.operation_id == operation.compute_operation_id() for operation in first.operations)


def test_duplicate_operation_order_key_is_rejected() -> None:
    spec = WaveOperationSpec(
        order_key="same",
        operation_kind="read",
        mutation_class=MutationClass.SAFE_READ,
        payload={},
    )
    with pytest.raises(ValueError, match="order_key"):
        WavePlan.build(source=_source(), specs=(spec, spec))


def test_source_artifacts_are_exactly_verified_and_tamper_fails(tmp_path: Path) -> None:
    artifact = tmp_path / "data" / "source.json"
    artifact.parent.mkdir()
    artifact.write_text('{"source":1}\n', encoding="utf-8")
    source = WaveSourceEvidence.build(
        project=_project(),
        policy_version="wave-policy-v1",
        artifacts=(EvidenceArtifact(path="data/source.json", sha256=file_sha256(artifact)),),
    )

    source.verify_artifacts(tmp_path)
    artifact.write_text('{"source":2}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        source.verify_artifacts(tmp_path)


def test_project_binding_rejects_cross_project_ids_and_numeric_strings() -> None:
    with pytest.raises(ValidationError, match="identity is inconsistent"):
        ProjectBinding(project_key="legendary-poet", community_id=60805374, owner_id=-60805374)

    with pytest.raises(ValidationError):
        ProjectBinding.model_validate(
            {"project_key": "legendary-poet", "community_id": "235216998", "owner_id": -235216998},
            strict=True,
        )


def test_plan_rejects_tamper_reordering_and_missing_coverage() -> None:
    plan = _plan(MutationClass.SAFE_READ, MutationClass.SAFE_READ)
    payload = plan.model_dump(mode="json")
    payload["operations"][0]["payload"]["index"] = 9
    with pytest.raises(ValidationError, match="operation_id mismatch"):
        WavePlan.model_validate_json(json.dumps(payload))

    payload = plan.model_dump(mode="json")
    payload["operations"] = list(reversed(payload["operations"]))
    with pytest.raises(ValidationError, match="deterministically ordered"):
        WavePlan.model_validate_json(json.dumps(payload))


def test_atomic_json_replaces_existing_file_without_bom(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "result.json"
    write_json_atomic(path, {"status": "first"})
    write_json_atomic(path, {"status": "second", "text": "поэт"})

    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert json.loads(raw.decode("utf-8")) == {"status": "second", "text": "поэт"}
    assert list(path.parent.glob(f".{path.name}.*.tmp")) == []


class _RecordingAdapter:
    def __init__(self, *, fail_unknown_at: int | None = None) -> None:
        self.calls: list[str] = []
        self.fail_unknown_at = fail_unknown_at

    def execute(self, operation: WaveOperation) -> dict[str, object]:
        self.calls.append(operation.operation_id)
        if self.fail_unknown_at == operation.sequence:
            raise UnknownProviderOutcomeError("response lost after dispatch")
        return {"remote_identity": f"remote-{operation.sequence}"}


def test_engine_executes_each_operation_once_and_commits_structured_evidence(tmp_path: Path) -> None:
    plan = _plan(MutationClass.SAFE_READ, MutationClass.SAFE_READ)
    plan_path = tmp_path / "plan.json"
    intent = _intent(plan_path, plan, enabled=False)
    adapter = _RecordingAdapter()

    result = WaveEngine().apply(
        plan=plan,
        intent=intent,
        adapter=adapter,
        source=_source(),
        repository_root=tmp_path,
        source_file_path=tmp_path / "source-evidence.json",
        plan_file_path=plan_path,
        journal_directory=tmp_path / "journal",
        provider_writes_enabled=False,
    )

    assert result.status is WaveStatus.SUCCEEDED
    assert len(adapter.calls) == 2
    assert [item.status for item in result.operations] == [OperationStatus.SUCCEEDED, OperationStatus.SUCCEEDED]
    assert (tmp_path / "journal" / "preflight-summary.json").is_file()
    assert (tmp_path / "journal" / "result.json").is_file()
    assert len(list((tmp_path / "journal").glob("00000*-*.json"))) == 2


def test_engine_rejects_plan_path_mismatch_digest_mismatch_and_nonempty_journal(tmp_path: Path) -> None:
    plan = _plan(MutationClass.SAFE_READ)
    plan_path = tmp_path / "plan.json"
    intent = _intent(plan_path, plan, enabled=False)
    other = tmp_path / "other.json"
    _write_plan(other, plan)

    with pytest.raises(ValueError, match="supplied plan path"):
        WaveEngine().apply(
            plan=plan,
            intent=intent,
            adapter=_RecordingAdapter(),
            source=_source(),
            repository_root=tmp_path,
            source_file_path=tmp_path / "source-evidence.json",
            plan_file_path=other,
            journal_directory=tmp_path / "journal-a",
            provider_writes_enabled=False,
        )

    plan_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        WaveEngine().apply(
            plan=plan,
            intent=intent,
            adapter=_RecordingAdapter(),
            source=_source(),
            repository_root=tmp_path,
            source_file_path=tmp_path / "source-evidence.json",
            plan_file_path=plan_path,
            journal_directory=tmp_path / "journal-b",
            provider_writes_enabled=False,
        )

    _write_plan(plan_path, plan)
    journal = tmp_path / "journal-c"
    journal.mkdir()
    (journal / "stale.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="already exists"):
        WaveEngine().apply(
            plan=plan,
            intent=intent,
            adapter=_RecordingAdapter(),
            source=_source(),
            repository_root=tmp_path,
            source_file_path=tmp_path / "source-evidence.json",
            plan_file_path=plan_path,
            journal_directory=journal,
            provider_writes_enabled=False,
        )


def test_ambiguous_failure_is_unknown_non_retryable_and_never_replayed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_ci(monkeypatch)
    plan = _plan(
        MutationClass.SAFE_READ,
        MutationClass.AMBIGUOUS_MUTATION,
        MutationClass.AMBIGUOUS_MUTATION,
    )
    plan_path = tmp_path / "plan.json"
    intent = _intent(plan_path, plan, enabled=True)
    adapter = _RecordingAdapter(fail_unknown_at=1)

    result = WaveEngine().apply(
        plan=plan,
        intent=intent,
        adapter=adapter,
        source=_source(),
        repository_root=tmp_path,
        source_file_path=tmp_path / "source-evidence.json",
        plan_file_path=plan_path,
        journal_directory=tmp_path / "journal",
        provider_writes_enabled=True,
    )

    assert result.status is WaveStatus.UNKNOWN_REQUIRES_RECONCILIATION
    assert adapter.calls == [plan.operations[0].operation_id, plan.operations[1].operation_id]
    unknown = result.operations[1]
    assert unknown.status is OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION
    assert unknown.attempt_count == 1
    assert unknown.retry_safe is False
    assert unknown.unknown_requires_reconciliation is True
    assert result.operations[2].status is OperationStatus.NOT_ATTEMPTED
    assert result.operations[2].attempt_count == 0


def test_ambiguous_mutation_requires_two_confirmations_and_is_blocked_in_ci(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(MutationClass.AMBIGUOUS_MUTATION)
    plan_path = tmp_path / "plan.json"
    intent = _intent(plan_path, plan, enabled=True)
    _clear_ci(monkeypatch)

    with pytest.raises(ValueError, match="two explicit"):
        WaveEngine().apply(
            plan=plan,
            intent=intent,
            adapter=_RecordingAdapter(),
            source=_source(),
            repository_root=tmp_path,
            source_file_path=tmp_path / "source-evidence.json",
            plan_file_path=plan_path,
            journal_directory=tmp_path / "journal-a",
            provider_writes_enabled=False,
        )

    monkeypatch.setenv("CI", "true")
    with pytest.raises(ValueError, match="prohibited in CI"):
        WaveEngine().apply(
            plan=plan,
            intent=intent,
            adapter=_RecordingAdapter(),
            source=_source(),
            repository_root=tmp_path,
            source_file_path=tmp_path / "source-evidence.json",
            plan_file_path=plan_path,
            journal_directory=tmp_path / "journal-b",
            provider_writes_enabled=True,
        )


def test_result_requires_exact_status_and_mutation_semantics() -> None:
    safe_plan = _plan(MutationClass.SAFE_READ)
    unknown = WaveOperationResult(
        operation_id=safe_plan.operations[0].operation_id,
        status=OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION,
        attempt_count=1,
        retry_safe=False,
        unknown_requires_reconciliation=True,
        evidence={},
        error_kind="unknown_provider_outcome",
    )
    with pytest.raises(ValueError, match="safe-read"):
        WaveResult.build(
            plan=safe_plan,
            status=WaveStatus.UNKNOWN_REQUIRES_RECONCILIATION,
            operations=(unknown,),
        )

    succeeded = WaveOperationResult(
        operation_id=safe_plan.operations[0].operation_id,
        status=OperationStatus.SUCCEEDED,
        attempt_count=1,
        retry_safe=False,
        unknown_requires_reconciliation=False,
        evidence={},
    )
    with pytest.raises(ValidationError, match="failed result"):
        payload = {
            "schema_name": "video-manager.wave-result",
            "schema_version": 1,
            "plan_self_digest": safe_plan.self_digest,
            "project": safe_plan.project.model_dump(mode="json"),
            "source_snapshot_id": safe_plan.source_snapshot_id,
            "operation_set_digest": safe_plan.operation_set_digest,
            "status": "failed",
            "operations": [succeeded.model_dump(mode="json")],
        }
        payload["self_digest"] = object_sha256(payload)
        WaveResult.model_validate_json(json.dumps(payload))


def test_result_requires_exact_ordered_plan_coverage() -> None:
    plan = _plan(MutationClass.SAFE_READ, MutationClass.SAFE_READ)
    operations = tuple(
        WaveOperationResult(
            operation_id=operation.operation_id,
            status=OperationStatus.SUCCEEDED,
            attempt_count=1,
            retry_safe=False,
            unknown_requires_reconciliation=False,
            evidence={},
        )
        for operation in plan.operations
    )
    result = WaveResult.build(plan=plan, status=WaveStatus.SUCCEEDED, operations=operations)
    result.assert_matches(plan)

    payload = result.model_dump(mode="json")
    payload["operations"] = list(reversed(payload["operations"]))
    payload_without_digest = dict(payload)
    payload_without_digest.pop("self_digest")
    payload["self_digest"] = object_sha256(payload_without_digest)
    tampered = WaveResult.model_validate_json(json.dumps(payload))
    with pytest.raises(ValueError, match="exact ordered"):
        tampered.assert_matches(plan)


def _unknown_result(plan: WavePlan) -> WaveResult:
    unknown = WaveOperationResult(
        operation_id=plan.operations[0].operation_id,
        status=OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION,
        attempt_count=1,
        retry_safe=False,
        unknown_requires_reconciliation=True,
        evidence={},
        error_kind="unknown_provider_outcome",
    )
    return WaveResult.build(
        plan=plan,
        status=WaveStatus.UNKNOWN_REQUIRES_RECONCILIATION,
        operations=(unknown,),
    )


class _ReconciliationAdapter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def reconcile(self, operation: WaveOperation) -> dict[str, object]:
        self.calls.append(operation.operation_id)
        return {"remote_identity": f"remote-{operation.sequence}", "matched_expected_delta": True}


def test_reconciliation_request_and_result_bind_exact_unknown_operations(tmp_path: Path) -> None:
    plan = _plan(MutationClass.AMBIGUOUS_MUTATION)
    result = _unknown_result(plan)
    request = WaveReconciliationRequest.build(plan=plan, result=result)
    adapter = _ReconciliationAdapter()
    output = tmp_path / "reconciliation-result.json"

    reconciliation = WaveEngine().reconcile(
        plan=plan,
        result=result,
        request=request,
        adapter=adapter,
        output_path=output,
    )

    assert adapter.calls == [plan.operations[0].operation_id]
    assert reconciliation.operations[0].status is OperationStatus.RECONCILED
    assert reconciliation.operations[0].evidence["matched_expected_delta"] is True
    assert output.is_file()
    reconciliation.assert_matches(request)

    with pytest.raises(ValueError, match="already exists"):
        WaveEngine().reconcile(
            plan=plan,
            result=result,
            request=request,
            adapter=adapter,
            output_path=output,
        )


def test_reconciliation_request_rejects_non_digest_operation_ids() -> None:
    plan = _plan(MutationClass.AMBIGUOUS_MUTATION)
    result = _unknown_result(plan)
    request = WaveReconciliationRequest.build(plan=plan, result=result)
    payload = request.model_dump(mode="json")
    payload["operation_ids"] = ["not-a-digest"]
    payload_without_digest = dict(payload)
    payload_without_digest.pop("self_digest")
    payload["self_digest"] = object_sha256(payload_without_digest)
    with pytest.raises(ValidationError, match="SHA-256"):
        WaveReconciliationRequest.model_validate_json(json.dumps(payload))
