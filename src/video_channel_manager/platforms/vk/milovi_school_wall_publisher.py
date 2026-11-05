"""A single exact Milovi Cake School postponed wall canary, never a bulk publisher.

Requires immutable editorial preview, current public-wall check, exact target
binding, separate operator confirmation, durable intent journal and community
write mutex. Unknown provider outcomes are never retried.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk.client import VkApiClient, VkApiError
from video_channel_manager.platforms.vk.lock import community_vk_write_lock_path, local_vk_write_lock
from video_channel_manager.platforms.vk.milovi_school_public_wall_audit import (
    MILOVI_COMMUNITY_ID,
    MILOVI_OWNER_ID,
    MILOVI_SERVICE_ALIAS,
    collect_exact_public_wall,
    classify_editorial_wall_posts,
)
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.wall import VkWallWriter
from video_channel_manager.platforms.vk.writer import VkWriteError

COMMUNITY_ACCOUNT = "vk-milovi-cake-community-key"
SOURCE_ID = "tech-mirror-glaze"
PUBLISH_DATE = 1794042000
EXPECTED_TEXT_SHA256 = "9cc8b4a2c18f062da24533efe8a6b8da97ce3e840ccf924f71d05bb9463147b0"
EXPECTED_GUID = "vcm-milovi-school-b0ab367a74ae756f99be"
CONFIRMATION = "MILOVI-CAKE-68859909-TECH-MIRROR-GLAZE-20261107-1200MSK"


class MiloviCanaryBlocked(RuntimeError):
    """An operation gate was not satisfied. Never fall back to another token."""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_canary_preview(*, preview_path: Path, editorial_path: Path) -> dict[str, Any]:
    p = json.loads(preview_path.read_text(encoding="utf-8"))
    editorial = editorial_path.read_text(encoding="utf-8")
    expected = {
        "schema_name": "video-manager.milovi-school-vk-wall-canary-preview",
        "schema_version": 1,
        "project_key": "milovi-cake",
        "owner_issue": 792,
        "community_id": MILOVI_COMMUNITY_ID,
        "owner_id": MILOVI_OWNER_ID,
        "credential_alias_for_later_execution": COMMUNITY_ACCOUNT,
        "source_article_id": SOURCE_ID,
        "publication_surface": "vk_wall_postponed",
        "publish_date_unix": PUBLISH_DATE,
        "guid": EXPECTED_GUID,
        "message_sha256": EXPECTED_TEXT_SHA256,
        "editorial_source_sha256": _sha256(editorial),
        "provider_writes_authorized": False,
        "operator_execution_approval": "not_granted",
        "release_eligible": False,
        "provider_effect_state": "not_dispatched",
    }
    for key, value in expected.items():
        if p.get(key) != value:
            raise MiloviCanaryBlocked(f"Preview identity or immutable contract mismatch: {key}")
    if p.get("attachment_tokens") != [] or p.get("automatic_execution") is not False:
        raise MiloviCanaryBlocked("Only text-only and provider-inert preview is eligible for separate approval")
    if p.get("publish_at_msk") != "2026-11-07T12:00:00+03:00":
        raise MiloviCanaryBlocked("Canary time mismatch")
    text = p.get("message")
    if not isinstance(text, str) or _sha256(text) != EXPECTED_TEXT_SHA256:
        raise MiloviCanaryBlocked("Frozen message digest mismatch")
    url = "https://french.milovicake.ru/articles/tech-mirror-glaze/"
    if p.get("source_article_url") != url or text.count(url) != 1:
        raise MiloviCanaryBlocked("Only approved School canonical URL is allowed")
    return p


class MiloviCommunitySchoolWriter(VkWallWriter):
    """Community-authorized text writer bound to one Milovi Cake alias."""

    def assert_token_scopes(self, *required_scopes: str) -> Any:
        if self.account_alias != COMMUNITY_ACCOUNT:
            raise MiloviCanaryBlocked("Milovi School publisher requires its exact account alias")
        token = self.token_store.load_token(COMMUNITY_ACCOUNT)
        if token.token_type != "community" or token.is_expired():
            raise MiloviCanaryBlocked("Milovi School requires a nonexpired community key")
        if any(scope not in token.scopes for scope in required_scopes):
            raise MiloviCanaryBlocked("Milovi community key has no verified wall permission")
        return token

    def _token_value(self) -> str:
        return self.assert_token_scopes("wall").access_token

    def send_one(self, plan: dict[str, Any]) -> int:
        self.assert_method_circuit_closed("wall.post")
        self.assert_token_scopes("wall")
        response = self._call(
            "wall.post",
            params={
                "owner_id": MILOVI_OWNER_ID,
                "from_group": True,
                "message": plan["message"],
                "publish_date": PUBLISH_DATE,
                "guid": EXPECTED_GUID,
            },
            retry_transient=False,
        )
        post_id = response.get("post_id") if isinstance(response, dict) else response
        if type(post_id) is not int or post_id <= 0:
            raise MiloviCanaryBlocked("VK did not return an exact positive post ID; never retry")
        return post_id


def _atomic_update_journal(path: Path, journal: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("x", encoding="utf-8") as handle:
        json.dump(journal, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def read_public_preflight(*, store: VkTokenStore, api_version: str) -> dict[str, Any]:
    if not store.token_exists(MILOVI_SERVICE_ALIAS):
        raise MiloviCanaryBlocked("Milovi service key missing; cannot read exact public wall")
    if store.load_token(MILOVI_SERVICE_ALIAS).token_type != "service":
        raise MiloviCanaryBlocked("Service read alias has wrong credential type")
    api = VkApiClient(token_store=store, account_alias=MILOVI_SERVICE_ALIAS, api_version=api_version, max_attempts=1)
    try:
        posts = collect_exact_public_wall(api)
    finally:
        api.close()
    audit = classify_editorial_wall_posts(posts, (SOURCE_ID,))
    matching = audit["source_classification"][0]["matches"]
    if matching:
        raise MiloviCanaryBlocked("The exact School URL is already on the public wall")
    return {
        "public_wall_posts": len(posts),
        "same_source_url_present": False,
        "captured_utc": datetime.now(UTC).isoformat(),
    }


def schedule_canary_once(
    *,
    store: VkTokenStore,
    api_version: str,
    preview_path: Path,
    editorial_path: Path,
    journal_path: Path,
    confirmation: str,
    admin_queue_witness: str,
) -> dict[str, Any]:
    """Execute at most one live provider mutation; do not automatically retry."""
    if confirmation != CONFIRMATION:
        raise MiloviCanaryBlocked("Exact operator confirmation is missing")
    if admin_queue_witness != "OWNER_REPORTED_EMPTY_2026-11-05":
        raise MiloviCanaryBlocked("Admin queue witness is missing or not the reviewed account")
    plan = load_canary_preview(preview_path=preview_path, editorial_path=editorial_path)
    if datetime.now(UTC).timestamp() + 300 >= PUBLISH_DATE:
        raise MiloviCanaryBlocked("Proposed slot is no longer safely in future")
    if not store.token_exists(COMMUNITY_ACCOUNT):
        raise MiloviCanaryBlocked("Milovi Cake community key not installed")
    if store.load_token(COMMUNITY_ACCOUNT).token_type != "community":
        raise MiloviCanaryBlocked("A user token cannot substitute for the community key")
    if journal_path.exists():
        raise MiloviCanaryBlocked("Durable canary journal already exists. Reconcile first; never resend")
    with local_vk_write_lock(
        community_vk_write_lock_path(store.data_dir, community_id=MILOVI_COMMUNITY_ID),
        account=COMMUNITY_ACCOUNT,
        community_id=MILOVI_COMMUNITY_ID,
        operation="milovi-school-postponed-canary:tech-mirror-glaze",
    ):
        if journal_path.exists():
            raise MiloviCanaryBlocked("Canary journal created concurrently; stop")
        latest = read_public_preflight(store=store, api_version=api_version)
        community_api = VkApiClient(
            token_store=store, account_alias=COMMUNITY_ACCOUNT, api_version=api_version, max_attempts=1
        )
        try:
            permissions_mask, enabled = community_api.get_community_token_permissions()
            group = community_api.get_community(MILOVI_COMMUNITY_ID)
            if group.ref.channel_id != str(MILOVI_COMMUNITY_ID) or "wall" not in enabled:
                raise MiloviCanaryBlocked("Community token no longer bound to Milovi Cake wall")
        finally:
            community_api.close()
        journal: dict[str, Any] = {
            "schema_version": 1,
            "project_key": "milovi-cake",
            "community_id": MILOVI_COMMUNITY_ID,
            "owner_id": MILOVI_OWNER_ID,
            "source_id": SOURCE_ID,
            "message_sha256": EXPECTED_TEXT_SHA256,
            "publish_date": PUBLISH_DATE,
            "guid": EXPECTED_GUID,
            "community_permission_mask": permissions_mask,
            "latest_public_preflight": latest,
            "admin_queue_witness": admin_queue_witness,
            "provider_writes_attempted": 0,
            "post_id": None,
            "state": "intent_prepared",
        }
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        with journal_path.open("x", encoding="utf-8") as handle:
            json.dump(journal, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        journal["state"] = "dispatch_started_ambiguous_if_no_ack"
        journal["provider_writes_attempted"] = 1
        _atomic_update_journal(journal_path, journal)
        writer = MiloviCommunitySchoolWriter(
            token_store=store, account_alias=COMMUNITY_ACCOUNT, api_version=api_version, max_attempts=1
        )
        try:
            post_id = writer.send_one(plan)
            journal["post_id"] = post_id
            journal["state"] = "vk_accepted_pending_admin_postflight"
        except (VkWriteError, VkApiError, MiloviCanaryBlocked) as exc:
            journal["state"] = "provider_result_ambiguous_or_rejected_reconcile_no_retry"
            journal["failure_type"] = type(exc).__name__
            journal["failure_code"] = getattr(exc, "code", None)
            _atomic_update_journal(journal_path, journal)
            raise
        finally:
            writer.close()
        _atomic_update_journal(journal_path, journal)
        return journal
