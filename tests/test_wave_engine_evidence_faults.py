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
    WaveApplyIntent,
    WaveOperationResult,
    WaveOperationSpec,
    WavePlan,
    WaveResult,
    WaveSourceEvidence,
    WaveStatus,
)
from video_channel_manager.wave_engine import canonical
from video_channel_manager.wave_engine.canonical import object_sha256, read_json_object, resolve_repository_relative_path

_SOURCE_BYTES = b'{"source":1}\n'


def _project(key: str = "legendary-poet") -> ProjectBinding:
    if key == "legendary-poet":
        return ProjectBinding(project_key=key, community_id=235216998, owner_id=-235216998)
    return ProjectBinding(project_key=key, community_id=60805374, owner_id=-60805374)


def _source(*, project_key: str = "legendary-poet", policy_version: str = "wave-policy-v1") -> WaveSourceEvidence:
    return WaveSourceEvidence.build(
        project=_project(project_key),
        policy_version=policy_version,
        artifacts=(
            EvidenceArtifact(
                path="data/source.json",
                sha256=hashlib.sha256(_SOURCE_BYTES).hexdigest(),
            ),
        ),
    )


def _plan(source: WaveSourceEvidence, count: int = 2) -> WavePlan:
    return WavePlan.build(
        source=source,
        specs=tuple(
            WaveOperationSpec(
                order_key=f"{index:06d}",
                operation_kind=f"read-{index}",
                mutation_class=MutationClass.SAFE_READ,
                payload={"index": index},
            )
            for index in range(count)
        ),
    )


def _result(plan: WavePlan) -> WaveResult:
    return WaveResult.build(
        plan=plan,
        status=WaveStatus.SUCCEEDED,
        operations=tuple(
            WaveOperationResult(
                operation_id=operation.operation_id,
                status=OperationStatus.SUCCEEDED,
                attempt_count=1,
                retry_safe=False,
                unknown_requires_reconciliation=False,
                evidence={"remote_identity": f"remote-{operation.sequence}"},
            )
            for operation in plan.operations
        ),
    )


def test_atomic_replace_failure_preserves_old_file_and_cleans_orphan_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "result.json"
    canonical.write_json_atomic(path, {"status": "old"})
    original = path.read_bytes()

    def fail_replace(source: str | bytes | Path, destination: str | bytes | Path) -> None:
        del source, destination
        raise OSError("simulated interrupted atomic replace")

    monkeypatch.setattr(canonical.os, "replace", fail_replace)
    with pytest.raises(OSError, match="interrupted atomic replace"):
        canonical.write_json_atomic(path, {"status": "new"})

    assert path.read_bytes() == original
    assert list(tmp_path.glob(f".{path.name}.*.tmp")) == []


@pytest.mark.parametrize(
    "raw",
    [
        "{",
        "[]",
        '"scalar"',
        "\ufeff{not-json}",
    ],
)
def test_read_json_object_rejects_truncated_malformed_and_non_object_evidence(tmp_path: Path, raw: str) -> None:
    path = tmp_path / "evidence.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises((ValueError, json.JSONDecodeError)):
        read_json_object(path)


def test_source_evidence_rejects_extra_fields_and_wrong_snapshot_even_with_rehashed_outer_digest() -> None:
    source = _source()

    extra = source.model_dump(mode="json")
    extra["unexpected_authority"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        WaveSourceEvidence.model_validate_json(json.dumps(extra))

    wrong_snapshot = source.model_dump(mode="json")
    wrong_snapshot["source_snapshot_id"] = "0" * 64
    payload_without_digest = dict(wrong_snapshot)
    payload_without_digest.pop("self_digest")
    wrong_snapshot["self_digest"] = object_sha256(payload_without_digest)
    with pytest.raises(ValidationError, match="source_snapshot_id mismatch"):
        WaveSourceEvidence.model_validate_json(json.dumps(wrong_snapshot))


def test_apply_intent_rejects_cross_project_wrong_policy_and_wrong_source_snapshot() -> None:
    poet_source = _source()
    poet_plan = _plan(poet_source)
    intent = WaveApplyIntent.build(
        source=poet_source,
        source_path="source.json",
        source_file_sha256="1" * 64,
        plan=poet_plan,
        plan_path="plan.json",
        plan_file_sha256="2" * 64,
        enable_provider_writes=False,
    )

    lord_source = _source(project_key="lord-god-strength")
    lord_plan = _plan(lord_source)
    with pytest.raises(ValueError, match="binding mismatch"):
        intent.assert_matches(lord_plan, lord_source)

    other_policy_source = _source(policy_version="wave-policy-v2")
    other_policy_plan = _plan(other_policy_source)
    with pytest.raises(ValueError, match="binding mismatch"):
        intent.assert_matches(other_policy_plan, other_policy_source)


def test_result_rejects_missing_duplicate_and_cross_plan_operation_coverage() -> None:
    source = _source()
    plan = _plan(source)
    result = _result(plan)

    missing = result.model_dump(mode="json")
    missing["operations"] = missing["operations"][:-1]
    missing_without_digest = dict(missing)
    missing_without_digest.pop("self_digest")
    missing["self_digest"] = object_sha256(missing_without_digest)
    parsed_missing = WaveResult.model_validate_json(json.dumps(missing))
    with pytest.raises(ValueError, match="exact ordered"):
        parsed_missing.assert_matches(plan)

    duplicate = result.model_dump(mode="json")
    duplicate["operations"] = [duplicate["operations"][0], duplicate["operations"][0]]
    duplicate_without_digest = dict(duplicate)
    duplicate_without_digest.pop("self_digest")
    duplicate["self_digest"] = object_sha256(duplicate_without_digest)
    parsed_duplicate = WaveResult.model_validate_json(json.dumps(duplicate))
    with pytest.raises(ValueError, match="exact ordered"):
        parsed_duplicate.assert_matches(plan)

    other_plan = _plan(_source(policy_version="wave-policy-v2"))
    with pytest.raises(ValueError, match="binding mismatch"):
        result.assert_matches(other_plan)


def test_repository_path_resolution_rejects_parent_and_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="escapes"):
        resolve_repository_relative_path(root, "../outside.json", require_file=True)

    symlink = root / "linked.json"
    try:
        symlink.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable in this test environment")
    with pytest.raises(ValueError, match="escapes"):
        resolve_repository_relative_path(root, "linked.json", require_file=True)
