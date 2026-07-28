#!/usr/bin/env python3
"""Independently verify a completed Pushkin «Туча» apply handoff ZIP."""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

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
from verify_vk_reviewed_correction_pushkin_cloud_dry_run import verify_bundle as verify_dry_run_bundle

_PLAN_SHA = "sha256:207ee6e5622692b504254c7d7aa3579fd2907614eaf88d1b6e0ac7c1eacf517c"
_DECISIONS_SHA = "sha256:eaddbce693498a87cd888642642073bb0198c85087659543756ae61763e80a75"
_DECISION_SET = "p1-pushkin-cloud-20260728"
_COMMUNITY_ID = 235216998
_TARGET_ID = "-235216998_456239106"
_AFTER_GUARD = "sha256:3ddb0ec7988bc49115192083d5ad513a1d01d462cf3efe24c593a01ddee5cff5"
_COVERAGE_SHA = "sha256:94ef18173ade06658d421cbaeced7fdbada8d9766760adfee289df7bdbe3148e"
_MEMBERSHIPS_SHA = "sha256:bdb556321dce7b5dd9400de33c92fb186dce55faac327f0a5a077491bfd5b966"
_ALLOWED_STATUSES = frozenset({"updated_and_verified", "already_applied"})
_REQUIRED_FILES = frozenset(
    {
        "00-source-vk-snapshot.json",
        "01-preflight.txt",
        "02-apply.txt",
        "03-result.json",
        "04-final-vk-snapshot.json",
        "README.txt",
        "dry-run-verification.json",
        "manifest.json",
        "plan-review.html",
        "plan-review.md",
        "plan.json",
        "previous-reviewed-dry-run.zip",
        "reviewed-decisions.json",
        "source-review-bundle.zip",
    }
)
_OPTIONAL_FILES = frozenset({"05-independent-verification.json"})


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--json-output", type=Path)
    return parser


def _verify_previous_dry_run(raw_zip: bytes) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="vk-pushkin-cloud-dry-run-verify-") as temp_dir:
        path = Path(temp_dir) / "previous-reviewed-dry-run.zip"
        path.write_bytes(raw_zip)
        report = verify_dry_run_bundle(path)
    if report.get("status") != "verified_dry_run":
        raise ValueError("Previous Pushkin Cloud dry-run did not pass verification")
    if report.get("plan_sha256") != _PLAN_SHA:
        raise ValueError("Previous dry-run belongs to another plan")
    return report


