#!/usr/bin/env python3
"""Independently verify a reviewed VK correction dry-run handoff ZIP."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

_TARGET_IDS = frozenset(
    {
        "-235216998_456239046",
        "-235216998_456239047",
        "-235216998_456239050",
    }
)
_REPLACEMENT_IDS = frozenset(
    {
        "align-yesenin-spiritual-verdict-with-site-standard",
        "correct-academic-date",
    }
)
_STANCE_SOURCE_IDS = frozenset(
    {
        "site-project-charter",
        "site-theological-guidelines",
        "site-editorial-judgment-policy",
        "site-yesenin-profile",
        "research-religious-heart",
        "research-false-peace",
    }
)
_REQUIRED_FILES = frozenset(
    {
        "00-source-vk-snapshot.json",
        "01-preflight.txt",
        "manifest.json",
        "plan-review.html",
        "plan-review.md",
        "plan.json",
        "README.txt",
        "reviewed-decisions.json",
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


def _coverage_sha256(snapshot: dict[str, Any]) -> str:
    ids = sorted(
        _remote_id(item)
        for item in snapshot.get("videos", [])
        if isinstance(item, dict)
    )
    return _canonical_sha256(ids)


def _membership_sha256(snapshot: dict[str, Any]) -> str:
    rows = sorted(
        (
            str(item["collection_ref"]["remote_id"]),
            str(item["video_ref"]["remote_id"]),
        )
        for item in snapshot.get("memberships", [])
        if isinstance(item, dict)
    )
    return _canonical_sha256(rows)


def _verify_manifest(raw: dict[str, bytes], manifest: dict[str, Any]) -> None:
    records = {
        str(item["name"]): item
        for item in manifest.get("files", [])
        if isinstance(item, dict) and item.get("name")
    }
    missing_records = sorted((_REQUIRED_FILES - {"manifest.json"}) - records.keys())
    if missing_records:
        raise ValueError(
            "Manifest is missing required file records: " + ", ".join(missing_records)
        )
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


def _verify_source_review_bundle(raw_zip: bytes, expected_sha256: str) -> dict[str, Any]:
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
            raise ValueError(
                "Nested source review bundle is missing: " + ", ".join(missing)
            )
        nested_raw = {name: archive.read(name) for name in names}
    manifest = _json_bytes(nested_raw["manifest.json"], name="nested manifest.json")
    queue = _json_bytes(nested_raw["review-queue.json"], name="review-queue.json")
    if manifest.get("status") != "review_only_completed":
        raise ValueError("Nested source review bundle is not completed")
    if queue.get("mode") != "review_only" or int(queue.get("remote_writes", -1)) != 0:
        raise ValueError("Nested source review bundle is not review-only")
    records = {
        str(item["name"]): item
        for item in manifest.get("files", [])
        if isinstance(item, dict) and item.get("name")
    }
    for name, record in records.items():
        content = nested_raw.get(name)
        if content is None:
            raise ValueError(f"Nested source review file is missing: {name}")
        if int(record.get("size_bytes", -1)) != len(content):
            raise ValueError(f"Nested source review size mismatch: {name}")
        if str(record.get("sha256")) != _file_sha256(content):
            raise ValueError(f"Nested source review SHA-256 mismatch: {name}")
    return queue


def _verify_editorial_profile(plan: dict[str, Any]) -> None:
    profile = plan.get("editorial_profile")
    if not isinstance(profile, dict):
        raise ValueError("Plan has no editorial_profile")
    expected = {
        "profile_id": "the-legendary-poet-historical-evangelical-v1",
        "judgment_mode": "asymmetric_evidence_based",
        "last_hour_rule": "acknowledge_once_not_equal_to_documented_life",
        "tone": "sorrow_without_sentimental_acquittal_or_gloating",
        "gospel_call": "repent_and_believe_in_christ",
    }
    for field, value in expected.items():
        if profile.get(field) != value:
            raise ValueError(f"Unexpected editorial_profile.{field}")
    principles = {str(value) for value in profile.get("principles", [])}
    required_principles = {
        "judge_public_confession_and_stable_fruits_by_scripture",
        "do_not_invent_last_hour_conversion",
        "do_not_balance_documented_unbelief_with_bare_possibility",
        "state_eternal_danger_plainly_when_evidence_is_strong",
        "speak_with_grief_not_superiority",
    }
    if not required_principles <= principles:
        raise ValueError("Editorial profile is missing required principles")
    stance_sources = {str(value) for value in plan.get("stance_source_ids", [])}
    if not _STANCE_SOURCE_IDS <= stance_sources:
        raise ValueError("Plan is missing required site or Research stance sources")


def verify_bundle(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        missing = sorted(_REQUIRED_FILES - names)
        if missing:
            raise ValueError("Bundle is missing required files: " + ", ".join(missing))
        raw = {name: archive.read(name) for name in names}

    manifest = _json_bytes(raw["manifest.json"], name="manifest.json")
    plan = _json_bytes(raw["plan.json"], name="plan.json")
    decisions = _json_bytes(
        raw["reviewed-decisions.json"], name="reviewed-decisions.json"
    )
    snapshot = _json_bytes(
        raw["00-source-vk-snapshot.json"], name="00-source-vk-snapshot.json"
    )
    _verify_manifest(raw, manifest)

    if manifest.get("status") != "completed" or manifest.get("mode") != "dry-run":
        raise ValueError("Handoff is not a completed dry-run")
    if manifest.get("component_scope") != "descriptions_only":
        raise ValueError("Handoff is not descriptions_only")
    if manifest.get("correction_scope") != "reviewed_factual_and_sensitive":
        raise ValueError("Unexpected correction scope")
    if int(manifest.get("community_id", 0)) != 235216998:
        raise ValueError("Handoff targets another VK community")
    if (
        int(manifest.get("ready", -1)) != 3
        or int(manifest.get("already_applied", -1)) != 0
        or int(manifest.get("conflicts", -1)) != 0
        or int(manifest.get("remote_writes", -1)) != 0
    ):
        raise ValueError("Unexpected dry-run preflight counts or remote_writes")

    expected_plan_sha = _canonical_sha256(
        {key: value for key, value in plan.items() if key != "plan_sha256"}
    )
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
    if int(plan.get("target_community_id", 0)) != 235216998:
        raise ValueError("Plan targets another VK community")
    _verify_editorial_profile(plan)

    summary = plan.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Plan has no summary")
    expected_summary = {
        "video_text_operations": 3,
        "titles_to_update": 0,
        "descriptions_to_update": 3,
        "albums_to_rename": 0,
        "placements_to_add": 0,
        "placements_to_remove": 0,
        "videos_to_delete": 0,
        "review_only": 0,
        "deferred_editorial_review": 0,
        "total_operations": 3,
    }
    for field, value in expected_summary.items():
        if int(summary.get(field, -1)) != value:
            raise ValueError(f"Unexpected plan summary field: {field}")
    if plan.get("album_title_operations"):
        raise ValueError("Correction plan contains album operations")

    videos = {
        _remote_id(item): item
        for item in snapshot.get("videos", [])
        if isinstance(item, dict)
    }
    if len(videos) != 111:
        raise ValueError("Source snapshot must contain exactly 111 videos")
    if len(snapshot.get("collections", [])) != 17:
        raise ValueError("Source snapshot must contain exactly 17 collections")
    if len(snapshot.get("memberships", [])) != 294:
        raise ValueError("Source snapshot must contain exactly 294 memberships")
    coverage = _coverage_sha256(snapshot)
    memberships = _membership_sha256(snapshot)
    if plan.get("target_video_ids_sha256") != coverage:
        raise ValueError("Source video coverage differs from the plan")
    if plan.get("initial_memberships_sha256") != memberships:
        raise ValueError("Source membership state differs from the plan")

    operations = plan.get("video_text_operations")
    if not isinstance(operations, list) or len(operations) != 3:
        raise ValueError("Plan must contain exactly three video operations")
    operation_by_id = {str(item.get("target_video_id")): item for item in operations}
    if set(operation_by_id) != _TARGET_IDS:
        raise ValueError("Correction target IDs differ from the reviewed set")

    replacement_index = {
        str(item["replacement_id"]): item
        for item in decisions.get("shared_replacements", [])
        if isinstance(item, dict) and item.get("replacement_id")
    }
    if set(replacement_index) != _REPLACEMENT_IDS:
        raise ValueError("Reviewed replacement IDs differ from the approved set")
    decision_index = {
        str(item["target_video_id"]): item
        for item in decisions.get("decisions", [])
        if isinstance(item, dict) and item.get("target_video_id")
    }
    if set(decision_index) != _TARGET_IDS:
        raise ValueError("Reviewed decision targets differ from the approved set")

    for remote_id, operation in operation_by_id.items():
        source_video = videos.get(remote_id)
        if source_video is None:
            raise ValueError(f"Correction target is absent from snapshot: {remote_id}")
        if operation.get("before_title") != operation.get("after_title"):
            raise ValueError(f"Title text changes in correction operation: {remote_id}")
        if operation.get("before_title_sha256") != operation.get("after_title_sha256"):
            raise ValueError(f"Title SHA changes in correction operation: {remote_id}")
        if bool(operation.get("title_changed")):
            raise ValueError(f"title_changed is true: {remote_id}")
        if not bool(operation.get("description_changed")):
            raise ValueError(f"description_changed is false: {remote_id}")
        if not bool(operation.get("reviewed_correction")):
            raise ValueError(f"reviewed_correction is false: {remote_id}")
        if source_video.get("title") != operation.get("before_title"):
            raise ValueError(
                f"Source title differs from reviewed before-state: {remote_id}"
            )
        if source_video.get("description") != operation.get("before_description"):
            raise ValueError(
                f"Source description differs from reviewed before-state: {remote_id}"
            )
        for side in ("before", "after"):
            if operation.get(f"{side}_title_sha256") != _canonical_sha256(
                operation.get(f"{side}_title")
            ):
                raise ValueError(f"{side}-title SHA mismatch: {remote_id}")
            if operation.get(f"{side}_description_sha256") != _canonical_sha256(
                operation.get(f"{side}_description")
            ):
                raise ValueError(f"{side}-description SHA mismatch: {remote_id}")

        reviewed_decision = decision_index[remote_id]
        if operation.get("decision_id") != reviewed_decision.get("decision_id"):
            raise ValueError(f"Decision ID mismatch: {remote_id}")
        replacement_ids = [
            str(item.get("replacement_id"))
            for item in operation.get("applied_replacements", [])
            if isinstance(item, dict)
        ]
        if replacement_ids != list(reviewed_decision.get("replacement_ids", [])):
            raise ValueError(f"Applied replacement order differs: {remote_id}")
        if set(replacement_ids) != _REPLACEMENT_IDS:
            raise ValueError(f"Applied replacements differ from approved set: {remote_id}")
        source_ids = {
            str(item.get("source_id"))
            for item in operation.get("source_evidence", [])
            if isinstance(item, dict)
        }
        if not _STANCE_SOURCE_IDS <= source_ids:
            raise ValueError(f"Operation lacks site or Research evidence: {remote_id}")
        if not {
            "feb-esenin-pss-v4-text",
            "feb-esenin-pss-v4-commentary",
        } <= source_ids:
            raise ValueError(f"Operation lacks academic dating evidence: {remote_id}")

        expected_after = str(operation.get("before_description") or "")
        for replacement_id in replacement_ids:
            replacement = replacement_index[replacement_id]
            old = str(replacement.get("old") or "")
            new = str(replacement.get("new") or "")
            expected_count = int(replacement.get("expected_count", 1))
            if expected_after.count(old) != expected_count:
                raise ValueError(
                    f"Replacement {replacement_id} is ambiguous in {remote_id}"
                )
            expected_after = expected_after.replace(old, new)
        if expected_after != operation.get("after_description"):
            raise ValueError(
                f"After-description differs from approved replacements: {remote_id}"
            )
        final_text = str(operation.get("after_description") or "")
        required_phrases = (
            "По доступным историческим свидетельствам Есенин умер неверующим",
            "вечная погибель под Божьим судом",
            "если не покаетесь, все так же погибнете",
            "1913–1915 гг. (предположительная датировка академического издания)",
        )
        if not all(phrase in final_text for phrase in required_phrases):
            raise ValueError(
                f"Approved conclusion or academic date is missing: {remote_id}"
            )
        if "окончательный суд о человеке принадлежит Богу" in final_text:
            raise ValueError(f"Superseded cautious text remains: {remote_id}")
        if "1912 г." in final_text:
            raise ValueError(f"Superseded date remains: {remote_id}")
        if len(final_text) > 5000:
            raise ValueError(f"After-description exceeds 5000 characters: {remote_id}")

    nested_queue = _verify_source_review_bundle(
        raw["source-review-bundle.zip"],
        str(plan.get("source_review_bundle_sha256") or ""),
    )
    if nested_queue.get("source_plan_sha256") != plan.get("source_plan_sha256"):
        raise ValueError("Nested review queue belongs to another source plan")

    preflight = raw["01-preflight.txt"].decode("utf-8-sig")
    required_preflight = (
        f"plan: {plan['plan_sha256']}",
        f"video coverage: {coverage}",
        f"membership state: {memberships}",
        "ready: 3",
        "already applied: 0",
        "conflicts: 0",
        "Dry-run only. No VK mutation method was called.",
    )
    if not all(value in preflight for value in required_preflight):
        raise ValueError("Preflight does not contain the exact reviewed guards")
    if re.search(r"(?i)--execute|video\.edit", preflight):
        raise ValueError("Dry-run preflight contains a mutation marker")

    return {
        "schema_name": "video-manager.vk-reviewed-correction-dry-run-verification",
        "schema_version": 1,
        "status": "verified_dry_run",
        "bundle": str(path),
        "bundle_sha256": _file_sha256(path.read_bytes()),
        "plan_sha256": plan["plan_sha256"],
        "decisions_sha256": decisions_sha256,
        "community_id": 235216998,
        "operations": 3,
        "target_video_ids": sorted(_TARGET_IDS),
        "ready": 3,
        "already_applied": 0,
        "conflicts": 0,
        "videos": 111,
        "collections": 17,
        "memberships": 294,
        "video_coverage_sha256": coverage,
        "memberships_sha256": memberships,
        "remote_writes": 0,
    }


def main() -> int:
    args = _parser().parse_args()
    try:
        report = verify_bundle(args.bundle)
    except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        report = {
            "schema_name": "video-manager.vk-reviewed-correction-dry-run-verification",
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
