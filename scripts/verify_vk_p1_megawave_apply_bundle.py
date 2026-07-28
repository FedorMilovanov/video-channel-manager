#!/usr/bin/env python3
"""Independently verify the completed one-command VK P1 megawave handoff."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from verify_vk_p1_megawave_plan import verify as verify_plan
from verify_vk_reviewed_correction_apply_bundle import (
    _collection_titles,
    _coverage_sha256,
    _file_sha256,
    _json_bytes,
    _membership_identity_rows,
    _membership_position_changes,
    _membership_sha256,
    _verify_manifest,
    _video_map,
)
from verify_vk_reviewed_correction_pushkin_cloud_apply_bundle import (
    verify_bundle as verify_pushkin_cloud_apply,
)

_ALLOWED_STATUSES = frozenset({"updated_and_verified", "already_applied"})
_REQUIRED_FILES = frozenset(
    {
        "00-source-vk-snapshot.json",
        "01-decisions.json",
        "02-plan.json",
        "03-plan-review.md",
        "04-plan-review.html",
        "05-plan-verification.json",
        "06-preflight.txt",
        "07-apply.txt",
        "08-result.json",
        "09-final-vk-snapshot.json",
        "README.txt",
        "manifest.json",
        "megawave-policy.json",
        "source-pushkin-cloud-apply.zip",
        "source-review-bundle.zip",
    }
)
_OPTIONAL_FILES = frozenset({"10-independent-verification.json"})


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--json-output", type=Path)
    return parser


def _count(text: str, label: str) -> int:
    match = re.search(rf"(?m)^\s*{re.escape(label)}:\s*(\d+)\s*$", text)
    if not match:
        raise ValueError(f"Preflight is missing count: {label}")
    return int(match.group(1))


def _write_temp(directory: Path, name: str, raw: bytes) -> Path:
    path = directory / name
    path.write_bytes(raw)
    return path


def verify_bundle(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        names = [entry.filename for entry in archive.infolist()]
        if len(names) != len(set(names)):
            raise ValueError("Megawave bundle contains duplicate ZIP entries")
        name_set = set(names)
        missing = sorted(_REQUIRED_FILES - name_set)
        if missing:
            raise ValueError("Megawave bundle is missing required files: " + ", ".join(missing))
        unexpected = sorted(name_set - (_REQUIRED_FILES | _OPTIONAL_FILES))
        if unexpected:
            raise ValueError("Megawave bundle contains unexpected files: " + ", ".join(unexpected))
        raw = {name: archive.read(name) for name in names}

    manifest = _json_bytes(raw["manifest.json"], name="manifest.json")
    policy = _json_bytes(raw["megawave-policy.json"], name="megawave-policy.json")
    decisions = _json_bytes(raw["01-decisions.json"], name="01-decisions.json")
    plan = _json_bytes(raw["02-plan.json"], name="02-plan.json")
    plan_verification = _json_bytes(raw["05-plan-verification.json"], name="05-plan-verification.json")
    result = _json_bytes(raw["08-result.json"], name="08-result.json")
    source = _json_bytes(raw["00-source-vk-snapshot.json"], name="00-source-vk-snapshot.json")
    final = _json_bytes(raw["09-final-vk-snapshot.json"], name="09-final-vk-snapshot.json")
    _verify_manifest(raw, manifest)

    if manifest.get("status") != "completed":
        raise ValueError("Megawave wrapper status is not completed")
    if manifest.get("mode") != "apply" or manifest.get("component_scope") != "descriptions_only":
        raise ValueError("Megawave handoff has unexpected mode or component scope")
    if manifest.get("correction_scope") != "reviewed_factual_and_sensitive":
        raise ValueError("Megawave correction scope differs")
    if manifest.get("decision_set_id") != "p1-all-remaining-megawave-20260728":
        raise ValueError("Megawave decision set differs")
    if int(manifest.get("community_id", 0)) != 235216998:
        raise ValueError("Megawave community differs")
    if int(manifest.get("conflicts", -1)) != 0:
        raise ValueError("Megawave reports conflicts")
    if int(manifest.get("operations", -1)) != 42:
        raise ValueError("Megawave manifest operation count differs")

    if policy.get("mode") != "single_megawave" or int(policy.get("target_count", 0)) != 42:
        raise ValueError("Embedded megawave policy differs")
    expected_source_apply_sha = str(policy.get("source_apply_bundle_sha256") or "")
    if _file_sha256(raw["source-pushkin-cloud-apply.zip"]) != expected_source_apply_sha:
        raise ValueError("Source Pushkin Cloud apply ZIP differs")
    if _file_sha256(raw["source-review-bundle.zip"]) != str(policy.get("source_review_bundle_sha256") or ""):
        raise ValueError("Source review bundle differs")

    with tempfile.TemporaryDirectory(prefix="vk-p1-megawave-verify-") as temp:
        directory = Path(temp)
        source_path = _write_temp(directory, "source.json", raw["00-source-vk-snapshot.json"])
        policy_path = _write_temp(directory, "policy.json", raw["megawave-policy.json"])
        review_path = _write_temp(directory, "review.zip", raw["source-review-bundle.zip"])
        decisions_path = _write_temp(directory, "decisions.json", raw["01-decisions.json"])
        plan_path = _write_temp(directory, "plan.json", raw["02-plan.json"])
        source_apply_path = _write_temp(directory, "source-apply.zip", raw["source-pushkin-cloud-apply.zip"])

        source_apply_report = verify_pushkin_cloud_apply(source_apply_path)
        if source_apply_report.get("status") != "verified_completed":
            raise ValueError("Source Pushkin Cloud apply did not pass independent verification")
        plan_report = verify_plan(source_path, policy_path, review_path, decisions_path, plan_path)
        if plan_report.get("status") != "verified_plan":
            raise ValueError("Embedded megawave plan did not pass deterministic verification")

    if plan_verification.get("status") != "verified_plan":
        raise ValueError("Embedded plan verification status differs")
    if plan_verification.get("plan_sha256") != plan.get("plan_sha256"):
        raise ValueError("Embedded plan verification belongs to another plan")
    if manifest.get("plan_sha256") != plan.get("plan_sha256"):
        raise ValueError("Manifest plan digest differs")
    if manifest.get("decisions_sha256") != plan.get("decisions_sha256"):
        raise ValueError("Manifest decisions digest differs")
    if decisions.get("decision_set_id") != manifest.get("decision_set_id"):
        raise ValueError("Decisions belong to another megawave")

    preflight = raw["06-preflight.txt"].decode("utf-8-sig")
    ready = _count(preflight, "ready")
    already = _count(preflight, "already applied")
    conflicts = _count(preflight, "conflicts")
    if ready + already != 42 or conflicts != 0:
        raise ValueError("Megawave preflight counts differ")
    for guard in (
        f"plan: {plan['plan_sha256']}",
        f"video coverage: {plan['target_video_ids_sha256']}",
        f"membership state: {plan['initial_memberships_sha256']}",
        "No VK mutation method was called",
    ):
        if guard not in preflight:
            raise ValueError("Megawave preflight is missing an exact guard")

    if result.get("status") != "completed" or result.get("plan_sha256") != plan.get("plan_sha256"):
        raise ValueError("Megawave result journal does not confirm the exact plan")
    result_operations = result.get("operations")
    if not isinstance(result_operations, list) or len(result_operations) != 42:
        raise ValueError("Megawave result journal operation count differs")
    statuses = Counter(str(item.get("status")) for item in result_operations)
    if any(status not in _ALLOWED_STATUSES for status in statuses):
        raise ValueError("Megawave result journal contains an unsupported operation status")
    result_ids = [str(item.get("remote_id")) for item in result_operations]
    target_ids = [str(item.get("video_id")) for item in policy.get("targets", [])]
    if set(result_ids) != set(target_ids) or len(set(result_ids)) != 42:
        raise ValueError("Megawave result target coverage differs")
    remote_writes = int(statuses.get("updated_and_verified", 0))
    if int(manifest.get("remote_writes", -1)) != remote_writes:
        raise ValueError("Megawave manifest write count differs from result journal")

    source_videos = _video_map(source)
    final_videos = _video_map(final)
    if set(source_videos) != set(final_videos) or len(final_videos) != 111:
        raise ValueError("VK video inventory changed during megawave")
    if len(source.get("collections", [])) != 17 or len(final.get("collections", [])) != 17:
        raise ValueError("VK collection inventory changed during megawave")
    if len(source.get("memberships", [])) != 294 or len(final.get("memberships", [])) != 294:
        raise ValueError("VK membership inventory changed during megawave")

    operations = {
        str(item.get("target_video_id")): item
        for item in plan.get("video_text_operations", [])
        if isinstance(item, dict)
    }
    if set(operations) != set(target_ids):
        raise ValueError("Megawave plan target coverage differs from policy")

    changed_descriptions: list[str] = []
    for remote_id, before_video in source_videos.items():
        after_video = final_videos[remote_id]
        if before_video.get("title") != after_video.get("title"):
            raise ValueError(f"Title changed during megawave: {remote_id}")
        operation = operations.get(remote_id)
        if operation is None:
            if before_video.get("description") != after_video.get("description"):
                raise ValueError(f"Non-target description changed: {remote_id}")
            continue
        if before_video.get("description") != operation.get("before_description"):
            raise ValueError(f"Source target description differs from plan: {remote_id}")
        if after_video.get("description") != operation.get("after_description"):
            raise ValueError(f"Final target description differs from plan: {remote_id}")
        if before_video.get("description") != after_video.get("description"):
            changed_descriptions.append(remote_id)

    if len(changed_descriptions) != 42:
        raise ValueError("Final snapshot does not contain all 42 reviewed after-states")
    if remote_writes + int(statuses.get("already_applied", 0)) != 42:
        raise ValueError("Result journal does not account for all 42 megawave operations")
    if _collection_titles(source) != _collection_titles(final):
        raise ValueError("VK collection identities or titles changed")
    if Counter(_membership_identity_rows(source)) != Counter(_membership_identity_rows(final)):
        raise ValueError("VK membership identity changed")
    position_changes = _membership_position_changes(source, final)
    if position_changes:
        raise ValueError("VK membership positions changed")
    if _coverage_sha256(source) != _coverage_sha256(final):
        raise ValueError("VK video coverage digest changed")
    if _membership_sha256(source) != _membership_sha256(final):
        raise ValueError("VK membership digest changed")

    if "10-independent-verification.json" in raw:
        embedded = _json_bytes(
            raw["10-independent-verification.json"],
            name="10-independent-verification.json",
        )
        if embedded.get("status") != "verified_completed" or embedded.get("plan_sha256") != plan.get("plan_sha256"):
            raise ValueError("Embedded independent verification differs")

    return {
        "schema_name": "video-manager.vk-p1-megawave-apply-verification",
        "schema_version": 1,
        "status": "verified_completed",
        "bundle": str(path),
        "bundle_sha256": _file_sha256(path.read_bytes()),
        "decision_set_id": manifest["decision_set_id"],
        "plan_sha256": plan["plan_sha256"],
        "decisions_sha256": plan["decisions_sha256"],
        "operations": 42,
        "operation_statuses": dict(statuses),
        "remote_writes": remote_writes,
        "already_applied": int(statuses.get("already_applied", 0)),
        "target_video_ids": sorted(target_ids),
        "videos": 111,
        "collections": 17,
        "memberships": 294,
        "non_target_videos_verified_unchanged": 69,
        "membership_identity_unchanged": True,
        "membership_position_changes": [],
        "source_pushkin_cloud_apply_status": source_apply_report["status"],
        "plan_verification_status": plan_report["status"],
    }


def main() -> int:
    args = _parser().parse_args()
    try:
        report = verify_bundle(args.bundle)
    except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        report = {
            "schema_name": "video-manager.vk-p1-megawave-apply-verification",
            "schema_version": 1,
            "status": "verification_failed",
            "bundle": str(args.bundle),
            "error": str(exc),
        }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.json_output:
        args.json_output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report.get("status") == "verified_completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
