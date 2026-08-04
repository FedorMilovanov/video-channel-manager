from __future__ import annotations

import ast
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from video_channel_manager.wave_engine.canonical import file_sha256
from video_channel_manager.wave_engine.models import EvidenceArtifact, ProjectBinding
from video_channel_manager.wave_engine.package_a import (
    OperatorBoardState,
    PackageAError,
    PackageAInputMode,
    PackageARunRequest,
    RecoveryDecisionKind,
    SqliteLedgerContract,
    SqliteStageMapEntry,
    execute_package_a,
    load_local_records,
    load_package_a_request,
    verify_package_a_outputs,
)
from video_channel_manager.wave_engine.reconciliation import (
    BoundedSourceSnapshot,
    BoundedTargetSnapshot,
    LocalMutationStage,
    LocalReconciliationRecord,
    RemoteAssociationKind,
    RemoteMediaType,
    RemoteObservationState,
    RemoteReconciliationObservation,
    TargetCoverageKind,
)


NOW = datetime(2026, 8, 5, 1, 0, tzinfo=UTC)
CAPTURED = NOW - timedelta(minutes=5)
LORD_GOD = ProjectBinding(project_key="lord-god-strength", community_id=60805374, owner_id=-60805374)
ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _artifact(root: Path, path: Path) -> EvidenceArtifact:
    return EvidenceArtifact(path=path.relative_to(root).as_posix(), sha256=file_sha256(path))


def _source_snapshot(source_ids: tuple[str, ...]) -> BoundedSourceSnapshot:
    return BoundedSourceSnapshot.build(
        project=LORD_GOD,
        channel_id="UCeSJsC6go2c9pdJCuUI1BYA",
        captured_at=CAPTURED,
        bounded_source_video_ids=source_ids,
    )


def _observation(
    *,
    source_id: str,
    remote_id: str,
    state: RemoteObservationState = RemoteObservationState.VERIFIED,
    media_type: RemoteMediaType = RemoteMediaType.VIDEO,
) -> RemoteReconciliationObservation:
    return RemoteReconciliationObservation(
        source_video_id=source_id,
        remote_id=remote_id,
        state=state,
        association_kind=RemoteAssociationKind.EXACT_SOURCE_ID,
        media_type=media_type,
        duration_seconds=90 if state is RemoteObservationState.VERIFIED else None,
        postflight_verified=state is RemoteObservationState.VERIFIED,
    )


def _target_snapshot(
    source_ids: tuple[str, ...],
    observations: tuple[RemoteReconciliationObservation, ...] = (),
) -> BoundedTargetSnapshot:
    return BoundedTargetSnapshot.build(
        project=LORD_GOD,
        captured_at=CAPTURED,
        coverage_kind=TargetCoverageKind.COMPLETE_OWNER_CATALOG,
        bounded_source_video_ids=source_ids,
        observations=observations,
    )


def _write_snapshot_inputs(
    root: Path,
    *,
    source_ids: tuple[str, ...],
    observations: tuple[RemoteReconciliationObservation, ...] = (),
) -> tuple[EvidenceArtifact, EvidenceArtifact]:
    source_path = root / "inputs" / "source-snapshot.json"
    target_path = root / "inputs" / "target-snapshot.json"
    _write_json(source_path, _source_snapshot(source_ids).model_dump(mode="json"))
    _write_json(target_path, _target_snapshot(source_ids, observations).model_dump(mode="json"))
    return _artifact(root, source_path), _artifact(root, target_path)


def _canonical_request(
    root: Path,
    *,
    source_ids: tuple[str, ...],
    records: tuple[LocalReconciliationRecord, ...],
    observations: tuple[RemoteReconciliationObservation, ...] = (),
) -> PackageARunRequest:
    source_artifact, target_artifact = _write_snapshot_inputs(
        root,
        source_ids=source_ids,
        observations=observations,
    )
    records_path = root / "inputs" / "local-records.json"
    _write_json(records_path, [item.model_dump(mode="json") for item in records])
    return PackageARunRequest.build(
        project=LORD_GOD,
        source_snapshot=source_artifact,
        target_snapshot=target_artifact,
        input_mode=PackageAInputMode.CANONICAL_JSON,
        local_records_json=_artifact(root, records_path),
        maximum_snapshot_age_seconds=3600,
    )


