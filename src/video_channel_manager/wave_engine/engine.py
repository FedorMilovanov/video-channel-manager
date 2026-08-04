from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from video_channel_manager.wave_engine.canonical import (
    file_sha256,
    is_ci_environment,
    resolve_repository_relative_path,
    write_json_atomic,
)
from video_channel_manager.wave_engine.models import (
    MutationClass,
    OperationStatus,
    WaveApplyIntent,
    WaveOperation,
    WaveOperationResult,
    WavePlan,
    WaveReconciliationRequest,
    WaveReconciliationResult,
    WaveResult,
    WaveSourceEvidence,
    WaveStatus,
)


class OperationAdapter(Protocol):
    def execute(self, operation: WaveOperation) -> Mapping[str, Any]: ...


class ReconciliationAdapter(Protocol):
    def reconcile(self, operation: WaveOperation) -> Mapping[str, Any]: ...


class UnknownProviderOutcomeError(RuntimeError):
    """The provider may have accepted the mutation; replay is prohibited."""


class OperationRejectedError(RuntimeError):
    """The operation was rejected before provider dispatch."""


class WaveEngine:
    def apply(
        self,
        *,
        source: WaveSourceEvidence,
        plan: WavePlan,
        intent: WaveApplyIntent,
        adapter: OperationAdapter,
        repository_root: Path,
        source_file_path: Path,
        plan_file_path: Path,
        journal_directory: Path,
        provider_writes_enabled: bool,
    ) -> WaveResult:
        intent.assert_matches(plan, source)
        root = repository_root.resolve()
        expected_source_path = resolve_repository_relative_path(root, intent.source_path, require_file=True)
        supplied_source_path = source_file_path.resolve()
        if supplied_source_path != expected_source_path:
            raise ValueError("supplied source path differs from the exact apply-intent source_path")
        if file_sha256(supplied_source_path) != intent.source_file_sha256:
            raise ValueError("source evidence file SHA-256 differs from the apply intent")
        source.verify_artifacts(root)

        expected_plan_path = resolve_repository_relative_path(root, intent.plan_path, require_file=True)
        supplied_plan_path = plan_file_path.resolve()
        if supplied_plan_path != expected_plan_path:
            raise ValueError("supplied plan path differs from the exact apply-intent plan_path")
        if file_sha256(supplied_plan_path) != intent.plan_file_sha256:
            raise ValueError("plan file SHA-256 differs from the apply intent")

        journal = journal_directory.resolve()
        try:
            journal.relative_to(root)
        except ValueError as exc:
            raise ValueError("journal directory must remain inside the repository root") from exc
        if journal in {supplied_source_path, supplied_plan_path}:
            raise ValueError("journal directory cannot overwrite source or plan evidence")
        if journal.exists():
            raise ValueError("journal directory already exists; automatic replay is prohibited")

        contains_mutation = any(
            operation.mutation_class is MutationClass.AMBIGUOUS_MUTATION for operation in plan.operations
        )
        if contains_mutation and is_ci_environment():
            raise ValueError("ambiguous provider mutations are prohibited in CI")
        if contains_mutation and (not intent.enable_provider_writes or not provider_writes_enabled):
            raise ValueError("ambiguous mutations require two explicit provider-write confirmations")

        journal.mkdir(parents=True, exist_ok=False)
        write_json_atomic(
            journal / "preflight-summary.json",
            {
                "schema_name": "video-manager.wave-preflight",
                "schema_version": 1,
                "status": "passed",
                "source_path": intent.source_path,
                "source_file_sha256": intent.source_file_sha256,
                "source_self_digest": source.self_digest,
                "plan_path": intent.plan_path,
                "plan_file_sha256": intent.plan_file_sha256,
                "plan_self_digest": plan.self_digest,
                "apply_intent_self_digest": intent.self_digest,
                "project": plan.project.model_dump(mode="json"),
                "source_snapshot_id": plan.source_snapshot_id,
                "operation_count": len(plan.operations),
                "operation_set_digest": plan.operation_set_digest,
                "contains_ambiguous_mutation": contains_mutation,
            },
        )

        operation_results: list[WaveOperationResult] = []
        stop = False
        overall = WaveStatus.SUCCEEDED

        for operation in plan.operations:
            if stop:
                operation_results.append(
                    WaveOperationResult(
                        operation_id=operation.operation_id,
                        status=OperationStatus.NOT_ATTEMPTED,
                        attempt_count=0,
                        retry_safe=False,
                        unknown_requires_reconciliation=False,
                        evidence={},
                        error_kind="blocked_after_terminal_outcome",
                    )
                )
                continue

            journal_path = journal / f"{operation.sequence:06d}-{operation.operation_id}.json"
            journal_payload = {
                "schema_name": "video-manager.wave-operation-journal",
                "schema_version": 1,
                "stage": "intent_committed",
                "plan_self_digest": plan.self_digest,
                "apply_intent_self_digest": intent.self_digest,
                "operation": operation.model_dump(mode="json"),
            }
            write_json_atomic(journal_path, journal_payload)
            journal_payload["stage"] = "dispatch_started"
            write_json_atomic(journal_path, journal_payload)

            try:
                evidence = dict(adapter.execute(operation))
                result = WaveOperationResult(
                    operation_id=operation.operation_id,
                    status=OperationStatus.SUCCEEDED,
                    attempt_count=1,
                    retry_safe=False,
                    unknown_requires_reconciliation=False,
                    evidence=evidence,
                )
            except OperationRejectedError as exc:
                result = WaveOperationResult(
                    operation_id=operation.operation_id,
                    status=OperationStatus.FAILED,
                    attempt_count=1,
                    retry_safe=True,
                    unknown_requires_reconciliation=False,
                    evidence={},
                    error_kind="rejected_before_dispatch",
                    error_message=str(exc),
                )
                overall = WaveStatus.FAILED
                stop = True
            except UnknownProviderOutcomeError as exc:
                if operation.mutation_class is MutationClass.SAFE_READ:
                    result = WaveOperationResult(
                        operation_id=operation.operation_id,
                        status=OperationStatus.FAILED,
                        attempt_count=1,
                        retry_safe=True,
                        unknown_requires_reconciliation=False,
                        evidence={},
                        error_kind="safe_read_response_lost",
                        error_message=str(exc),
                    )
                    overall = WaveStatus.FAILED
                else:
                    result = WaveOperationResult(
                        operation_id=operation.operation_id,
                        status=OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION,
                        attempt_count=1,
                        retry_safe=False,
                        unknown_requires_reconciliation=True,
                        evidence={},
                        error_kind="unknown_provider_outcome",
                        error_message=str(exc),
                    )
                    overall = WaveStatus.UNKNOWN_REQUIRES_RECONCILIATION
                stop = True
            except Exception as exc:
                if operation.mutation_class is MutationClass.AMBIGUOUS_MUTATION:
                    result = WaveOperationResult(
                        operation_id=operation.operation_id,
                        status=OperationStatus.UNKNOWN_REQUIRES_RECONCILIATION,
                        attempt_count=1,
                        retry_safe=False,
                        unknown_requires_reconciliation=True,
                        evidence={},
                        error_kind="unclassified_ambiguous_failure",
                        error_message=str(exc),
                    )
                    overall = WaveStatus.UNKNOWN_REQUIRES_RECONCILIATION
                else:
                    result = WaveOperationResult(
                        operation_id=operation.operation_id,
                        status=OperationStatus.FAILED,
                        attempt_count=1,
                        retry_safe=True,
                        unknown_requires_reconciliation=False,
                        evidence={},
                        error_kind="safe_read_failure",
                        error_message=str(exc),
                    )
                    overall = WaveStatus.FAILED
                stop = True

            operation_results.append(result)
            write_json_atomic(
                journal_path,
                {
                    **journal_payload,
                    "stage": "result_committed",
                    "result": result.model_dump(mode="json"),
                },
            )

        wave_result = WaveResult.build(plan=plan, status=overall, operations=tuple(operation_results))
        write_json_atomic(journal / "result.json", wave_result.model_dump(mode="json"))
        return wave_result

    def reconcile(
        self,
        *,
        plan: WavePlan,
        result: WaveResult,
        request: WaveReconciliationRequest,
        adapter: ReconciliationAdapter,
        output_path: Path,
    ) -> WaveReconciliationResult:
        request.assert_matches(plan, result)
        if output_path.exists():
            raise ValueError("reconciliation output already exists; overwrite is prohibited")
        operation_by_id = {operation.operation_id: operation for operation in plan.operations}
        reconciled: list[WaveOperationResult] = []
        for operation_id in request.operation_ids:
            operation = operation_by_id[operation_id]
            evidence = dict(adapter.reconcile(operation))
            reconciled.append(
                WaveOperationResult(
                    operation_id=operation_id,
                    status=OperationStatus.RECONCILED,
                    attempt_count=1,
                    retry_safe=False,
                    unknown_requires_reconciliation=False,
                    evidence=evidence,
                )
            )
        reconciliation = WaveReconciliationResult.build(request=request, operations=tuple(reconciled))
        write_json_atomic(output_path, reconciliation.model_dump(mode="json"))
        return reconciliation
