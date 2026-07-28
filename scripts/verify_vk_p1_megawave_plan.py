#!/usr/bin/env python3
"""Independently verify the deterministic VK P1 megawave decisions and plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.catalog import canonical_sha256
from video_channel_manager.platforms.vk.editorial_correction_wave import build_vk_reviewed_correction_wave
from video_channel_manager.platforms.vk.editorial_megawave import build_vk_p1_megawave_decisions

_URL_RE = re.compile(r"https?://[^\s]+")
_HASHTAG_RE = re.compile(r"(?<!\w)#[\wА-Яа-яЁё]+")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_snapshot", type=Path)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--review-bundle", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--json-output", type=Path)
    return parser


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _audit(path: Path) -> AuditPackage:
    try:
        return AuditPackage.model_validate(json.loads(path.read_text(encoding="utf-8-sig")))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Cannot load AuditPackage {path}: {exc}") from exc


def _file_sha(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _queue(path: Path, policy: dict[str, Any]) -> dict[str, Any]:
    if _file_sha(path) != str(policy.get("source_review_bundle_sha256") or ""):
        raise ValueError("Review bundle SHA differs from policy")
    with zipfile.ZipFile(path) as archive:
        names = [entry.filename for entry in archive.infolist()]
        if len(names) != len(set(names)):
            raise ValueError("Review bundle contains duplicate entries")
        manifest = json.loads(archive.read("manifest.json").decode("utf-8-sig"))
        queue = json.loads(archive.read("review-queue.json").decode("utf-8-sig"))
        records = {
            str(item.get("name")): item
            for item in manifest.get("files", [])
            if isinstance(item, dict) and item.get("name")
        }
        for name, record in records.items():
            raw = archive.read(name)
            if len(raw) != int(record.get("size_bytes", -1)):
                raise ValueError(f"Review member size mismatch: {name}")
            digest = f"sha256:{hashlib.sha256(raw).hexdigest()}"
            if digest != str(record.get("sha256") or ""):
                raise ValueError(f"Review member digest mismatch: {name}")
    if manifest.get("status") != "review_only_completed" or int(manifest.get("remote_writes", -1)) != 0:
        raise ValueError("Review manifest is not completed read-only")
    if queue.get("mode") != "review_only" or int(queue.get("remote_writes", -1)) != 0:
        raise ValueError("Review queue is not read-only")
    return queue


def verify(
    source_snapshot: Path,
    policy_path: Path,
    review_bundle: Path,
    decisions_path: Path,
    plan_path: Path,
) -> dict[str, Any]:
    policy = _json(policy_path)
    source = _audit(source_snapshot)
    queue = _queue(review_bundle, policy)
    decisions = _json(decisions_path)
    plan = _json(plan_path)

    expected_decisions = build_vk_p1_megawave_decisions(source, queue, policy)
    if canonical_sha256(decisions) != canonical_sha256(expected_decisions) or decisions != expected_decisions:
        raise ValueError("Megawave decisions differ from deterministic reconstruction")

    expected_plan = build_vk_reviewed_correction_wave(
        source,
        expected_decisions,
        source_review_bundle_sha256=_file_sha(review_bundle),
    )
    if canonical_sha256(plan) != canonical_sha256(expected_plan) or plan != expected_plan:
        raise ValueError("Megawave plan differs from deterministic reconstruction")

    summary = plan.get("summary") or {}
    if int(summary.get("descriptions_to_update", -1)) != 42 or int(summary.get("total_operations", -1)) != 42:
        raise ValueError("Megawave plan must contain exactly 42 description operations")
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
            raise ValueError(f"Megawave plan has unexpected scope: {field}")

    expected_ids = [str(item["video_id"]) for item in policy["targets"]]
    operations = plan.get("video_text_operations")
    if not isinstance(operations, list) or len(operations) != 42:
        raise ValueError("Megawave plan operation list differs")
    operation_ids = [str(item.get("target_video_id")) for item in operations]
    if set(operation_ids) != set(expected_ids) or len(set(operation_ids)) != 42:
        raise ValueError("Megawave target coverage differs")

    after_hashes: set[str] = set()
    for operation in operations:
        if operation.get("before_title") != operation.get("after_title"):
            raise ValueError("Megawave operation changes a title")
        before = str(operation.get("before_description") or "")
        after = str(operation.get("after_description") or "")
        if _URL_RE.findall(before) != _URL_RE.findall(after):
            raise ValueError(f"URLs changed: {operation.get('target_video_id')}")
        if _HASHTAG_RE.findall(before) != _HASHTAG_RE.findall(after):
            raise ValueError(f"Hashtags changed: {operation.get('target_video_id')}")
        if len(after) > 5000:
            raise ValueError(f"After description exceeds 5000: {operation.get('target_video_id')}")
        if not operation.get("reviewed_correction"):
            raise ValueError("Megawave operation is not a reviewed correction")
        after_hashes.add(str(operation.get("after_description_sha256") or ""))

    if len(after_hashes) != 37:
        raise ValueError("Megawave must contain exactly 37 unique rewritten descriptions")

    return {
        "schema_name": "video-manager.vk-p1-megawave-plan-verification",
        "schema_version": 1,
        "status": "verified_plan",
        "decision_set_id": decisions["decision_set_id"],
        "policy_sha256": canonical_sha256(policy),
        "decisions_sha256": canonical_sha256(decisions),
        "plan_sha256": plan["plan_sha256"],
        "review_bundle_sha256": _file_sha(review_bundle),
        "targets": 42,
        "unique_descriptions": 37,
        "videos": 111,
        "collections": len(source.collections),
        "memberships": len(source.memberships),
        "titles_changed": 0,
        "remote_writes": 0,
        "urls_and_hashtags_unchanged": True,
        "deterministic_reconstruction": True,
    }


def main() -> int:
    args = _parser().parse_args()
    try:
        report = verify(
            args.source_snapshot,
            args.policy,
            args.review_bundle,
            args.decisions,
            args.plan,
        )
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        report = {
            "schema_name": "video-manager.vk-p1-megawave-plan-verification",
            "schema_version": 1,
            "status": "verification_failed",
            "error": str(exc),
        }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.json_output:
        args.json_output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report.get("status") == "verified_plan" else 1


if __name__ == "__main__":
    raise SystemExit(main())