def test_package_a_end_to_end_partitions_recovery_and_builds_static_board(tmp_path: Path) -> None:
    source_ids = tuple(sorted(("duplicate", "missing", "processing", "present", "unknown")))
    records = tuple(
        sorted(
            (
                LocalReconciliationRecord(
                    source_video_id="duplicate",
                    stage=LocalMutationStage.INVENTORY_ONLY,
                ),
                LocalReconciliationRecord(
                    source_video_id="missing",
                    stage=LocalMutationStage.NEVER_DISPATCHED,
                ),
                LocalReconciliationRecord(
                    source_video_id="processing",
                    stage=LocalMutationStage.PROCESSING,
                    remote_ids=("-60805374_456250003",),
                ),
                LocalReconciliationRecord(
                    source_video_id="present",
                    stage=LocalMutationStage.VERIFIED,
                    remote_ids=("-60805374_456250001",),
                ),
                LocalReconciliationRecord(
                    source_video_id="unknown",
                    stage=LocalMutationStage.UNKNOWN_REQUIRES_RECONCILIATION,
                ),
            ),
            key=lambda item: item.source_video_id,
        )
    )
    observations = (
        _observation(source_id="duplicate", remote_id="-60805374_456250004"),
        _observation(source_id="duplicate", remote_id="-60805374_456250005"),
        _observation(
            source_id="processing",
            remote_id="-60805374_456250003",
            state=RemoteObservationState.PROCESSING,
            media_type=RemoteMediaType.UNKNOWN,
        ),
        _observation(source_id="present", remote_id="-60805374_456250001"),
    )
    request = _canonical_request(
        tmp_path,
        source_ids=source_ids,
        records=records,
        observations=observations,
    )
    request_path = tmp_path / "package-a-request.json"
    _write_json(request_path, request.model_dump(mode="json"))

    loaded = load_package_a_request(request_path)
    summary = execute_package_a(
        loaded,
        input_root=tmp_path,
        output_directory=tmp_path / "output",
        evaluated_at=NOW,
    )
    verified = verify_package_a_outputs(
        evidence_path=tmp_path / "output" / "reconciliation-evidence.json",
        recovery_path=tmp_path / "output" / "recovery-decisions.json",
        board_path=tmp_path / "output" / "operator-board.json",
        summary_path=tmp_path / "output" / "run-summary.json",
    )

    assert verified == summary
    assert summary.provider_queries == 0
    assert summary.provider_writes == 0
    assert summary.write_plan_created is False
    recovery = json.loads((tmp_path / "output" / "recovery-decisions.json").read_text(encoding="utf-8"))
    assert recovery["totals"] == {
        "blocked": 1,
        "eligible_after_separate_review": 1,
        "no_action": 1,
        "reconcile_only": 2,
        "total": 5,
    }
    decisions = {item["source_video_id"]: item for item in recovery["items"]}
    assert decisions["present"]["decision"] == RecoveryDecisionKind.NO_ACTION.value
    assert decisions["duplicate"]["decision"] == RecoveryDecisionKind.BLOCKED.value
    assert decisions["processing"]["decision"] == RecoveryDecisionKind.RECONCILE_ONLY.value
    assert decisions["unknown"]["decision"] == RecoveryDecisionKind.RECONCILE_ONLY.value
    assert decisions["missing"]["decision"] == RecoveryDecisionKind.ELIGIBLE_AFTER_SEPARATE_REVIEW.value
    assert all(item["provider_write_authorized"] is False for item in recovery["items"])
    assert all(item["automatic_execution"] is False for item in recovery["items"])

    board = json.loads((tmp_path / "output" / "operator-board.json").read_text(encoding="utf-8"))
    assert board["state"] == OperatorBoardState.BLOCKED.value
    assert board["mutation_authorized"] is False
    board_html = (tmp_path / "output" / "operator-board.html").read_text(encoding="utf-8")
    assert "<script" not in board_html.casefold()
    assert "<form" not in board_html.casefold()
    assert "Provider writes: 0" in board_html


