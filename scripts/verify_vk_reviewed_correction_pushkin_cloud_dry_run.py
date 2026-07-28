#!/usr/bin/env python3
"""Verify the exact reviewed contents of the Pushkin «Туча» dry-run ZIP."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

_BUNDLE_SHA = "sha256:8131a1a5845547eb1fc78b313e3de50d22a433a8dc7c559329bafd58cc6521a5"
_PLAN_SHA = "sha256:207ee6e5622692b504254c7d7aa3579fd2907614eaf88d1b6e0ac7c1eacf517c"
_DECISIONS_SHA = "sha256:eaddbce693498a87cd888642642073bb0198c85087659543756ae61763e80a75"
_SOURCE_APPLY_SHA = "sha256:27c6e98d845a54d53513e386f627c32a3618d0b3dbfd1946132f20ec9c8bde69"
_SOURCE_REVIEW_SHA = "sha256:f38191f18d859ef2bcd445f558204ac76e3c3ebbe4f6414cb3436542df7b4c61"
_COVERAGE_SHA = "sha256:94ef18173ade06658d421cbaeced7fdbada8d9766760adfee289df7bdbe3148e"
_MEMBERSHIPS_SHA = "sha256:bdb556321dce7b5dd9400de33c92fb186dce55faac327f0a5a077491bfd5b966"
_DECISION_SET = "p1-pushkin-cloud-20260728"
_COMMUNITY_ID = 235216998
_TARGET_ID = "-235216998_456239106"
_EXPECTED_TITLE = "«Последняя Туча Рассеянной Бури» ⚡ Пушкин Танцует Последнюю Бурю"
_BEFORE_GUARD = "sha256:c06815c12dc652d793823bd1c65d7b34edbdfd1e614c0bc7bfaffca77a555eeb"
_AFTER_GUARD = "sha256:3ddb0ec7988bc49115192083d5ad513a1d01d462cf3efe24c593a01ddee5cff5"
_EXPECTED_AFTER_LENGTH = 4100
_REPLACEMENT_IDS = (
    "remove-unsupported-personal-superlative",
    "qualify-cloud-psychological-autobiography",
    "correct-pushkin-1835-biography-and-context",
    "correct-duel-death-and-limit-prophecy",
    "attribute-interpretation-and-document-publication",
)
_EXPECTED_MEMBERS = {
    "00-build.txt": (395, "sha256:065d426f132dd34042b6abc5ee3771cb354e494d17565fefcdae68dd21d6fc1a"),
    "00-source-vk-snapshot.json": (2599240, "sha256:41eccb6058891049d01b7ff9269c8e66dc478c8e65b8dcbc220102625e52a726"),
    "01-preflight.txt": (675, "sha256:8257d65725a075b066a345243b8e26a7dde6a27f1572c4088409b531107681cf"),
    "plan-review.html": (20818, "sha256:aa08bc5296a3976b9b4c075f59c100ea01f5627dbdafba5c221209b30a5f80c9"),
    "plan-review.md": (19872, "sha256:231224b960fb199139d9c572f536ccadb252b942dd4556ea6cc1947ba0859354"),
    "plan.json": (62923, "sha256:7735b4d662748536b18ecbe57bac72666b2e943a434786ec51904087dea60045"),
    "README.txt": (1732, "sha256:29953cd9ffe47fa77d73894b3c2cc1756e635ab4f60d4ab6fcb8744bcc363b2a"),
    "reviewed-decisions.json": (22795, "sha256:eadd9cfe13fff58cbe847a031ee833967f64a2dc7d04c49454d8ec00d6df724f"),
    "source-apply-verification.json": (1369, "sha256:dd6c0ef61d45251007888a52f44ce3cb4625044a8edb48876e0464b1ff19e718"),
    "source-review-bundle.zip": (459225, _SOURCE_REVIEW_SHA),
}
_REQUIRED_FILES = frozenset({"manifest.json", *_EXPECTED_MEMBERS})
_URL_RE = re.compile(r"https?://[^\s]+")
_HASHTAG_RE = re.compile(r"(?<!\w)#[\wА-Яа-яЁё]+")


def _file_sha(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _canonical_sha(value: Any) -> str:
    return _file_sha(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def _json(raw: bytes, name: str) -> dict[str, Any]:
    value = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{name} must contain an object")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify_bundle(path: Path) -> dict[str, Any]:
    bundle_sha = _file_sha(path.read_bytes())
    _require(bundle_sha == _BUNDLE_SHA, "Outer ZIP SHA-256 differs from reviewed bundle")
    with zipfile.ZipFile(path) as archive:
        names = [entry.filename for entry in archive.infolist()]
        _require(len(names) == len(set(names)), "ZIP contains duplicate entries")
        _require(set(names) == set(_REQUIRED_FILES), "ZIP member set differs")
        raw = {name: archive.read(name) for name in names}

    manifest = _json(raw["manifest.json"], "manifest.json")
    plan = _json(raw["plan.json"], "plan.json")
    decisions = _json(raw["reviewed-decisions.json"], "reviewed-decisions.json")
    source = _json(raw["00-source-vk-snapshot.json"], "00-source-vk-snapshot.json")
    source_apply = _json(raw["source-apply-verification.json"], "source-apply-verification.json")

    records = {
        str(item.get("name")): item
        for item in manifest.get("files", [])
        if isinstance(item, dict) and item.get("name")
    }
    _require(set(records) == set(_EXPECTED_MEMBERS), "Manifest records differ")
    for name, (size, expected_sha) in _EXPECTED_MEMBERS.items():
        content = raw[name]
        record = records[name]
        _require(len(content) == size, f"{name}: reviewed size mismatch")
        _require(_file_sha(content) == expected_sha, f"{name}: reviewed SHA mismatch")
        _require(int(record.get("size_bytes", -1)) == size, f"{name}: manifest size mismatch")
        _require(str(record.get("sha256")) == expected_sha, f"{name}: manifest SHA mismatch")

    _require(manifest.get("status") == "completed", "Dry-run wrapper status is not completed")
    _require(manifest.get("mode") == "dry-run", "Bundle is not dry-run")
    _require(manifest.get("component_scope") == "descriptions_only", "Scope is not descriptions_only")
    _require(manifest.get("decision_set_id") == _DECISION_SET, "Wrong decision set")
    _require(int(manifest.get("community_id", 0)) == _COMMUNITY_ID, "Wrong community")
    _require(int(manifest.get("ready", -1)) == 1, "Expected ready=1")
    _require(int(manifest.get("already_applied", -1)) == 0, "Expected already_applied=0")
    _require(int(manifest.get("conflicts", -1)) == 0, "Expected conflicts=0")
    _require(int(manifest.get("remote_writes", -1)) == 0, "Dry-run reports writes")
    _require(manifest.get("source_apply_bundle_sha256") == _SOURCE_APPLY_SHA, "Source apply SHA differs")
    _require(manifest.get("source_review_bundle_sha256") == _SOURCE_REVIEW_SHA, "Source review SHA differs")

    calculated_plan_sha = _canonical_sha({key: value for key, value in plan.items() if key != "plan_sha256"})
    _require(calculated_plan_sha == _PLAN_SHA, "Plan self-digest differs")
    _require(plan.get("plan_sha256") == _PLAN_SHA, "Plan SHA differs")
    _require(manifest.get("plan_sha256") == _PLAN_SHA, "Manifest plan SHA differs")
    _require(_canonical_sha(decisions) == _DECISIONS_SHA, "Decisions canonical SHA differs")
    _require(plan.get("policy") == decisions, "Plan policy differs from decisions")
    _require(plan.get("policy_sha256") == _DECISIONS_SHA, "Policy SHA differs")
    _require(plan.get("decisions_sha256") == _DECISIONS_SHA, "Decisions SHA differs")
    _require(plan.get("decision_set_id") == _DECISION_SET, "Plan decision set differs")
    _require(plan.get("target_video_ids_sha256") == _COVERAGE_SHA, "Video coverage differs")
    _require(plan.get("initial_memberships_sha256") == _MEMBERSHIPS_SHA, "Membership digest differs")

    summary = plan.get("summary") or {}
    _require(int(summary.get("videos_in_snapshot", -1)) == 111, "Snapshot video count differs")
    _require(int(summary.get("descriptions_to_update", -1)) == 1, "Expected one description update")
    _require(int(summary.get("total_operations", -1)) == 1, "Expected one total operation")
    for field in (
        "titles_to_update",
        "albums_to_rename",
        "placements_to_add",
        "placements_to_remove",
        "videos_to_delete",
        "review_only",
        "deferred_editorial_review",
    ):
        _require(int(summary.get(field, -1)) == 0, f"Unexpected non-description scope: {field}")

    operations = plan.get("video_text_operations")
    _require(isinstance(operations, list) and len(operations) == 1, "Expected exactly one operation")
    operation = operations[0]
    _require(operation.get("target_video_id") == _TARGET_ID, "Wrong target ID")
    _require(operation.get("before_title") == _EXPECTED_TITLE, "Source title differs")
    _require(operation.get("after_title") == _EXPECTED_TITLE, "Title must remain unchanged")
    _require(operation.get("before_description_sha256") == _BEFORE_GUARD, "Before guard differs")
    _require(operation.get("after_description_sha256") == _AFTER_GUARD, "After guard differs")
    _require(len(str(operation.get("after_description") or "")) == _EXPECTED_AFTER_LENGTH, "After length differs")
    _require(operation.get("reviewed_correction") is True, "Operation is not reviewed correction")

    replacements = operation.get("applied_replacements")
    _require(isinstance(replacements, list), "Applied replacements must be a list")
    _require(
        tuple(str(item.get("replacement_id")) for item in replacements) == _REPLACEMENT_IDS,
        "Replacement order differs",
    )
    rendered = str(operation.get("before_description") or "")
    for replacement in replacements:
        old = str(replacement.get("old") or "")
        new = str(replacement.get("new") or "")
        _require(int(replacement.get("expected_count", -1)) == 1, "Replacement count guard differs")
        _require(rendered.count(old) == 1, f"Old text count differs: {replacement.get('replacement_id')}")
        rendered = rendered.replace(old, new, 1)
    after = str(operation.get("after_description") or "")
    _require(rendered == after, "After-state is not exact replacement reconstruction")
    before = str(operation.get("before_description") or "")
    _require(_URL_RE.findall(before) == _URL_RE.findall(after), "URLs changed")
    _require(_HASHTAG_RE.findall(before) == _HASHTAG_RE.findall(after), "Hashtags changed")

    _require(len(source.get("videos", [])) == 111, "Source snapshot video count differs")
    _require(len(source.get("collections", [])) == 17, "Source snapshot collection count differs")
    _require(len(source.get("memberships", [])) == 294, "Source snapshot membership count differs")
    source_videos = {
        str(item["ref"]["remote_id"]): item
        for item in source.get("videos", [])
        if isinstance(item, dict) and isinstance(item.get("ref"), dict)
    }
    _require(_TARGET_ID in source_videos, "Target is absent from source snapshot")
    _require(source_videos[_TARGET_ID].get("title") == operation.get("before_title"), "Snapshot title differs")
    _require(
        source_videos[_TARGET_ID].get("description") == operation.get("before_description"),
        "Snapshot description differs",
    )

    _require(source_apply.get("status") == "verified_completed", "Source Blok apply is not verified")
    _require(source_apply.get("bundle_sha256") == _SOURCE_APPLY_SHA, "Source Blok apply bundle differs")
    _require(source_apply.get("operation_statuses") == {"updated_and_verified": 2}, "Source Blok statuses differ")
    _require(int(source_apply.get("operations", -1)) == 2, "Source Blok operation count differs")
    _require(int(source_apply.get("remote_writes", -1)) == 2, "Source Blok write count differs")
    _require(source_apply.get("video_coverage_sha256") == _COVERAGE_SHA, "Source coverage differs")
    _require(source_apply.get("memberships_sha256") == _MEMBERSHIPS_SHA, "Source memberships differ")
    _require(source_apply.get("membership_identity_unchanged") is True, "Source membership identity changed")
    _require(source_apply.get("membership_position_changes") == [], "Source membership positions changed")

    with zipfile.ZipFile(io.BytesIO(raw["source-review-bundle.zip"])) as nested:
        nested_names = [entry.filename for entry in nested.infolist()]
        _require(len(nested_names) == len(set(nested_names)), "Nested review has duplicate entries")
        _require(
            set(nested_names)
            == {
                "manifest.json",
                "review-queue.json",
                "review-queue.md",
                "review-queue.html",
                "review-queue.csv",
                "README.txt",
            },
            "Nested review member set differs",
        )
        queue = _json(nested.read("review-queue.json"), "review-queue.json")
    _require(queue.get("mode") == "review_only", "Nested review is not review-only")
    _require(int(queue.get("remote_writes", -1)) == 0, "Nested review reports writes")

    preflight = raw["01-preflight.txt"].decode("utf-8-sig")
    for required in (
        f"plan: {_PLAN_SHA}",
        f"video coverage: {_COVERAGE_SHA}",
        f"membership state: {_MEMBERSHIPS_SHA}",
        "ready: 1",
        "already applied: 0",
        "conflicts: 0",
        "No VK mutation method was called",
    ):
        _require(required in preflight, f"Preflight missing exact guard: {required}")

    return {
        "schema_name": "video-manager.vk-reviewed-correction-pushkin-cloud-dry-run-verification",
        "schema_version": 1,
        "status": "verified_dry_run",
        "artifact_review": "exact_independently_reviewed_contents",
        "bundle": str(path),
        "bundle_sha256": bundle_sha,
        "decision_set_id": _DECISION_SET,
        "plan_sha256": _PLAN_SHA,
        "decisions_sha256": _DECISIONS_SHA,
        "community_id": _COMMUNITY_ID,
        "operations": 1,
        "target_video_ids": [_TARGET_ID],
        "ready": 1,
        "already_applied": 0,
        "conflicts": 0,
        "remote_writes": 0,
        "videos": 111,
        "collections": 17,
        "memberships": 294,
        "video_coverage_sha256": _COVERAGE_SHA,
        "memberships_sha256": _MEMBERSHIPS_SHA,
        "after_description_sha256": _AFTER_GUARD,
        "after_description_length": _EXPECTED_AFTER_LENGTH,
        "canonical_text_hashes_verified": True,
        "reviewed_replacements_reconstructed": True,
        "urls_and_hashtags_unchanged": True,
        "exact_member_hashes_verified": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    try:
        report = verify_bundle(args.bundle)
    except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        report = {
            "schema_name": "video-manager.vk-reviewed-correction-pushkin-cloud-dry-run-verification",
            "schema_version": 1,
            "status": "verification_failed",
            "bundle": str(args.bundle),
            "error": str(exc),
        }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.json_output:
        args.json_output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report.get("status") == "verified_dry_run" else 1


if __name__ == "__main__":
    raise SystemExit(main())
