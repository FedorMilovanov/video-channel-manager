from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/svodka-custom-emoji-capability-canary.yml"
REGISTRY = ROOT / "docs/operations/retirement-registry-v1.json"
EVIDENCE_DIR = ROOT / "content/telegram/svodka/custom-emoji-canary/evidence"
OUTCOME = EVIDENCE_DIR / "svodka-custom-emoji-outcome-31421838994-1.json"
MANIFEST = EVIDENCE_DIR / "manifest-31421838994-1.json"

EXPECTED_OUTCOME_SHA256 = "204032d5817be391821a2a393d5950ec9a5ce75b51883807d15504503e28dd77"
EXPECTED_OUTCOME_SIZE = 1206
EXPECTED_ARCHIVE_SHA256 = "b01fef30c370cb807626d36d6bdd98f544c5bde08a156568e9ce3b4210a5d7e9"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_custom_emoji_canary_is_retired_and_not_executable() -> None:
    assert not WORKFLOW.exists()

    registry = _load(REGISTRY)
    retired = {
        item["id"]: item for item in registry["retired_families"]  # type: ignore[index]
    }
    item = retired["svodka-custom-emoji-capability-canary-v1"]

    assert item["status"] == "retired_non_executable"
    assert item["execution_prohibited"] is True
    assert item["replacement"] is None
    assert item["issues"] == [273, 534]


def test_archived_custom_emoji_outcome_preserves_blocking_ambiguity() -> None:
    raw = OUTCOME.read_bytes()
    assert len(raw) == EXPECTED_OUTCOME_SIZE
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_OUTCOME_SHA256

    outcome = json.loads(raw)
    assert outcome["publication_id"] == "svodka-custom-emoji-capability-canary"
    assert outcome["workflow_run_id"] == "31421838994"
    assert outcome["workflow_run_attempt"] == "1"
    assert outcome["state"] == "unknown"
    assert outcome["provider_effect"] == "may_exist"
    assert outcome["message_id"] is None

    manifest = _load(MANIFEST)
    assert manifest["execution_prohibited"] is True
    assert manifest["reclassification_performed"] is False
    assert manifest["provider_access_performed"] is False
    assert manifest["provider_write_performed"] is False

    source_run = manifest["source_run"]
    assert isinstance(source_run, dict)
    assert source_run == {
        "run_id": 31421838994,
        "run_attempt": 1,
        "head_sha": "8eb584e19f7ba7c8cb78f5b9121cb312ac13bd06",
    }

    artifact = manifest["github_actions_artifact"]
    assert isinstance(artifact, dict)
    assert artifact["artifact_id"] == 9075800305
    assert artifact["size_bytes"] == 1384
    assert artifact["sha256"] == EXPECTED_ARCHIVE_SHA256

    archived_member = manifest["archived_member"]
    assert isinstance(archived_member, dict)
    assert archived_member["size_bytes"] == EXPECTED_OUTCOME_SIZE
    assert archived_member["sha256"] == EXPECTED_OUTCOME_SHA256

    preserved = manifest["preserved_outcome"]
    assert isinstance(preserved, dict)
    assert preserved == {
        "state": "unknown",
        "provider_effect": "may_exist",
        "message_id": None,
        "blind_retry_allowed": False,
    }
