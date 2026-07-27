from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.catalog import canonical_sha256, text_sha256
from video_channel_manager.platforms.vk.editorial_cleanup import clean_vk_description, clean_vk_title
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text

VK_EDITORIAL_CLEANUP_SCHEMA = "video-manager.vk-editorial-plan"
VK_EDITORIAL_CLEANUP_VERSION = 1
_FACT_RE = re.compile(
    r"\b(?:1[0-9]{3}|20[0-9]{2})\b|впервые|написал|написано|создан|родил|умер|гибел|"
    r"биограф|публикац|журнал|сборник|музей|архив|исследовател|историческ|псих|"
    r"самоубий|религи|вер[ауы]\b",
    re.IGNORECASE,
)
_SENSITIVE_RE = re.compile(
    r"самоубий|суицид|смерт|псих|грех|невери|Иисус|Христ|Бог\b|религи",
    re.IGNORECASE,
)
_TRIGGER_FAMILIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("dates", re.compile(r"\b(?:1[0-9]{3}|20[0-9]{2})\b")),
    (
        "authorship_or_creation",
        re.compile(r"впервые|написал|написано|создан", re.IGNORECASE),
    ),
    (
        "biography_or_death",
        re.compile(r"родил|умер|гибел|биограф|смерт", re.IGNORECASE),
    ),
    (
        "publication_or_history",
        re.compile(
            r"публикац|журнал|сборник|музей|архив|исследовател|историческ",
            re.IGNORECASE,
        ),
    ),
    (
        "psychology_or_self_harm",
        re.compile(r"псих|самоубий|суицид", re.IGNORECASE),
    ),
    (
        "religion_or_theology",
        re.compile(r"грех|невери|Иисус|Христ|Бог\b|религи|вер[ауы]\b", re.IGNORECASE),
    ),
)


def _is_system_collection(collection: Any) -> bool:
    raw_id = collection.metadata.get("id")
    return (
        collection.privacy_status == "system"
        or collection.ref.remote_id.startswith("-")
        or isinstance(raw_id, int)
        and raw_id < 0
        or bool(collection.metadata.get("is_system"))
    )


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _paragraphs(value: str) -> list[str]:
    return [paragraph for raw in re.split(r"\n\s*\n+", value) if (paragraph := _compact(raw))]


def _expanded_term(value: str, match: re.Match[str]) -> str:
    start, end = match.span()
    while start > 0 and (value[start - 1].isalnum() or value[start - 1] in "_-"):
        start -= 1
    while end < len(value) and (value[end].isalnum() or value[end] in "_-"):
        end += 1
    return value[start:end]


def _unique_matches(pattern: re.Pattern[str], value: str) -> list[str]:
    matches: list[str] = []
    seen: set[str] = set()
    for match in pattern.finditer(value):
        term = _expanded_term(value, match)
        key = term.casefold()
        if key not in seen:
            seen.add(key)
            matches.append(term)
    return matches


def _localized_evidence(pattern: re.Pattern[str], value: str) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for paragraph in _paragraphs(value):
        terms = _unique_matches(pattern, paragraph)
        if not terms:
            continue
        excerpt = paragraph if len(paragraph) <= 700 else f"{paragraph[:699].rstrip()}…"
        evidence.append({"matched_terms": terms, "excerpt": excerpt})
    return evidence


def _trigger_families(value: str) -> list[str]:
    return [name for name, pattern in _TRIGGER_FAMILIES if pattern.search(value)]


def build_vk_deferred_editorial_findings(remote_id: str, description: str) -> list[dict[str, Any]]:
    """Return deterministic review markers with exact local evidence.

    A marker means only that a passage should be checked. It is not a claim that
    the passage is wrong and it never authorizes an automatic correction.
    """

    findings: list[dict[str, Any]] = []
    factual_evidence = _localized_evidence(_FACT_RE, description)
    if factual_evidence:
        findings.append(
            {
                "kind": "factual_editorial_review",
                "target_video_id": remote_id,
                "message": "Technical cleanup preserves the factual body; claims require sourced review.",
                "trigger_families": _trigger_families(description),
                "matched_terms": _unique_matches(_FACT_RE, description),
                "evidence": factual_evidence,
            }
        )

    sensitive_evidence = _localized_evidence(_SENSITIVE_RE, description)
    if sensitive_evidence:
        findings.append(
            {
                "kind": "sensitive_claim_review",
                "target_video_id": remote_id,
                "message": "Sensitive religious, medical, death, or self-harm claims require manual review.",
                "trigger_families": _trigger_families(description),
                "matched_terms": _unique_matches(_SENSITIVE_RE, description),
                "evidence": sensitive_evidence,
            }
        )
    return findings


