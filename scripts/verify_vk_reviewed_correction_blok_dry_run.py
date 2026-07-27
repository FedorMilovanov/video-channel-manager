#!/usr/bin/env python3
"""Verify the exact reviewed contents of a Blok correction dry-run ZIP."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

_PLAN_SHA = "sha256:53bed1c056868731dcb1f9c04b8d3188fd4295baa5d14364b1f8b72187cea4fb"
_DECISIONS_SHA = "sha256:3b8e3f661d317a03483e568b90ef361de8bc325abe19d9d049076dd24b7f103e"
_SOURCE_PLAN_SHA = "sha256:b4eede44954bcb148550bcb2c0a372e4f23b72d892cc3aadcc5d71321a2e9294"
_SOURCE_APPLY_SHA = "sha256:608e20328315459eb1ef5d2e0a38829055967319b6e60ae9d77039e7d18ec7b8"
_SOURCE_REVIEW_SHA = "sha256:f38191f18d859ef2bcd445f558204ac76e3c3ebbe4f6414cb3436542df7b4c61"
_VIDEO_COVERAGE_SHA = "sha256:94ef18173ade06658d421cbaeced7fdbada8d9766760adfee289df7bdbe3148e"
_MEMBERSHIPS_SHA = "sha256:bdb556321dce7b5dd9400de33c92fb186dce55faac327f0a5a077491bfd5b966"
_SNAPSHOT_ID = "409fc46b-000e-4152-9dc4-2e4ea32fcb94"
_DECISION_SET = "p1-blok-night-20260728"
_COMMUNITY_ID = 235216998
_KNOWN_OUTER_SHAS = frozenset(
    {
        "sha256:03303cb0b2c726f684fa62620423205929b10c58e801747a59d26f72adc4229a",
    }
)
_EXPECTED_MEMBERS = {
    "00-build.txt": (
        386,
        "sha256:669b46175f0855ae2967852867635411bc8f95a77de6790e53d7154a67e78108",
    ),
    "00-source-vk-snapshot.json": (
        2600188,
        "sha256:87b853b64d3e955026739f41c1333fa14d4fa25f6f79f2c300d0c347c7e06cde",
    ),
    "01-preflight.txt": (
        789,
        "sha256:e7c931ece3af917c97df007508e9467cf6c3c1b0da209731c040368ea26b4558",
    ),
    "plan-review.html": (
        25006,
        "sha256:a3f91b92a0e9845dd67b55c7515060637177f77932d34688daf8261b33bb06a8",
    ),
    "plan-review.md": (
        24065,
        "sha256:ec7ff1ea617de70192bb5232b8c96252ec2fea6a9b82c759ddb5a58878f71858",
    ),
    "plan.json": (
        57715,
        "sha256:1f1adbdad63d0b2996cd364805bc4429c046a9796a152a9dd48c785af82f1882",
    ),
    "README.txt": (
        1603,
        "sha256:a3989aac7683ad0ec792b514a4ad9483202347b0bfc5a049ff53ea1b65afa2c5",
    ),
    "reviewed-decisions.json": (
        17085,
        "sha256:9b34b8c4bbcf2142af992f8cc870e00ab358e56f772f068ab4d13035c06f87ef",
    ),
    "source-apply-verification.json": (
        1368,
        "sha256:c4718f2c958b1ebd4e4f08749bac7c33543c1eba51e41620c93b7914a874b8b2",
    ),
    "source-review-bundle.zip": (459225, _SOURCE_REVIEW_SHA),
}
_REQUIRED_FILES = frozenset({"manifest.json", *_EXPECTED_MEMBERS})
_TARGETS = {
    "-235216998_456239120": {
        "decision_id": "correct-456239120",
        "title": "Бесконечная Петля Блока ⚡ «Ночь, улица, фонарь, аптека…»",
        "guard": "sha256:252ec08971ddaa0b2fbffee2fc428cdd0641879abd10dc09bf7c44504eae15f1",
        "after_guard": "sha256:ac95b72a59b03e7fc8ef07ecf906fbb05ef3534e7ad0757d2c65db60b893f407",
        "replacements": ["remove-unsupported-silver-age-superlative"],
        "after_length": 713,
    },
    "-235216998_456239126": {
        "decision_id": "correct-456239126",
        "title": "«Ночь, Улица, Фонарь, Аптека…» ⚡ Пульс Мёртвого Города ⚡ Александр Блок",
        "guard": "sha256:dd321580877a2be9dec0109e2f875204973c2471e9790d9d4d8c145ffe82e9b0",
        "after_guard": "sha256:753e2bc4f2bb41e37ce9285b4f6cd02a0013a9a0296f4a36dba63d97ee94cf27",
        "replacements": [
            "correct-gippius-memory-and-limit-inference",
            "attribute-competing-pharmacy-prototypes",
            "separate-cycle-fact-from-interpretation",
            "correct-blok-final-illness-and-exit-timeline",
        ],
        "after_length": 4735,
    },
}
_REPLACEMENT_IDS = frozenset(
    {
        "correct-gippius-memory-and-limit-inference",
        "attribute-competing-pharmacy-prototypes",
        "separate-cycle-fact-from-interpretation",
        "correct-blok-final-illness-and-exit-timeline",
        "remove-unsupported-silver-age-superlative",
    }
)
_SOURCE_IDS = frozenset(
    {
        "rvb-blok-complete-edition",
        "feb-gippius-meetings",
        "culture-blok-pharmacy-exhibition",
        "likhachev-blok-pharmacy-commentary",
        "russian-thought-first-publication",
        "culture-blok-biography",
        "bigenc-blok",
        "site-project-charter",
        "site-editorial-judgment-policy",
        "research-knowledge-base",
    }
)
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
    "точный момент рождения стихотворения",
    "аптекой самоубийц",
    "В «Страшном мире» всё прекрасное и духовное уничтожено",
    "почти не приходил в сознание",
    "самое безысходное стихотворение Серебряного века",
)
_URL_RE = re.compile(r"https?://[^\s]+")
_HASHTAG_RE = re.compile(r"(?<!\w)#[\wА-Яа-яЁё]+")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--json-output", type=Path)
    return parser


def _file_sha(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _canonical_sha(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _file_sha(raw)


def _json(raw: bytes, name: str) -> dict[str, Any]:
    value = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{name} must contain a JSON object")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _remote_id(item: dict[str, Any]) -> str:
    ref = item.get("ref")
    if not isinstance(ref, dict) or not ref.get("remote_id"):
        raise ValueError("Snapshot item has no remote_id")
    return str(ref["remote_id"])


def _read_bundle(path: Path) -> tuple[dict[str, bytes], str]:
    bundle_sha = _file_sha(path.read_bytes())
    with zipfile.ZipFile(path) as archive:
        names = [entry.filename for entry in archive.infolist()]
        _require(len(names) == len(set(names)), "Bundle contains duplicate ZIP entries")
        _require(set(names) == set(_REQUIRED_FILES), "Bundle contains a different file set")
        return {name: archive.read(name) for name in names}, bundle_sha


def _verify_members(raw: dict[str, bytes], manifest: dict[str, Any]) -> None:
    records = {
        str(item.get("name")): item
        for item in manifest.get("files", [])
        if isinstance(item, dict) and item.get("name")
    }
    _require(set(records) == set(_EXPECTED_MEMBERS), "Manifest file records differ from reviewed contents")
    for name, (expected_size, expected_sha) in _EXPECTED_MEMBERS.items():
        content = raw[name]
        record = records[name]
        _require(len(content) == expected_size, f"Reviewed member size mismatch: {name}")
        _require(_file_sha(content) == expected_sha, f"Reviewed member SHA-256 mismatch: {name}")
        _require(int(record.get("size_bytes", -1)) == expected_size, f"Manifest size mismatch: {name}")
        _require(str(record.get("sha256")) == expected_sha, f"Manifest SHA-256 mismatch: {name}")


def _verify_nested_review(raw_zip: bytes) -> None:
    _require(_file_sha(raw_zip) == _SOURCE_REVIEW_SHA, "Nested source review bundle SHA-256 mismatch")
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
        names = [entry.filename for entry in archive.infolist()]
        _require(len(names) == len(set(names)), "Nested source review has duplicate entries")
        required = {
            "manifest.json",
            "review-queue.json",
            "review-queue.md",
            "review-queue.html",
            "review-queue.csv",
            "README.txt",
        }
        _require(set(names) == required, "Nested source review bundle has a different file set")
        nested = {name: archive.read(name) for name in names}
    manifest = _json(nested["manifest.json"], "nested manifest.json")
    queue = _json(nested["review-queue.json"], "review-queue.json")
    _require(manifest.get("status") == "review_only_completed", "Nested review is not completed")
    _require(queue.get("mode") == "review_only", "Nested review is not review-only")
    _require(int(queue.get("remote_writes", -1)) == 0, "Nested review reports remote writes")
    records = {
        str(item.get("name")): item
        for item in manifest.get("files", [])
        if isinstance(item, dict) and item.get("name")
    }
    _require(set(records) == required - {"manifest.json"}, "Nested manifest file records differ")
    for name, record in records.items():
        content = nested[name]
        _require(int(record.get("size_bytes", -1)) == len(content), f"Nested size mismatch: {name}")
        _require(str(record.get("sha256")) == _file_sha(content), f"Nested SHA-256 mismatch: {name}")


def _verify_source_apply(source: dict[str, Any], manifest: dict[str, Any]) -> None:
    _require(source.get("status") == "verified_completed", "Source Fet apply verification is not completed")
    _require(source.get("bundle_sha256") == _SOURCE_APPLY_SHA, "Source Fet apply bundle SHA-256 mismatch")
    _require(manifest.get("source_apply_bundle_sha256") == _SOURCE_APPLY_SHA, "Manifest source apply SHA mismatch")
    _require(source.get("operation_statuses") == {"updated_and_verified": 2}, "Source Fet statuses differ")
    _require(int(source.get("operations", -1)) == 2, "Source Fet apply operation count differs")
    _require(int(source.get("remote_writes", -1)) == 2, "Source Fet apply write count differs")
    _require(
        int(source.get("non_target_videos_verified_unchanged", -1)) == 109,
        "Source Fet non-target proof differs",
    )
    _require(source.get("membership_identity_unchanged") is True, "Source Fet membership identity changed")
    _require(source.get("membership_position_changes") == [], "Source Fet membership positions changed")
    _require(source.get("video_coverage_sha256") == _VIDEO_COVERAGE_SHA, "Source video coverage differs")
    _require(source.get("memberships_sha256") == _MEMBERSHIPS_SHA, "Source memberships differ")


def _verify_decisions(decisions: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    _require(decisions.get("decision_set_id") == _DECISION_SET, "Decisions have another decision set")
    _require(int(decisions.get("target_community_id", 0)) == _COMMUNITY_ID, "Decisions target another community")
    _require(decisions.get("source_plan_sha256") == _SOURCE_PLAN_SHA, "Decisions source plan differs")
    _require(decisions.get("source_review_bundle_sha256") == _SOURCE_REVIEW_SHA, "Decisions source review differs")
    _require(
        decisions.get("description_guard_hash_algorithm") == "video-manager.text-sha256-v1",
        "Decisions use another description guard hash algorithm",
    )
    sources = {
        str(item.get("source_id"))
        for item in decisions.get("sources", [])
        if isinstance(item, dict) and item.get("source_id")
    }
    _require(sources == set(_SOURCE_IDS), "Reviewed source set differs")
    replacements = {
        str(item.get("replacement_id")): item
        for item in decisions.get("shared_replacements", [])
        if isinstance(item, dict) and item.get("replacement_id")
    }
    _require(set(replacements) == set(_REPLACEMENT_IDS), "Blok replacement IDs differ from reviewed set")
    for replacement_id, replacement in replacements.items():
        _require(int(replacement.get("expected_count", -1)) == 1, f"Replacement is not exact-once: {replacement_id}")
        old = str(replacement.get("old") or "")
        new = str(replacement.get("new") or "")
        _require(_URL_RE.findall(old) == _URL_RE.findall(new), f"Replacement changes URLs: {replacement_id}")
        _require(
            _HASHTAG_RE.findall(old) == _HASHTAG_RE.findall(new),
            f"Replacement changes hashtags: {replacement_id}",
        )
    by_video = {
        str(item.get("target_video_id")): item
        for item in decisions.get("decisions", [])
        if isinstance(item, dict)
    }
    _require(set(by_video) == set(_TARGETS), "Blok decision target IDs differ from reviewed set")
    return by_video, replacements


def _verify_operation(
    remote_id: str,
    operation: dict[str, Any],
    source_video: dict[str, Any],
    decision: dict[str, Any],
    replacements: dict[str, Any],
) -> None:
    expected = _TARGETS[remote_id]
    before_title = str(operation.get("before_title") or "")
    after_title = str(operation.get("after_title") or "")
    before_desc = str(operation.get("before_description") or "")
    after_desc = str(operation.get("after_description") or "")
    _require(operation.get("decision_id") == expected["decision_id"], f"Decision ID mismatch: {remote_id}")
    _require(before_title == expected["title"] == after_title, f"Title changes in Blok operation: {remote_id}")
    _require(not bool(operation.get("title_changed")), f"title_changed is true: {remote_id}")
    _require(bool(operation.get("description_changed")), f"description_changed is false: {remote_id}")
    _require(bool(operation.get("reviewed_correction")), f"reviewed_correction is false: {remote_id}")
    _require(source_video.get("title") == before_title, f"Source title differs: {remote_id}")
    _require(source_video.get("description") == before_desc, f"Source description differs: {remote_id}")
    _require(len(after_desc) == expected["after_length"], f"Corrected description length differs: {remote_id}")
    hashes = {
        "before_title_sha256": _canonical_sha(before_title),
        "after_title_sha256": _canonical_sha(after_title),
        "before_description_sha256": _canonical_sha(before_desc),
        "after_description_sha256": _canonical_sha(after_desc),
    }
    for field, expected_hash in hashes.items():
        _require(operation.get(field) == expected_hash, f"Canonical text SHA-256 mismatch: {field}: {remote_id}")
    _require(hashes["before_description_sha256"] == expected["guard"], f"Reviewed guard mismatch: {remote_id}")
    _require(hashes["after_description_sha256"] == expected["after_guard"], f"Reviewed after guard mismatch: {remote_id}")
    _require(decision.get("expected_description_sha256") == expected["guard"], f"Decision guard mismatch: {remote_id}")
    _require(
        decision.get("replacement_ids") == expected["replacements"],
        f"Decision replacement order differs: {remote_id}",
    )
    applied = operation.get("applied_replacements")
    _require(isinstance(applied, list), f"Operation has no applied replacements: {remote_id}")
    applied_ids = [str(item.get("replacement_id")) for item in applied if isinstance(item, dict)]
    _require(applied_ids == expected["replacements"], f"Applied replacement order differs: {remote_id}")
    rebuilt = before_desc
    for item in applied:
        _require(isinstance(item, dict), f"Applied replacement is invalid: {remote_id}")
        replacement_id = str(item.get("replacement_id"))
        reviewed = replacements.get(replacement_id)
        _require(item == reviewed, f"Applied replacement differs from reviewed policy: {replacement_id}")
        old = str(reviewed["old"])
        new = str(reviewed["new"])
        count = int(reviewed["expected_count"])
        _require(rebuilt.count(old) == count, f"Replacement occurrence mismatch: {replacement_id}")
        rebuilt = rebuilt.replace(old, new, count)
    _require(rebuilt == after_desc, f"After-state is not reconstructed by reviewed replacements: {remote_id}")
    _require(_URL_RE.findall(before_desc) == _URL_RE.findall(after_desc), f"URLs changed: {remote_id}")
    _require(_HASHTAG_RE.findall(before_desc) == _HASHTAG_RE.findall(after_desc), f"Hashtags changed: {remote_id}")
    _require(after_desc.count("🎧 The Legendary Poet -") == 1, f"Final footer count differs: {remote_id}")


def verify_bundle(path: Path) -> dict[str, Any]:
    raw, outer_sha = _read_bundle(path)
    manifest = _json(raw["manifest.json"], "manifest.json")
    plan = _json(raw["plan.json"], "plan.json")
    decisions = _json(raw["reviewed-decisions.json"], "reviewed-decisions.json")
    snapshot = _json(raw["00-source-vk-snapshot.json"], "00-source-vk-snapshot.json")
    source_apply = _json(raw["source-apply-verification.json"], "source-apply-verification.json")
    build = _json(raw["00-build.txt"], "00-build.txt")
    _verify_members(raw, manifest)

    _require(manifest.get("status") == "completed", "Handoff is not completed")
    _require(manifest.get("artifact_kind") == "verified dry-run", "Handoff is not a verified dry-run")
    _require(manifest.get("mode") == "dry-run", "Handoff is not dry-run")
    _require(manifest.get("component_scope") == "descriptions_only", "Handoff is not descriptions_only")
    _require(manifest.get("correction_scope") == "reviewed_factual_and_sensitive", "Unexpected correction scope")
    _require(manifest.get("decision_set_id") == _DECISION_SET, "Handoff has another decision set")
    _require(int(manifest.get("community_id", 0)) == _COMMUNITY_ID, "Handoff targets another community")
    _require(
        (
            int(manifest.get("ready", -1)),
            int(manifest.get("already_applied", -1)),
            int(manifest.get("conflicts", -1)),
            int(manifest.get("remote_writes", -1)),
        )
        == (2, 0, 0, 0),
        "Unexpected dry-run counts or remote_writes",
    )
    _require(manifest.get("plan_sha256") == _PLAN_SHA, "Manifest plan SHA-256 differs")
    _require(manifest.get("source_review_bundle_sha256") == _SOURCE_REVIEW_SHA, "Manifest review SHA differs")
    _require(build.get("status") == "reviewed_correction_plan_built", "Build receipt status differs")
    _require(build.get("plan_sha256") == _PLAN_SHA, "Build receipt plan SHA differs")
    _require(int(build.get("descriptions_to_update", -1)) == 2, "Build receipt description count differs")
    _require(int(build.get("remote_writes", -1)) == 0, "Build receipt reports remote writes")

    calculated_plan_sha = _canonical_sha({key: value for key, value in plan.items() if key != "plan_sha256"})
    _require(calculated_plan_sha == _PLAN_SHA == plan.get("plan_sha256"), "Plan self-digest mismatch")
    decisions_sha = _canonical_sha(decisions)
    _require(decisions_sha == _DECISIONS_SHA, "Reviewed decisions digest differs")
    _require(plan.get("policy") == decisions, "Plan policy differs from reviewed decisions")
    _require(plan.get("policy_sha256") == decisions_sha, "Plan policy SHA differs")
    _require(plan.get("decisions_sha256") == decisions_sha, "Plan decisions SHA differs")
    _require(plan.get("decision_set_id") == _DECISION_SET, "Plan has another decision set")
    _require(plan.get("target_snapshot_id") == _SNAPSHOT_ID, "Plan snapshot ID differs")
    _require(plan.get("target_video_ids_sha256") == _VIDEO_COVERAGE_SHA, "Plan coverage SHA differs")
    _require(plan.get("initial_memberships_sha256") == _MEMBERSHIPS_SHA, "Plan memberships SHA differs")
    _require(plan.get("source_plan_sha256") == _SOURCE_PLAN_SHA, "Plan source description SHA differs")
    _require(plan.get("operation_scope") == "editorial_only", "Plan is not editorial_only")
    _require(plan.get("component_scope") == "descriptions_only", "Plan is not descriptions_only")
    _require(plan.get("correction_scope") == "reviewed_factual_and_sensitive", "Plan correction scope differs")
    _require(int(plan.get("target_community_id", 0)) == _COMMUNITY_ID, "Plan targets another community")
    _require(not plan.get("album_title_operations"), "Plan contains album operations")

    summary = plan.get("summary")
    _require(isinstance(summary, dict), "Plan has no summary")
    _require(int(summary.get("video_text_operations", -1)) == 2, "Plan operation count differs")
    _require(int(summary.get("descriptions_to_update", -1)) == 2, "Plan description count differs")
    for key in (
        "titles_to_update",
        "albums_to_rename",
        "placements_to_add",
        "placements_to_remove",
        "videos_to_delete",
        "review_only",
        "deferred_editorial_review",
    ):
        _require(int(summary.get(key, -1)) == 0, f"Plan contains forbidden scope: {key}")
    _require(int(summary.get("total_operations", -1)) == 2, "Plan total operation count differs")

    _verify_source_apply(source_apply, manifest)
    _verify_nested_review(raw["source-review-bundle.zip"])
    decisions_by_video, replacements = _verify_decisions(decisions)

    _require(snapshot.get("snapshot_id") == _SNAPSHOT_ID, "Source snapshot ID mismatch")
    videos = {_remote_id(item): item for item in snapshot.get("videos", []) if isinstance(item, dict)}
    _require(len(videos) == 111, "Source snapshot must contain exactly 111 videos")
    _require(len(snapshot.get("collections", [])) == 17, "Source snapshot must contain exactly 17 collections")
    _require(len(snapshot.get("memberships", [])) == 294, "Source snapshot must contain exactly 294 memberships")
    _require(_canonical_sha(sorted(videos)) == _VIDEO_COVERAGE_SHA, "Snapshot video coverage differs")
    membership_rows = sorted(
        (
            str(item["collection_ref"]["remote_id"]),
            str(item["video_ref"]["remote_id"]),
        )
        for item in snapshot.get("memberships", [])
        if isinstance(item, dict)
    )
    _require(_canonical_sha(membership_rows) == _MEMBERSHIPS_SHA, "Snapshot membership identity differs")

    operations = plan.get("video_text_operations")
    _require(isinstance(operations, list) and len(operations) == 2, "Plan must contain exactly two operations")
    by_video = {
        str(item.get("target_video_id")): item
        for item in operations
        if isinstance(item, dict)
    }
    _require(set(by_video) == set(_TARGETS), "Blok correction target IDs differ from reviewed set")
    for remote_id, operation in by_video.items():
        _verify_operation(
            remote_id,
            operation,
            videos[remote_id],
            decisions_by_video[remote_id],
            replacements,
        )

    combined_after = "\n".join(str(item["after_description"]) for item in by_video.values())
    for required in _REQUIRED_FINAL_WORDING:
        _require(required in combined_after, f"Corrected descriptions are missing reviewed wording: {required}")
    for forbidden in _FORBIDDEN_FINAL_WORDING:
        _require(forbidden not in combined_after, f"Corrected descriptions retain forbidden wording: {forbidden}")

    preflight = raw["01-preflight.txt"].decode("utf-8-sig")
    for required in (
        f"plan: {_PLAN_SHA}",
        f"video coverage: {_VIDEO_COVERAGE_SHA}",
        f"membership state: {_MEMBERSHIPS_SHA}",
        "ready: 2",
        "already applied: 0",
        "conflicts: 0",
        "No VK mutation method was called",
    ):
        _require(required in preflight, f"Preflight is missing exact evidence: {required}")

    return {
        "schema_name": "video-manager.vk-reviewed-correction-blok-dry-run-verification",
        "schema_version": 1,
        "status": "verified_dry_run",
        "artifact_review": "exact_independently_reviewed_contents",
        "bundle": str(path),
        "bundle_sha256": outer_sha,
        "outer_bundle_sha256_known": outer_sha in _KNOWN_OUTER_SHAS,
        "plan_sha256": _PLAN_SHA,
        "decisions_sha256": _DECISIONS_SHA,
        "community_id": _COMMUNITY_ID,
        "operations": 2,
        "target_video_ids": sorted(_TARGETS),
        "videos": 111,
        "collections": 17,
        "memberships": 294,
        "remote_writes": 0,
        "canonical_text_hashes_verified": True,
        "reviewed_replacements_reconstructed": True,
        "urls_and_hashtags_unchanged": True,
        "exact_member_hashes_verified": True,
    }


def main() -> int:
    args = _parser().parse_args()
    try:
        report = verify_bundle(args.bundle)
    except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        report = {
            "schema_name": "video-manager.vk-reviewed-correction-blok-dry-run-verification",
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
