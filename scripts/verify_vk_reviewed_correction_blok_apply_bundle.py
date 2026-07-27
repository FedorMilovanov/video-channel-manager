#!/usr/bin/env python3
"""Independently verify a completed Blok correction apply handoff ZIP."""

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
from verify_vk_reviewed_correction_blok_dry_run import verify_bundle as verify_dry_run_bundle

_PLAN_SHA = "sha256:53bed1c056868731dcb1f9c04b8d3188fd4295baa5d14364b1f8b72187cea4fb"
_DECISIONS_SHA = "sha256:3b8e3f661d317a03483e568b90ef361de8bc325abe19d9d049076dd24b7f103e"
_DECISION_SET = "p1-blok-night-20260728"
_COMMUNITY_ID = 235216998
_TARGET_IDS = frozenset({"-235216998_456239120", "-235216998_456239126"})
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
_REQUIRED_FINAL_WORDING = (
    "датированным 10 октября",
    "Около каждого дома есть аптека",
    "спор о прототипе продолжается",
    "нескольких документированных версиях",
    "литературной интерпретацией",
    "разрешение для него было получено лишь 23 июля",
    "художественным и человеческим завещанием",
    "одно из самых узнаваемых и мрачных восьмистиший",
)
_FORBIDDEN_FINAL_WORDING = (
    "фиксирует почти точный момент рождения стихотворения",
    "которую из‑за частых самоубийств в этом районе называли «аптекой самоубийц»",
    "В «Страшном мире» всё прекрасное и духовное уничтожено",
    "последние недели он почти не приходил в сознание",
    "самое безысходное стихотворение Серебряного века",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--json-output", type=Path)
    return parser


def _verify_previous_dry_run(raw_zip: bytes) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="vk-blok-correction-dry-run-verify-") as temp_dir:
        path = Path(temp_dir) / "previous-reviewed-dry-run.zip"
        path.write_bytes(raw_zip)
        report = verify_dry_run_bundle(path)
    if report.get("status") != "verified_dry_run":
        raise ValueError("Previous Blok reviewed dry-run did not pass verification")
    if report.get("plan_sha256") != _PLAN_SHA:
        raise ValueError("Previous Blok dry-run belongs to another plan")
    if int(report.get("operations", -1)) != 2:
        raise ValueError("Previous Blok dry-run has an unexpected operation count")
    if set(report.get("target_video_ids") or []) != _TARGET_IDS:
        raise ValueError("Previous Blok dry-run targets another video set")
    return report


def _verify_plan_and_result(
    manifest: dict[str, Any],
    plan: dict[str, Any],
    decisions: dict[str, Any],
    result: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], Counter[str]]:
    if manifest.get("status") != "completed":
        raise ValueError("Apply handoff wrapper status is not completed")
    if manifest.get("mode") != "apply" or manifest.get("component_scope") != "descriptions_only":
        raise ValueError("Handoff is not a descriptions-only apply bundle")
    if manifest.get("correction_scope") != "reviewed_factual_and_sensitive":
        raise ValueError("Apply handoff has an unexpected correction scope")
    if manifest.get("decision_set_id") != _DECISION_SET:
        raise ValueError("Apply handoff belongs to another decision set")
    if int(manifest.get("community_id", 0)) != _COMMUNITY_ID:
        raise ValueError("Apply handoff targets another VK community")
    if int(manifest.get("conflicts", -1)) != 0:
        raise ValueError("Apply handoff reports conflicts")

    if plan.get("plan_sha256") != _PLAN_SHA or manifest.get("plan_sha256") != _PLAN_SHA:
        raise ValueError("Apply handoff differs from the reviewed Blok plan")
    if plan.get("decisions_sha256") != _DECISIONS_SHA or plan.get("policy_sha256") != _DECISIONS_SHA:
        raise ValueError("Apply plan decisions digest differs")
    if plan.get("policy") != decisions:
        raise ValueError("Plan policy differs from reviewed-decisions.json")
    if decisions.get("decision_set_id") != _DECISION_SET:
        raise ValueError("Reviewed decisions belong to another decision set")
    if plan.get("decision_set_id") != _DECISION_SET:
        raise ValueError("Plan belongs to another decision set")
    if plan.get("operation_scope") != "editorial_only":
        raise ValueError("Plan is not editorial_only")
    if plan.get("component_scope") != "descriptions_only":
        raise ValueError("Plan is not descriptions_only")
    if plan.get("correction_scope") != "reviewed_factual_and_sensitive":
        raise ValueError("Plan has an unexpected correction scope")
    if int(plan.get("target_community_id", 0)) != _COMMUNITY_ID:
        raise ValueError("Plan targets another VK community")
    if plan.get("album_title_operations"):
        raise ValueError("Blok correction plan contains album operations")

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
        raise ValueError("Plan must contain exactly two Blok description corrections")

    operations = plan.get("video_text_operations")
    if not isinstance(operations, list) or len(operations) != 2:
        raise ValueError("Plan must contain exactly two Blok video operations")
    operation_by_id = {str(item.get("target_video_id")): item for item in operations}
    if set(operation_by_id) != _TARGET_IDS:
        raise ValueError("Blok apply target IDs differ from the reviewed set")

    combined_after = "\n".join(str(item.get("after_description") or "") for item in operations)
    for required in _REQUIRED_FINAL_WORDING:
        if required not in combined_after:
            raise ValueError(f"Blok corrected descriptions are missing reviewed wording: {required}")
    for forbidden in _FORBIDDEN_FINAL_WORDING:
        if forbidden in combined_after:
            raise ValueError(f"Blok corrected descriptions retain forbidden wording: {forbidden}")

    if result.get("status") != "completed" or result.get("plan_sha256") != _PLAN_SHA:
        raise ValueError("Result journal does not confirm the reviewed Blok plan")
    if int(result.get("community_id", 0)) != _COMMUNITY_ID:
        raise ValueError("Result journal belongs to another VK community")
    result_operations = result.get("operations")
    if not isinstance(result_operations, list):
        raise ValueError("Result operations must be a list")
    statuses = Counter(str(item.get("status")) for item in result_operations if isinstance(item, dict))
    if sum(statuses.values()) != 2:
        raise ValueError("Result operation count differs from the plan")
    unexpected = sorted(set(statuses) - _ALLOWED_STATUSES)
    if unexpected:
        raise ValueError("Unexpected result operation statuses: " + ", ".join(unexpected))
    result_ids = {
        str(item.get("remote_id"))
        for item in result_operations
        if isinstance(item, dict) and item.get("remote_id") is not None
    }
    if result_ids != _TARGET_IDS:
        raise ValueError("Result operation IDs differ from the reviewed plan")
    return operation_by_id, statuses


