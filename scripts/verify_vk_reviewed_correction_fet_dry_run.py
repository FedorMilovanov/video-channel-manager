#!/usr/bin/env python3
"""Verify the exact reviewed contents of a Fet correction dry-run ZIP."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

_PLAN_SHA = "sha256:095c0a1cce72a46eaee0a1ea37ca2e2ee6a682bbf393f3d02d6d7abece1872ec"
_DECISIONS_SHA = "sha256:ac13aaf20358d42db1808bcda46dd2a04fffc6c56abc85d6b3246fb10b3cd2d0"
_SOURCE_PLAN_SHA = "sha256:b4eede44954bcb148550bcb2c0a372e4f23b72d892cc3aadcc5d71321a2e9294"
_SOURCE_APPLY_SHA = "sha256:af11d5c882d8068b316b606723410f6d45bda49d5dd327c92dc011b265f23398"
_SOURCE_REVIEW_SHA = "sha256:f38191f18d859ef2bcd445f558204ac76e3c3ebbe4f6414cb3436542df7b4c61"
_VIDEO_COVERAGE_SHA = "sha256:94ef18173ade06658d421cbaeced7fdbada8d9766760adfee289df7bdbe3148e"
_MEMBERSHIPS_SHA = "sha256:bdb556321dce7b5dd9400de33c92fb186dce55faac327f0a5a077491bfd5b966"
_SNAPSHOT_ID = "c8020c66-29e6-40e1-8f65-9f412c4dc158"
_DECISION_SET = "p1-fet-whisper-20260727"
_COMMUNITY_ID = 235216998
_KNOWN_OUTER_SHAS = frozenset(
    {
        "sha256:0f8020fd76456f8b6490e17e2142d46ca8f18f397ded400c3c093bbf719539f5",
        "sha256:8e173fba66cc0b298d1d87db384cb6a15e60c0c8d36c45db4ebb3e580a2221b9",
    }
)
_EXPECTED_MEMBERS = {
    "00-build.txt": (
        385,
        "sha256:807b4f190140dce52c0dabed4f00912d4a7dc0b77d8a75a0621339045f0c7a92",
    ),
    "00-source-vk-snapshot.json": (
        2597646,
        "sha256:25fc588011fe3e2fe85113bb417e1025f2926538d2d47306a8d0c7a500a2b79f",
    ),
    "01-preflight.txt": (
        789,
        "sha256:d039c9db452408b869e4e6b22da385209cf2cd6fcf6d5780d581547e34466843",
    ),
    "plan-review.html": (
        26846,
        "sha256:37bc58a64cb06b8fc2c3804668571b4c02f46764558984b7136974493b4400a9",
    ),
    "plan-review.md": (
        25904,
        "sha256:4c5bdd58feb7ac4f69236755be87e477c4bac199c0b84a5cad7211d278e5a4e5",
    ),
    "plan.json": (
        60561,
        "sha256:b055b628ba658b36c851d33f85c26ede11785f0adf0acd796be937dcf12a7c5e",
    ),
    "README.txt": (
        1523,
        "sha256:0c70156625f2a3d5a0aecdc543095c7f236d6c79caa022836dd90af11b55485d",
    ),
    "reviewed-decisions.json": (
        17281,
        "sha256:6cef2d641a9e59a1dd249fe2001e429e43e7bb4446bdf86e6ee13310e62e4ef0",
    ),
    "source-apply-verification.json": (
        1942,
        "sha256:27a7d777814200775c5efd799beb9af2415bc3a188a9657a8a215218c551a2e7",
    ),
    "source-review-bundle.zip": (459225, _SOURCE_REVIEW_SHA),
}
_REQUIRED_FILES = frozenset({"manifest.json", *_EXPECTED_MEMBERS})
_TARGETS = {
    "-235216998_456239127": {
        "decision_id": "correct-456239127",
        "title": "«Шёпот, Робкое Дыханье…» ⚡ Афанасий Фет",
        "guard": "sha256:eb10b7f1e529c26c240dada4116d2a9666b33bb4e0e167839ad3f9762e959203",
        "replacements": ["replace-short-fet-biography-and-attribution"],
    },
    "-235216998_456239143": {
        "decision_id": "correct-456239143",
        "title": "«Шёпот, Робкое Дыханье…» ⚡ Фет Слышит Пульс Зари",
        "guard": "sha256:76c74c96f9aaa93d952531094d42c4b7a168f901566688bd349febd8b7b0c6b9",
        "replacements": [
            "qualify-whisper-biographical-background",
            "attribute-lazich-death-and-cycle",
            "correct-late-love-cycle-and-fet-death",
            "remove-truncated-footer-fragment",
        ],
    },
}
_REPLACEMENT_IDS = frozenset(
    {
        "replace-short-fet-biography-and-attribution",
        "qualify-whisper-biographical-background",
        "attribute-lazich-death-and-cycle",
        "correct-late-love-cycle-and-fet-death",
        "remove-truncated-footer-fragment",
    }
)
_SOURCE_IDS = frozenset(
    {
        "rvb-fet-bukhshtab-biography",
        "rvb-fet-complete-edition",
        "voplit-fet-verb-free-chernyshevsky",
        "feb-fet-death-kudryavtseva",
        "feb-kle-fet-lazich-cycle",
        "site-project-charter",
        "site-editorial-judgment-policy",
        "research-knowledge-base",
    }
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


def _read_bundle(path: Path) -> tuple[dict[str, bytes], str]:
    bundle_sha = _file_sha(path.read_bytes())
    with zipfile.ZipFile(path) as archive:
        names = [entry.filename for entry in archive.infolist()]
        _require(len(names) == len(set(names)), "Bundle contains duplicate ZIP entries")
        _require(set(names) == set(_REQUIRED_FILES), "Bundle contains a different file set")
        return {name: archive.read(name) for name in names}, bundle_sha


def _verify_members(raw: dict[str, bytes], manifest: dict[str, Any]) -> None:
    records = {
        str(item.get("name")): item for item in manifest.get("files", []) if isinstance(item, dict) and item.get("name")
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
        _require(required <= set(names), "Nested source review bundle is incomplete")
        nested = {name: archive.read(name) for name in names}
    manifest = _json(nested["manifest.json"], "nested manifest.json")
    queue = _json(nested["review-queue.json"], "review-queue.json")
    _require(manifest.get("status") == "review_only_completed", "Nested review is not completed")
    _require(queue.get("mode") == "review_only", "Nested review is not review-only")
    _require(int(queue.get("remote_writes", -1)) == 0, "Nested review reports remote writes")


def _verify_source_apply(source: dict[str, Any], manifest: dict[str, Any]) -> None:
    _require(source.get("status") == "verified_completed", "Source apply verification is not completed")
    _require(source.get("bundle_sha256") == _SOURCE_APPLY_SHA, "Source apply bundle SHA-256 mismatch")
    _require(manifest.get("source_apply_bundle_sha256") == _SOURCE_APPLY_SHA, "Manifest source apply SHA mismatch")
    _require(source.get("operation_statuses") == {"updated_and_verified": 3}, "Source apply statuses differ")
    _require(int(source.get("operations", -1)) == 3, "Source apply operation count differs")
    _require(int(source.get("remote_writes", -1)) == 3, "Source apply write count differs")
    _require(int(source.get("non_target_videos_verified_unchanged", -1)) == 108, "Source non-target proof differs")
    _require(source.get("membership_identity_unchanged") is True, "Source membership identity changed")
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
    _require(set(replacements) == set(_REPLACEMENT_IDS), "Fet replacement IDs differ from the reviewed set")
    for replacement_id, replacement in replacements.items():
        _require(int(replacement.get("expected_count", -1)) == 1, f"Replacement is not exact-once: {replacement_id}")
        old = str(replacement.get("old") or "")
        new = str(replacement.get("new") or "")
        _require(_URL_RE.findall(old) == _URL_RE.findall(new), f"Replacement changes URLs: {replacement_id}")
        _require(
            _HASHTAG_RE.findall(old) == _HASHTAG_RE.findall(new), f"Replacement changes hashtags: {replacement_id}"
        )
    by_video = {
        str(item.get("target_video_id")): item for item in decisions.get("decisions", []) if isinstance(item, dict)
    }
    _require(set(by_video) == set(_TARGETS), "Fet decision target IDs differ from the reviewed set")
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
    _require(before_title == expected["title"] == after_title, f"Title changes in Fet operation: {remote_id}")
    _require(not bool(operation.get("title_changed")), f"title_changed is true: {remote_id}")
    _require(bool(operation.get("description_changed")), f"description_changed is false: {remote_id}")
    _require(source_video.get("title") == before_title, f"Source title differs: {remote_id}")
    _require(source_video.get("description") == before_desc, f"Source description differs: {remote_id}")
    _require(0 < len(after_desc) <= 5000, f"Invalid corrected description length: {remote_id}")
    hashes = {
        "before_title_sha256": _canonical_sha(before_title),
        "after_title_sha256": _canonical_sha(after_title),
        "before_description_sha256": _canonical_sha(before_desc),
        "after_description_sha256": _canonical_sha(after_desc),
    }
    for field, expected_hash in hashes.items():
        _require(operation.get(field) == expected_hash, f"Canonical text SHA-256 mismatch: {field}: {remote_id}")
    _require(hashes["before_description_sha256"] == expected["guard"], f"Reviewed guard mismatch: {remote_id}")
    _require(decision.get("expected_description_sha256") == expected["guard"], f"Decision guard mismatch: {remote_id}")
    _require(
        decision.get("replacement_ids") == expected["replacements"], f"Decision replacement order differs: {remote_id}"
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
    _require(rebuilt == after_desc, f"After-state is not exactly reconstructed by reviewed replacements: {remote_id}")
    _require(
        _URL_RE.findall(before_desc) == _URL_RE.findall(after_desc), f"URLs changed during Fet correction: {remote_id}"
    )
    _require(
        _HASHTAG_RE.findall(before_desc) == _HASHTAG_RE.findall(after_desc),
        f"Hashtags changed during Fet correction: {remote_id}",
    )
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
    _require(plan.get("target_snapshot_id") == _SNAPSHOT_ID, "Plan snapshot ID differs")
    _require(plan.get("target_video_ids_sha256") == _VIDEO_COVERAGE_SHA, "Plan coverage SHA differs")
    _require(plan.get("initial_memberships_sha256") == _MEMBERSHIPS_SHA, "Plan memberships SHA differs")
    _require(plan.get("source_plan_sha256") == _SOURCE_PLAN_SHA, "Plan source description SHA differs")
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
    videos = {
        str(item.get("ref", {}).get("remote_id")): item
        for item in snapshot.get("videos", [])
        if isinstance(item, dict) and isinstance(item.get("ref"), dict)
    }
    _require(len(videos) == 111, "Source snapshot must contain exactly 111 videos")
    _require(len(snapshot.get("collections", [])) == 17, "Source snapshot must contain exactly 17 collections")
    _require(len(snapshot.get("memberships", [])) == 294, "Source snapshot must contain exactly 294 memberships")
    operations = plan.get("video_text_operations")
    _require(isinstance(operations, list) and len(operations) == 2, "Plan must contain exactly two operations")
    by_video = {str(item.get("target_video_id")): item for item in operations if isinstance(item, dict)}
    _require(set(by_video) == set(_TARGETS), "Fet correction target IDs differ from the reviewed set")
    for remote_id, operation in by_video.items():
        _verify_operation(
            remote_id,
            operation,
            videos[remote_id],
            decisions_by_video[remote_id],
            replacements,
        )
    combined_after = "\n".join(str(item["after_description"]) for item in by_video.values())
    for required in (
        "датируется 1850 годом",
        "прямого авторского посвящения",
        "могло скрывать самоубийство",
        "другой поздний цикл 1882–1892 годов",
        "воспоминаниям секретаря Е. В. Кудрявцевой",
    ):
        _require(required in combined_after, f"Corrected descriptions are missing reviewed wording: {required}")
    for forbidden in (
        "Фет посвятил его Марии Лазич",
        "Фет всю жизнь писал только ей",
        "Последнее стихотворение, посвящённое Марии Лазич, датировано 1892 годом",
        "единственной героиней любовной лирики на всю жизнь",
        "смерть наступила от сердечного приступа",
    ):
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
        "schema_name": "video-manager.vk-reviewed-correction-fet-dry-run-verification",
        "schema_version": 3,
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
            "schema_name": "video-manager.vk-reviewed-correction-fet-dry-run-verification",
            "schema_version": 3,
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
