from __future__ import annotations

import hashlib
import importlib
from pathlib import Path

import pytest

from video_channel_manager.wave_engine import (
    EvidenceArtifact,
    MutationClass,
    ProjectBinding,
    WaveApplyIntent,
    WaveEngine,
    WaveOperation,
    WaveOperationSpec,
    WavePlan,
    WaveSourceEvidence,
)
from video_channel_manager.wave_engine.canonical import file_sha256, write_json_atomic


engine_module = importlib.import_module("video_channel_manager.wave_engine.engine")
_SOURCE_BYTES = b'{"source":1}\n'


class InjectedCrash(RuntimeError):
    pass


class RecordingAdapter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def execute(self, operation: WaveOperation) -> dict[str, object]:
        self.calls.append(operation.operation_id)
        return {"remote_identity": f"read-{operation.sequence}"}


def _prepared(root: Path) -> tuple[WaveSourceEvidence, WavePlan, WaveApplyIntent, Path, Path]:
    project = ProjectBinding(project_key="legendary-poet", community_id=235216998, owner_id=-235216998)
    artifact = root / "data" / "source.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(_SOURCE_BYTES)
    source = WaveSourceEvidence.build(
        project=project,
        policy_version="wave-policy-v1",
        artifacts=(EvidenceArtifact(path="data/source.json", sha256=hashlib.sha256(_SOURCE_BYTES).hexdigest()),),
    )
    plan = WavePlan.build(
        source=source,
        specs=(
            WaveOperationSpec(
                order_key="000000",
                operation_kind="fault-read",
                mutation_class=MutationClass.SAFE_READ,
                payload={"index": 0},
            ),
        ),
    )
    source_path = root / "source-evidence.json"
    plan_path = root / "plan.json"
    write_json_atomic(source_path, source.model_dump(mode="json"))
    write_json_atomic(plan_path, plan.model_dump(mode="json"))
    intent = WaveApplyIntent.build(
        source=source,
        source_path="source-evidence.json",
        source_file_sha256=file_sha256(source_path),
        plan=plan,
        plan_path="plan.json",
        plan_file_sha256=file_sha256(plan_path),
        enable_provider_writes=False,
    )
    return source, plan, intent, source_path, plan_path


@pytest.mark.parametrize(
    ("target", "expected_calls"),
    [
        ("preflight-summary.json", 0),
        ("intent_committed", 0),
        ("dispatch_started", 0),
        ("result_committed", 1),
        ("result.json", 1),
    ],
)
def test_crash_after_durable_boundary_blocks_automatic_child_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
    expected_calls: int,
) -> None:
    source, plan, intent, source_path, plan_path = _prepared(tmp_path)
    journal = tmp_path / "journal"
    adapter = RecordingAdapter()
    original_write = engine_module.write_json_atomic

    def crashing_write(path: Path, value: object) -> None:
        original_write(path, value)
        payload = value if isinstance(value, dict) else {}
        if path.name == target or payload.get("stage") == target:
            raise InjectedCrash(target)

    monkeypatch.setattr(engine_module, "write_json_atomic", crashing_write)
    with pytest.raises(InjectedCrash, match=re.escape(target)):
        WaveEngine().apply(
            source=source,
            plan=plan,
            intent=intent,
            adapter=adapter,
            repository_root=tmp_path,
            source_file_path=source_path,
            plan_file_path=plan_path,
            journal_directory=journal,
            provider_writes_enabled=False,
        )

    assert len(adapter.calls) == expected_calls
    assert journal.is_dir()

    monkeypatch.setattr(engine_module, "write_json_atomic", original_write)
    with pytest.raises(ValueError, match="journal directory already exists"):
        WaveEngine().apply(
            source=source,
            plan=plan,
            intent=intent,
            adapter=adapter,
            repository_root=tmp_path,
            source_file_path=source_path,
            plan_file_path=plan_path,
            journal_directory=journal,
            provider_writes_enabled=False,
        )
    assert len(adapter.calls) == expected_calls
