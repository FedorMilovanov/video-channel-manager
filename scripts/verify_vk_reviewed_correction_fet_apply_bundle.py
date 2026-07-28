#!/usr/bin/env python3
"""Independently verify the reviewed Fet correction apply handoff ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from verify_vk_reviewed_correction_fet_dry_run import verify_bundle as verify_dry_run_bundle

_TARGET_IDS = frozenset({"-235216998_456239127", "-235216998_456239143"})
_ALLOWED_OPERATION_STATUSES = frozenset({"updated_and_verified", "already_applied"})
_REQUIRED_FILES = frozenset(
    {
        "00-source-vk-snapshot.json",
        "01-preflight.txt",
        "02-apply.txt",
        "03-result.json",
        "04-final-vk-snapshot.json",
        "manifest.json",
        "plan-review.html",
        "plan-review.md",
        "plan.json",
        "previous-reviewed-dry-run.zip",
        "reviewed-decisions.json",
        "source-review-bundle.zip",
    }
)
_REQUIRED_FINAL_WORDING = (
    "датируется 1850 годом",
    "прямого авторского посвящения",
    "могло скрывать самоубийство",
    "другой поздний цикл 1882–1892 годов",
    "воспоминаниям секретаря Е. В. Кудрявцевой",
)
_FORBIDDEN_FINAL_WORDING = (
    "Фет посвятил его Марии Лазич",
    "Фет всю жизнь писал только ей",
    "Последнее стихотворение, посвящённое Марии Лазич, датировано 1892 годом",
    "единственной героиней любовной лирики на всю жизнь",
    "смерть наступила от сердечного приступа",
    "🎧 The Leg\n\n🎧 The Legendary Poet",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--json-output", type=Path)
    return parser


def _json_bytes(raw: bytes, *, name: str) -> dict[str, Any]:
    payload = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must contain a JSON object")
    return payload


def _canonical_sha256(value: Any) -> str:
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(rendered).hexdigest()}"


def _file_sha256(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _remote_id(item: dict[str, Any]) -> str:
    ref = item.get("ref")
    if not isinstance(ref, dict) or not ref.get("remote_id"):
        raise ValueError("Snapshot item has no remote_id")
    return str(ref["remote_id"])


def _video_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_remote_id(item): item for item in snapshot.get("videos", []) if isinstance(item, dict)}


def _coverage_sha256(snapshot: dict[str, Any]) -> str:
    return _canonical_sha256(sorted(_video_map(snapshot)))


def _membership_identity_rows(snapshot: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        (
            str(item["collection_ref"]["remote_id"]),
            str(item["video_ref"]["remote_id"]),
        )
        for item in snapshot.get("memberships", [])
        if isinstance(item, dict)
    ]


def _membership_positions(snapshot: dict[str, Any]) -> dict[tuple[str, str], int | None]:
    return {
        (
            str(item["collection_ref"]["remote_id"]),
            str(item["video_ref"]["remote_id"]),
        ): item.get("position")
        for item in snapshot.get("memberships", [])
        if isinstance(item, dict)
    }


def _membership_position_changes(source: dict[str, Any], final: dict[str, Any]) -> list[dict[str, Any]]:
    before = _membership_positions(source)
    after = _membership_positions(final)
    return [
        {
            "collection_id": collection_id,
            "video_id": video_id,
            "before_position": before[(collection_id, video_id)],
            "after_position": after[(collection_id, video_id)],
        }
        for collection_id, video_id in sorted(before.keys() & after.keys())
        if before[(collection_id, video_id)] != after[(collection_id, video_id)]
    ]


def _membership_sha256(snapshot: dict[str, Any]) -> str:
    return _canonical_sha256(sorted(_membership_identity_rows(snapshot)))


def _collection_titles(snapshot: dict[str, Any]) -> dict[str, str]:
    return {
        _remote_id(item): str(item.get("title") or "")
        for item in snapshot.get("collections", [])
        if isinstance(item, dict)
    }


def _verify_manifest(raw: dict[str, bytes], manifest: dict[str, Any]) -> None:
    records = {
        str(item["name"]): item for item in manifest.get("files", []) if isinstance(item, dict) and item.get("name")
    }
    missing_records = sorted((_REQUIRED_FILES - {"manifest.json"}) - records.keys())
    if missing_records:
        raise ValueError("Manifest is missing required file records: " + ", ".join(missing_records))
    issues: list[str] = []
    for name, record in records.items():
        content = raw.get(name)
        if content is None:
            issues.append(f"{name}: missing from ZIP")
            continue
        if int(record.get("size_bytes", -1)) != len(content):
            issues.append(f"{name}: size mismatch")
        if str(record.get("sha256")) != _file_sha256(content):
            issues.append(f"{name}: SHA-256 mismatch")
    if issues:
        raise ValueError("Bundle integrity failed: " + "; ".join(issues))


def _verify_previous_dry_run(raw_zip: bytes, plan_sha256: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="vk-fet-correction-dry-run-verify-") as temp_dir:
        path = Path(temp_dir) / "previous-reviewed-dry-run.zip"
        path.write_bytes(raw_zip)
        report = verify_dry_run_bundle(path)
    if report.get("status") != "verified_dry_run":
        raise ValueError("Previous Fet reviewed dry-run did not pass verification")
    if report.get("plan_sha256") != plan_sha256:
        raise ValueError("Previous Fet dry-run belongs to another plan")
    if int(report.get("operations", -1)) != 2:
        raise ValueError("Previous Fet dry-run has an unexpected operation count")
    if set(report.get("target_video_ids") or []) != _TARGET_IDS:
        raise ValueError("Previous Fet dry-run targets another video set")
    return report


def _verify_plan_and_result(
    manifest: dict[str, Any],
    plan: dict[str, Any],
    decisions: dict[str, Any],
    result: dict[str, Any],
) -> tuple[str, str, dict[str, dict[str, Any]], Counter[str]]:
    if manifest.get("mode") != "apply":
        raise ValueError("Handoff is not an apply bundle")
    if manifest.get("component_scope") != "descriptions_only":
        raise ValueError("Apply handoff is not descriptions_only")
    if manifest.get("correction_scope") != "reviewed_factual_and_sensitive":
        raise ValueError("Apply handoff has an unexpected correction scope")
    if manifest.get("decision_set_id") != "p1-fet-whisper-20260727":
        raise ValueError("Apply handoff belongs to another decision set")
    if int(manifest.get("community_id", 0)) != 235216998:
        raise ValueError("Apply handoff targets another VK community")
    if int(manifest.get("conflicts", -1)) != 0:
        raise ValueError("Apply handoff reports conflicts")

    plan_sha256 = _canonical_sha256({key: value for key, value in plan.items() if key != "plan_sha256"})
    if plan.get("plan_sha256") != plan_sha256:
        raise ValueError("Plan self-digest mismatch")
    if manifest.get("plan_sha256") != plan_sha256:
        raise ValueError("Manifest plan SHA-256 differs from plan.json")

    decisions_sha256 = _canonical_sha256(decisions)
    if plan.get("policy") != decisions:
        raise ValueError("Plan policy differs from reviewed-decisions.json")
    if plan.get("policy_sha256") != decisions_sha256:
        raise ValueError("Plan policy_sha256 mismatch")
    if plan.get("decisions_sha256") != decisions_sha256:
        raise ValueError("Plan decisions_sha256 mismatch")
    if decisions.get("decision_set_id") != "p1-fet-whisper-20260727":
        raise ValueError("Reviewed decisions belong to another decision set")

    if plan.get("operation_scope") != "editorial_only":
        raise ValueError("Plan is not editorial_only")
    if plan.get("component_scope") != "descriptions_only":
        raise ValueError("Plan is not descriptions_only")
    if plan.get("correction_scope") != "reviewed_factual_and_sensitive":
        raise ValueError("Plan has an unexpected correction_scope")
    if plan.get("decision_set_id") != "p1-fet-whisper-20260727":
        raise ValueError("Plan belongs to another decision set")
    if int(plan.get("target_community_id", 0)) != 235216998:
        raise ValueError("Plan targets another VK community")
    if plan.get("album_title_operations"):
        raise ValueError("Fet correction plan contains album operations")

    summary = plan.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Plan has no summary")
    zero_fields = (
        "titles_to_update",
        "albums_to_rename",
        "placements_to_add",
        "placements_to_remove",
        "videos_to_delete",
        "review_only",
        "deferred_editorial_review",
    )
    if any(int(summary.get(field, -1)) != 0 for field in zero_fields):
        raise ValueError("Plan contains non-reviewed or non-description scope")
    if (
        int(summary.get("video_text_operations", -1)) != 2
        or int(summary.get("descriptions_to_update", -1)) != 2
        or int(summary.get("total_operations", -1)) != 2
    ):
        raise ValueError("Plan must contain exactly two Fet description corrections")

    operations = plan.get("video_text_operations")
    if not isinstance(operations, list) or len(operations) != 2:
        raise ValueError("Plan must contain exactly two Fet video operations")
    operation_by_id = {str(item.get("target_video_id")): item for item in operations}
    if set(operation_by_id) != _TARGET_IDS:
        raise ValueError("Fet apply target IDs differ from the reviewed set")

    combined_after = "\n".join(str(item.get("after_description") or "") for item in operations)
    for required in _REQUIRED_FINAL_WORDING:
        if required not in combined_after:
            raise ValueError(f"Fet corrected descriptions are missing reviewed wording: {required}")
    for forbidden in _FORBIDDEN_FINAL_WORDING:
        if forbidden in combined_after:
            raise ValueError(f"Fet corrected descriptions retain forbidden wording: {forbidden}")

    if result.get("status") != "completed":
        raise ValueError("Result journal is not completed")
    if result.get("plan_sha256") != plan_sha256:
        raise ValueError("Result journal belongs to another plan")
    if int(result.get("community_id", 0)) != 235216998:
        raise ValueError("Result journal belongs to another VK community")
    result_operations = result.get("operations")
    if not isinstance(result_operations, list):
        raise ValueError("Result operations must be a list")
    statuses = Counter(str(item.get("status")) for item in result_operations if isinstance(item, dict))
    if sum(statuses.values()) != 2:
        raise ValueError("Result operation count differs from the Fet plan")
    unexpected_statuses = sorted(set(statuses) - _ALLOWED_OPERATION_STATUSES)
    if unexpected_statuses:
        raise ValueError("Unexpected result operation statuses: " + ", ".join(unexpected_statuses))
    result_ids = {
        str(item.get("remote_id"))
        for item in result_operations
        if isinstance(item, dict) and item.get("remote_id") is not None
    }
    if result_ids != _TARGET_IDS:
        raise ValueError("Result operation IDs differ from the reviewed Fet plan")
    return plan_sha256, decisions_sha256, operation_by_id, statuses


def _verify_snapshots(
    source: dict[str, Any],
    final: dict[str, Any],
    operation_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    source_videos = _video_map(source)
    final_videos = _video_map(final)
    if set(source_videos) != set(final_videos):
        raise ValueError("VK video inventory changed during Fet correction execution")
    if len(final_videos) != 111:
        raise ValueError("Final snapshot must contain exactly 111 videos")
    if len(source.get("collections", [])) != 17 or len(final.get("collections", [])) != 17:
        raise ValueError("VK collection inventory changed")
    if len(source.get("memberships", [])) != 294 or len(final.get("memberships", [])) != 294:
        raise ValueError("VK membership inventory changed")

    mismatches: list[str] = []
    for remote_id, before_video in source_videos.items():
        after_video = final_videos[remote_id]
        operation = operation_by_id.get(remote_id)
        if operation is None:
            if before_video.get("title") != after_video.get("title"):
                mismatches.append(f"{remote_id}: non-target title changed")
            if before_video.get("description") != after_video.get("description"):
                mismatches.append(f"{remote_id}: non-target description changed")
            continue
        if before_video.get("title") != operation.get("before_title"):
            mismatches.append(f"{remote_id}: source title differs from reviewed before-state")
        if before_video.get("description") != operation.get("before_description"):
            mismatches.append(f"{remote_id}: source description differs from reviewed before-state")
        if after_video.get("title") != operation.get("after_title"):
            mismatches.append(f"{remote_id}: final title differs from reviewed title")
        if before_video.get("title") != after_video.get("title"):
            mismatches.append(f"{remote_id}: title changed during correction")
        if after_video.get("description") != operation.get("after_description"):
            mismatches.append(f"{remote_id}: final description differs from reviewed after-state")
        if not bool(operation.get("reviewed_correction")):
            mismatches.append(f"{remote_id}: reviewed_correction is false")
    if mismatches:
        raise ValueError("Final Fet VK state verification failed: " + "; ".join(mismatches[:12]))

    final_target_text = "\n".join(str(final_videos[remote_id].get("description") or "") for remote_id in _TARGET_IDS)
    for required in _REQUIRED_FINAL_WORDING:
        if required not in final_target_text:
            raise ValueError(f"Final VK descriptions are missing reviewed Fet wording: {required}")
    for forbidden in _FORBIDDEN_FINAL_WORDING:
        if forbidden in final_target_text:
            raise ValueError(f"Final VK descriptions retain forbidden Fet wording: {forbidden}")

    if _collection_titles(source) != _collection_titles(final):
        raise ValueError("VK album inventory or titles changed during Fet correction")
    if Counter(_membership_identity_rows(source)) != Counter(_membership_identity_rows(final)):
        raise ValueError("VK album memberships changed during Fet correction")
    return _membership_position_changes(source, final)


def verify_bundle(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        missing = sorted(_REQUIRED_FILES - names)
        if missing:
            raise ValueError("Bundle is missing required files: " + ", ".join(missing))
        raw = {name: archive.read(name) for name in names}

    manifest = _json_bytes(raw["manifest.json"], name="manifest.json")
    plan = _json_bytes(raw["plan.json"], name="plan.json")
    decisions = _json_bytes(raw["reviewed-decisions.json"], name="reviewed-decisions.json")
    result = _json_bytes(raw["03-result.json"], name="03-result.json")
    source = _json_bytes(raw["00-source-vk-snapshot.json"], name="00-source-vk-snapshot.json")
    final = _json_bytes(raw["04-final-vk-snapshot.json"], name="04-final-vk-snapshot.json")
    _verify_manifest(raw, manifest)

    plan_sha256, decisions_sha256, operation_by_id, statuses = _verify_plan_and_result(
        manifest,
        plan,
        decisions,
        result,
    )
    previous_report = _verify_previous_dry_run(raw["previous-reviewed-dry-run.zip"], plan_sha256)
    expected_dry_run_sha = _file_sha256(raw["previous-reviewed-dry-run.zip"])
    if manifest.get("source_dry_run_bundle_sha256") not in {None, expected_dry_run_sha}:
        raise ValueError("Manifest source dry-run SHA-256 mismatch")

    position_changes = _verify_snapshots(source, final, operation_by_id)
    source_coverage = _coverage_sha256(source)
    final_coverage = _coverage_sha256(final)
    expected_coverage = plan.get("target_video_ids_sha256")
    if source_coverage != expected_coverage or final_coverage != expected_coverage:
        raise ValueError("Video coverage SHA-256 differs from the reviewed Fet plan")
    source_memberships = _membership_sha256(source)
    final_memberships = _membership_sha256(final)
    expected_memberships = plan.get("initial_memberships_sha256")
    if source_memberships != expected_memberships or final_memberships != expected_memberships:
        raise ValueError("Membership SHA-256 differs from the reviewed Fet plan")
    if result.get("initial_memberships_sha256") != expected_memberships:
        raise ValueError("Result membership SHA-256 differs from the reviewed Fet plan")

    preflight = raw["01-preflight.txt"].decode("utf-8-sig")
    for required in (
        f"plan: {plan_sha256}",
        f"video coverage: {expected_coverage}",
        f"membership state: {expected_memberships}",
        "conflicts: 0",
    ):
        if required not in preflight:
            raise ValueError("Fet apply preflight is missing an exact guard")
    if "No VK mutation method was called" not in preflight:
        raise ValueError("Fet apply preflight does not prove its read-only phase")

    if "05-independent-verification.json" in raw:
        embedded = _json_bytes(raw["05-independent-verification.json"], name="05-independent-verification.json")
        if embedded.get("status") != "verified_completed":
            raise ValueError("Embedded Fet postflight verification is not completed")
        if embedded.get("plan_sha256") != plan_sha256:
            raise ValueError("Embedded Fet postflight verification belongs to another plan")

    wrapper_status = str(manifest.get("status") or "unknown")
    return {
        "schema_name": "video-manager.vk-reviewed-correction-fet-apply-verification",
        "schema_version": 1,
        "status": "verified_completed",
        "bundle": str(path),
        "bundle_sha256": _file_sha256(path.read_bytes()),
        "wrapper_status": wrapper_status,
        "wrapper_error": manifest.get("error"),
        "decision_set_id": "p1-fet-whisper-20260727",
        "plan_sha256": plan_sha256,
        "decisions_sha256": decisions_sha256,
        "community_id": 235216998,
        "operations": 2,
        "operation_statuses": dict(sorted(statuses.items())),
        "remote_writes": statuses.get("updated_and_verified", 0),
        "target_video_ids": sorted(_TARGET_IDS),
        "videos": len(_video_map(final)),
        "collections": len(final.get("collections", [])),
        "memberships": len(final.get("memberships", [])),
        "video_coverage_sha256": final_coverage,
        "memberships_sha256": final_memberships,
        "non_target_videos_verified_unchanged": len(_video_map(final)) - len(_TARGET_IDS),
        "previous_dry_run_status": previous_report["status"],
        "membership_identity_unchanged": True,
        "membership_position_changes": position_changes,
        "warning": (
            "The outer wrapper reported failure after the authoritative result journal and final VK state "
            "were completed and verified. Membership identities are unchanged; position-only churn is "
            "recorded as read-order metadata."
            if wrapper_status != "completed"
            else (
                "Membership identities are unchanged; position-only churn is recorded as read-order metadata."
                if position_changes
                else None
            )
        ),
    }


def main() -> int:
    args = _parser().parse_args()
    try:
        report = verify_bundle(args.bundle)
    except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        report = {
            "schema_name": "video-manager.vk-reviewed-correction-fet-apply-verification",
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
