from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from video_channel_manager.platforms.vk.delete_orchestrator.evidence import DeleteEvidence
from video_channel_manager.platforms.vk.delete_orchestrator.gateway import DeleteGateway, OwnerInventory
from video_channel_manager.platforms.vk.delete_orchestrator.models import DeleteOperation, VideoGuard


def text_sha256(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def raw_video_guard(payload: dict[str, Any]) -> VideoGuard:
    owner_id = payload.get("owner_id")
    video_id = payload.get("id")
    if not isinstance(owner_id, int) or not isinstance(video_id, int):
        raise ValueError("VK video response has no exact owner/id")
    return VideoGuard(
        remote_id=f"{owner_id}_{video_id}",
        title=str(payload.get("title") or ""),
        description_sha256=text_sha256(str(payload.get("description") or "")),
        duration_seconds=int(payload.get("duration") or 0),
        owner_id=owner_id,
        video_id=video_id,
        vk_type=str(payload.get("type") or "video"),
        date=int(payload.get("date") or 0),
    )


def guard_differences(expected: VideoGuard, payload: dict[str, Any]) -> dict[str, tuple[object, object]]:
    actual = raw_video_guard(payload)
    differences: dict[str, tuple[object, object]] = {}
    for field in (
        "remote_id",
        "title",
        "description_sha256",
        "duration_seconds",
        "owner_id",
        "video_id",
        "vk_type",
        "date",
    ):
        expected_value = getattr(expected, field)
        actual_value = getattr(actual, field)
        if expected_value != actual_value:
            differences[field] = (expected_value, actual_value)
    return differences


def _count_field(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, dict):
        raw = value.get("count")
        return int(raw) if isinstance(raw, int) else 0
    return 0


def inventory_index(inventory: OwnerInventory) -> Mapping[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in inventory.items:
        owner_id = item.get("owner_id")
        video_id = item.get("id")
        if not isinstance(owner_id, int) or not isinstance(video_id, int):
            continue
        remote_id = f"{owner_id}_{video_id}"
        if remote_id in result:
            raise FatalInvariantError(f"Owner inventory returned duplicate ID: {remote_id}")
        result[remote_id] = item
    return MappingProxyType(result)


@dataclass(frozen=True)
class EpochGuard:
    inventory: OwnerInventory
    inventory_by_id: Mapping[str, dict[str, Any]]
    published_video_ids: frozenset[str]
    postponed_video_ids: frozenset[str]
    exact_protected_fallbacks: frozenset[str]


class FatalInvariantError(RuntimeError):
    pass


class TransientInvariantError(RuntimeError):
    pass


class OperationConflictError(RuntimeError):
    pass


def stable_owner_inventory(*, community_id: int, gateway: DeleteGateway) -> OwnerInventory:
    first = gateway.owner_inventory(community_id)
    second = gateway.owner_inventory(community_id)
    if first.ids != second.ids or first.reported_count != second.reported_count:
        only_first = sorted(first.ids - second.ids)
        only_second = sorted(second.ids - first.ids)
        raise TransientInvariantError(
            "VK owner inventory did not produce two identical complete observations: "
            f"first_count={first.reported_count} second_count={second.reported_count} "
            f"only_first={only_first[:5]} only_second={only_second[:5]}"
        )
    return second


def build_epoch_guard(
    *,
    community_id: int,
    evidence: DeleteEvidence,
    gateway: DeleteGateway,
) -> EpochGuard:
    inventory = stable_owner_inventory(community_id=community_id, gateway=gateway)
    by_id = inventory_index(inventory)
    visible = frozenset(by_id)
    missing_protected = sorted(evidence.protected_video_ids - visible)
    exact_fallbacks: set[str] = set()
    truly_missing: list[str] = []
    guard_drift: dict[str, dict[str, tuple[object, object]]] = {}
    for remote_id in missing_protected:
        exact = gateway.exact_video(remote_id)
        if exact is None:
            truly_missing.append(remote_id)
            continue
        differences = guard_differences(evidence.video_guards[remote_id], exact)
        if differences:
            guard_drift[remote_id] = differences
            continue
        exact_fallbacks.add(remote_id)
    if truly_missing:
        raise FatalInvariantError(f"Protected VK videos are absent by inventory and exact lookup: {truly_missing[:10]}")
    if guard_drift:
        sample = {key: guard_drift[key] for key in sorted(guard_drift)[:3]}
        raise FatalInvariantError(f"Protected exact fallback did not match signed evidence: {sample}")
    if inventory.reported_count is not None:
        logical_count = len(visible) + len(exact_fallbacks)
        if inventory.reported_count != logical_count:
            raise TransientInvariantError(
                "VK owner inventory has an unexplained count/items gap; candidate absence is not yet provable: "
                f"reported={inventory.reported_count} visible={len(visible)} "
                f"guarded_shadow={len(exact_fallbacks)} logical={logical_count}"
            )
    published = gateway.wall_video_ids(community_id=community_id, postponed=False)
    postponed = gateway.wall_video_ids(community_id=community_id, postponed=True)
    missing_published = sorted(evidence.published_video_ids - published)
    missing_postponed = sorted(evidence.postponed_video_ids - postponed)
    if missing_published:
        raise FatalInvariantError(f"Signed published wall attachments disappeared: {missing_published[:10]}")
    if missing_postponed:
        raise FatalInvariantError(f"Signed postponed wall attachments disappeared: {missing_postponed[:10]}")
    return EpochGuard(
        inventory=inventory,
        inventory_by_id=by_id,
        published_video_ids=published,
        postponed_video_ids=postponed,
        exact_protected_fallbacks=frozenset(exact_fallbacks),
    )


def precheck_operation(
    operation: DeleteOperation,
    *,
    community_id: int,
    managed_album_ids: frozenset[str],
    epoch_guard: EpochGuard,
    gateway: DeleteGateway,
) -> None:
    candidate = epoch_guard.inventory_by_id.get(operation.candidate_vk_id)
    primary = epoch_guard.inventory_by_id.get(operation.primary_vk_id)
    if candidate is None:
        raise OperationConflictError(f"Candidate is absent from the stable owner inventory: {operation.operation_id}")
    if primary is None:
        raise FatalInvariantError(f"Primary copy is absent from the stable owner inventory: {operation.operation_id}")
    candidate_diff = guard_differences(operation.candidate_guard, candidate)
    primary_diff = guard_differences(operation.primary_guard, primary)
    if candidate_diff:
        raise OperationConflictError(f"Candidate immutable guard changed: {operation.operation_id}: {candidate_diff}")
    if primary_diff:
        raise FatalInvariantError(f"Primary immutable guard changed: {operation.operation_id}: {primary_diff}")
    views = int(candidate.get("views") or 0)
    comments = _count_field(candidate.get("comments"))
    likes = _count_field(candidate.get("likes"))
    reposts = _count_field(candidate.get("reposts"))
    if views > operation.maximum_views:
        raise OperationConflictError(f"Candidate views exceed signed maximum: {operation.operation_id}: {views}")
    if operation.required_zero_engagement and any((comments, likes, reposts)):
        raise OperationConflictError(
            f"Candidate acquired engagement: {operation.operation_id}: "
            f"comments={comments}, likes={likes}, reposts={reposts}"
        )
    if operation.candidate_vk_id in epoch_guard.published_video_ids:
        raise OperationConflictError(f"Candidate is now published on the wall: {operation.operation_id}")
    if operation.candidate_vk_id in epoch_guard.postponed_video_ids:
        raise OperationConflictError(f"Candidate is now scheduled on the wall: {operation.operation_id}")
    candidate_albums = gateway.album_ids(community_id=community_id, remote_id=operation.candidate_vk_id)
    primary_albums = gateway.album_ids(community_id=community_id, remote_id=operation.primary_vk_id)
    actual_candidate_managed = candidate_albums.intersection(managed_album_ids)
    actual_primary_managed = primary_albums.intersection(managed_album_ids)
    if actual_candidate_managed != frozenset(operation.candidate_managed_album_ids):
        raise OperationConflictError(
            f"Candidate managed album memberships changed: {operation.operation_id}: {sorted(actual_candidate_managed)}"
        )
    if actual_primary_managed != frozenset(operation.primary_managed_album_ids):
        raise FatalInvariantError(
            f"Primary managed album memberships changed: {operation.operation_id}: {sorted(actual_primary_managed)}"
        )
