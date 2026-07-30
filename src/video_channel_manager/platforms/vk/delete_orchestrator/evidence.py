from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from video_channel_manager.platforms.vk.catalog import canonical_sha256
from video_channel_manager.platforms.vk.delete_orchestrator.models import DeletePolicy, VideoGuard


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def text_sha256(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _video_guard(raw: dict[str, object]) -> VideoGuard:
    ref = raw.get("ref")
    metadata = raw.get("metadata")
    if not isinstance(ref, dict) or not isinstance(metadata, dict):
        raise ValueError("Wall-audit video record has no ref/metadata")
    owner_id = metadata.get("owner_id")
    video_id = metadata.get("id")
    remote_id = ref.get("remote_id")
    if not isinstance(owner_id, int) or not isinstance(video_id, int) or not isinstance(remote_id, str):
        raise ValueError("Wall-audit video record has invalid identity")
    description = str(raw.get("description") or "")
    raw_duration = raw.get("duration_seconds")
    duration_seconds = raw_duration if isinstance(raw_duration, int) else 0
    return VideoGuard(
        remote_id=remote_id,
        title=str(raw.get("title") or ""),
        description_sha256=text_sha256(description),
        duration_seconds=duration_seconds,
        owner_id=owner_id,
        video_id=video_id,
        vk_type=str(metadata.get("type") or "video"),
        date=int(metadata.get("date") or 0),
    )


@dataclass(frozen=True)
class DeleteEvidence:
    all_video_ids: frozenset[str]
    protected_video_ids: frozenset[str]
    published_video_ids: frozenset[str]
    postponed_video_ids: frozenset[str]
    video_guards: Mapping[str, VideoGuard]
    audit_sha256: str
    bundle_sha256: str

    @classmethod
    def from_wall_audit_zip(cls, path: Path, policy: DeletePolicy) -> DeleteEvidence:
        policy_payload = policy.model_dump(mode="json")
        source = policy_payload.get("source")
        if not isinstance(source, dict):
            raise ValueError("Delete policy has no source evidence block")
        expected_bundle_sha = source.get("wall_audit_sha256")
        actual_bundle_sha = sha256_file(path)
        if expected_bundle_sha != actual_bundle_sha:
            raise ValueError(f"Wall-audit ZIP digest mismatch: {actual_bundle_sha}")
        with zipfile.ZipFile(path) as archive:
            try:
                audit_raw = archive.read("03-wall-content-audit.json")
                videos_raw = archive.read("00-videos.json")
            except KeyError as exc:
                raise ValueError("Wall-audit ZIP is missing required JSON evidence") from exc
        audit = json.loads(audit_raw.decode("utf-8-sig"))
        videos = json.loads(videos_raw.decode("utf-8-sig"))
        if not isinstance(audit, dict) or not isinstance(videos, list):
            raise ValueError("Wall-audit evidence has unexpected roots")
        embedded_sha = audit.get("audit_sha256")
        calculated_sha = canonical_sha256({key: value for key, value in audit.items() if key != "audit_sha256"})
        if embedded_sha != calculated_sha:
            raise ValueError("Wall audit self-digest mismatch")
        expected_inner = source.get("wall_audit_inner_sha256")
        if expected_inner is not None and expected_inner != calculated_sha:
            raise ValueError("Policy is bound to another wall-audit document")
        raw_audit_videos = audit.get("videos")
        if not isinstance(raw_audit_videos, list):
            raise ValueError("Wall audit has no videos list")
        all_ids: set[str] = set()
        published: set[str] = set()
        postponed: set[str] = set()
        states: dict[str, str] = {}
        for raw in raw_audit_videos:
            if not isinstance(raw, dict):
                continue
            remote_id = str(raw.get("video_id") or "").strip()
            if not remote_id:
                continue
            state = str(raw.get("state") or "")
            all_ids.add(remote_id)
            states[remote_id] = state
            if state in {"published", "published_and_scheduled_conflict"}:
                published.add(remote_id)
            if state in {"scheduled", "published_and_scheduled_conflict"}:
                postponed.add(remote_id)
        guards: dict[str, VideoGuard] = {}
        for raw in videos:
            if not isinstance(raw, dict):
                continue
            guard = _video_guard(raw)
            if guard.remote_id in guards:
                raise ValueError(f"Duplicate video identity in source evidence: {guard.remote_id}")
            guards[guard.remote_id] = guard
        if set(guards) != all_ids:
            missing = sorted(all_ids - set(guards))
            extra = sorted(set(guards) - all_ids)
            raise ValueError(f"Wall-audit video evidence differs: missing={missing[:5]} extra={extra[:5]}")
        candidates = {operation.candidate_vk_id for operation in policy.operations}
        missing_candidates = candidates - all_ids
        if missing_candidates:
            raise ValueError(f"Signed candidates are missing from wall audit: {sorted(missing_candidates)[:5]}")
        unsafe_candidates = sorted(remote_id for remote_id in candidates if states.get(remote_id) != "unposted")
        if unsafe_candidates:
            raise ValueError(f"Signed candidates are not unposted in evidence: {unsafe_candidates[:5]}")
        primaries = {operation.primary_vk_id for operation in policy.operations}
        missing_primaries = primaries - all_ids
        if missing_primaries:
            raise ValueError(f"Signed primary copies are missing from wall audit: {sorted(missing_primaries)[:5]}")
        protected = all_ids - candidates
        return cls(
            all_video_ids=frozenset(all_ids),
            protected_video_ids=frozenset(protected),
            published_video_ids=frozenset(published),
            postponed_video_ids=frozenset(postponed),
            video_guards=MappingProxyType(guards),
            audit_sha256=calculated_sha,
            bundle_sha256=actual_bundle_sha,
        )
