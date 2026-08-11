from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from video_channel_manager.editorial._project_profiles import PROJECT_KEYS, PROJECT_VK_COMMUNITY_IDS
from video_channel_manager.platforms.vk.catalog import canonical_sha256

VK_OWNER_CLIPS_WALL_RECONCILIATION_SCHEMA = "vk-owner-clips-wall-reconciliation-v1"
_EXPECTED_OWNER_PROBE_SCHEMA = "vk-owner-clips-experimental-probe-v2"


def _validate_identity(*, project_key: str, community_id: int, owner_id: int) -> str:
    normalized_project = project_key.strip()
    if normalized_project not in PROJECT_KEYS:
        raise ValueError(f"unknown project_key for VK Clips reconciliation: {project_key}")
    if isinstance(community_id, bool) or not isinstance(community_id, int) or community_id <= 0:
        raise ValueError("VK community_id must be a positive integer")
    if isinstance(owner_id, bool) or not isinstance(owner_id, int) or owner_id >= 0:
        raise ValueError("VK owner_id must be a negative integer")
    if community_id not in PROJECT_VK_COMMUNITY_IDS.get(normalized_project, frozenset()):
        raise ValueError(
            f"VK community differs from canonical project identity for {normalized_project}: {community_id}"
        )
    if owner_id != -community_id:
        raise ValueError(f"VK owner differs from canonical community identity for {normalized_project}: {owner_id}")
    return normalized_project


def _walk_posts(post: dict[str, Any]) -> list[dict[str, Any]]:
    result = [post]
    history = post.get("copy_history")
    if isinstance(history, list):
        for item in history:
            if isinstance(item, dict):
                result.extend(_walk_posts(item))
    return result


def _attachment_video_payload(attachment: dict[str, Any]) -> dict[str, Any] | None:
    attachment_type = str(attachment.get("type") or "")
    if attachment_type not in {"video", "clip"}:
        return None
    payload = attachment.get(attachment_type)
    if not isinstance(payload, dict) and attachment_type == "clip":
        payload = attachment.get("video")
    return payload if isinstance(payload, dict) else None


def _remote_id(payload: dict[str, Any]) -> str | None:
    owner_id = payload.get("owner_id")
    video_id = payload.get("id")
    if isinstance(owner_id, bool) or isinstance(video_id, bool):
        return None
    if not isinstance(owner_id, int) or not isinstance(video_id, int) or owner_id == 0 or video_id <= 0:
        return None
    return f"{owner_id}_{video_id}"


def extract_wall_native_clips(
    published_posts: list[dict[str, Any]],
    *,
    owner_id: int,
) -> list[dict[str, Any]]:
    """Extract exact native Clips from raw wall evidence.

    Wall attachments may arrive with outer ``type=video`` even when the nested
    provider object proves ``video.type=short_video``. Only the nested object
    type is accepted as native Clip evidence.
    """

    records: dict[str, dict[str, Any]] = {}
    references: dict[str, list[dict[str, int]]] = defaultdict(list)
    for root_post in published_posts:
        if not isinstance(root_post, dict):
            continue
        root_owner = root_post.get("owner_id")
        root_post_id = root_post.get("id")
        root_ref = {
            "owner_id": root_owner if isinstance(root_owner, int) else 0,
            "post_id": root_post_id if isinstance(root_post_id, int) else 0,
        }
        for post in _walk_posts(root_post):
            attachments = post.get("attachments")
            if not isinstance(attachments, list):
                continue
            for attachment in attachments:
                if not isinstance(attachment, dict):
                    continue
                payload = _attachment_video_payload(attachment)
                if payload is None or str(payload.get("type") or "") != "short_video":
                    continue
                remote_id = _remote_id(payload)
                if remote_id is None:
                    raise ValueError("wall native Clip attachment has invalid owner/video identity")
                payload_owner = int(remote_id.split("_", 1)[0])
                if payload_owner != owner_id:
                    raise ValueError(
                        f"wall native Clip belongs to foreign owner {payload_owner}; expected exact owner {owner_id}"
                    )
                width = payload.get("width") if isinstance(payload.get("width"), int) else None
                height = payload.get("height") if isinstance(payload.get("height"), int) else None
                candidate = {
                    "remote_id": remote_id,
                    "owner_id": payload_owner,
                    "video_id": int(remote_id.split("_", 1)[1]),
                    "type": "short_video",
                    "title": str(payload.get("title") or remote_id),
                    "description": str(payload.get("description") or ""),
                    "duration_seconds": payload.get("duration") if isinstance(payload.get("duration"), int) else None,
                    "width": width,
                    "height": height,
                    "vertical": bool(width is not None and height is not None and width < height),
                }
                existing = records.get(remote_id)
                if existing is not None:
                    comparable_keys = ("owner_id", "video_id", "type")
                    if any(existing[key] != candidate[key] for key in comparable_keys):
                        raise ValueError(f"conflicting wall evidence for native Clip {remote_id}")
                else:
                    records[remote_id] = candidate
                if root_ref not in references[remote_id]:
                    references[remote_id].append(root_ref)

    result: list[dict[str, Any]] = []
    for remote_id in sorted(records):
        record = dict(records[remote_id])
        record["wall_post_refs"] = references[remote_id]
        result.append(record)
    return result


