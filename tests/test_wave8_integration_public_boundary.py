from __future__ import annotations

import ast
from pathlib import Path

import video_channel_manager.wave_engine as wave_engine
from video_channel_manager.wave_engine.integration import (
    INTEGRATION_SCHEMA,
    IntegrationEvidenceError,
    IntegrationOutcome,
    IntegrationStageKind,
    OperationIntegrationEvidence,
    build_operation_integration_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "video_channel_manager"
INTEGRATION_MODULE = SRC / "wave_engine" / "integration.py"


def test_public_wave_engine_exports_supported_integration_boundary() -> None:
    assert wave_engine.OperationIntegrationEvidence is OperationIntegrationEvidence
    assert wave_engine.IntegrationEvidenceError is IntegrationEvidenceError
    assert wave_engine.IntegrationOutcome is IntegrationOutcome
    assert wave_engine.IntegrationStageKind is IntegrationStageKind
    assert wave_engine.build_operation_integration_evidence is build_operation_integration_evidence


def test_production_code_cannot_import_private_integration_helpers() -> None:
    violations: list[str] = []
    for path in SRC.rglob("*.py"):
        if path == INTEGRATION_MODULE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "video_channel_manager.wave_engine.integration":
                private_names = [alias.name for alias in node.names if alias.name.startswith("_")]
                if private_names:
                    violations.append(f"{path.relative_to(ROOT)}: {sorted(private_names)}")
    assert violations == []


def test_integration_schema_has_one_production_authority() -> None:
    authorities = [
        path.relative_to(ROOT) for path in SRC.rglob("*.py") if INTEGRATION_SCHEMA in path.read_text(encoding="utf-8")
    ]
    assert authorities == [Path("src/video_channel_manager/wave_engine/integration.py")]
