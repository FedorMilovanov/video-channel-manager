from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from video_channel_manager.editorial._project_profiles import resolve_project_key
from video_channel_manager.platforms.http import HttpFailureKind
from video_channel_manager.platforms.vk.catalog import canonical_sha256
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text
from video_channel_manager.platforms.vk.wall import VkWallWriter
from video_channel_manager.platforms.vk.wall_safety import (
    VkWallSnapshot,
    VkWallSurface,
    build_wall_snapshot,
    canonical_wall_attachment,
)
from video_channel_manager.platforms.vk.writer import VkWriteError

VK_POSTPONED_TEXT_EDIT_REQUEST_SCHEMA = "video-manager.vk-postponed-text-edit-request"
VK_POSTPONED_TEXT_EDIT_REQUEST_VERSION = 1
VK_POSTPONED_TEXT_EDIT_PLAN_SCHEMA = "video-manager.vk-postponed-text-edit-plan"
VK_POSTPONED_TEXT_EDIT_PLAN_VERSION = 1
VK_POSTPONED_TEXT_EDIT_RESULT_SCHEMA = "video-manager.vk-postponed-text-edit-result"
VK_POSTPONED_TEXT_EDIT_RESULT_VERSION = 1

_TRANSIENT_PROVIDER_CODES = frozenset({6, 9, 10, 29})
_TRANSIENT_FAILURE_KINDS = frozenset(
    {
        HttpFailureKind.RATE_LIMIT,
        HttpFailureKind.TRANSIENT_HTTP,
        HttpFailureKind.PROVIDER_TRANSIENT,
    }
)


class VkPostponedTextState(StrEnum):
    BEFORE = "before"
    AFTER = "after"
    CONFLICT = "conflict"


class VkPostponedTextEditError(RuntimeError):
    pass


def _normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _text_sha256(value: str) -> str:
    normalized = _normalize_newlines(value)
    return f"sha256:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"


def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{time.time_ns()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return cast(dict[str, Any], payload)


def calculate_vk_postponed_text_plan_sha256(plan: Mapping[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in plan.items() if key != "plan_sha256"})


def _validate_project_identity(
    *, project_key: object, community_id: object, owner_id: object
) -> tuple[str, int, int]:
    if type(community_id) is not int or community_id <= 0:
        raise ValueError("community_id must be a positive exact integer")
    if type(owner_id) is not int or owner_id != -community_id:
        raise ValueError("owner_id must exactly equal -community_id")
    resolved = resolve_project_key(
        {
            "project_key": project_key,
            "community_id": community_id,
            "owner_id": owner_id,
        }
    )
    if resolved is None or resolved != project_key:
        raise ValueError("project/community/owner identity is unknown or inconsistent")
    return resolved, community_id, owner_id


def _validate_rule(raw: object, *, index: int) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"rules[{index}] must be an object")
    match = str(raw.get("match") or "").strip()
    if match not in {"exact", "prefix"}:
        raise ValueError(f"rules[{index}].match must be exact or prefix")
    value = _normalize_newlines(str(raw.get("value") or "")).strip()
    if not value or "\n" in value:
        raise ValueError(f"rules[{index}].value must be one non-empty line")
    expected = raw.get("expected_per_post")
    if type(expected) is not int or expected < 0:
        raise ValueError(f"rules[{index}].expected_per_post must be a non-negative exact integer")
    return {"match": match, "value": value, "expected_per_post": expected}


