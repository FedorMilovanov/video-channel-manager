#!/usr/bin/env python3
"""Independently verify the reviewed Fet correction dry-run handoff ZIP."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

_TARGET_IDS = frozenset({"-235216998_456239127", "-235216998_456239143"})
_REPLACEMENT_IDS = frozenset(
    {
        "replace-short-fet-biography-and-attribution",
        "qualify-whisper-biographical-background",
        "attribute-lazich-death-and-cycle",
        "correct-late-love-cycle-and-fet-death",
        "remove-truncated-footer-fragment",
    }
)
_REQUIRED_FILES = frozenset(
    {
        "00-source-vk-snapshot.json",
        "01-preflight.txt",
        "README.txt",
        "manifest.json",
        "plan-review.html",
        "plan-review.md",
        "plan.json",
        "reviewed-decisions.json",
        "source-apply-verification.json",
        "source-review-bundle.zip",
    }
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


def _verify_source_review_bundle(raw_zip: bytes, expected_sha256: str) -> None:
    if _file_sha256(raw_zip) != expected_sha256:
        raise ValueError("Nested source review bundle SHA-256 mismatch")
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
        names = set(archive.namelist())
        required = {
            "manifest.json",
            "review-queue.json",
            "review-queue.md",
            "review-queue.html",
            "review-queue.csv",
            "README.txt",
        }
        missing = sorted(required - names)
        if missing:
            raise ValueError("Nested source review bundle is missing: " + ", ".join(missing))
        nested_raw = {name: archive.read(name) for name in names}
    manifest = _json_bytes(nested_raw["manifest.json"], name="nested manifest.json")
    queue = _json_bytes(nested_raw["review-queue.json"], name="review-queue.json")
    if manifest.get("status") != "review_only_completed":
        raise ValueError("Nested source review bundle is not completed")
    if queue.get("mode") != "review_only" or int(queue.get("remote_writes", -1)) != 0:
        raise ValueError("Nested source review bundle is not review-only")
    records = {
        str(item["name"]): item for item in manifest.get("files", []) if isinstance(item, dict) and item.get("name")
    }
    for name, record in records.items():
        content = nested_raw.get(name)
        if content is None:
            raise ValueError(f"Nested source review file is missing: {name}")
        if int(record.get("size_bytes", -1)) != len(content):
            raise ValueError(f"Nested source review size mismatch: {name}")
        if str(record.get("sha256")) != _file_sha256(content):
            raise ValueError(f"Nested source review SHA-256 mismatch: {name}")


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
    snapshot = _json_bytes(raw["00-source-vk-snapshot.json"], name="00-source-vk-snapshot.json")
    source_apply = _json_bytes(raw["source-apply-verification.json"], name="source-apply-verification.json")
    _verify_manifest(raw, manifest)

    if manifest.get("status") != "completed" or manifest.get("mode") != "dry-run":
        raise ValueError("Handoff is not a completed dry-run")
    if manifest.get("component_scope") != "descriptions_only":
        raise ValueError("Handoff is not descriptions_only")
    if manifest.get("decision_set_id") != "p1-fet-whisper-20260727":
        raise ValueError("Handoff has another decision set")
    if int(manifest.get("community_id", 0)) != 235216998:
        raise ValueError("Handoff targets another VK community")
    if (
        int(manifest.get("ready", -1)) != 2
        or int(manifest.get("already_applied", -1)) != 0
        or int(manifest.get("conflicts", -1)) != 0
        or int(manifest.get("remote_writes", -1)) != 0
    ):
        raise ValueError("Unexpected dry-run counts or remote_writes")

    expected_plan_sha = _canonical_sha256({key: value for key, value in plan.items() if key != "plan_sha256"})
    if plan.get("plan_sha256") != expected_plan_sha:
        raise ValueError("Plan self-digest mismatch")
    if manifest.get("plan_sha256") != expected_plan_sha:
        raise ValueError("Manifest plan SHA-256 differs from plan.json")
    if plan.get("policy") != decisions:
        raise ValueError("Plan policy differs from reviewed-decisions.json")
    decisions_sha256 = _canonical_sha256(decisions)
    if plan.get("policy_sha256") != decisions_sha256:
        raise ValueError("Plan policy_sha256 mismatch")
    if plan.get("decisions_sha256") != decisions_sha256:
        raise ValueError("Plan decisions_sha256 mismatch")

    if plan.get("operation_scope") != "editorial_only":
        raise ValueError("Plan is not editorial_only")
    if plan.get("component_scope") != "descriptions_only":
        raise ValueError("Plan is not descriptions_only")
    if plan.get("correction_scope") != "reviewed_factual_and_sensitive":
        raise ValueError("Plan has an unexpected correction_scope")
    if plan.get("decision_set_id") != "p1-fet-whisper-20260727":
        raise ValueError("Plan has another decision set")
    if int(plan.get("target_community_id", 0)) != 235216998:
        raise ValueError("Plan targets another VK community")
    if plan.get("album_title_operations"):
        raise ValueError("Fet correction plan contains album operations")

    summary = plan.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Plan has no summary")
    if (
        int(summary.get("video_text_operations", -1)) != 2
        or int(summary.get("descriptions_to_update", -1)) != 2
        or int(summary.get("total_operations", -1)) != 2
        or int(summary.get("titles_to_update", -1)) != 0
        or int(summary.get("albums_to_rename", -1)) != 0
        or int(summary.get("placements_to_add", -1)) != 0
        or int(summary.get("placements_to_remove", -1)) != 0
        or int(summary.get("videos_to_delete", -1)) != 0
    ):
        raise ValueError("Plan summary has unexpected scope")

    if source_apply.get("status") != "verified_completed":
        raise ValueError("Source apply verification is not completed")
    if int(source_apply.get("operations", -1)) != 3:
        raise ValueError("Source apply verification has unexpected operation count")
    if int(source_apply.get("non_target_videos_verified_unchanged", -1)) != 108:
        raise ValueError("Source apply did not verify the remaining 108 videos")

    videos = {_remote_id(item): item for item in snapshot.get("videos", []) if isinstance(item, dict)}
    if len(videos) != 111:
        raise ValueError("Source snapshot must contain exactly 111 videos")
    if len(snapshot.get("collections", [])) != 17:
        raise ValueError("Source snapshot must contain exactly 17 collections")
    if len(snapshot.get("memberships", [])) != 294:
        raise ValueError("Source snapshot must contain exactly 294 memberships")

    operations = plan.get("video_text_operations")
    if not isinstance(operations, list) or len(operations) != 2:
        raise ValueError("Plan must contain exactly two operations")
    operation_by_id = {str(item.get("target_video_id")): item for item in operations}
    if set(operation_by_id) != _TARGET_IDS:
        raise ValueError("Fet correction target IDs differ from the reviewed set")

    replacement_ids = {
        str(item.get("replacement_id")) for item in decisions.get("shared_replacements", []) if isinstance(item, dict)
    }
    if replacement_ids != _REPLACEMENT_IDS:
        raise ValueError("Fet replacement IDs differ from the reviewed set")

    for remote_id, operation in operation_by_id.items():
        source_video = videos.get(remote_id)
        if source_video is None:
            raise ValueError(f"Fet target is absent from snapshot: {remote_id}")
        if operation.get("before_title") != operation.get("after_title"):
            raise ValueError(f"Title changes in Fet operation: {remote_id}")
        if bool(operation.get("title_changed")):
            raise ValueError(f"title_changed is true: {remote_id}")
        if not bool(operation.get("description_changed")):
            raise ValueError(f"description_changed is false: {remote_id}")
        if source_video.get("title") != operation.get("before_title"):
            raise ValueError(f"Source title differs from guarded title: {remote_id}")
        if source_video.get("description") != operation.get("before_description"):
            raise ValueError(f"Source description differs from guarded description: {remote_id}")
        after_description = str(operation.get("after_description") or "")
        if not after_description or len(after_description) > 5000:
            raise ValueError(f"Invalid corrected description length: {remote_id}")

    combined_after = "\n".join(str(operation["after_description"]) for operation in operation_by_id.values())
    for required in (
        "датируется 1850 годом",
        "прямого авторского посвящения",
        "могло скрывать самоубийство",
        "другой поздний цикл 1882–1892 годов",
        "воспоминаниям секретаря Е. В. Кудрявцевой",
    ):
        if required not in combined_after:
            raise ValueError(f"Corrected descriptions are missing reviewed wording: {required}")
    for forbidden in (
        "Фет посвятил его Марии Лазич",
        "Фет всю жизнь писал только ей",
        "Последнее стихотворение, посвящённое Марии Лазич, датировано 1892 годом",
        "единственной героиней любовной лирики на всю жизнь",
        "смерть наступила от сердечного приступа",
        "🎧 The Leg\n\n🎧 The Legendary Poet",
    ):
        if forbidden in combined_after:
            raise ValueError(f"Corrected descriptions retain forbidden wording: {forbidden}")

    expected_review_sha = str(decisions.get("source_review_bundle_sha256") or "")
    _verify_source_review_bundle(raw["source-review-bundle.zip"], expected_review_sha)
    if manifest.get("source_review_bundle_sha256") != expected_review_sha:
        raise ValueError("Manifest source review bundle SHA-256 mismatch")

    preflight = raw["01-preflight.txt"].decode("utf-8-sig")
    for required in (
        f"plan: {expected_plan_sha}",
        "ready: 2",
        "already applied: 0",
        "conflicts: 0",
        "No VK mutation method was called",
    ):
        if required not in preflight:
            raise ValueError(f"Preflight is missing exact evidence: {required}")

    return {
        "schema_name": "video-manager.vk-reviewed-correction-fet-dry-run-verification",
        "schema_version": 1,
        "status": "verified_dry_run",
        "bundle": str(path),
        "bundle_sha256": _file_sha256(path.read_bytes()),
        "plan_sha256": expected_plan_sha,
        "decisions_sha256": decisions_sha256,
        "community_id": 235216998,
        "operations": 2,
        "target_video_ids": sorted(_TARGET_IDS),
        "videos": 111,
        "collections": 17,
        "memberships": 294,
        "remote_writes": 0,
        "source_apply_status": source_apply["status"],
    }


def main() -> int:
    args = _parser().parse_args()
    try:
        report = verify_bundle(args.bundle)
    except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        report = {
            "schema_name": "video-manager.vk-reviewed-correction-fet-dry-run-verification",
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