def verify_bundle(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        names = [entry.filename for entry in archive.infolist()]
        if len(names) != len(set(names)):
            raise ValueError("Apply bundle contains duplicate ZIP entries")
        name_set = set(names)
        missing = sorted(_REQUIRED_FILES - name_set)
        if missing:
            raise ValueError("Bundle is missing required files: " + ", ".join(missing))
        unexpected = sorted(name_set - (_REQUIRED_FILES | _OPTIONAL_FILES))
        if unexpected:
            raise ValueError("Bundle contains unexpected files: " + ", ".join(unexpected))
        raw = {name: archive.read(name) for name in names}

    manifest = _json_bytes(raw["manifest.json"], name="manifest.json")
    plan = _json_bytes(raw["plan.json"], name="plan.json")
    decisions = _json_bytes(raw["reviewed-decisions.json"], name="reviewed-decisions.json")
    result = _json_bytes(raw["03-result.json"], name="03-result.json")
    source = _json_bytes(raw["00-source-vk-snapshot.json"], name="00-source-vk-snapshot.json")
    final = _json_bytes(raw["04-final-vk-snapshot.json"], name="04-final-vk-snapshot.json")
    _verify_manifest(raw, manifest)

    if manifest.get("status") != "completed":
        raise ValueError("Apply wrapper status is not completed")
    if manifest.get("mode") != "apply" or manifest.get("component_scope") != "descriptions_only":
        raise ValueError("Handoff is not a descriptions-only apply bundle")
    if manifest.get("correction_scope") != "reviewed_factual_and_sensitive":
        raise ValueError("Unexpected correction scope")
    if manifest.get("decision_set_id") != _DECISION_SET:
        raise ValueError("Wrong decision set")
    if int(manifest.get("community_id", 0)) != _COMMUNITY_ID:
        raise ValueError("Wrong community")
    if int(manifest.get("conflicts", -1)) != 0:
        raise ValueError("Apply handoff reports conflicts")
    if plan.get("plan_sha256") != _PLAN_SHA or manifest.get("plan_sha256") != _PLAN_SHA:
        raise ValueError("Apply handoff differs from reviewed plan")
    if plan.get("decisions_sha256") != _DECISIONS_SHA or plan.get("policy_sha256") != _DECISIONS_SHA:
        raise ValueError("Decisions digest differs")
    if plan.get("policy") != decisions:
        raise ValueError("Plan policy differs from reviewed decisions")
    if plan.get("decision_set_id") != _DECISION_SET or decisions.get("decision_set_id") != _DECISION_SET:
        raise ValueError("Decision set differs")
    if plan.get("target_video_ids_sha256") != _COVERAGE_SHA:
        raise ValueError("Video coverage differs")
    if plan.get("initial_memberships_sha256") != _MEMBERSHIPS_SHA:
        raise ValueError("Membership digest differs")

    summary = plan.get("summary") or {}
    if int(summary.get("descriptions_to_update", -1)) != 1 or int(summary.get("total_operations", -1)) != 1:
        raise ValueError("Plan must contain one description correction")
    for field in (
        "titles_to_update",
        "albums_to_rename",
        "placements_to_add",
        "placements_to_remove",
        "videos_to_delete",
        "review_only",
        "deferred_editorial_review",
    ):
        if int(summary.get(field, -1)) != 0:
            raise ValueError(f"Unexpected non-description scope: {field}")

    operations = plan.get("video_text_operations")
    if not isinstance(operations, list) or len(operations) != 1:
        raise ValueError("Plan must contain one video operation")
    operation = operations[0]
    if str(operation.get("target_video_id")) != _TARGET_ID:
        raise ValueError("Target ID differs")
    if operation.get("after_description_sha256") != _AFTER_GUARD:
        raise ValueError("Reviewed after-state guard differs")
    if operation.get("before_title") != operation.get("after_title"):
        raise ValueError("Reviewed operation changes title")
    if not bool(operation.get("reviewed_correction")):
        raise ValueError("Operation is not reviewed correction")

    if result.get("status") != "completed" or result.get("plan_sha256") != _PLAN_SHA:
        raise ValueError("Result journal does not confirm reviewed plan")
    if int(result.get("community_id", 0)) != _COMMUNITY_ID:
        raise ValueError("Result journal belongs to another community")
    result_operations = result.get("operations")
    if not isinstance(result_operations, list) or len(result_operations) != 1:
        raise ValueError("Result journal must contain one operation")
    result_operation = result_operations[0]
    if str(result_operation.get("remote_id")) != _TARGET_ID:
        raise ValueError("Result target differs")
    status = str(result_operation.get("status"))
    if status not in _ALLOWED_STATUSES:
        raise ValueError(f"Unexpected result status: {status}")
    statuses = Counter({status: 1})

    previous_report = _verify_previous_dry_run(raw["previous-reviewed-dry-run.zip"])
    expected_dry_run_sha = _file_sha256(raw["previous-reviewed-dry-run.zip"])
    if manifest.get("source_dry_run_bundle_sha256") not in {None, expected_dry_run_sha}:
        raise ValueError("Manifest source dry-run SHA-256 mismatch")

    source_videos = _video_map(source)
    final_videos = _video_map(final)
    if set(source_videos) != set(final_videos) or len(final_videos) != 111:
        raise ValueError("VK video inventory changed")
    if len(source.get("collections", [])) != 17 or len(final.get("collections", [])) != 17:
        raise ValueError("VK collection inventory changed")
    if len(source.get("memberships", [])) != 294 or len(final.get("memberships", [])) != 294:
        raise ValueError("VK membership inventory changed")

    mismatches: list[str] = []
    for remote_id, before_video in source_videos.items():
        after_video = final_videos[remote_id]
        if before_video.get("title") != after_video.get("title"):
            mismatches.append(f"{remote_id}: title changed")
        if remote_id == _TARGET_ID:
            if before_video.get("title") != operation.get("before_title"):
                mismatches.append(f"{remote_id}: source title differs")
            if before_video.get("description") != operation.get("before_description"):
                mismatches.append(f"{remote_id}: source description differs")
            if after_video.get("description") != operation.get("after_description"):
                mismatches.append(f"{remote_id}: final description differs")
        elif before_video.get("description") != after_video.get("description"):
            mismatches.append(f"{remote_id}: non-target description changed")
    if mismatches:
        raise ValueError("Final VK state verification failed: " + "; ".join(mismatches[:12]))

    if _collection_titles(source) != _collection_titles(final):
        raise ValueError("VK collection identities or titles changed")
    if Counter(_membership_identity_rows(source)) != Counter(_membership_identity_rows(final)):
        raise ValueError("VK membership identity changed")
    position_changes = _membership_position_changes(source, final)

    if _coverage_sha256(source) != _COVERAGE_SHA or _coverage_sha256(final) != _COVERAGE_SHA:
        raise ValueError("Video coverage SHA differs")
    if _membership_sha256(source) != _MEMBERSHIPS_SHA or _membership_sha256(final) != _MEMBERSHIPS_SHA:
        raise ValueError("Membership SHA differs")
    if result.get("initial_memberships_sha256") != _MEMBERSHIPS_SHA:
        raise ValueError("Result membership SHA differs")

    preflight = raw["01-preflight.txt"].decode("utf-8-sig")
    for required in (
        f"plan: {_PLAN_SHA}",
        f"video coverage: {_COVERAGE_SHA}",
        f"membership state: {_MEMBERSHIPS_SHA}",
        "conflicts: 0",
        "No VK mutation method was called",
    ):
        if required not in preflight:
            raise ValueError("Apply preflight is missing an exact guard")

    if "05-independent-verification.json" in raw:
        embedded = _json_bytes(raw["05-independent-verification.json"], name="05-independent-verification.json")
        if embedded.get("status") != "verified_completed" or embedded.get("plan_sha256") != _PLAN_SHA:
            raise ValueError("Embedded verification differs")

    return {
        "schema_name": "video-manager.vk-reviewed-correction-pushkin-cloud-apply-verification",
        "schema_version": 1,
        "status": "verified_completed",
        "bundle": str(path),
        "bundle_sha256": _file_sha256(path.read_bytes()),
        "wrapper_status": manifest.get("status"),
        "wrapper_error": manifest.get("error"),
        "decision_set_id": _DECISION_SET,
        "plan_sha256": _PLAN_SHA,
        "decisions_sha256": _DECISIONS_SHA,
        "community_id": _COMMUNITY_ID,
        "operations": 1,
        "operation_statuses": dict(statuses),
        "remote_writes": int(statuses.get("updated_and_verified", 0)),
        "target_video_ids": [_TARGET_ID],
        "videos": 111,
        "collections": 17,
        "memberships": 294,
        "video_coverage_sha256": _COVERAGE_SHA,
        "memberships_sha256": _MEMBERSHIPS_SHA,
        "non_target_videos_verified_unchanged": 110,
        "previous_dry_run_status": previous_report["status"],
        "membership_identity_unchanged": True,
        "membership_position_changes": position_changes,
        "warning": (
            "Membership position values changed while identity pairs remained stable."
            if position_changes
            else None
        ),
    }


def main() -> int:
    args = _parser().parse_args()
    try:
        report = verify_bundle(args.bundle)
    except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        report = {
            "schema_name": "video-manager.vk-reviewed-correction-pushkin-cloud-apply-verification",
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