def _sqlite_contract() -> SqliteLedgerContract:
    return SqliteLedgerContract(
        table_name="current_state",
        source_video_id_column="source_id",
        stage_column="stage",
        remote_owner_id_column="owner_id",
        remote_object_id_column="object_id",
        evidence_digest_column="evidence_digest",
        stage_map=(
            SqliteStageMapEntry(raw_stage="failed", stage=LocalMutationStage.PRE_DISPATCH_FAILED),
            SqliteStageMapEntry(raw_stage="planned", stage=LocalMutationStage.NEVER_DISPATCHED),
        ),
    )


def _sqlite_request(root: Path, ledger_path: Path, source_ids: tuple[str, ...]) -> PackageARunRequest:
    source_artifact, target_artifact = _write_snapshot_inputs(root, source_ids=source_ids)
    return PackageARunRequest.build(
        project=LORD_GOD,
        source_snapshot=source_artifact,
        target_snapshot=target_artifact,
        input_mode=PackageAInputMode.SQLITE_LEDGER,
        sqlite_ledger=_artifact(root, ledger_path),
        sqlite_contract=_sqlite_contract(),
        maximum_snapshot_age_seconds=3600,
    )


def test_sqlite_ingest_uses_reviewed_contract_and_read_only_current_rows(tmp_path: Path) -> None:
    ledger_path = tmp_path / "inputs" / "upload-ledger.db"
    ledger_path.parent.mkdir(parents=True)
    with sqlite3.connect(ledger_path) as connection:
        connection.execute(
            "CREATE TABLE current_state (source_id TEXT, stage TEXT, owner_id INTEGER, "
            "object_id INTEGER, evidence_digest TEXT)"
        )
        connection.executemany(
            "INSERT INTO current_state VALUES (?, ?, ?, ?, ?)",
            (
                ("failed-source", "failed", None, None, "a" * 64),
                ("planned-source", "planned", None, None, None),
            ),
        )
    source_ids = ("failed-source", "planned-source")
    request = _sqlite_request(tmp_path, ledger_path, source_ids)

    records = load_local_records(request, input_root=tmp_path)
    assert tuple(item.source_video_id for item in records) == source_ids
    assert records[0].stage is LocalMutationStage.PRE_DISPATCH_FAILED
    assert records[0].evidence_digests == ("a" * 64,)
    assert records[1].stage is LocalMutationStage.NEVER_DISPATCHED

    summary = execute_package_a(
        request,
        input_root=tmp_path,
        output_directory=tmp_path / "output",
        evaluated_at=NOW,
    )
    assert summary.provider_queries == 0
    recovery = json.loads((tmp_path / "output" / "recovery-decisions.json").read_text(encoding="utf-8"))
    assert recovery["totals"]["eligible_after_separate_review"] == 2


def test_sqlite_ingest_rejects_unmapped_stage_and_duplicate_source_rows(tmp_path: Path) -> None:
    ledger_path = tmp_path / "inputs" / "upload-ledger.db"
    ledger_path.parent.mkdir(parents=True)
    with sqlite3.connect(ledger_path) as connection:
        connection.execute(
            "CREATE TABLE current_state (source_id TEXT, stage TEXT, owner_id INTEGER, "
            "object_id INTEGER, evidence_digest TEXT)"
        )
        connection.executemany(
            "INSERT INTO current_state VALUES (?, ?, ?, ?, ?)",
            (
                ("duplicate-source", "planned", None, None, None),
                ("duplicate-source", "mystery", None, None, None),
            ),
        )
    request = _sqlite_request(tmp_path, ledger_path, ("duplicate-source",))

    with pytest.raises(PackageAError, match="duplicate source row|not mapped"):
        load_local_records(request, input_root=tmp_path)


def test_sqlite_contract_rejects_identifier_injection() -> None:
    with pytest.raises(ValidationError, match="simple SQLite identifier"):
        SqliteLedgerContract(
            table_name='current_state"; DROP TABLE current_state; --',
            source_video_id_column="source_id",
            stage_column="stage",
            stage_map=(SqliteStageMapEntry(raw_stage="planned", stage=LocalMutationStage.NEVER_DISPATCHED),),
        )


