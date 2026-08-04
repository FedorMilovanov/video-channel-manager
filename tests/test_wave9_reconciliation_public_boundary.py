from __future__ import annotations

import ast
from pathlib import Path

import video_channel_manager.wave_engine as wave_engine
from video_channel_manager.wave_engine.reconciliation import (
    RECONCILIATION_SCHEMA,
    BoundedSourceSnapshot,
    BoundedTargetSnapshot,
    LocalMutationStage,
    LocalReconciliationRecord,
    ReadOnlyReconciliationError,
    ReadOnlyReconciliationEvidence,
    ReconciliationReason,
    ReconciliationState,
    RemoteAssociationKind,
    RemoteMediaType,
    RemoteObservationState,
    RemoteReconciliationObservation,
    TargetCoverageKind,
    build_read_only_reconciliation_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "video_channel_manager"
RECONCILIATION_MODULE = SRC / "wave_engine" / "reconciliation.py"


def test_public_wave_engine_exports_supported_read_only_reconciliation_boundary() -> None:
    expected = {
        "BoundedSourceSnapshot": BoundedSourceSnapshot,
        "BoundedTargetSnapshot": BoundedTargetSnapshot,
        "LocalMutationStage": LocalMutationStage,
        "LocalReconciliationRecord": LocalReconciliationRecord,
        "ReadOnlyReconciliationError": ReadOnlyReconciliationError,
        "ReadOnlyReconciliationEvidence": ReadOnlyReconciliationEvidence,
        "ReconciliationReason": ReconciliationReason,
        "ReconciliationState": ReconciliationState,
        "RemoteAssociationKind": RemoteAssociationKind,
        "RemoteMediaType": RemoteMediaType,
        "RemoteObservationState": RemoteObservationState,
        "RemoteReconciliationObservation": RemoteReconciliationObservation,
        "TargetCoverageKind": TargetCoverageKind,
        "build_read_only_reconciliation_evidence": build_read_only_reconciliation_evidence,
    }
    for name, value in expected.items():
        assert getattr(wave_engine, name) is value


def test_reconciliation_module_has_no_mutation_engine_or_writer_imports() -> None:
    tree = ast.parse(RECONCILIATION_MODULE.read_text(encoding="utf-8"), filename=str(RECONCILIATION_MODULE))
    forbidden_names = {
        "MutationClass",
        "OperationAdapter",
        "WaveApplyIntent",
        "WaveEngine",
        "WaveOperation",
        "WaveOperationSpec",
        "WavePlan",
    }
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        module = node.module if isinstance(node, ast.ImportFrom) else ""
        imported_names = {alias.name for alias in node.names}
        if imported_names & forbidden_names:
            violations.append(f"forbidden names: {sorted(imported_names & forbidden_names)}")
        if module and (
            module.endswith(".writer")
            or module.endswith(".upload_media")
            or module.endswith(".thumbnail_writer")
            or module == "video_channel_manager.wave_engine.engine"
        ):
            violations.append(f"forbidden module: {module}")
    assert violations == []


def test_production_code_cannot_import_private_reconciliation_helpers() -> None:
    violations: list[str] = []
    for path in SRC.rglob("*.py"):
        if path == RECONCILIATION_MODULE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "video_channel_manager.wave_engine.reconciliation":
                private_names = [alias.name for alias in node.names if alias.name.startswith("_")]
                if private_names:
                    violations.append(f"{path.relative_to(ROOT)}: {sorted(private_names)}")
    assert violations == []


def test_reconciliation_schema_has_one_production_authority() -> None:
    authorities = [
        path.relative_to(ROOT)
        for path in SRC.rglob("*.py")
        if RECONCILIATION_SCHEMA in path.read_text(encoding="utf-8")
    ]
    assert authorities == [Path("src/video_channel_manager/wave_engine/reconciliation.py")]


def test_reconciliation_evidence_structurally_forbids_writes_and_write_plans() -> None:
    fields = ReadOnlyReconciliationEvidence.model_fields
    assert fields["provider_writes"].default == 0
    assert fields["write_plan_created"].default is False
    assert "operations" not in fields
    assert "plan" not in fields
