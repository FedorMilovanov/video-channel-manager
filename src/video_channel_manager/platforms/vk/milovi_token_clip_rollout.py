"""Provider-inert Issue #323 state/read helpers retained for canonical status/continue.

This module intentionally has no upload/wall writer composition, execution
confirmation, command runner, ``main()``, or ``__main__`` surface. The historic
token rollout authority is retired; only deterministic parsing, inventory
cardinality, journal interpretation, and target proof helpers remain.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from video_channel_manager.editorial._project_profiles import MILOVI_CAKE, resolve_project_key
from video_channel_manager.platforms.vk import VkApiClient, VkInventoryService, VkTokenStore
from video_channel_manager.platforms.vk.milovi_immediate_wall import (
    MILOVI_COMMUNITY_ID,
    MILOVI_OWNER_ID,
    MILOVI_SOURCE_ALLOWLIST,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import (
    ROLL_OUT_IDS,
    SOURCE_SNAPSHOT_ID,
    YOUTUBE_CHANNEL_ID,
    SourceAsset,
)
from video_channel_manager.platforms.vk.upload_lifecycle import UploadStage, VkUploadReadiness

CANARY_SOURCE_ID = "d48QLgOuiTs"
JOURNAL_SCHEMA = "video-manager.milovi-issue-323-token-daily-journal"
MAX_TOKEN_CLIP_SECONDS = 60.0
MILOVI_SCREEN_NAME = "milovi_cake"

if frozenset(ROLL_OUT_IDS) != MILOVI_SOURCE_ALLOWLIST or ROLL_OUT_IDS[0] != CANARY_SOURCE_ID:
    raise RuntimeError("Issue #323 reviewed allowlist/canary differs from canonical source snapshot")


class MiloviTokenRolloutBlocked(RuntimeError):
    """Historical name for an Issue #323 read/state safety blocker."""


def _new_journal() -> dict[str, Any]:
    return {
        "schema_name": JOURNAL_SCHEMA,
        "schema_version": 1,
        "project_key": MILOVI_CAKE,
        "community_id": MILOVI_COMMUNITY_ID,
        "owner_id": MILOVI_OWNER_ID,
        "youtube_channel_id": YOUTUBE_CHANNEL_ID,
        "source_snapshot_id": SOURCE_SNAPSHOT_ID,
        "transport": "official_vk_api_token",
        "browser_used": False,
        "canary_source_id": CANARY_SOURCE_ID,
        "canary_verified": False,
        "provider_write_attempted": False,
        "items": {source_id: {"status": "pending"} for source_id in ROLL_OUT_IDS},
    }