def _validated_owner_probe(
    payload: dict[str, Any],
    *,
    project_key: str,
    community_id: int,
    owner_id: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    if payload.get("schema") != _EXPECTED_OWNER_PROBE_SCHEMA:
        raise ValueError("unsupported VK owner Clips probe schema")
    if payload.get("read_only") is not True or payload.get("provider_effect") != "safe_read_only":
        raise ValueError("owner Clips probe is not proven read-only")
    if str(payload.get("project_key") or "") != project_key:
        raise ValueError("owner Clips probe project differs from reconciliation target")
    community = payload.get("community")
    if not isinstance(community, dict):
        raise ValueError("owner Clips probe has no exact community evidence")
    if community.get("community_id") != community_id or community.get("owner_id") != owner_id:
        raise ValueError("owner Clips probe exact community/owner differs from reconciliation target")
    if community.get("managed_by_token") is not True:
        raise ValueError("owner Clips probe did not prove exact managed community")

    provider_probe = payload.get("provider_probe")
    coverage = payload.get("coverage")
    clips = payload.get("clips")
    if not isinstance(provider_probe, dict) or not isinstance(coverage, dict) or not isinstance(clips, list):
        raise ValueError("owner Clips probe is structurally incomplete")
    if coverage.get("surface_complete_claim") is not False:
        raise ValueError("experimental owner Clips probe must not claim complete surface")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in clips:
        if not isinstance(item, dict):
            raise ValueError("owner Clips probe contains a non-object clip record")
        remote_id = str(item.get("remote_id") or "")
        if not remote_id.startswith(f"{owner_id}_"):
            raise ValueError(f"owner Clips probe contains foreign or invalid remote ID: {remote_id}")
        if item.get("is_native_clip") is not True or item.get("type") != "short_video":
            raise ValueError(f"owner Clips probe clip lacks exact type=short_video proof: {remote_id}")
        if remote_id in seen:
            raise ValueError(f"owner Clips probe contains duplicate remote ID: {remote_id}")
        seen.add(remote_id)
        normalized.append(item)
    if coverage.get("clip_count") != len(normalized):
        raise ValueError("owner Clips probe clip_count differs from exact clip records")
    return normalized, provider_probe, coverage


def build_owner_clips_wall_reconciliation(
    *,
    project_key: str,
    community_id: int,
    owner_id: int,
    published_posts: list[dict[str, Any]],
    owner_probe: dict[str, Any],
) -> dict[str, Any]:
    normalized_project = _validate_identity(
        project_key=project_key,
        community_id=community_id,
        owner_id=owner_id,
    )
    wall_clips = extract_wall_native_clips(published_posts, owner_id=owner_id)
    probe_clips, provider_probe, probe_coverage = _validated_owner_probe(
        owner_probe,
        project_key=normalized_project,
        community_id=community_id,
        owner_id=owner_id,
    )

    wall_by_id = {str(item["remote_id"]): item for item in wall_clips}
    probe_by_id = {str(item["remote_id"]): item for item in probe_clips}
    wall_ids = set(wall_by_id)
    probe_ids = set(probe_by_id)
    both_ids = sorted(wall_ids & probe_ids)
    wall_only_ids = sorted(wall_ids - probe_ids)
    owner_only_ids = sorted(probe_ids - wall_ids)

    endpoint_ok = provider_probe.get("status") == "ok"
    pagination_complete = provider_probe.get("pagination_complete") is True
    owner_probe_covers_all_wall = endpoint_ok and not wall_only_ids
    status = "probe_error"
    if endpoint_ok and wall_only_ids:
        status = "wall_coverage_gap"
    elif owner_probe_covers_all_wall:
        status = "wall_coverage_reconciled_experimental"

    result: dict[str, Any] = {
        "schema": VK_OWNER_CLIPS_WALL_RECONCILIATION_SCHEMA,
        "project_key": normalized_project,
        "community_id": community_id,
        "owner_id": owner_id,
        "read_only": True,
        "provider_writes": 0,
        "status": status,
        "input_evidence": {
            "published_wall_posts_sha256": canonical_sha256(published_posts),
            "owner_probe_sha256": canonical_sha256(owner_probe),
            "owner_probe_schema": owner_probe.get("schema"),
            "owner_probe_status": provider_probe.get("status"),
            "owner_probe_pagination_complete": pagination_complete,
        },
        "wall_evidence": {
            "published_post_count": len(published_posts),
            "native_clip_count": len(wall_clips),
            "all_native_clips_exact_owner": True,
            "identity_rule": "nested attachment video.type=short_video",
            "clips": wall_clips,
        },
        "owner_probe_evidence": {
            "native_clip_count": len(probe_clips),
            "provider_reported_total": provider_probe.get("provider_reported_total"),
            "pagination_complete": pagination_complete,
            "surface_complete_claim": False,
        },
        "reconciliation": {
            "both_count": len(both_ids),
            "wall_only_count": len(wall_only_ids),
            "owner_only_count": len(owner_only_ids),
            "both_remote_ids": both_ids,
            "wall_only_remote_ids": wall_only_ids,
            "owner_only_remote_ids": owner_only_ids,
            "owner_probe_covers_all_wall_native_clips": owner_probe_covers_all_wall,
            "surface_complete_claim": False,
            "surface_complete_reason": (
                "shortVideo.getOwnerVideos remains an experimental web-client endpoint; wall reconciliation proves coverage of independent wall evidence, not complete provider-surface authority"
            ),
        },
        "required_remote_ids": {
            "declared_by_probe": probe_coverage.get("required_remote_ids", []),
            "found_as_clips_by_probe": probe_coverage.get("required_remote_ids_found_as_clips", []),
            "missing_from_probe": probe_coverage.get("required_remote_ids_missing_from_probe", []),
        },
    }
    result["reconciliation_sha256"] = canonical_sha256(
        {key: value for key, value in result.items() if key != "reconciliation_sha256"}
    )
    return result


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Reconcile VK owner-Clips probe with raw published wall evidence.")
    root.add_argument("--project", required=True)
    root.add_argument("--community", type=int, required=True)
    root.add_argument("--owner-id", type=int, required=True)
    root.add_argument("--published-wall-posts", type=Path, required=True)
    root.add_argument("--owner-probe", type=Path, required=True)
    root.add_argument("--output", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    published_posts = _load_json(args.published_wall_posts)
    owner_probe = _load_json(args.owner_probe)
    if not isinstance(published_posts, list):
        raise ValueError("published wall evidence must be a JSON list")
    if not isinstance(owner_probe, dict):
        raise ValueError("owner Clips probe must be a JSON object")
    result = build_owner_clips_wall_reconciliation(
        project_key=args.project,
        community_id=args.community,
        owner_id=args.owner_id,
        published_posts=published_posts,
        owner_probe=owner_probe,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "wall_clips": result["wall_evidence"]["native_clip_count"],
                "owner_probe_clips": result["owner_probe_evidence"]["native_clip_count"],
                "both": result["reconciliation"]["both_count"],
                "wall_only": result["reconciliation"]["wall_only_count"],
                "owner_only": result["reconciliation"]["owner_only_count"],
                "surface_complete_claim": False,
                "provider_writes": 0,
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "VK_OWNER_CLIPS_WALL_RECONCILIATION_SCHEMA",
    "build_owner_clips_wall_reconciliation",
    "extract_wall_native_clips",
]
