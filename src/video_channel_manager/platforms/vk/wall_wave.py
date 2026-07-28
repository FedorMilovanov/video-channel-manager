from __future__ import annotations

import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk.catalog import canonical_sha256
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text
from video_channel_manager.platforms.vk.wall_content_audit import extract_video_ids_from_post

VK_WALL_WAVE_POLICY_SCHEMA = "video-manager.vk-wall-wave-policy"
VK_WALL_WAVE_POLICY_VERSION = 1
VK_WALL_WAVE_SOURCE_SCHEMA = "video-manager.vk-wall-content-audit"
VK_WALL_WAVE_SOURCE_HANDOFF_SCHEMA = "video-manager.vk-wall-content-audit-handoff"


def sha256_bytes(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def message_sha256(message: str) -> str:
    return canonical_sha256(canonical_vk_text(message))


def calculate_wall_wave_policy_sha256(policy: dict[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in policy.items() if key != "policy_sha256"})


def _required_dict(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _required_list(value: object, *, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    return value


def validate_wall_wave_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema_name") != VK_WALL_WAVE_POLICY_SCHEMA:
        raise ValueError("Unexpected VK wall wave policy schema")
    if policy.get("schema_version") != VK_WALL_WAVE_POLICY_VERSION:
        raise ValueError("Unsupported VK wall wave policy version")
    community_id = policy.get("community_id")
    if not isinstance(community_id, int) or community_id <= 0:
        raise ValueError("community_id must be a positive integer")
    if str(policy.get("decision_set_id") or "").strip() != "vk-wall-wave-202608":
        raise ValueError("Unexpected VK wall wave decision set")
    if policy.get("policy_sha256") != calculate_wall_wave_policy_sha256(policy):
        raise ValueError("VK wall wave policy self-digest does not match its contents")

    operations = _required_list(policy.get("operations"), name="operations")
    if len(operations) != 12:
        raise ValueError(f"VK wall wave must contain exactly 12 operations, found {len(operations)}")

    operation_ids: list[str] = []
    video_ids: list[str] = []
    publish_dates: list[int] = []
    for index, raw_operation in enumerate(operations):
        operation = _required_dict(raw_operation, name=f"operations[{index}]")
        operation_id = str(operation.get("operation_id") or "").strip()
        video_id = str(operation.get("video_id") or "").strip()
        attachment = str(operation.get("attachment") or "").strip()
        message = canonical_vk_text(str(operation.get("message") or ""))
        publish_date = operation.get("publish_date")
        publish_at = str(operation.get("publish_at") or "").strip()
        if not operation_id or not video_id or not attachment or not message or not publish_at:
            raise ValueError(f"Incomplete VK wall wave operation at index {index}")
        if not video_id.startswith(f"-{community_id}_"):
            raise ValueError(f"Operation targets another VK community: {video_id}")
        if attachment != f"video{video_id}":
            raise ValueError(f"Attachment does not match video identity: {operation_id}")
        if operation.get("expected_source_state") != "unposted" or operation.get("mode") != "postponed":
            raise ValueError(f"Operation is not an approved postponed unposted transition: {operation_id}")
        if not isinstance(publish_date, int) or publish_date <= 0:
            raise ValueError(f"Invalid publish_date: {operation_id}")
        parsed_publish_at = datetime.fromisoformat(publish_at)
        if parsed_publish_at.tzinfo is None or int(parsed_publish_at.timestamp()) != publish_date:
            raise ValueError(f"publish_at and publish_date differ: {operation_id}")
        if operation.get("message_sha256") != message_sha256(message):
            raise ValueError(f"Message SHA differs: {operation_id}")
        required_url = operation.get("required_url")
        if required_url is not None and str(required_url).strip() not in message:
            raise ValueError(f"required_url is absent from message: {operation_id}")
        operation_ids.append(operation_id)
        video_ids.append(video_id)
        publish_dates.append(publish_date)

    for label, values in (
        ("operation IDs", operation_ids),
        ("video IDs", video_ids),
        ("publish dates", publish_dates),
    ):
        duplicates = sorted(str(item) for item, count in Counter(values).items() if count > 1)
        if duplicates:
            raise ValueError(f"Duplicate {label}: {duplicates}")
    if publish_dates != sorted(publish_dates):
        raise ValueError("VK wall wave operations are not ordered by publish_date")

    summary = _required_dict(policy.get("summary"), name="summary")
    if summary != {
        "first_publish_at": str(operations[0]["publish_at"]),
        "immediate_posts": 0,
        "last_publish_at": str(operations[-1]["publish_at"]),
        "postponed_posts": 12,
        "unique_videos": 12,
    }:
        raise ValueError("VK wall wave summary does not match operations")


def _json_object(raw: bytes, *, name: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot decode JSON {name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {name}")
    return value


def verify_source_audit_bundle(source_bundle: Path, policy: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_wall_wave_policy(policy)
    raw_bundle = source_bundle.read_bytes()
    actual_bundle_sha = sha256_bytes(raw_bundle)
    if actual_bundle_sha != str(policy.get("source_audit_bundle_sha256") or ""):
        raise ValueError("Source wall audit outer SHA differs from policy")
    if source_bundle.name != str(policy.get("source_audit_bundle_name") or ""):
        raise ValueError("Source wall audit filename differs from policy")

    with zipfile.ZipFile(source_bundle) as archive:
        names = [entry.filename for entry in archive.infolist()]
        if len(names) != len(set(names)):
            raise ValueError("Source wall audit ZIP contains duplicate entries")
        required_names = {
            "00-videos.json",
            "01-published-wall-posts.json",
            "02-postponed-wall-posts.json",
            "03-wall-content-audit.json",
            "04-wall-content-audit.md",
            "README.txt",
            "manifest.json",
        }
        if set(names) != required_names:
            raise ValueError(f"Unexpected source wall audit members: {sorted(set(names) ^ required_names)}")
        manifest = _json_object(archive.read("manifest.json"), name="manifest.json")
        audit = _json_object(archive.read("03-wall-content-audit.json"), name="03-wall-content-audit.json")
        for raw_record in _required_list(manifest.get("files"), name="manifest.files"):
            record = _required_dict(raw_record, name="manifest file record")
            name = str(record.get("name") or "")
            content = archive.read(name)
            if len(content) != int(record.get("size_bytes", -1)):
                raise ValueError(f"Source wall audit file size differs: {name}")
            if sha256_bytes(content) != str(record.get("sha256") or ""):
                raise ValueError(f"Source wall audit file SHA differs: {name}")

    community_id = int(policy["community_id"])
    if manifest.get("schema_name") != VK_WALL_WAVE_SOURCE_HANDOFF_SCHEMA or manifest.get("schema_version") != 1:
        raise ValueError("Unexpected source wall audit handoff schema")
    if manifest.get("mode") != "read-only" or int(manifest.get("community_id", 0)) != community_id:
        raise ValueError("Source wall audit handoff is not the approved read-only community audit")
    if audit.get("schema_name") != VK_WALL_WAVE_SOURCE_SCHEMA or audit.get("schema_version") != 1:
        raise ValueError("Unexpected source wall audit schema")
    if not bool(audit.get("read_only")) or int(audit.get("community_id", 0)) != community_id:
        raise ValueError("Source wall audit is not read-only for the approved community")
    expected_audit_sha = canonical_sha256({key: value for key, value in audit.items() if key != "audit_sha256"})
    if audit.get("audit_sha256") != expected_audit_sha:
        raise ValueError("Source wall audit self-digest differs")
    if audit.get("audit_sha256") != policy.get("source_audit_sha256"):
        raise ValueError("Source wall audit SHA differs from policy")
    if manifest.get("audit_sha256") != audit.get("audit_sha256"):
        raise ValueError("Source wall audit manifest and audit SHA differ")
    if audit.get("summary") != policy.get("source_audit_summary") or manifest.get("summary") != audit.get("summary"):
        raise ValueError("Source wall audit summary differs from policy")

    source_videos = {
        str(item.get("video_id") or ""): item
        for item in _required_list(audit.get("videos"), name="audit.videos")
        if isinstance(item, dict)
    }
    if len(source_videos) != int(audit["summary"]["videos"]):
        raise ValueError("Source wall audit video identities are incomplete or duplicated")
    for operation in policy["operations"]:
        video_id = str(operation["video_id"])
        source_video = source_videos.get(video_id)
        if source_video is None:
            raise ValueError(f"Scheduled video is absent from source audit: {video_id}")
        if source_video.get("state") != "unposted":
            raise ValueError(f"Scheduled video is not source-audited as unposted: {video_id}")
        if canonical_vk_text(str(source_video.get("title") or "")) != canonical_vk_text(str(operation["video_title"])):
            raise ValueError(f"Scheduled video title differs from source audit: {video_id}")

    verification = {
        "schema_name": "video-manager.vk-wall-wave-source-verification",
        "schema_version": 1,
        "status": "verified",
        "community_id": community_id,
        "bundle_name": source_bundle.name,
        "bundle_sha256": actual_bundle_sha,
        "audit_sha256": audit["audit_sha256"],
        "source_videos": len(source_videos),
        "approved_unposted_targets": len(policy["operations"]),
        "source_summary": audit["summary"],
    }
    return audit, verification


def _post_reference(post: dict[str, Any], *, queue: str) -> dict[str, Any]:
    owner_id = post.get("owner_id")
    post_id = post.get("id")
    result: dict[str, Any] = {
        "queue": queue,
        "owner_id": owner_id if isinstance(owner_id, int) else None,
        "post_id": post_id if isinstance(post_id, int) else None,
        "date": post.get("date") if isinstance(post.get("date"), int) else None,
        "message": canonical_vk_text(str(post.get("text") or "")),
    }
    if isinstance(owner_id, int) and isinstance(post_id, int):
        result["url"] = f"https://vk.com/wall{owner_id}_{post_id}"
    return result


def _post_index(posts: list[dict[str, Any]], *, queue: str) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for post in posts:
        reference = _post_reference(post, queue=queue)
        for video_id in extract_video_ids_from_post(post):
            index[video_id].append(reference)
    return dict(index)


def build_wall_wave_preflight(
    policy: dict[str, Any],
    *,
    published_posts: list[dict[str, Any]],
    postponed_posts: list[dict[str, Any]],
    now: datetime | None = None,
    minimum_future_seconds: int = 300,
) -> dict[str, Any]:
    validate_wall_wave_policy(policy)
    if minimum_future_seconds < 0:
        raise ValueError("minimum_future_seconds cannot be negative")
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    current_timestamp = int(current.timestamp())
    published_index = _post_index(published_posts, queue="published")
    postponed_index = _post_index(postponed_posts, queue="postponed")

    states: list[dict[str, Any]] = []
    global_conflicts: list[str] = []
    for operation in policy["operations"]:
        video_id = str(operation["video_id"])
        expected_message = canonical_vk_text(str(operation["message"]))
        references = [*published_index.get(video_id, []), *postponed_index.get(video_id, [])]
        exact = [
            item
            for item in references
            if item["message"] == expected_message
            and (
                item["queue"] == "published"
                or int(item.get("date") or 0) == int(operation["publish_date"])
            )
        ]
        different = [item for item in references if item not in exact]
        if len(exact) == 1 and not different:
            state = "already_applied"
            detail = "exact approved post exists"
        elif not references:
            if int(operation["publish_date"]) <= current_timestamp + minimum_future_seconds:
                state = "conflict"
                detail = "approved publish date is no longer safely in the future"
            else:
                state = "ready"
                detail = "video is absent from published and postponed wall posts"
        else:
            state = "conflict"
            detail = "video has duplicate, differently worded, or differently scheduled wall references"
        if state == "conflict":
            global_conflicts.append(f"{operation['operation_id']}: {detail}")
        states.append(
            {
                "operation_id": operation["operation_id"],
                "video_id": video_id,
                "publish_date": operation["publish_date"],
                "state": state,
                "detail": detail,
                "references": references,
            }
        )

    counts = Counter(str(item["state"]) for item in states)
    return {
        "schema_name": "video-manager.vk-wall-wave-preflight",
        "schema_version": 1,
        "status": "blocked" if counts["conflict"] else "ready",
        "community_id": policy["community_id"],
        "decision_set_id": policy["decision_set_id"],
        "policy_sha256": policy["policy_sha256"],
        "checked_at": current.astimezone(UTC).isoformat(),
        "published_wall_posts": len(published_posts),
        "postponed_wall_posts": len(postponed_posts),
        "total_operations": len(states),
        "ready": counts["ready"],
        "already_applied": counts["already_applied"],
        "conflicts": counts["conflict"],
        "global_conflicts": global_conflicts,
        "states": states,
    }


def comparable_preflight(preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        "community_id": preflight.get("community_id"),
        "decision_set_id": preflight.get("decision_set_id"),
        "policy_sha256": preflight.get("policy_sha256"),
        "published_wall_posts": preflight.get("published_wall_posts"),
        "postponed_wall_posts": preflight.get("postponed_wall_posts"),
        "ready": preflight.get("ready"),
        "already_applied": preflight.get("already_applied"),
        "conflicts": preflight.get("conflicts"),
        "states": [
            {
                "operation_id": item.get("operation_id"),
                "video_id": item.get("video_id"),
                "publish_date": item.get("publish_date"),
                "state": item.get("state"),
                "references": item.get("references"),
            }
            for item in preflight.get("states", [])
            if isinstance(item, dict)
        ],
    }


def verify_wall_wave_postflight(policy: dict[str, Any], preflight: dict[str, Any]) -> dict[str, Any]:
    validate_wall_wave_policy(policy)
    if preflight.get("conflicts") != 0 or preflight.get("ready") != 0:
        raise ValueError("VK wall wave postflight still contains ready or conflicting operations")
    if preflight.get("already_applied") != len(policy["operations"]):
        raise ValueError("VK wall wave postflight does not cover every approved operation")
    states = _required_list(preflight.get("states"), name="postflight.states")
    if any(not isinstance(item, dict) or item.get("state") != "already_applied" for item in states):
        raise ValueError("VK wall wave postflight contains a non-final state")
    published = sum(
        1
        for item in states
        if any(ref.get("queue") == "published" for ref in item.get("references", []) if isinstance(ref, dict))
    )
    postponed = len(states) - published
    return {
        "schema_name": "video-manager.vk-wall-wave-verification",
        "schema_version": 1,
        "status": "verified_completed",
        "community_id": policy["community_id"],
        "decision_set_id": policy["decision_set_id"],
        "policy_sha256": policy["policy_sha256"],
        "verified_operations": len(states),
        "verified_published": published,
        "verified_postponed": postponed,
        "unique_videos": len({str(item["video_id"]) for item in policy["operations"]}),
    }


def wall_post_id(response: object) -> int:
    if isinstance(response, int) and response > 0:
        return response
    if isinstance(response, dict):
        raw = response.get("post_id")
        if isinstance(raw, int) and raw > 0:
            return raw
    raise ValueError(f"VK wall.post returned no positive post ID: {response!r}")


__all__ = [
    "VK_WALL_WAVE_POLICY_SCHEMA",
    "VK_WALL_WAVE_POLICY_VERSION",
    "build_wall_wave_preflight",
    "calculate_wall_wave_policy_sha256",
    "comparable_preflight",
    "message_sha256",
    "sha256_bytes",
    "validate_wall_wave_policy",
    "verify_source_audit_bundle",
    "verify_wall_wave_postflight",
    "wall_post_id",
]
