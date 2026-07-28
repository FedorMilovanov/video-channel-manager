from __future__ import annotations

import copy
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from video_channel_manager.platforms.vk.catalog import canonical_sha256
from video_channel_manager.platforms.vk.wall_wave import (
    build_wall_wave_preflight,
    calculate_wall_wave_policy_sha256,
    message_sha256,
    sha256_bytes,
    validate_wall_wave_policy,
    verify_source_audit_bundle,
    verify_wall_wave_postflight,
    wall_post_id,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "content" / "policies" / "vk-wall-wave-202608.json"


def _policy() -> dict[str, object]:
    value = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _post(operation: dict[str, object], *, message: str | None = None, date: int | None = None) -> dict[str, object]:
    owner_text, video_text = str(operation["video_id"]).split("_", maxsplit=1)
    return {
        "owner_id": int(owner_text),
        "id": int(video_text),
        "date": int(operation["publish_date"] if date is None else date),
        "text": str(operation["message"] if message is None else message),
        "attachments": [
            {
                "type": "video",
                "video": {"owner_id": int(owner_text), "id": int(video_text)},
            }
        ],
    }


def test_committed_wall_wave_policy_is_self_consistent() -> None:
    policy = _policy()
    validate_wall_wave_policy(policy)

    assert policy["policy_sha256"] == calculate_wall_wave_policy_sha256(policy)
    assert len(policy["operations"]) == 12
    assert len({item["video_id"] for item in policy["operations"]}) == 12
    assert all(item["message_sha256"] == message_sha256(item["message"]) for item in policy["operations"])


def test_preflight_accepts_only_absent_or_exact_posts() -> None:
    policy = _policy()
    operations = policy["operations"]
    first = operations[0]
    second = operations[1]
    now = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)

    preflight = build_wall_wave_preflight(
        policy,
        published_posts=[],
        postponed_posts=[_post(first)],
        now=now,
    )
    states = {item["operation_id"]: item["state"] for item in preflight["states"]}

    assert preflight["status"] == "ready"
    assert preflight["ready"] == 11
    assert preflight["already_applied"] == 1
    assert preflight["conflicts"] == 0
    assert states[first["operation_id"]] == "already_applied"
    assert states[second["operation_id"]] == "ready"


def test_preflight_blocks_different_message_or_schedule() -> None:
    policy = _policy()
    first = policy["operations"][0]
    now = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)

    wrong_message = build_wall_wave_preflight(
        policy,
        published_posts=[],
        postponed_posts=[_post(first, message="Другой текст")],
        now=now,
    )
    wrong_date = build_wall_wave_preflight(
        policy,
        published_posts=[],
        postponed_posts=[_post(first, date=int(first["publish_date"]) + 60)],
        now=now,
    )

    assert wrong_message["conflicts"] == 1
    assert wrong_date["conflicts"] == 1
    assert wrong_message["states"][0]["state"] == "conflict"
    assert wrong_date["states"][0]["state"] == "conflict"


def test_preflight_blocks_ready_post_when_date_is_no_longer_future() -> None:
    policy = _policy()
    first_date = int(policy["operations"][0]["publish_date"])
    preflight = build_wall_wave_preflight(
        policy,
        published_posts=[],
        postponed_posts=[],
        now=datetime.fromtimestamp(first_date - 120, tz=UTC),
        minimum_future_seconds=300,
    )

    assert preflight["conflicts"] == 1
    assert preflight["states"][0]["state"] == "conflict"
    assert preflight["states"][0]["detail"] == "approved publish date is no longer safely in the future"


