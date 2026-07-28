#!/usr/bin/env python3
"""Independently verify a VK descriptions-only apply handoff ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.editorial_cleanup_plan import (
    membership_state_sha256,
    target_video_ids_sha256,
    validate_vk_editorial_cleanup_plan,
)
from video_channel_manager.platforms.vk.text_writer import vk_texts_equivalent

_REQUIRED_FILES = frozenset(
    {
        "00-source-vk-snapshot.json",
        "03-result.json",
        "04-final-vk-snapshot.json",
        "manifest.json",
        "plan.json",
    }
)
_ALLOWED_OPERATION_STATUSES = frozenset({"updated_and_verified", "already_applied"})


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--json-output", type=Path)
    return parser


def _json_bytes(raw: bytes, *, name: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot decode {name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must contain a JSON object")
    return payload


def _remote_id(item: Any) -> str:
    return str(item.ref.remote_id)


def _membership_rows(package: AuditPackage) -> list[tuple[str, str, int | None, str | None]]:
    return [
        (
            str(item.collection_ref.remote_id),
            str(item.video_ref.remote_id),
            item.position,
            item.membership_id,
        )
        for item in package.memberships
    ]


def verify_bundle(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        missing = sorted(_REQUIRED_FILES - names)
        if missing:
            raise ValueError(f"Bundle is missing required files: {', '.join(missing)}")
        raw = {name: archive.read(name) for name in names}

    manifest = _json_bytes(raw["manifest.json"], name="manifest.json")
    plan = _json_bytes(raw["plan.json"], name="plan.json")
    result = _json_bytes(raw["03-result.json"], name="03-result.json")
    source_payload = _json_bytes(raw["00-source-vk-snapshot.json"], name="00-source-vk-snapshot.json")
    final_payload = _json_bytes(raw["04-final-vk-snapshot.json"], name="04-final-vk-snapshot.json")

    manifest_files = {
        str(item["name"]): item for item in manifest.get("files", []) if isinstance(item, dict) and "name" in item
    }
    integrity_issues: list[str] = []
    for name, item in manifest_files.items():
        content = raw.get(name)
        if content is None:
            integrity_issues.append(f"{name}: missing from ZIP")
            continue
        expected_size = item.get("size_bytes")
        if expected_size != len(content):
            integrity_issues.append(f"{name}: size mismatch")
        expected_sha = item.get("sha256")
        actual_sha = f"sha256:{hashlib.sha256(content).hexdigest()}"
        if expected_sha != actual_sha:
            integrity_issues.append(f"{name}: SHA-256 mismatch")
    if integrity_issues:
        raise ValueError("Bundle integrity failed: " + "; ".join(integrity_issues))

    validate_vk_editorial_cleanup_plan(plan)
    source = AuditPackage.model_validate(source_payload)
    final = AuditPackage.model_validate(final_payload)

    if result.get("status") != "completed":
        raise ValueError("Result journal is not completed")
    if result.get("plan_sha256") != plan.get("plan_sha256"):
        raise ValueError("Result journal belongs to another plan")
    if result.get("community_id") != plan.get("target_community_id"):
        raise ValueError("Result journal belongs to another VK community")

    operations = plan.get("video_text_operations")
    if not isinstance(operations, list):
        raise ValueError("Plan video_text_operations must be a list")
    operation_by_id = {str(item["target_video_id"]): item for item in operations}
    if len(operation_by_id) != len(operations):
        raise ValueError("Plan contains duplicate target video IDs")

    result_operations = result.get("operations")
    if not isinstance(result_operations, list):
        raise ValueError("Result operations must be a list")
    result_statuses = Counter(str(item.get("status")) for item in result_operations if isinstance(item, dict))
    if sum(result_statuses.values()) != len(operations):
        raise ValueError("Result operation count differs from the plan")
    unexpected_statuses = sorted(set(result_statuses) - _ALLOWED_OPERATION_STATUSES)
    if unexpected_statuses:
        raise ValueError(f"Unexpected result statuses: {', '.join(unexpected_statuses)}")
    result_ids = {
        str(item.get("remote_id"))
        for item in result_operations
        if isinstance(item, dict) and item.get("remote_id") is not None
    }
    if result_ids != set(operation_by_id):
        raise ValueError("Result operation IDs differ from the plan")

    source_videos = {_remote_id(item): item for item in source.videos}
    final_videos = {_remote_id(item): item for item in final.videos}
    if set(source_videos) != set(final_videos):
        raise ValueError("VK video inventory changed during the description wave")
    if set(final_videos) != set(operation_by_id):
        raise ValueError("Final video coverage differs from the reviewed plan")

    mismatches: list[str] = []
    for remote_id, operation in operation_by_id.items():
        before = source_videos[remote_id]
        after = final_videos[remote_id]
        if before.title != operation.get("before_title"):
            mismatches.append(f"{remote_id}: source title differs from reviewed before-title")
        if after.title != operation.get("after_title"):
            mismatches.append(f"{remote_id}: final title differs from reviewed after-title")
        if before.title != after.title:
            mismatches.append(f"{remote_id}: title changed during descriptions-only execution")
        if not vk_texts_equivalent(before.description, str(operation.get("before_description", ""))):
            mismatches.append(f"{remote_id}: source description differs from reviewed before-state")
        if after.description != operation.get("after_description"):
            mismatches.append(f"{remote_id}: final description differs from reviewed after-state")
        if not bool(operation.get("semantic_body_preserved")):
            mismatches.append(f"{remote_id}: semantic-body guard is false")
    if mismatches:
        raise ValueError("Final VK state verification failed: " + "; ".join(mismatches[:10]))

    source_collection_titles = {_remote_id(item): item.title for item in source.collections}
    final_collection_titles = {_remote_id(item): item.title for item in final.collections}
    if source_collection_titles != final_collection_titles:
        raise ValueError("VK album inventory or titles changed during the description wave")
    if _membership_rows(source) != _membership_rows(final):
        raise ValueError("VK album memberships changed during the description wave")

    source_coverage = target_video_ids_sha256(source)
    final_coverage = target_video_ids_sha256(final)
    expected_coverage = plan.get("target_video_ids_sha256")
    if source_coverage != expected_coverage or final_coverage != expected_coverage:
        raise ValueError("Video coverage SHA-256 differs from the reviewed plan")

    source_memberships = membership_state_sha256(source)
    final_memberships = membership_state_sha256(final)
    expected_memberships = plan.get("initial_memberships_sha256")
    if source_memberships != expected_memberships or final_memberships != expected_memberships:
        raise ValueError("Membership SHA-256 differs from the reviewed plan")
    if result.get("initial_memberships_sha256") != expected_memberships:
        raise ValueError("Result membership SHA-256 differs from the reviewed plan")

    wrapper_status = str(manifest.get("status") or "unknown")
    wrapper_error = manifest.get("error")
    return {
        "schema_name": "video-manager.vk-description-apply-verification",
        "schema_version": 1,
        "status": "verified_completed",
        "bundle": str(path),
        "wrapper_status": wrapper_status,
        "wrapper_error": wrapper_error,
        "plan_sha256": plan["plan_sha256"],
        "community_id": plan["target_community_id"],
        "operations": len(operations),
        "operation_statuses": dict(sorted(result_statuses.items())),
        "videos": len(final.videos),
        "collections": len(final.collections),
        "memberships": len(final.memberships),
        "video_coverage_sha256": final_coverage,
        "memberships_sha256": final_memberships,
        "warning": (
            "The outer wrapper reported failure after the authoritative result journal and final VK state "
            "were already completed and verified."
            if wrapper_status != "completed"
            else None
        ),
    }


def main() -> int:
    args = _parser().parse_args()
    try:
        report = verify_bundle(args.bundle)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        report = {
            "schema_name": "video-manager.vk-description-apply-verification",
            "schema_version": 1,
            "status": "verification_failed",
            "bundle": str(args.bundle),
            "error": str(exc),
        }
        exit_code = 2
    else:
        exit_code = 0

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(rendered, end="")
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered, encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