def test_package_a_rejects_input_and_output_tampering(tmp_path: Path) -> None:
    source_ids = ("source",)
    request = _canonical_request(
        tmp_path,
        source_ids=source_ids,
        records=(
            LocalReconciliationRecord(
                source_video_id="source",
                stage=LocalMutationStage.NEVER_DISPATCHED,
            ),
        ),
    )
    records_path = tmp_path / "inputs" / "local-records.json"
    records_path.write_text("[]\n", encoding="utf-8")
    with pytest.raises(PackageAError, match="SHA-256 mismatch"):
        execute_package_a(
            request,
            input_root=tmp_path,
            output_directory=tmp_path / "output",
            evaluated_at=NOW,
        )

    request = _canonical_request(
        tmp_path,
        source_ids=source_ids,
        records=(
            LocalReconciliationRecord(
                source_video_id="source",
                stage=LocalMutationStage.NEVER_DISPATCHED,
            ),
        ),
    )
    execute_package_a(
        request,
        input_root=tmp_path,
        output_directory=tmp_path / "output",
        evaluated_at=NOW,
    )
    board_path = tmp_path / "output" / "operator-board.md"
    board_path.write_text(board_path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    with pytest.raises(PackageAError, match="output SHA-256 mismatch"):
        verify_package_a_outputs(
            evidence_path=tmp_path / "output" / "reconciliation-evidence.json",
            recovery_path=tmp_path / "output" / "recovery-decisions.json",
            board_path=tmp_path / "output" / "operator-board.json",
            summary_path=tmp_path / "output" / "run-summary.json",
        )


def test_package_a_request_digest_and_mode_contract_fail_closed(tmp_path: Path) -> None:
    source_artifact, target_artifact = _write_snapshot_inputs(tmp_path, source_ids=("source",))
    records_path = tmp_path / "inputs" / "local-records.json"
    _write_json(records_path, [])
    records_artifact = _artifact(tmp_path, records_path)
    request = PackageARunRequest.build(
        project=LORD_GOD,
        source_snapshot=source_artifact,
        target_snapshot=target_artifact,
        input_mode=PackageAInputMode.CANONICAL_JSON,
        local_records_json=records_artifact,
        maximum_snapshot_age_seconds=3600,
    )
    payload = request.model_dump()
    payload["self_digest"] = "0" * 64
    with pytest.raises(ValidationError, match="self_digest mismatch"):
        PackageARunRequest.model_validate(payload)

    with pytest.raises(ValidationError, match="requires only local_records_json"):
        PackageARunRequest(
            project=LORD_GOD,
            source_snapshot=source_artifact,
            target_snapshot=target_artifact,
            input_mode=PackageAInputMode.CANONICAL_JSON,
            local_records_json=records_artifact,
            sqlite_ledger=records_artifact,
            maximum_snapshot_age_seconds=3600,
            self_digest="0" * 64,
        )


def test_package_a_public_boundary_has_no_provider_or_write_plan_imports() -> None:
    package_path = ROOT / "src" / "video_channel_manager" / "wave_engine" / "package_a.py"
    cli_path = ROOT / "src" / "video_channel_manager" / "wave_engine" / "package_a_cli.py"
    package_tree = ast.parse(package_path.read_text(encoding="utf-8"))
    cli_text = cli_path.read_text(encoding="utf-8")
    imported_modules: set[str] = set()
    imported_names: set[str] = set()
    for node in ast.walk(package_tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module)
            imported_names.update(alias.name for alias in node.names)
    assert not any(module.startswith("video_channel_manager.platforms") for module in imported_modules)
    assert not {"WavePlan", "WaveEngine", "OperationAdapter", "UploadWriterProtocol"} & imported_names
    assert "enable-provider-writes" not in cli_text
    assert "provider_writes_enabled" not in cli_text
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'video-manager-package-a = "video_channel_manager.wave_engine.package_a_cli:run"' in pyproject