def test_postflight_requires_all_twelve_exact_posts() -> None:
    policy = _policy()
    preflight = build_wall_wave_preflight(
        policy,
        published_posts=[],
        postponed_posts=[_post(operation) for operation in policy["operations"]],
        now=datetime(2026, 7, 29, 12, 0, tzinfo=UTC),
    )

    verification = verify_wall_wave_postflight(policy, preflight)

    assert verification["status"] == "verified_completed"
    assert verification["verified_operations"] == 12
    assert verification["verified_postponed"] == 12
    assert verification["verified_published"] == 0


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_source_bundle(tmp_path: Path, policy: dict[str, object]) -> Path:
    operations = policy["operations"]
    selected = [
        {
            "video_id": operation["video_id"],
            "title": operation["video_title"],
            "state": "unposted",
        }
        for operation in operations
    ]
    dummy_count = 111 - len(selected)
    dummies = [
        {
            "video_id": f"-235216998_{900000000 + index}",
            "title": f"Fixture {index}",
            "state": "unposted" if index < 76 else "published",
        }
        for index in range(dummy_count)
    ]
    audit = {
        "schema_name": "video-manager.vk-wall-content-audit",
        "schema_version": 1,
        "community_id": 235216998,
        "read_only": True,
        "summary": copy.deepcopy(policy["source_audit_summary"]),
        "videos": [*selected, *dummies],
        "duplicate_post_references": [],
        "unknown_published_video_ids": [],
        "unknown_postponed_video_ids": [],
        "status": "review_required",
    }
    audit["audit_sha256"] = canonical_sha256({key: value for key, value in audit.items() if key != "audit_sha256"})
    policy["source_audit_sha256"] = audit["audit_sha256"]

    bundle_dir = tmp_path / "source"
    bundle_dir.mkdir()
    _write_json(bundle_dir / "00-videos.json", [])
    _write_json(bundle_dir / "01-published-wall-posts.json", [])
    _write_json(bundle_dir / "02-postponed-wall-posts.json", [])
    _write_json(bundle_dir / "03-wall-content-audit.json", audit)
    (bundle_dir / "04-wall-content-audit.md").write_text("# Fixture\n", encoding="utf-8")
    (bundle_dir / "README.txt").write_text("fixture\n", encoding="utf-8")

    files = []
    for path in sorted(bundle_dir.iterdir()):
        raw = path.read_bytes()
        files.append({"name": path.name, "size_bytes": len(raw), "sha256": sha256_bytes(raw)})
    manifest = {
        "schema_name": "video-manager.vk-wall-content-audit-handoff",
        "schema_version": 1,
        "status": "review_required",
        "mode": "read-only",
        "community_id": 235216998,
        "audit_sha256": audit["audit_sha256"],
        "summary": audit["summary"],
        "files": files,
    }
    _write_json(bundle_dir / "manifest.json", manifest)

    bundle = tmp_path / "fixture-source-audit.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle_dir.iterdir()):
            archive.write(path, arcname=path.name)
    policy["source_audit_bundle_name"] = bundle.name
    policy["source_audit_bundle_sha256"] = sha256_bytes(bundle.read_bytes())
    policy["policy_sha256"] = calculate_wall_wave_policy_sha256(policy)
    return bundle


def test_source_audit_verifier_locks_selected_videos_to_unposted_state(tmp_path: Path) -> None:
    policy = copy.deepcopy(_policy())
    bundle = _build_source_bundle(tmp_path, policy)

    audit, verification = verify_source_audit_bundle(bundle, policy)

    assert audit["audit_sha256"] == policy["source_audit_sha256"]
    assert verification["status"] == "verified"
    assert verification["source_videos"] == 111
    assert verification["approved_unposted_targets"] == 12


def test_source_audit_verifier_rejects_non_unposted_target(tmp_path: Path) -> None:
    policy = copy.deepcopy(_policy())
    bundle = _build_source_bundle(tmp_path, policy)
    extracted = tmp_path / "tampered"
    with zipfile.ZipFile(bundle) as archive:
        archive.extractall(extracted)
    audit = json.loads((extracted / "03-wall-content-audit.json").read_text(encoding="utf-8"))
    audit["videos"][0]["state"] = "published"
    audit["audit_sha256"] = canonical_sha256({key: value for key, value in audit.items() if key != "audit_sha256"})
    _write_json(extracted / "03-wall-content-audit.json", audit)

    # Rebuild a fully self-consistent bundle so the semantic state guard is the failure.
    files = []
    for path in sorted(extracted.iterdir()):
        if path.name == "manifest.json":
            continue
        raw = path.read_bytes()
        files.append({"name": path.name, "size_bytes": len(raw), "sha256": sha256_bytes(raw)})
    manifest = json.loads((extracted / "manifest.json").read_text(encoding="utf-8"))
    manifest["audit_sha256"] = audit["audit_sha256"]
    manifest["files"] = files
    _write_json(extracted / "manifest.json", manifest)
    tampered_bundle = tmp_path / "tampered-source-audit.zip"
    with zipfile.ZipFile(tampered_bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(extracted.iterdir()):
            archive.write(path, arcname=path.name)
    policy["source_audit_bundle_name"] = tampered_bundle.name
    policy["source_audit_bundle_sha256"] = sha256_bytes(tampered_bundle.read_bytes())
    policy["source_audit_sha256"] = audit["audit_sha256"]
    policy["policy_sha256"] = calculate_wall_wave_policy_sha256(policy)

    with pytest.raises(ValueError, match="not source-audited as unposted"):
        verify_source_audit_bundle(tampered_bundle, policy)


def test_wall_post_response_requires_positive_post_id() -> None:
    assert wall_post_id(17) == 17
    assert wall_post_id({"post_id": 18}) == 18
    with pytest.raises(ValueError, match="no positive post ID"):
        wall_post_id({"post_id": 0})