def validate_vk_postponed_text_edit_request(request: Mapping[str, Any]) -> dict[str, Any]:
    if request.get("schema_name") != VK_POSTPONED_TEXT_EDIT_REQUEST_SCHEMA:
        raise ValueError("unsupported VK postponed-text edit request schema")
    if request.get("schema_version") != VK_POSTPONED_TEXT_EDIT_REQUEST_VERSION:
        raise ValueError("unsupported VK postponed-text edit request version")
    project_key, community_id, owner_id = _validate_project_identity(
        project_key=request.get("project_key"),
        community_id=request.get("community_id"),
        owner_id=request.get("owner_id"),
    )
    expected_count = request.get("expected_postponed_count")
    if type(expected_count) is not int or expected_count <= 0:
        raise ValueError("expected_postponed_count must be a positive exact integer")
    raw_ids = request.get("target_post_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise ValueError("target_post_ids must be a non-empty list")
    if any(type(post_id) is not int or post_id <= 0 for post_id in raw_ids):
        raise ValueError("target_post_ids must contain positive exact integers")
    target_ids = cast(list[int], list(raw_ids))
    if target_ids != sorted(target_ids) or len(target_ids) != len(set(target_ids)):
        raise ValueError("target_post_ids must be sorted and unique")
    raw_rules = request.get("rules")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ValueError("rules must be a non-empty list")
    rules = [_validate_rule(rule, index=index) for index, rule in enumerate(raw_rules)]
    allow_attachments = request.get("allow_attachments", False)
    if type(allow_attachments) is not bool:
        raise ValueError("allow_attachments must be an exact boolean")
    normalized: dict[str, Any] = {
        "schema_name": VK_POSTPONED_TEXT_EDIT_REQUEST_SCHEMA,
        "schema_version": VK_POSTPONED_TEXT_EDIT_REQUEST_VERSION,
        "project_key": project_key,
        "community_id": community_id,
        "owner_id": owner_id,
        "expected_postponed_count": expected_count,
        "target_post_ids": target_ids,
        "rules": rules,
        "allow_attachments": allow_attachments,
    }
    normalized["request_sha256"] = canonical_sha256(normalized)
    return normalized


def _canonical_attachments(post: Mapping[str, Any]) -> tuple[str, ...]:
    raw = post.get("attachments") or []
    if not isinstance(raw, list):
        raise VkPostponedTextEditError("post attachments must be a list")
    tokens: list[str] = []
    for index, attachment in enumerate(raw):
        if not isinstance(attachment, Mapping):
            raise VkPostponedTextEditError(f"attachment #{index} is not an object")
        token = canonical_wall_attachment(attachment)
        if token is None:
            raise VkPostponedTextEditError(
                f"attachment #{index} cannot be preserved through canonical wall.edit identity"
            )
        tokens.append(token)
    return tuple(sorted(tokens))


def _read_complete_wall(
    writer: VkWallWriter,
    *,
    community_id: int,
    max_posts_per_surface: int,
) -> tuple[VkWallSnapshot, list[dict[str, Any]], list[dict[str, Any]]]:
    published, published_pages, published_complete = writer._read_wall_surface(
        community_id=community_id,
        surface=VkWallSurface.PUBLISHED,
        max_posts=max_posts_per_surface,
    )
    postponed, postponed_pages, postponed_complete = writer._read_wall_surface(
        community_id=community_id,
        surface=VkWallSurface.POSTPONED,
        max_posts=max_posts_per_surface,
    )
    snapshot = build_wall_snapshot(
        community_id=community_id,
        published_items=published,
        postponed_items=postponed,
        published_pages=published_pages,
        postponed_pages=postponed_pages,
        complete=published_complete and postponed_complete,
    )
    if not snapshot.complete:
        raise VkPostponedTextEditError("VK wall snapshot is incomplete")
    return snapshot, published, postponed


def _read_postponed(
    writer: VkWallWriter,
    *,
    community_id: int,
    owner_id: int,
    expected_count: int,
    max_posts_per_surface: int,
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    posts, _pages, complete = writer._read_wall_surface(
        community_id=community_id,
        surface=VkWallSurface.POSTPONED,
        max_posts=max_posts_per_surface,
    )
    if not complete or len(posts) != expected_count:
        raise VkPostponedTextEditError(
            f"postponed surface changed or is incomplete: expected {expected_count}, observed {len(posts)}"
        )
    return posts, _postponed_by_id(posts, owner_id=owner_id)


def _postponed_by_id(posts: list[dict[str, Any]], *, owner_id: int) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for post in posts:
        post_id = post.get("id")
        if post.get("owner_id") != owner_id or type(post_id) is not int or post_id <= 0:
            raise VkPostponedTextEditError("postponed surface contains an invalid post identity")
        if post_id in result:
            raise VkPostponedTextEditError(f"postponed surface duplicated post_id {post_id}")
        result[post_id] = post
    return result


def _line_matches_rule(line: str, rule: Mapping[str, Any]) -> bool:
    candidate = line.strip()
    value = str(rule["value"])
    return candidate == value if rule["match"] == "exact" else candidate.startswith(value)


def _apply_rules(text: str, rules: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    kept: list[str] = []
    removed: list[dict[str, Any]] = []
    counts = [0 for _ in rules]
    for line_number, line in enumerate(_normalize_newlines(text).split("\n"), start=1):
        matches = [index for index, rule in enumerate(rules) if _line_matches_rule(line, rule)]
        if len(matches) > 1:
            raise VkPostponedTextEditError(
                f"line {line_number} matches multiple removal rules: {line.strip()}"
            )
        if not matches:
            kept.append(line)
            continue
        rule_index = matches[0]
        counts[rule_index] += 1
        removed.append({"line_number": line_number, "line": line.strip(), "rule_index": rule_index})
    for index, rule in enumerate(rules):
        expected = int(rule["expected_per_post"])
        if counts[index] != expected:
            raise VkPostponedTextEditError(
                f"rule {index} expected {expected} match(es), observed {counts[index]}"
            )
    after = "\n".join(kept).strip("\n")
    if not after.strip():
        raise VkPostponedTextEditError("text cleanup would produce an empty post")
    if canonical_vk_text(after) != after:
        raise VkPostponedTextEditError("resulting text is not stable canonical VK plain text")
    return after, removed


def build_vk_postponed_text_edit_plan(
    writer: VkWallWriter,
    request: Mapping[str, Any],
    *,
    max_posts_per_surface: int = 10000,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    normalized = validate_vk_postponed_text_edit_request(request)
    community_id = int(normalized["community_id"])
    owner_id = int(normalized["owner_id"])
    snapshot, _published, postponed = _read_complete_wall(
        writer,
        community_id=community_id,
        max_posts_per_surface=max_posts_per_surface,
    )
    expected_count = int(normalized["expected_postponed_count"])
    if len(postponed) != expected_count:
        raise VkPostponedTextEditError(
            f"postponed count changed: expected {expected_count}, observed {len(postponed)}"
        )
    by_id = _postponed_by_id(postponed, owner_id=owner_id)
    rules = cast(list[dict[str, Any]], normalized["rules"])
    allow_attachments = bool(normalized["allow_attachments"])
    operations: list[dict[str, Any]] = []
    for post_id in cast(list[int], normalized["target_post_ids"]):
        post = by_id.get(post_id)
        if post is None:
            raise VkPostponedTextEditError(f"target post {post_id} is absent from postponed surface")
        publish_date = post.get("date")
        if type(publish_date) is not int or publish_date <= 0:
            raise VkPostponedTextEditError(f"target post {post_id} has no exact publish_date")
        before_text = _normalize_newlines(str(post.get("text") or ""))
        attachments = _canonical_attachments(post)
        if attachments and not allow_attachments:
            raise VkPostponedTextEditError(
                f"target post {post_id} has attachments but allow_attachments is false"
            )
        after_text, removed_lines = _apply_rules(before_text, rules)
        operation_seed = {
            "project_key": normalized["project_key"],
            "owner_id": owner_id,
            "post_id": post_id,
            "publish_date": publish_date,
            "before_text_sha256": _text_sha256(before_text),
            "after_text_sha256": _text_sha256(after_text),
            "attachments": list(attachments),
        }
        operations.append(
            {
                "operation_id": (
                    "vk-postponed-text-edit-"
                    + canonical_sha256(operation_seed).removeprefix("sha256:")[:32]
                ),
                "owner_id": owner_id,
                "post_id": post_id,
                "publish_date": publish_date,
                "before_text": before_text,
                "before_text_sha256": operation_seed["before_text_sha256"],
                "after_text": after_text,
                "after_text_sha256": operation_seed["after_text_sha256"],
                "attachments": list(attachments),
                "removed_lines": removed_lines,
            }
        )
    captured_at = generated_at or datetime.now(UTC)
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    plan: dict[str, Any] = {
        "schema_name": VK_POSTPONED_TEXT_EDIT_PLAN_SCHEMA,
        "schema_version": VK_POSTPONED_TEXT_EDIT_PLAN_VERSION,
        "generated_at": captured_at.astimezone(UTC).isoformat(),
        "project_key": normalized["project_key"],
        "community_id": community_id,
        "owner_id": owner_id,
        "expected_postponed_count": expected_count,
        "target_post_ids": normalized["target_post_ids"],
        "allow_attachments": allow_attachments,
        "rules": rules,
        "request_sha256": normalized["request_sha256"],
        "source_snapshot": snapshot.as_dict(),
        "operation_count": len(operations),
        "operations": operations,
    }
    plan["plan_sha256"] = calculate_vk_postponed_text_plan_sha256(plan)
    return validate_vk_postponed_text_edit_plan(plan)


def validate_vk_postponed_text_edit_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if plan.get("schema_name") != VK_POSTPONED_TEXT_EDIT_PLAN_SCHEMA:
        raise ValueError("unsupported VK postponed-text edit plan schema")
    if plan.get("schema_version") != VK_POSTPONED_TEXT_EDIT_PLAN_VERSION:
        raise ValueError("unsupported VK postponed-text edit plan version")
    project_key, community_id, owner_id = _validate_project_identity(
        project_key=plan.get("project_key"),
        community_id=plan.get("community_id"),
        owner_id=plan.get("owner_id"),
    )
    expected_count = plan.get("expected_postponed_count")
    if type(expected_count) is not int or expected_count <= 0:
        raise ValueError("expected_postponed_count must be a positive exact integer")
    target_ids_raw = plan.get("target_post_ids")
    operations_raw = plan.get("operations")
    rules_raw = plan.get("rules")
    if not isinstance(target_ids_raw, list) or not isinstance(operations_raw, list):
        raise ValueError("target_post_ids and operations must be lists")
    if any(type(post_id) is not int or post_id <= 0 for post_id in target_ids_raw):
        raise ValueError("target_post_ids must contain positive exact integers")
    target_ids = cast(list[int], target_ids_raw)
    if target_ids != sorted(target_ids) or len(target_ids) != len(set(target_ids)):
        raise ValueError("target_post_ids must be sorted and unique")
    if plan.get("operation_count") != len(operations_raw) or len(operations_raw) != len(target_ids):
        raise ValueError("operation_count must exactly match target_post_ids")
    if not isinstance(rules_raw, list) or not rules_raw:
        raise ValueError("rules must be a non-empty list")
    rules = [_validate_rule(rule, index=index) for index, rule in enumerate(rules_raw)]
    allow_attachments = plan.get("allow_attachments")
    if type(allow_attachments) is not bool:
        raise ValueError("allow_attachments must be an exact boolean")
    snapshot_raw = plan.get("source_snapshot")
    if not isinstance(snapshot_raw, Mapping):
        raise ValueError("source_snapshot must be an object")
    snapshot = VkWallSnapshot.from_mapping(snapshot_raw)
    if snapshot.community_id != community_id or not snapshot.complete:
        raise ValueError("source_snapshot is incomplete or belongs to another community")
    postponed_fingerprints = {
        post.post_id: post for post in snapshot.posts if post.surface is VkWallSurface.POSTPONED
    }
    if len(postponed_fingerprints) != expected_count:
        raise ValueError("source_snapshot postponed count differs from plan baseline")
    generated_at = datetime.fromisoformat(str(plan.get("generated_at") or ""))
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    request_payload = {
        "schema_name": VK_POSTPONED_TEXT_EDIT_REQUEST_SCHEMA,
        "schema_version": VK_POSTPONED_TEXT_EDIT_REQUEST_VERSION,
        "project_key": project_key,
        "community_id": community_id,
        "owner_id": owner_id,
        "expected_postponed_count": expected_count,
        "target_post_ids": target_ids,
        "rules": rules,
        "allow_attachments": allow_attachments,
    }
    if plan.get("request_sha256") != canonical_sha256(request_payload):
        raise ValueError("request_sha256 does not match the plan request fields")

    operations: list[dict[str, Any]] = []
    operation_ids: set[str] = set()
    for index, raw in enumerate(operations_raw):
        if not isinstance(raw, Mapping):
            raise ValueError(f"operations[{index}] must be an object")
        operation = dict(raw)
        post_id = operation.get("post_id")
        publish_date = operation.get("publish_date")
        if (
            operation.get("owner_id") != owner_id
            or type(post_id) is not int
            or post_id <= 0
            or type(publish_date) is not int
            or publish_date <= 0
        ):
            raise ValueError(f"operations[{index}] has invalid identity or publish_date")
        before_text = _normalize_newlines(str(operation.get("before_text") or ""))
        after_text = _normalize_newlines(str(operation.get("after_text") or ""))
        if not before_text or not after_text or before_text == after_text:
            raise ValueError(f"operations[{index}] must contain distinct non-empty texts")
        if operation.get("before_text_sha256") != _text_sha256(before_text):
            raise ValueError(f"operations[{index}] before_text hash mismatch")
        if operation.get("after_text_sha256") != _text_sha256(after_text):
            raise ValueError(f"operations[{index}] after_text hash mismatch")
        attachments = operation.get("attachments")
        if (
            not isinstance(attachments, list)
            or any(not isinstance(item, str) for item in attachments)
            or attachments != sorted(attachments)
            or len(attachments) != len(set(attachments))
        ):
            raise ValueError(f"operations[{index}] attachments must be sorted unique strings")
        if attachments and not allow_attachments:
            raise ValueError(f"operations[{index}] has attachments while allow_attachments is false")
        source = postponed_fingerprints.get(post_id)
        if source is None:
            raise ValueError(f"operations[{index}] target is absent from source_snapshot")
        if (
            source.owner_id != owner_id
            or source.publish_date != publish_date
            or source.text_sha256 != operation.get("before_text_sha256")
            or list(source.attachments) != attachments
        ):
            raise ValueError(f"operations[{index}] before-state differs from source_snapshot")
        expected_after, expected_removed = _apply_rules(before_text, rules)
        if operation.get("after_text") != expected_after or operation.get("removed_lines") != expected_removed:
            raise ValueError(f"operations[{index}] does not match the declared removal rules")
        seed = {
            "project_key": project_key,
            "owner_id": owner_id,
            "post_id": post_id,
            "publish_date": publish_date,
            "before_text_sha256": operation["before_text_sha256"],
            "after_text_sha256": operation["after_text_sha256"],
            "attachments": attachments,
        }
        expected_id = "vk-postponed-text-edit-" + canonical_sha256(seed).removeprefix("sha256:")[:32]
        operation_id = operation.get("operation_id")
        if operation_id != expected_id or not isinstance(operation_id, str) or operation_id in operation_ids:
            raise ValueError(f"operations[{index}] operation_id is invalid or duplicated")
        operation_ids.add(operation_id)
        operations.append(operation)
    if [operation["post_id"] for operation in operations] != target_ids:
        raise ValueError("operation order must exactly match target_post_ids")
    if plan.get("plan_sha256") != calculate_vk_postponed_text_plan_sha256(plan):
        raise ValueError("plan self-digest does not match its contents")
    return dict(plan)


def load_vk_postponed_text_edit_request(path: Path) -> dict[str, Any]:
    return validate_vk_postponed_text_edit_request(_read_json_object(path))


def load_vk_postponed_text_edit_plan(path: Path) -> dict[str, Any]:
    return validate_vk_postponed_text_edit_plan(_read_json_object(path))


def write_vk_postponed_text_document(path: Path, payload: object) -> None:
    _write_json_atomic(path, payload)


def _classify(
    operation: Mapping[str, Any], post: Mapping[str, Any] | None
) -> tuple[VkPostponedTextState, str | None]:
    if post is None:
        return VkPostponedTextState.CONFLICT, "post_absent_from_postponed_surface"
    if post.get("owner_id") != operation["owner_id"] or post.get("id") != operation["post_id"]:
        return VkPostponedTextState.CONFLICT, "post_identity_changed"
    if post.get("date") != operation["publish_date"]:
        return VkPostponedTextState.CONFLICT, "publish_date_changed"
    try:
        attachments = list(_canonical_attachments(post))
    except VkPostponedTextEditError:
        return VkPostponedTextState.CONFLICT, "attachments_not_canonical"
    if attachments != operation["attachments"]:
        return VkPostponedTextState.CONFLICT, "attachments_changed"
    text = _normalize_newlines(str(post.get("text") or ""))
    digest = _text_sha256(text)
    if text == operation["after_text"] and digest == operation["after_text_sha256"]:
        return VkPostponedTextState.AFTER, None
    if text == operation["before_text"] and digest == operation["before_text_sha256"]:
        return VkPostponedTextState.BEFORE, None
    return VkPostponedTextState.CONFLICT, "text_matches_neither_before_nor_after"


def _classify_operations(
    operations: list[dict[str, Any]], by_id: Mapping[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for operation in operations:
        state, reason = _classify(operation, by_id.get(operation["post_id"]))
        states.append(
            {
                "operation_id": operation["operation_id"],
                "post_id": operation["post_id"],
                "state": state.value,
                "reason": reason,
            }
        )
    return states


def reconcile_vk_postponed_text_edit_plan(
    writer: VkWallWriter,
    plan: Mapping[str, Any],
    *,
    max_posts_per_surface: int = 10000,
) -> dict[str, Any]:
    validated = validate_vk_postponed_text_edit_plan(plan)
    snapshot, _published, postponed = _read_complete_wall(
        writer,
        community_id=validated["community_id"],
        max_posts_per_surface=max_posts_per_surface,
    )
    if len(postponed) != validated["expected_postponed_count"]:
        raise VkPostponedTextEditError("postponed count differs from the immutable plan baseline")
    states = _classify_operations(
        cast(list[dict[str, Any]], validated["operations"]),
        _postponed_by_id(postponed, owner_id=validated["owner_id"]),
    )
    counts = {state.value: sum(row["state"] == state.value for row in states) for state in VkPostponedTextState}
    return {
        "schema_name": "video-manager.vk-postponed-text-edit-reconciliation",
        "schema_version": 1,
        "status": "ready" if counts[VkPostponedTextState.CONFLICT.value] == 0 else "blocked",
        "project_key": validated["project_key"],
        "community_id": validated["community_id"],
        "owner_id": validated["owner_id"],
        "plan_sha256": validated["plan_sha256"],
        "postponed_count": len(postponed),
        "operation_count": validated["operation_count"],
        "before": counts[VkPostponedTextState.BEFORE.value],
        "after": counts[VkPostponedTextState.AFTER.value],
        "conflict": counts[VkPostponedTextState.CONFLICT.value],
        "states": states,
        "snapshot": snapshot.as_dict(),
        "observed_at": datetime.now(UTC).isoformat(),
    }


def _non_target_fingerprints(
    snapshot: VkWallSnapshot, *, owner_id: int, target_ids: set[int]
) -> dict[tuple[str, str], dict[str, object]]:
    return {
        (post.surface.value, post.remote_id): post.as_dict()
        for post in snapshot.posts
        if not (
            post.surface is VkWallSurface.POSTPONED
            and post.owner_id == owner_id
            and post.post_id in target_ids
        )
    }


def _failure_is_transient(exc: Exception | None) -> bool:
    return (
        isinstance(exc, VkWriteError)
        and (exc.kind in _TRANSIENT_FAILURE_KINDS or exc.code in _TRANSIENT_PROVIDER_CODES)
    )


def _base_result(plan: Mapping[str, Any], status: str, *, results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_name": VK_POSTPONED_TEXT_EDIT_RESULT_SCHEMA,
        "schema_version": VK_POSTPONED_TEXT_EDIT_RESULT_VERSION,
        "status": status,
        "project_key": plan["project_key"],
        "community_id": plan["community_id"],
        "owner_id": plan["owner_id"],
        "plan_sha256": plan["plan_sha256"],
        "operation_count": plan["operation_count"],
        "results": results,
        "finished_at": datetime.now(UTC).isoformat(),
    }


def _save_result(output_dir: Path, result: dict[str, Any]) -> dict[str, Any]:
    _write_json_atomic(output_dir / "result.json", result)
    return result


def _persist_intent(
    output_dir: Path,
    *,
    ordinal: int,
    operation: Mapping[str, Any],
    attempt: int,
) -> tuple[Path, dict[str, Any]]:
    path = output_dir / "journal" / f"{ordinal:04d}-{operation['post_id']}-attempt-{attempt}.json"
    journal: dict[str, Any] = {
        "schema_name": "video-manager.vk-postponed-text-edit-operation-result",
        "schema_version": 1,
        "operation_id": operation["operation_id"],
        "owner_id": operation["owner_id"],
        "post_id": operation["post_id"],
        "publish_date": operation["publish_date"],
        "before_text_sha256": operation["before_text_sha256"],
        "after_text_sha256": operation["after_text_sha256"],
        "attachments": operation["attachments"],
        "attempt": attempt,
        "state": "intent_persisted",
        "provider_effect": "not_dispatched",
        "started_at": datetime.now(UTC).isoformat(),
        "finished_at": None,
        "error": None,
    }
    _write_json_atomic(path, journal)
    return path, journal


def execute_vk_postponed_text_edit_plan(
    writer: VkWallWriter,
    plan: Mapping[str, Any],
    *,
    output_dir: Path,
    confirm_plan_sha256: str,
    enable_provider_writes: bool,
    minimum_future_seconds: int = 600,
    inter_operation_delay_seconds: float = 25.0,
    postflight_delay_seconds: float = 3.0,
    transient_retry_delay_seconds: float = 90.0,
    max_transient_retries: int = 1,
    max_posts_per_surface: int = 10000,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, Any]:
    validated = validate_vk_postponed_text_edit_plan(plan)
    if not enable_provider_writes:
        raise VkPostponedTextEditError("provider writes require explicit enable_provider_writes=True")
    if confirm_plan_sha256 != validated["plan_sha256"]:
        raise VkPostponedTextEditError("explicit plan SHA-256 confirmation mismatch")
    if minimum_future_seconds < 0 or max_transient_retries < 0:
        raise ValueError("minimum_future_seconds and max_transient_retries cannot be negative")
    delays = (
        inter_operation_delay_seconds,
        postflight_delay_seconds,
        transient_retry_delay_seconds,
    )
    if any(delay < 0 for delay in delays):
        raise ValueError("operation delays cannot be negative")

    output_dir.mkdir(parents=True, exist_ok=True)
    initial_snapshot, _published, initial_postponed = _read_complete_wall(
        writer,
        community_id=validated["community_id"],
        max_posts_per_surface=max_posts_per_surface,
    )
    if len(initial_postponed) != validated["expected_postponed_count"]:
        raise VkPostponedTextEditError("live postponed count differs from immutable plan")
    operations = cast(list[dict[str, Any]], validated["operations"])
    initial_states = _classify_operations(
        operations,
        _postponed_by_id(initial_postponed, owner_id=validated["owner_id"]),
    )
    if any(row["state"] == VkPostponedTextState.CONFLICT.value for row in initial_states):
        result = _base_result(validated, "blocked_conflict", results=[])
        result["initial_states"] = initial_states
        return _save_result(output_dir, result)

    current_epoch = int(now().astimezone(UTC).timestamp())
    pending_ids = {
        row["post_id"] for row in initial_states if row["state"] == VkPostponedTextState.BEFORE.value
    }
    too_close = [
        operation["post_id"]
        for operation in operations
        if operation["post_id"] in pending_ids
        and operation["publish_date"] <= current_epoch + minimum_future_seconds
    ]
    if too_close:
        raise VkPostponedTextEditError(
            "pending post(s) are too close to publication: " + ", ".join(map(str, too_close))
        )

    _write_json_atomic(output_dir / "live-before.json", initial_snapshot.as_dict())
    results: list[dict[str, Any]] = [
        {
            "operation_id": row["operation_id"],
            "post_id": row["post_id"],
            "state": "already_after",
            "provider_effect": "verified",
            "attempts": 0,
        }
        for row in initial_states
        if row["state"] == VkPostponedTextState.AFTER.value
    ]
    verified_ids = {result["post_id"] for result in results}

    with local_vk_write_lock(
        output_dir / "vk-postponed-text-edit.lock",
        account=writer.account_alias,
        community_id=validated["community_id"],
        operation="vk-postponed-text-edit",
    ):
        for ordinal, operation in enumerate(operations, start=1):
            post_id = operation["post_id"]
            if post_id in verified_ids:
                continue
            if inter_operation_delay_seconds:
                sleep(inter_operation_delay_seconds)
            _posts, before_by_id = _read_postponed(
                writer,
                community_id=validated["community_id"],
                owner_id=validated["owner_id"],
                expected_count=validated["expected_postponed_count"],
                max_posts_per_surface=max_posts_per_surface,
            )
            state, reason = _classify(operation, before_by_id.get(post_id))
            if state is VkPostponedTextState.AFTER:
                results.append(
                    {
                        "operation_id": operation["operation_id"],
                        "post_id": post_id,
                        "state": "verified_before_dispatch",
                        "provider_effect": "verified",
                        "attempts": 0,
                    }
                )
                verified_ids.add(post_id)
                continue
            if state is VkPostponedTextState.CONFLICT:
                result = _base_result(validated, "stopped_conflict", results=results)
                result.update({"stopped_post_id": post_id, "stop_reason": reason, "initial_states": initial_states})
                return _save_result(output_dir, result)

            attempt = 0
            while True:
                attempt += 1
                journal_path, journal = _persist_intent(
                    output_dir,
                    ordinal=ordinal,
                    operation=operation,
                    attempt=attempt,
                )
                dispatch_error: Exception | None = None
                try:
                    response = writer._call(
                        "wall.edit",
                        params={
                            "owner_id": validated["owner_id"],
                            "post_id": post_id,
                            "message": operation["after_text"],
                            "publish_date": operation["publish_date"],
                            "attachments": ",".join(operation["attachments"]),
                        },
                        retry_transient=False,
                    )
                    journal["dispatch_response_type"] = type(response).__name__
                    journal["provider_effect"] = "may_exist"
                except Exception as exc:
                    dispatch_error = exc
                    journal["provider_effect"] = "may_exist"
                    journal["error"] = f"{type(exc).__name__}: {exc}"
                    if isinstance(exc, VkWriteError):
                        journal["error_code"] = exc.code
                        journal["failure_kind"] = exc.kind.value if exc.kind is not None else None
                    _write_json_atomic(journal_path, journal)

                if postflight_delay_seconds:
                    sleep(postflight_delay_seconds)
                try:
                    _after_posts, after_by_id = _read_postponed(
                        writer,
                        community_id=validated["community_id"],
                        owner_id=validated["owner_id"],
                        expected_count=validated["expected_postponed_count"],
                        max_posts_per_surface=max_posts_per_surface,
                    )
                    after_state, after_reason = _classify(operation, after_by_id.get(post_id))
                except Exception as exc:
                    journal.update(
                        {
                            "state": "unknown_requires_reconciliation",
                            "provider_effect": "may_exist",
                            "reconciliation_error": f"{type(exc).__name__}: {exc}",
                            "finished_at": datetime.now(UTC).isoformat(),
                        }
                    )
                    _write_json_atomic(journal_path, journal)
                    result = _base_result(
                        validated, "unknown_requires_reconciliation", results=results + [journal]
                    )
                    result.update({"stopped_post_id": post_id, "initial_states": initial_states})
                    return _save_result(output_dir, result)

                if after_state is VkPostponedTextState.AFTER:
                    journal.update(
                        {
                            "state": "verified",
                            "provider_effect": "verified",
                            "error": None,
                            "finished_at": datetime.now(UTC).isoformat(),
                        }
                    )
                    _write_json_atomic(journal_path, journal)
                    results.append(
                        {
                            "operation_id": operation["operation_id"],
                            "post_id": post_id,
                            "state": "verified",
                            "provider_effect": "verified",
                            "attempts": attempt,
                        }
                    )
                    verified_ids.add(post_id)
                    break
                if after_state is VkPostponedTextState.CONFLICT:
                    journal.update(
                        {
                            "state": "unknown_requires_reconciliation",
                            "provider_effect": "may_exist",
                            "stop_reason": after_reason,
                            "finished_at": datetime.now(UTC).isoformat(),
                        }
                    )
                    _write_json_atomic(journal_path, journal)
                    result = _base_result(
                        validated, "unknown_requires_reconciliation", results=results + [journal]
                    )
                    result.update({"stopped_post_id": post_id, "initial_states": initial_states})
                    return _save_result(output_dir, result)

                journal["provider_effect"] = "confirmed_absent"
                journal["finished_at"] = datetime.now(UTC).isoformat()
                if isinstance(dispatch_error, VkWriteError) and dispatch_error.code == 14:
                    journal["state"] = "captcha_required_confirmed_absent"
                    _write_json_atomic(journal_path, journal)
                    result = _base_result(validated, "stopped_captcha_required", results=results + [journal])
                    result.update({"stopped_post_id": post_id, "initial_states": initial_states})
                    return _save_result(output_dir, result)
                if _failure_is_transient(dispatch_error) and attempt <= max_transient_retries:
                    journal["state"] = "transient_confirmed_absent_waiting_retry"
                    _write_json_atomic(journal_path, journal)
                    if transient_retry_delay_seconds:
                        sleep(transient_retry_delay_seconds)
                    _retry_posts, retry_by_id = _read_postponed(
                        writer,
                        community_id=validated["community_id"],
                        owner_id=validated["owner_id"],
                        expected_count=validated["expected_postponed_count"],
                        max_posts_per_surface=max_posts_per_surface,
                    )
                    retry_state, retry_reason = _classify(operation, retry_by_id.get(post_id))
                    if retry_state is VkPostponedTextState.AFTER:
                        results.append(
                            {
                                "operation_id": operation["operation_id"],
                                "post_id": post_id,
                                "state": "verified_after_delayed_reconciliation",
                                "provider_effect": "verified",
                                "attempts": attempt,
                            }
                        )
                        verified_ids.add(post_id)
                        break
                    if retry_state is VkPostponedTextState.CONFLICT:
                        result = _base_result(
                            validated, "unknown_requires_reconciliation", results=results + [journal]
                        )
                        result.update(
                            {
                                "stopped_post_id": post_id,
                                "stop_reason": retry_reason,
                                "initial_states": initial_states,
                            }
                        )
                        return _save_result(output_dir, result)
                    continue
                journal["state"] = "confirmed_absent"
                _write_json_atomic(journal_path, journal)
                result = _base_result(validated, "stopped_confirmed_absent", results=results + [journal])
                result.update({"stopped_post_id": post_id, "initial_states": initial_states})
                return _save_result(output_dir, result)

    final_snapshot, _final_published, final_postponed = _read_complete_wall(
        writer,
        community_id=validated["community_id"],
        max_posts_per_surface=max_posts_per_surface,
    )
    final_states = _classify_operations(
        operations,
        _postponed_by_id(final_postponed, owner_id=validated["owner_id"]),
    )
    if any(row["state"] != VkPostponedTextState.AFTER.value for row in final_states):
        result = _base_result(validated, "final_postcondition_failed", results=results)
        result.update({"initial_states": initial_states, "final_states": final_states})
        return _save_result(output_dir, result)
    target_ids = set(cast(list[int], validated["target_post_ids"]))
    if _non_target_fingerprints(
        initial_snapshot, owner_id=validated["owner_id"], target_ids=target_ids
    ) != _non_target_fingerprints(
        final_snapshot, owner_id=validated["owner_id"], target_ids=target_ids
    ):
        result = _base_result(validated, "non_target_postcondition_failed", results=results)
        result.update({"initial_states": initial_states, "final_states": final_states})
        return _save_result(output_dir, result)

    result = _base_result(validated, "succeeded", results=results)
    result.update(
        {
            "postponed_count_before": len(initial_postponed),
            "postponed_count_after": len(final_postponed),
            "already_after_before_apply": sum(
                row["state"] == VkPostponedTextState.AFTER.value for row in initial_states
            ),
            "newly_verified": sum(
                row.get("provider_effect") == "verified" and int(row.get("attempts", 0)) > 0
                for row in results
            ),
            "total_verified": len(final_states),
            "non_target_wall_objects_unchanged": len(
                _non_target_fingerprints(
                    final_snapshot, owner_id=validated["owner_id"], target_ids=target_ids
                )
            ),
            "non_target_postponed_unchanged": len(final_postponed) - validated["operation_count"],
            "initial_states": initial_states,
            "final_states": final_states,
            "live_before_snapshot_sha256": initial_snapshot.snapshot_sha256,
            "live_after_snapshot_sha256": final_snapshot.snapshot_sha256,
        }
    )
    _write_json_atomic(output_dir / "live-after.json", final_snapshot.as_dict())
    return _save_result(output_dir, result)


__all__ = [
    "VK_POSTPONED_TEXT_EDIT_PLAN_SCHEMA",
    "VK_POSTPONED_TEXT_EDIT_PLAN_VERSION",
    "VK_POSTPONED_TEXT_EDIT_REQUEST_SCHEMA",
    "VK_POSTPONED_TEXT_EDIT_REQUEST_VERSION",
    "VK_POSTPONED_TEXT_EDIT_RESULT_SCHEMA",
    "VK_POSTPONED_TEXT_EDIT_RESULT_VERSION",
    "VkPostponedTextEditError",
    "VkPostponedTextState",
    "build_vk_postponed_text_edit_plan",
    "calculate_vk_postponed_text_plan_sha256",
    "execute_vk_postponed_text_edit_plan",
    "load_vk_postponed_text_edit_plan",
    "load_vk_postponed_text_edit_request",
    "reconcile_vk_postponed_text_edit_plan",
    "validate_vk_postponed_text_edit_plan",
    "validate_vk_postponed_text_edit_request",
    "write_vk_postponed_text_document",
]