def _load_journal(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return _new_journal()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MiloviTokenRolloutBlocked("Issue #323 token journal is not a JSON object")
    expected = {
        "schema_name": JOURNAL_SCHEMA,
        "schema_version": 1,
        "project_key": MILOVI_CAKE,
        "community_id": MILOVI_COMMUNITY_ID,
        "owner_id": MILOVI_OWNER_ID,
        "youtube_channel_id": YOUTUBE_CHANNEL_ID,
        "source_snapshot_id": SOURCE_SNAPSHOT_ID,
        "transport": "official_vk_api_token",
        "browser_used": False,
        "canary_source_id": CANARY_SOURCE_ID,
    }
    mismatch = {key: (value, payload.get(key)) for key, value in expected.items() if payload.get(key) != value}
    if mismatch:
        raise MiloviTokenRolloutBlocked(f"Issue #323 token journal binding mismatch: {mismatch}")
    items = payload.get("items")
    if not isinstance(items, dict) or tuple(items) != ROLL_OUT_IDS:
        raise MiloviTokenRolloutBlocked("Issue #323 token journal allowlist/order differs")
    return payload


def validate_token_clip_media_facts(facts: Mapping[str, tuple[int, int, float]]) -> None:
    """Validate frozen media facts without acquiring media or calling a provider."""

    if tuple(facts) != ROLL_OUT_IDS:
        raise MiloviTokenRolloutBlocked("Token Clip media facts differ from exact Issue #323 order")
    blockers: list[str] = []
    for source_id in ROLL_OUT_IDS:
        width, height, duration = facts[source_id]
        if width <= 0 or height <= width:
            blockers.append(f"{source_id}:not_vertical:{width}x{height}")
        if duration <= 0 or duration > MAX_TOKEN_CLIP_SECONDS:
            blockers.append(f"{source_id}:duration={duration:.3f}s")
    if blockers:
        raise MiloviTokenRolloutBlocked(
            "Provider-inert token Clip preflight failed; all 12 must be vertical and <=60.0s: " + ", ".join(blockers)
        )


def clip_readiness(asset: SourceAsset) -> VkUploadReadiness:
    return VkUploadReadiness(
        expected_title=asset.title,
        minimum_duration_seconds=max(1, asset.duration_seconds - 4),
        allowed_types=("short_video",),
        require_playable=True,
    )


def _prove_target(client: VkApiClient) -> None:
    matches = [item for item in client.list_managed_communities() if int(item.community_id) == MILOVI_COMMUNITY_ID]
    if len(matches) != 1:
        raise MiloviTokenRolloutBlocked("Stored VK user token does not prove management of Milovi community 68859909")
    screen = str(matches[0].screen_name or "").strip().casefold()
    if screen and screen != MILOVI_SCREEN_NAME:
        raise MiloviTokenRolloutBlocked(f"Community 68859909 resolved to unexpected screen_name {screen!r}")
    if (
        resolve_project_key(
            {"project_key": MILOVI_CAKE, "community_id": MILOVI_COMMUNITY_ID, "owner_id": MILOVI_OWNER_ID}
        )
        != MILOVI_CAKE
    ):
        raise MiloviTokenRolloutBlocked("Canonical Milovi project/community/owner identity failed")


def _resolve_account(store: VkTokenStore, api_version: str) -> tuple[str, VkApiClient]:
    preferred = {"milovi-cake": 0, "shared-vk-user": 1, "legendary-poet": 2}
    found: list[tuple[int, str, VkApiClient]] = []
    for account in store.list_accounts():
        if not store.token_exists(account.alias):
            continue
        client = VkApiClient(token_store=store, account_alias=account.alias, api_version=api_version)
        try:
            _prove_target(client)
        except Exception:
            continue
        found.append((preferred.get(account.alias, 10), account.alias, client))
    if not found:
        raise MiloviTokenRolloutBlocked("No stored VK user token proved administration of Milovi community 68859909")
    found.sort(key=lambda row: (row[0], row[1]))
    return found[0][1], found[0][2]


def _find_existing_clip(client: VkApiClient, asset: SourceAsset) -> str | None:
    package = VkInventoryService(client).build_audit_package(str(MILOVI_COMMUNITY_ID))
    if int(package.channel.ref.channel_id) != MILOVI_COMMUNITY_ID:
        raise MiloviTokenRolloutBlocked("VK inventory returned another community")
    marker = f"youtube.com/shorts/{asset.source_id}".casefold()
    matching = [
        record
        for record in package.videos
        if marker in str(record.description or "").casefold()
        and (record.duration_seconds is None or abs(int(record.duration_seconds) - asset.duration_seconds) <= 4)
    ]
    if len(matching) > 1:
        remote_ids = sorted(str(record.ref.remote_id) for record in matching)
        raise MiloviTokenRolloutBlocked(
            f"Multiple VK objects match {asset.source_id}; exact Clip cardinality is ambiguous: {remote_ids}"
        )
    if not matching:
        return None
    candidate = matching[0]
    video_type = str((candidate.metadata if isinstance(candidate.metadata, dict) else {}).get("vk_video_type") or "")
    if video_type != "short_video":
        raise MiloviTokenRolloutBlocked(
            f"Source marker for {asset.source_id} belongs to ordinary VK video; duplicate upload forbidden"
        )
    return str(candidate.ref.remote_id)


def _parse_remote_id(remote_id: str) -> tuple[int, int]:
    owner_text, sep, video_text = remote_id.partition("_")
    if not sep:
        raise MiloviTokenRolloutBlocked(f"Invalid VK remote ID: {remote_id}")
    owner_id, video_id = int(owner_text), int(video_text)
    if owner_id != MILOVI_OWNER_ID or video_id <= 0:
        raise MiloviTokenRolloutBlocked(f"VK object {remote_id} is outside exact Milovi owner")
    return owner_id, video_id


def _has_provider_effect(record: Mapping[str, Any]) -> bool:
    stage = UploadStage(str(record.get("stage")))
    if stage in {
        UploadStage.RESERVED,
        UploadStage.UPLOAD_STARTED,
        UploadStage.UPLOAD_RESPONSE_RECEIVED,
        UploadStage.PROCESSING,
        UploadStage.UNKNOWN_REQUIRES_RECONCILIATION,
        UploadStage.VERIFIED,
    }:
        return True
    return stage is UploadStage.RESERVATION_INTENT_COMMITTED and bool(record.get("reservation_dispatch_started_at"))


def _upload_remote_id(record: Mapping[str, Any]) -> str:
    reservation = record.get("reservation")
    if not isinstance(reservation, Mapping) or not isinstance(reservation.get("remote_id"), str):
        raise MiloviTokenRolloutBlocked("Upload journal lost exact reservation identity")
    return str(reservation["remote_id"])


__all__ = [
    "CANARY_SOURCE_ID",
    "MiloviTokenRolloutBlocked",
    "_find_existing_clip",
    "_has_provider_effect",
    "_load_journal",
    "_parse_remote_id",
    "_prove_target",
    "_resolve_account",
    "_upload_remote_id",
    "clip_readiness",
    "validate_token_clip_media_facts",
]
