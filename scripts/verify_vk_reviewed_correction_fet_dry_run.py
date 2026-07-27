#!/usr/bin/env python3
"""Independently verify the exact reviewed Fet correction dry-run handoff ZIP."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

_EXPECTED_BUNDLE_SHA256 = "sha256:8e173fba66cc0b298d1d87db384cb6a15e60c0c8d36c45db4ebb3e580a2221b9"
_EXPECTED_PLAN_SHA256 = "sha256:095c0a1cce72a46eaee0a1ea37ca2e2ee6a682bbf393f3d02d6d7abece1872ec"
_EXPECTED_DECISIONS_SHA256 = "sha256:ac13aaf20358d42db1808bcda46dd2a04fffc6c56abc85d6b3246fb10b3cd2d0"
_EXPECTED_SOURCE_PLAN_SHA256 = "sha256:b4eede44954bcb148550bcb2c0a372e4f23b72d892cc3aadcc5d71321a2e9294"
_EXPECTED_SOURCE_APPLY_BUNDLE_SHA256 = "sha256:af11d5c882d8068b316b606723410f6d45bda49d5dd327c92dc011b265f23398"
_EXPECTED_SOURCE_REVIEW_BUNDLE_SHA256 = "sha256:f38191f18d859ef2bcd445f558204ac76e3c3ebbe4f6414cb3436542df7b4c61"
_EXPECTED_VIDEO_COVERAGE_SHA256 = "sha256:94ef18173ade06658d421cbaeced7fdbada8d9766760adfee289df7bdbe3148e"
_EXPECTED_MEMBERSHIPS_SHA256 = "sha256:bdb556321dce7b5dd9400de33c92fb186dce55faac327f0a5a077491bfd5b966"
_EXPECTED_SNAPSHOT_ID = "c8020c66-29e6-40e1-8f65-9f412c4dc158"
_EXPECTED_DECISION_SET = "p1-fet-whisper-20260727"
_EXPECTED_COMMUNITY = 235216998
_EXPECTED_TARGETS = {
    "-235216998_456239127": {
        "decision_id": "correct-456239127",
        "title": "«Шёпот, Робкое Дыханье…» ⚡ Афанасий Фет",
        "before_description_sha256": "sha256:eb10b7f1e529c26c240dada4116d2a9666b33bb4e0e167839ad3f9762e959203",
        "replacement_ids": ["replace-short-fet-biography-and-attribution"],
    },
    "-235216998_456239143": {
        "decision_id": "correct-456239143",
        "title": "«Шёпот, Робкое Дыханье…» ⚡ Фет Слышит Пульс Зари",
        "before_description_sha256": "sha256:76c74c96f9aaa93d952531094d42c4b7a168f901566688bd349febd8b7b0c6b9",
        "replacement_ids": [
            "qualify-whisper-biographical-background",
            "attribute-lazich-death-and-cycle",
            "correct-late-love-cycle-and-fet-death",
            "remove-truncated-footer-fragment",
        ],
    },
}
_EXPECTED_REPLACEMENT_IDS = {
    "replace-short-fet-biography-and-attribution",
    "qualify-whisper-biographical-background",
    "attribute-lazich-death-and-cycle",
    "correct-late-love-cycle-and-fet-death",
    "remove-truncated-footer-fragment",
}
_REQUIRED_SOURCE_IDS = {
    "rvb-fet-bukhshtab-biography",
    "rvb-fet-complete-edition",
    "voplit-fet-verb-free-chernyshevsky",
    "feb-fet-death-kudryavtseva",
    "feb-kle-fet-lazich-cycle",
    "site-project-charter",
    "site-editorial-judgment-policy",
    "research-knowledge-base",
}
_REQUIRED_FILES = {
    "00-build.txt",
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
_URL_RE = re.compile(r"https?://[^\s]+")
_HASHTAG_RE = re.compile(r"(?<!\w)#[\wА-Яа-яЁё]+")


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


def _text_sha256(value: str) -> str:
    return _canonical_sha256(value)


def _file_sha256(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _remote_id(item: dict[str, Any]) -> str:
    ref = item.get("ref")
    if not isinstance(ref, dict) or not ref.get("remote_id"):
        raise ValueError("Snapshot item has no remote_id")
    return str(ref["remote_id"])


def _read_zip(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        names = [item.filename for item in archive.infolist()]
        duplicate_names = sorted({name for name in names if names.count(name) > 1})
        if duplicate_names:
            raise ValueError("Bundle contains duplicate ZIP entries: " + ", ".join(duplicate_names))
        missing = sorted(_REQUIRED_FILES - set(names))
        if missing:
            raise ValueError("Bundle is missing required files: " + ", ".join(missing))
        return {name: archive.read(name) for name in names}


def _verify_manifest(raw: dict[str, bytes], manifest: dict[str, Any]) -> None:
    records = {
        str(item["name"]): item
        for item in manifest.get("files", [])
        if isinstance(item, dict) and item.get("name")
    }
    required_records = _REQUIRED_FILES - {"manifest.json"}
    missing_records = sorted(required_records - records.keys())
    extra_records = sorted(records.keys() - required_records)
    if missing_records:
        raise ValueError("Manifest is missing required file records: " + ", ".join(missing_records))
    if extra_records:
        raise ValueError("Manifest has unexpected file records: " + ", ".join(extra_records))

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


def _verify_source_review_bundle(raw_zip: bytes) -> None:
    if _file_sha256(raw_zip) != _EXPECTED_SOURCE_REVIEW_BUNDLE_SHA256:
        raise ValueError("Nested source review bundle SHA-256 mismatch")
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
        names = [item.filename for item in archive.infolist()]
        if len(names) != len(set(names)):
            raise ValueError("Nested source review bundle has duplicate entries")
        required = {
            "manifest.json",
            "review-queue.json",
            "review-queue.md",
            "review-queue.html",
            "review-queue.csv",
            "README.txt",
        }
        missing = sorted(required - set(names))
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


def _verify_source_apply(source_apply: dict[str, Any], manifest: dict[str, Any]) -> None:
    if source_apply.get("status") != "verified_completed":
        raise ValueError("Source apply verification is not completed")
    if source_apply.get("bundle_sha256") != _EXPECTED_SOURCE_APPLY_BUNDLE_SHA256:
        raise ValueError("Source apply bundle SHA-256 differs from reviewed Esenin apply")
    if manifest.get("source_apply_bundle_sha256") != _EXPECTED_SOURCE_APPLY_BUNDLE_SHA256:
        raise ValueError("Manifest source apply bundle SHA-256 mismatch")
    if source_apply.get("plan_sha256") != "sha256:8f44f522321eb51a6f86e5aa958a56fb59c0716862094621cccf14b64cbc7593":
        raise ValueError("Source apply plan SHA-256 mismatch")
    if source_apply.get("decisions_sha256") != "sha256:a5d02d36ab195812ada192660276efd6ab82fcc7670ed55b825fb80f06d459b1":
        raise ValueError("Source apply decisions SHA-256 mismatch")
    if int(source_apply.get("community_id", 0)) != _EXPECTED_COMMUNITY:
        raise ValueError("Source apply targets another VK community")
    if int(source_apply.get("operations", -1)) != 3 or int(source_apply.get("remote_writes", -1)) != 3:
        raise ValueError("Source apply verification has unexpected operation counts")
    if source_apply.get("operation_statuses") != {"updated_and_verified": 3}:
        raise ValueError("Source apply does not prove three updated_and_verified operations")
    if int(source_apply.get("non_target_videos_verified_unchanged", -1)) != 108:
        raise ValueError("Source apply did not verify the remaining 108 videos")
    if source_apply.get("membership_identity_unchanged") is not True:
        raise ValueError("Source apply did not preserve membership identity")
    if source_apply.get("video_coverage_sha256") != _EXPECTED_VIDEO_COVERAGE_SHA256:
        raise ValueError("Source apply video coverage SHA-256 mismatch")
    if source_apply.get("memberships_sha256") != _EXPECTED_MEMBERSHIPS_SHA256:
        raise ValueError("Source apply memberships SHA-256 mismatch")
    if (
        int(source_apply.get("videos", -1)) != 111
        or int(source_apply.get("collections", -1)) != 17
        or int(source_apply.get("memberships", -1)) != 294
    ):
        raise ValueError("Source apply inventory counts are unexpected")


def _verify_decisions(decisions: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if decisions.get("decision_set_id") != _EXPECTED_DECISION_SET:
        raise ValueError("Decisions have another decision set")
    if int(decisions.get("target_community_id", 0)) != _EXPECTED_COMMUNITY:
        raise ValueError("Decisions target another VK community")
    if decisions.get("source_plan_sha256") != _EXPECTED_SOURCE_PLAN_SHA256:
        raise ValueError("Decisions source plan SHA-256 mismatch")
    if decisions.get("source_review_bundle_sha256") != _EXPECTED_SOURCE_REVIEW_BUNDLE_SHA256:
        raise ValueError("Decisions source review SHA-256 mismatch")
    if decisions.get("description_guard_hash_algorithm") != "video-manager.text-sha256-v1":
        raise ValueError("Decisions use another description guard hash algorithm")

    profile = decisions.get("editorial_profile")
    if not isinstance(profile, dict):
        raise ValueError("Decisions have no editorial profile")
    if (
        profile.get("profile_id") != "the-legendary-poet-historical-evangelical-v1"
        or profile.get("judgment_mode") != "asymmetric_evidence_based"
        or profile.get("last_hour_rule") != "acknowledge_once_not_equal_to_documented_life"
    ):
        raise ValueError("Decisions editorial profile differs from the approved owner stance")

    source_ids = {
        str(item.get("source_id"))
        for item in decisions.get("sources", [])
        if isinstance(item, dict) and item.get("source_id")
    }
    if source_ids != _REQUIRED_SOURCE_IDS:
        raise ValueError("Reviewed source set differs from the approved Fet evidence set")

    replacements = {
        str(item.get("replacement_id")): item
        for item in decisions.get("shared_replacements", [])
        if isinstance(item, dict) and item.get("replacement_id")
    }
    if set(replacements) != _EXPECTED_REPLACEMENT_IDS:
        raise ValueError("Fet replacement IDs differ from the reviewed set")
    for replacement_id, replacement in replacements.items():
        if int(replacement.get("expected_count", -1)) != 1:
            raise ValueError(f"Replacement is not exact-once: {replacement_id}")
        if not isinstance(replacement.get("old"), str) or not isinstance(replacement.get("new"), str):
            raise ValueError(f"Replacement has non-text old/new values: {replacement_id}")
        if _URL_RE.findall(str(replacement["old"])) != _URL_RE.findall(str(replacement["new"])):
            raise ValueError(f"Replacement changes URLs: {replacement_id}")
        if _HASHTAG_RE.findall(str(replacement["old"])) != _HASHTAG_RE.findall(str(replacement["new"])):
            raise ValueError(f"Replacement changes hashtags: {replacement_id}")

    decision_by_id: dict[str, dict[str, Any]] = {}
    for decision in decisions.get("decisions", []):
        if not isinstance(decision, dict):
            raise ValueError("Decision item is not an object")
        remote_id = str(decision.get("target_video_id"))
        if remote_id in decision_by_id:
            raise ValueError(f"Duplicate decision for video: {remote_id}")
        decision_by_id[remote_id] = decision
    if set(decision_by_id) != set(_EXPECTED_TARGETS):
        raise ValueError("Fet decision target IDs differ from the reviewed set")

    for remote_id, expected in _EXPECTED_TARGETS.items():
        decision = decision_by_id[remote_id]
        if decision.get("decision_id") != expected["decision_id"]:
            raise ValueError(f"Decision ID mismatch: {remote_id}")
        if decision.get("expected_title") != expected["title"]:
            raise ValueError(f"Decision title guard mismatch: {remote_id}")
        if decision.get("expected_description_sha256") != expected["before_description_sha256"]:
            raise ValueError(f"Decision description guard mismatch: {remote_id}")
        if decision.get("replacement_ids") != expected["replacement_ids"]:
            raise ValueError(f"Decision replacement order mismatch: {remote_id}")
        decision_sources = set(map(str, decision.get("source_ids", [])))
        if not decision_sources or not decision_sources <= source_ids:
            raise ValueError(f"Decision source IDs are invalid: {remote_id}")

    return decision_by_id, replacements


def _verify_operation(
    *,
    remote_id: str,
    operation: dict[str, Any],
    source_video: dict[str, Any],
    decision: dict[str, Any],
    replacements: dict[str, dict[str, Any]],
) -> None:
    expected = _EXPECTED_TARGETS[remote_id]
    before_title = str(operation.get("before_title") or "")
    after_title = str(operation.get("after_title") or "")
    before_description = str(operation.get("before_description") or "")
    after_description = str(operation.get("after_description") or "")

    if operation.get("operation_id") != f"video-text:reviewed-correction:{remote_id}":
        raise ValueError(f"Operation ID mismatch: {remote_id}")
    if operation.get("decision_id") != expected["decision_id"]:
        raise ValueError(f"Operation decision ID mismatch: {remote_id}")
    if before_title != expected["title"] or after_title != before_title:
        raise ValueError(f"Title changes or differs from reviewed title: {remote_id}")
    if bool(operation.get("title_changed")):
        raise ValueError(f"title_changed is true: {remote_id}")
    if not bool(operation.get("description_changed")) or before_description == after_description:
        raise ValueError(f"Description is not an actual correction: {remote_id}")
    if source_video.get("title") != before_title:
        raise ValueError(f"Source title differs from guarded title: {remote_id}")
    if source_video.get("description") != before_description:
        raise ValueError(f"Source description differs from guarded description: {remote_id}")
    if not after_description or len(after_description) > 5000:
        raise ValueError(f"Invalid corrected description length: {remote_id}")

    hash_checks = {
        "before_title_sha256": _text_sha256(before_title),
        "after_title_sha256": _text_sha256(after_title),
        "before_description_sha256": _text_sha256(before_description),
        "after_description_sha256": _text_sha256(after_description),
    }
    for field, expected_hash in hash_checks.items():
        if operation.get(field) != expected_hash:
            raise ValueError(f"Canonical text SHA-256 mismatch for {field}: {remote_id}")
    if operation.get("before_description_sha256") != decision.get("expected_description_sha256"):
        raise ValueError(f"Operation and decision description guards differ: {remote_id}")

    applied = operation.get("applied_replacements")
    if not isinstance(applied, list):
        raise ValueError(f"Operation has no applied_replacements list: {remote_id}")
    applied_ids = [str(item.get("replacement_id")) for item in applied if isinstance(item, dict)]
    if applied_ids != decision.get("replacement_ids"):
        raise ValueError(f"Applied replacement order differs from decision: {remote_id}")

    reconstructed = before_description
    for applied_item in applied:
        if not isinstance(applied_item, dict):
            raise ValueError(f"Applied replacement is not an object: {remote_id}")
        replacement_id = str(applied_item.get("replacement_id"))
        reviewed = replacements.get(replacement_id)
        if reviewed is None or applied_item != reviewed:
            raise ValueError(f"Applied replacement differs from reviewed policy: {replacement_id}")
        old = str(reviewed["old"])
        new = str(reviewed["new"])
        expected_count = int(reviewed["expected_count"])
        actual_count = reconstructed.count(old)
        if actual_count != expected_count:
            raise ValueError(
                f"Replacement occurrence mismatch for {replacement_id}: expected {expected_count}, got {actual_count}"
            )
        reconstructed = reconstructed.replace(old, new, expected_count)
    if reconstructed != after_description:
        raise ValueError(f"After-state is not exactly reconstructed by reviewed replacements: {remote_id}")

    if _URL_RE.findall(before_description) != _URL_RE.findall(after_description):
        raise ValueError(f"URLs changed during Fet correction: {remote_id}")
    if _HASHTAG_RE.findall(before_description) != _HASHTAG_RE.findall(after_description):
        raise ValueError(f"Hashtags changed during Fet correction: {remote_id}")
    if after_description.count("🎧 The Legendary Poet -") != 1:
        raise ValueError(f"Final footer count is not exactly one: {remote_id}")

    evidence = operation.get("source_evidence")
    if not isinstance(evidence, list):
        raise ValueError(f"Operation has no source evidence: {remote_id}")
    evidence_ids = {
        str(item.get("source_id")) for item in evidence if isinstance(item, dict) and item.get("source_id")
    }
    if evidence_ids != set(map(str, decision.get("source_ids", []))):
        raise ValueError(f"Operation source evidence differs from decision sources: {remote_id}")


def verify_bundle(path: Path) -> dict[str, Any]:
    bundle_bytes = path.read_bytes()
    bundle_sha256 = _file_sha256(bundle_bytes)
    if bundle_sha256 != _EXPECTED_BUNDLE_SHA256:
        raise ValueError(
            "Dry-run ZIP is not the exact independently reviewed Fet artifact: "
            f"expected {_EXPECTED_BUNDLE_SHA256}, got {bundle_sha256}"
        )

    raw = _read_zip(path)
    manifest = _json_bytes(raw["manifest.json"], name="manifest.json")
    plan = _json_bytes(raw["plan.json"], name="plan.json")
    decisions = _json_bytes(raw["reviewed-decisions.json"], name="reviewed-decisions.json")
    snapshot = _json_bytes(raw["00-source-vk-snapshot.json"], name="00-source-vk-snapshot.json")
    source_apply = _json_bytes(raw["source-apply-verification.json"], name="source-apply-verification.json")
    build = _json_bytes(raw["00-build.txt"], name="00-build.txt")

    _verify_manifest(raw, manifest)
    if (
        manifest.get("schema_name") != "video-manager.vk-reviewed-correction-handoff"
        or int(manifest.get("schema_version", 0)) != 2
        or manifest.get("status") != "completed"
        or manifest.get("artifact_kind") != "verified dry-run"
        or manifest.get("mode") != "dry-run"
        or manifest.get("component_scope") != "descriptions_only"
        or manifest.get("correction_scope") != "reviewed_factual_and_sensitive"
    ):
        raise ValueError("Handoff manifest does not describe the reviewed completed dry-run")
    if manifest.get("decision_set_id") != _EXPECTED_DECISION_SET:
        raise ValueError("Handoff has another decision set")
    if int(manifest.get("community_id", 0)) != _EXPECTED_COMMUNITY:
        raise ValueError("Handoff targets another VK community")
    if (
        int(manifest.get("ready", -1)) != 2
        or int(manifest.get("already_applied", -1)) != 0
        or int(manifest.get("conflicts", -1)) != 0
        or int(manifest.get("remote_writes", -1)) != 0
        or manifest.get("error") is not None
    ):
        raise ValueError("Unexpected dry-run counts, writes, or error state")
    if manifest.get("plan_sha256") != _EXPECTED_PLAN_SHA256:
        raise ValueError("Manifest plan SHA-256 differs from the reviewed plan")
    if manifest.get("source_review_bundle_sha256") != _EXPECTED_SOURCE_REVIEW_BUNDLE_SHA256:
        raise ValueError("Manifest source review bundle SHA-256 mismatch")

    if (
        build.get("status") != "reviewed_correction_plan_built"
        or build.get("plan_sha256") != _EXPECTED_PLAN_SHA256
        or int(build.get("descriptions_to_update", -1)) != 2
        or int(build.get("titles_to_update", -1)) != 0
        or int(build.get("albums_to_rename", -1)) != 0
        or int(build.get("remote_writes", -1)) != 0
    ):
        raise ValueError("Build receipt does not prove the exact read-only two-description plan")

    expected_plan_sha = _canonical_sha256({key: value for key, value in plan.items() if key != "plan_sha256"})
    if expected_plan_sha != _EXPECTED_PLAN_SHA256 or plan.get("plan_sha256") != expected_plan_sha:
        raise ValueError("Plan self-digest mismatch")
    decisions_sha256 = _canonical_sha256(decisions)
    if decisions_sha256 != _EXPECTED_DECISIONS_SHA256:
        raise ValueError("Reviewed decisions digest differs from the independently approved artifact")
    if plan.get("policy") != decisions:
        raise ValueError("Plan policy differs from reviewed-decisions.json")
    if plan.get("policy_sha256") != decisions_sha256 or plan.get("decisions_sha256") != decisions_sha256:
        raise ValueError("Plan decisions digest mismatch")
    if (
        plan.get("operation_scope") != "editorial_only"
        or plan.get("component_scope") != "descriptions_only"
        or plan.get("correction_scope") != "reviewed_factual_and_sensitive"
        or plan.get("decision_set_id") != _EXPECTED_DECISION_SET
        or int(plan.get("target_community_id", 0)) != _EXPECTED_COMMUNITY
    ):
        raise ValueError("Plan has an unexpected scope, decision set, or community")
    if plan.get("target_snapshot_id") != _EXPECTED_SNAPSHOT_ID:
        raise ValueError("Plan targets another source snapshot")
    if plan.get("target_video_ids_sha256") != _EXPECTED_VIDEO_COVERAGE_SHA256:
        raise ValueError("Plan video coverage SHA-256 mismatch")
    if plan.get("initial_memberships_sha256") != _EXPECTED_MEMBERSHIPS_SHA256:
        raise ValueError("Plan membership SHA-256 mismatch")
    if plan.get("source_plan_sha256") != _EXPECTED_SOURCE_PLAN_SHA256:
        raise ValueError("Plan source description-wave SHA-256 mismatch")
    if plan.get("source_review_bundle_sha256") != _EXPECTED_SOURCE_REVIEW_BUNDLE_SHA256:
        raise ValueError("Plan source review bundle SHA-256 mismatch")
    if plan.get("album_title_operations") or plan.get("review_only") or plan.get("deferred_editorial_review"):
        raise ValueError("Fet correction plan contains non-target operations or review queues")

    summary = plan.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Plan has no summary")
    expected_summary = {
        "videos_in_snapshot": 111,
        "video_text_operations": 2,
        "titles_to_update": 0,
        "descriptions_to_update": 2,
        "albums_to_rename": 0,
        "placements_to_add": 0,
        "placements_to_remove": 0,
        "videos_to_delete": 0,
        "review_only": 0,
        "deferred_editorial_review": 0,
        "total_operations": 2,
    }
    if summary != expected_summary:
        raise ValueError("Plan summary differs from the exact reviewed scope")

    decision_by_id, replacements = _verify_decisions(decisions)
    _verify_source_apply(source_apply, manifest)
    _verify_source_review_bundle(raw["source-review-bundle.zip"])

    if snapshot.get("schema_name") != "video-manager.audit-package":
        raise ValueError("Source snapshot has another schema")
    if snapshot.get("snapshot_id") != _EXPECTED_SNAPSHOT_ID:
        raise ValueError("Source snapshot ID mismatch")
    videos = {_remote_id(item): item for item in snapshot.get("videos", []) if isinstance(item, dict)}
    if len(videos) != 111 or len(snapshot.get("collections", [])) != 17 or len(snapshot.get("memberships", [])) != 294:
        raise ValueError("Source snapshot inventory counts differ from 111 / 17 / 294")

    operations = plan.get("video_text_operations")
    if not isinstance(operations, list) or len(operations) != 2:
        raise ValueError("Plan must contain exactly two operations")
    operation_by_id: dict[str, dict[str, Any]] = {}
    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError("Plan operation is not an object")
        remote_id = str(operation.get("target_video_id"))
        if remote_id in operation_by_id:
            raise ValueError(f"Duplicate operation for video: {remote_id}")
        operation_by_id[remote_id] = operation
    if set(operation_by_id) != set(_EXPECTED_TARGETS):
        raise ValueError("Fet correction target IDs differ from the reviewed set")

    for remote_id, operation in operation_by_id.items():
        source_video = videos.get(remote_id)
        if source_video is None:
            raise ValueError(f"Fet target is absent from snapshot: {remote_id}")
        _verify_operation(
            remote_id=remote_id,
            operation=operation,
            source_video=source_video,
            decision=decision_by_id[remote_id],
            replacements=replacements,
        )

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

    preflight = raw["01-preflight.txt"].decode("utf-8-sig")
    for required in (
        f"plan: {_EXPECTED_PLAN_SHA256}",
        f"video coverage: {_EXPECTED_VIDEO_COVERAGE_SHA256}",
        f"membership state: {_EXPECTED_MEMBERSHIPS_SHA256}",
        "ready: 2",
        "already applied: 0",
        "conflicts: 0",
        "Dry-run only. No VK mutation method was called.",
    ):
        if required not in preflight:
            raise ValueError(f"Preflight is missing exact evidence: {required}")
    if "video.edit" in preflight or "--execute" in preflight:
        raise ValueError("Dry-run preflight contains execute or mutation evidence")

    report_markdown = raw["plan-review.md"].decode("utf-8-sig")
    report_html = raw["plan-review.html"].decode("utf-8-sig")
    for required in (_EXPECTED_PLAN_SHA256, *sorted(_EXPECTED_TARGETS)):
        if required not in report_markdown or required not in report_html:
            raise ValueError(f"Human review reports omit reviewed evidence: {required}")

    readme = raw["README.txt"].decode("utf-8-sig")
    for required in (
        "Тип пакета: verified dry-run",
        "Статус: completed",
        "Ready: 2",
        "Already applied: 0",
        "Conflicts: 0",
        "DRY-RUN НЕ ВЫЗЫВАЕТ VK MUTATION API",
    ):
        if required not in readme:
            raise ValueError(f"README is missing dry-run safety evidence: {required}")

    return {
        "schema_name": "video-manager.vk-reviewed-correction-fet-dry-run-verification",
        "schema_version": 2,
        "status": "verified_dry_run",
        "artifact_review": "exact_independently_reviewed_bundle",
        "bundle": str(path),
        "bundle_sha256": bundle_sha256,
        "plan_sha256": _EXPECTED_PLAN_SHA256,
        "decisions_sha256": decisions_sha256,
        "source_apply_bundle_sha256": _EXPECTED_SOURCE_APPLY_BUNDLE_SHA256,
        "source_review_bundle_sha256": _EXPECTED_SOURCE_REVIEW_BUNDLE_SHA256,
        "community_id": _EXPECTED_COMMUNITY,
        "operations": 2,
        "target_video_ids": sorted(_EXPECTED_TARGETS),
        "videos": 111,
        "collections": 17,
        "memberships": 294,
        "remote_writes": 0,
        "canonical_text_hashes_verified": True,
        "reviewed_replacements_reconstructed": True,
        "urls_and_hashtags_unchanged": True,
        "source_apply_status": source_apply["status"],
    }


def main() -> int:
    args = _parser().parse_args()
    try:
        report = verify_bundle(args.bundle)
    except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        report = {
            "schema_name": "video-manager.vk-reviewed-correction-fet-dry-run-verification",
            "schema_version": 2,
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