def target_video_ids_sha256(target: AuditPackage) -> str:
    return canonical_sha256(sorted(video.ref.remote_id for video in target.videos))


def membership_state_sha256(target: AuditPackage) -> str:
    return canonical_sha256(
        sorted(
            (membership.collection_ref.remote_id, membership.video_ref.remote_id) for membership in target.memberships
        )
    )


def calculate_vk_editorial_plan_sha256(plan: dict[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in plan.items() if key != "plan_sha256"})


def build_vk_editorial_cleanup_plan(target: AuditPackage, policy: dict[str, Any]) -> dict[str, Any]:
    if target.channel.ref.platform.value != "vk":
        raise ValueError("VK editorial target must be a VK AuditPackage")
    title_overrides = {str(key): str(value) for key, value in dict(policy.get("title_overrides") or {}).items()}
    album_overrides = {str(key): str(value) for key, value in dict(policy.get("album_title_overrides") or {}).items()}
    maximum = int(policy.get("description_policy", {}).get("max_length", 5000))
    video_operations: list[dict[str, Any]] = []
    review_only: list[dict[str, Any]] = []
    proposed_titles: dict[str, str] = {}

    for video in target.videos:
        remote_id = video.ref.remote_id
        before_title = canonical_vk_text(video.title)
        before_description = canonical_vk_text(video.description)
        after_title = clean_vk_title(before_title, title_overrides.get(remote_id))
        after_description = clean_vk_description(before_description, policy)
        proposed_titles[remote_id] = after_title
        if not after_title:
            raise ValueError(f"Proposed title is blank: {remote_id}")
        if len(after_description) > maximum:
            review_only.append(
                {
                    "kind": "description_too_long",
                    "target_video_id": remote_id,
                    "length": len(after_description),
                    "maximum": maximum,
                }
            )
            after_description = before_description
        if before_title != after_title or before_description != after_description:
            video_operations.append(
                {
                    "operation_id": f"video-text:update:{remote_id}",
                    "target_video_id": remote_id,
                    "duration_seconds": video.duration_seconds,
                    "before_title": before_title,
                    "after_title": after_title,
                    "before_description": before_description,
                    "after_description": after_description,
                    "before_title_sha256": text_sha256(before_title),
                    "after_title_sha256": text_sha256(after_title),
                    "before_description_sha256": text_sha256(before_description),
                    "after_description_sha256": text_sha256(after_description),
                    "title_changed": before_title != after_title,
                    "description_changed": before_description != after_description,
                }
            )
        review_only.extend(build_vk_deferred_editorial_findings(remote_id, before_description))

    duplicate_titles: dict[str, list[str]] = defaultdict(list)
    for remote_id, title in proposed_titles.items():
        duplicate_titles[title.casefold()].append(remote_id)
    for remote_ids in duplicate_titles.values():
        if len(remote_ids) > 1:
            review_only.append(
                {
                    "kind": "duplicate_proposed_title",
                    "proposed_title": proposed_titles[remote_ids[0]],
                    "target_video_ids": sorted(remote_ids),
                }
            )
    if "-235216998_456239033" in proposed_titles:
        review_only.append(
            {
                "kind": "title_duration_conflict",
                "target_video_id": "-235216998_456239033",
                "message": "The 73-second video claims to be a full poem; confirm the label manually.",
            }
        )
    review_only.append(
        {
            "kind": "mention_rendering_ui_test_required",
            "message": "VK mention markup is excluded until ordinary-video UI behavior is tested.",
        }
    )

    album_operations: list[dict[str, Any]] = []
    for collection in target.collections:
        if _is_system_collection(collection):
            continue
        collection_id = collection.ref.remote_id
        before_title = canonical_vk_text(collection.title)
        after_title = canonical_vk_text(album_overrides.get(collection_id, before_title))
        if before_title != after_title:
            album_operations.append(
                {
                    "operation_id": f"album-title:update:{collection_id}",
                    "target_collection_id": collection_id,
                    "before_title": before_title,
                    "after_title": after_title,
                    "before_title_sha256": text_sha256(before_title),
                    "after_title_sha256": text_sha256(after_title),
                    "count": collection.metadata.get("count"),
                    "share_url": collection.metadata.get("share_url"),
                }
            )

    video_operations.sort(key=lambda item: item["operation_id"])
    album_operations.sort(key=lambda item: item["operation_id"])
    review_only.sort(key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    plan: dict[str, Any] = {
        "schema_name": VK_EDITORIAL_CLEANUP_SCHEMA,
        "schema_version": VK_EDITORIAL_CLEANUP_VERSION,
        "operation_scope": "editorial_only",
        "generated_at": datetime.now(UTC).isoformat(),
        "target_snapshot_id": str(target.snapshot_id),
        "target_community_id": int(target.channel.ref.channel_id),
        "target_video_ids_sha256": target_video_ids_sha256(target),
        "initial_memberships_sha256": membership_state_sha256(target),
        "policy": policy,
        "policy_sha256": canonical_sha256(policy),
        "video_text_operations": video_operations,
        "album_title_operations": album_operations,
        "review_only": review_only,
    }
    plan["summary"] = {
        "videos_in_snapshot": len(target.videos),
        "video_text_operations": len(video_operations),
        "titles_to_update": sum(bool(item["title_changed"]) for item in video_operations),
        "descriptions_to_update": sum(bool(item["description_changed"]) for item in video_operations),
        "albums_to_rename": len(album_operations),
        "placements_to_add": 0,
        "placements_to_remove": 0,
        "videos_to_delete": 0,
        "review_only": len(review_only),
        "total_operations": len(video_operations) + len(album_operations),
    }
    plan["plan_sha256"] = calculate_vk_editorial_plan_sha256(plan)
    validate_vk_editorial_cleanup_plan(plan)
    return plan


def validate_vk_editorial_cleanup_plan(plan: dict[str, Any]) -> None:
    if plan.get("schema_name") != VK_EDITORIAL_CLEANUP_SCHEMA:
        raise ValueError("Unexpected VK editorial plan schema")
    if plan.get("schema_version") != VK_EDITORIAL_CLEANUP_VERSION:
        raise ValueError("Unsupported VK editorial plan version")
    if plan.get("operation_scope") != "editorial_only":
        raise ValueError("VK editorial plan must have editorial_only scope")
    if not isinstance(plan.get("target_community_id"), int) or plan["target_community_id"] <= 0:
        raise ValueError("target_community_id must be a positive integer")
    for forbidden in ("placement_operations", "placement_removals", "video_deletions"):
        if plan.get(forbidden):
            raise ValueError(f"Editorial plan cannot contain {forbidden}")
    for field in (
        "target_video_ids_sha256",
        "initial_memberships_sha256",
        "policy_sha256",
        "plan_sha256",
    ):
        if not isinstance(plan.get(field), str) or not plan[field].startswith("sha256:"):
            raise ValueError(f"{field} must contain a SHA-256 digest")
    if plan["plan_sha256"] != calculate_vk_editorial_plan_sha256(plan):
        raise ValueError("VK editorial plan self-digest does not match its contents")

    operation_ids: list[str] = []
    maximum = int(plan.get("policy", {}).get("description_policy", {}).get("max_length", 5000))
    for operation in plan.get("video_text_operations", []):
        operation_ids.append(operation["operation_id"])
        for side in ("before", "after"):
            for field in ("title", "description"):
                value = str(operation[f"{side}_{field}"])
                if operation[f"{side}_{field}_sha256"] != text_sha256(value):
                    raise ValueError(f"Text hash mismatch in {operation['operation_id']}: {side}_{field}")
        if not canonical_vk_text(str(operation["after_title"])):
            raise ValueError(f"Blank title in {operation['operation_id']}")
        if len(str(operation["after_description"])) > maximum:
            raise ValueError(f"Description exceeds {maximum} characters in {operation['operation_id']}")
    for operation in plan.get("album_title_operations", []):
        operation_ids.append(operation["operation_id"])
        for side in ("before", "after"):
            value = str(operation[f"{side}_title"])
            if operation[f"{side}_title_sha256"] != text_sha256(value):
                raise ValueError(f"Album title hash mismatch in {operation['operation_id']}: {side}")
    duplicates = [item for item, count in Counter(operation_ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"Duplicate operation IDs: {duplicates}")
    summary = plan.get("summary")
    expected_total = len(plan.get("video_text_operations", [])) + len(plan.get("album_title_operations", []))
    if not isinstance(summary, dict) or int(summary.get("total_operations", -1)) != expected_total:
        raise ValueError("summary.total_operations does not match operations")
    if any(
        int(summary.get(field, -1)) != 0 for field in ("placements_to_add", "placements_to_remove", "videos_to_delete")
    ):
        raise ValueError("Editorial plan cannot contain catalog or deletion operations")


__all__ = [
    "build_vk_deferred_editorial_findings",
    "build_vk_editorial_cleanup_plan",
    "calculate_vk_editorial_plan_sha256",
    "membership_state_sha256",
    "target_video_ids_sha256",
    "validate_vk_editorial_cleanup_plan",
]