def _verify_snapshots(
    source: dict[str, Any],
    final: dict[str, Any],
    operation_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    source_videos = _video_map(source)
    final_videos = _video_map(final)
    if set(source_videos) != set(final_videos) or len(final_videos) != 111:
        raise ValueError("VK video inventory changed during Blok correction")
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
        raise ValueError("Final VK state verification failed: " + "; ".join(mismatches[:12]))
    if _collection_titles(source) != _collection_titles(final):
        raise ValueError("VK album inventory or titles changed during Blok correction")
    if Counter(_membership_identity_rows(source)) != Counter(_membership_identity_rows(final)):
        raise ValueError("VK album memberships changed during Blok correction")
    return _membership_position_changes(source, final)


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

    operation_by_id, statuses = _verify_plan_and_result(manifest, plan, decisions, result)
    previous_report = _verify_previous_dry_run(raw["previous-reviewed-dry-run.zip"])
    expected_dry_run_sha = _file_sha256(raw["previous-reviewed-dry-run.zip"])
    if manifest.get("source_dry_run_bundle_sha256") not in {None, expected_dry_run_sha}:
        raise ValueError("Manifest source dry-run SHA-256 mismatch")

    position_changes = _verify_snapshots(source, final, operation_by_id)
    expected_coverage = plan.get("target_video_ids_sha256")
    if _coverage_sha256(source) != expected_coverage or _coverage_sha256(final) != expected_coverage:
        raise ValueError("Video coverage SHA-256 differs from the reviewed plan")
    expected_memberships = plan.get("initial_memberships_sha256")
    if _membership_sha256(source) != expected_memberships or _membership_sha256(final) != expected_memberships:
        raise ValueError("Membership SHA-256 differs from the reviewed plan")
    if result.get("initial_memberships_sha256") != expected_memberships:
        raise ValueError("Result membership SHA-256 differs from the reviewed plan")

    preflight = raw["01-preflight.txt"].decode("utf-8-sig")
    for required in (
        f"plan: {_PLAN_SHA}",
        f"video coverage: {expected_coverage}",
        f"membership state: {expected_memberships}",
        "conflicts: 0",
        "No VK mutation method was called",
    ):
        if required not in preflight:
            raise ValueError("Apply preflight is missing an exact guard")

    if "05-independent-verification.json" in raw:
        embedded = _json_bytes(raw["05-independent-verification.json"], name="05-independent-verification.json")
        if embedded.get("status") != "verified_completed" or embedded.get("plan_sha256") != _PLAN_SHA:
            raise ValueError("Embedded postflight verification differs")

    return {
        "schema_name": "video-manager.vk-reviewed-correction-blok-apply-verification",
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
        "operations": 2,
        "operation_statuses": dict(statuses),
        "remote_writes": int(statuses.get("updated_and_verified", 0)),
        "target_video_ids": sorted(_TARGET_IDS),
        "videos": 111,
        "collections": 17,
        "memberships": 294,
        "video_coverage_sha256": expected_coverage,
        "memberships_sha256": expected_memberships,
        "non_target_videos_verified_unchanged": 109,
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
            "schema_name": "video-manager.vk-reviewed-correction-blok-apply-verification",
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
