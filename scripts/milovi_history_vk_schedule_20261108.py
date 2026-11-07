"""Single immutable owner-authorized MILOVI CAKE VK wall post postponed for Nov 8.

Posts a short teaser linking to the already verified Telegraph longread, and a
separate link to real MILOVI CAKE cakes. This is NOT a native VK Article.
Never retries an uncertain provider write or uses a shared/quarantined user key.
"""

from __future__ import annotations
import argparse
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk.client import VkApiClient, VkApiError
from video_channel_manager.platforms.vk.lock import community_vk_write_lock_path, local_vk_write_lock
from video_channel_manager.platforms.vk.milovi_school_public_wall_audit import collect_exact_public_wall
from video_channel_manager.platforms.vk.milovi_school_wall_publisher import MiloviCommunitySchoolWriter
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.writer import VkWriteError

PLAN = Path("content/editorial/milovi-cake/history-vk-20261108-1400.json")
COMMUNITY = 68859909
OWNER = -68859909
ALIAS = "vk-milovi-cake-community-key"
SERVICE = "vk-milovi-cake-service-key"
SLOT = datetime(2026, 11, 8, 14, 0, tzinfo=ZoneInfo("Europe/Moscow"))
CONFIRM = "SCHEDULE:MILOVI-CAKE:68859909:2026-11-08T14:00+03:00"
SOURCE = "https://telegra.ph/Kto-pridumal-konditerskoe-delo-Ot-myasnyh-pirogov-do-iskusstva-desertov-11-07-2"
CAKE = "https://milovicake.ru/"


class VkHistoryReleaseBlocked(RuntimeError):
    pass


def sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_plan(path: Path = PLAN) -> dict[str, Any]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    msg = plan["message"]
    if (
        plan.get("schema") != "video-channel-manager.milovi-history-vk-postponed-v1"
        or plan.get("project_key") != "milovi-cake"
        or plan.get("community_id") != COMMUNITY
        or plan.get("owner_id") != OWNER
        or plan.get("publication_surface") != "vk_wall_postponed"
        or plan.get("vk_native_article_created") is not False
        or plan.get("scheduled_at") != SLOT.isoformat()
        or plan.get("publish_date_unix") != int(SLOT.timestamp())
        or plan.get("credential_alias") != ALIAS
        or plan.get("public_read_alias") != SERVICE
        or plan.get("source_longread_url") != SOURCE
        or plan.get("business_cake_url") != CAKE
        or plan.get("attachments") != []
        or plan.get("provider_write_attempts") != 0
        or plan.get("verified_vk_post_id") is not None
        or plan.get("never_auto_retry_after_unknown") is not True
        or not isinstance(msg, str)
        or len(msg) > 3000
        or msg.count(SOURCE) != 1
        or msg.count(CAKE) != 1
        or sha(msg) != plan.get("message_sha256")
        or plan.get("guid")
        != "vcm-milovi-history-20261108-1400-" + hashlib.sha256(msg.encode("utf-8")).hexdigest()[:16]
    ):
        raise VkHistoryReleaseBlocked("Owner's exact VK target, text, two URLs, GUID or Nov 8 14 MSK release drifted")
    return plan


def _journal_update(path: Path, record: dict[str, Any]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    if temp.exists():
        raise VkHistoryReleaseBlocked("Unresolved VK journal temp file; reconcile instead of overwriting")
    with temp.open("x", encoding="utf-8") as fp:
        json.dump(record, fp, ensure_ascii=False, indent=2)
        fp.write("\n")
        fp.flush()
        os.fsync(fp.fileno())
    temp.replace(path)


def _read_public_duplicate_guard(store: VkTokenStore, api_version: str, source_url: str) -> dict[str, Any]:
    token = store.load_token(SERVICE)
    if token.token_type != "service" or token.is_expired():
        raise VkHistoryReleaseBlocked("Exact independent Milovi service read key unavailable")
    reader = VkApiClient(token_store=store, account_alias=SERVICE, api_version=api_version, max_attempts=1)
    try:
        posts = collect_exact_public_wall(reader)
    finally:
        reader.close()
    matches = []
    for post in posts:
        texts = [str(post.get("text") or "")]
        for attachment in post.get("attachments") or []:
            if isinstance(attachment, dict) and isinstance(attachment.get("link"), dict):
                texts.append(str(attachment["link"].get("url") or ""))
        if any(source_url in text for text in texts):
            matches.append(int(post["id"]))
    if matches:
        raise VkHistoryReleaseBlocked(
            f"Identical Telegraph history link already on public community wall, post IDs: {matches}"
        )
    return {
        "checked_utc": datetime.now(UTC).isoformat(),
        "published_count": len(posts),
        "same_source_public_matches": 0,
        "postponed_readback": "not_available_to_service_token",
    }


def schedule_once(
    *, plan_path: Path, journal_path: Path, data_dir: Path, confirmation: str, now: datetime | None = None
) -> dict[str, Any]:
    plan = load_plan(plan_path)
    clock = (now or datetime.now(UTC)).astimezone(UTC)
    if confirmation != CONFIRM:
        raise VkHistoryReleaseBlocked("User's exact reviewed single publication confirmation not bound")
    if datetime.fromtimestamp(plan["publish_date_unix"], UTC) <= clock + timedelta(minutes=5):
        raise VkHistoryReleaseBlocked("Owner's publication time passed or is too close; not a late burst")
    store = VkTokenStore(data_dir)
    if not store.token_exists(ALIAS) or not store.token_exists(SERVICE):
        raise VkHistoryReleaseBlocked("Exact Milovi community writer/service reader unavailable")
    key = store.load_token(ALIAS)
    if key.token_type != "community" or "wall" not in key.scopes or key.is_expired():
        raise VkHistoryReleaseBlocked("Only validated non-expired Milovi community wall key allowed")
    if journal_path.exists():
        raise VkHistoryReleaseBlocked("VK history release journal exists; do not retry, reconcile first")
    lock = community_vk_write_lock_path(store.data_dir, community_id=COMMUNITY)
    with local_vk_write_lock(
        lock, account=ALIAS, community_id=COMMUNITY, operation="milovi-cake-history-nov08-1400-single-wall-post"
    ):
        if journal_path.exists():
            raise VkHistoryReleaseBlocked("VK history release already started in another process")
        live = _read_public_duplicate_guard(store, get_settings().vk_api_version, SOURCE)
        inspector = VkApiClient(
            token_store=store, account_alias=ALIAS, api_version=get_settings().vk_api_version, max_attempts=1
        )
        try:
            perm_mask, scopes = inspector.get_community_token_permissions()
            group = inspector.get_community(COMMUNITY)
            if group.ref.channel_id != str(COMMUNITY) or "wall" not in scopes:
                raise VkHistoryReleaseBlocked("Current community key not bound to owner MILOVI CAKE wall")
        finally:
            inspector.close()
        record = dict(
            schema="video-channel-manager.milovi-history-vk-durable-intent",
            version=1,
            owner=OWNER,
            community=COMMUNITY,
            message_sha256=plan["message_sha256"],
            source_url=SOURCE,
            cake_order_url=CAKE,
            planned_for_moscow=SLOT.isoformat(),
            planned_for_unix=plan["publish_date_unix"],
            guid=plan["guid"],
            token_alias=ALIAS,
            credential_scopes_verified=["wall"],
            current_token_permission_mask=perm_mask,
            preflight_public_wall=live,
            admin_postponed_queue="not_api_verified; provider acceptance is not native VK article",
            native_article_created=False,
            provider_writes_attempted=0,
            post_id=None,
            state="intent_prepared",
            updated_utc=datetime.now(UTC).isoformat(),
        )
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        with journal_path.open("x", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        record["state"] = "dispatch_started_unknown_if_no_ack"
        record["provider_writes_attempted"] = 1
        record["updated_utc"] = datetime.now(UTC).isoformat()
        _journal_update(journal_path, record)
        writer = MiloviCommunitySchoolWriter(
            token_store=store, account_alias=ALIAS, api_version=get_settings().vk_api_version, max_attempts=1
        )
        try:
            writer.assert_method_circuit_closed("wall.post")
            writer.assert_token_scopes("wall")
            response = writer._call(
                "wall.post",
                params={
                    "owner_id": OWNER,
                    "from_group": True,
                    "message": plan["message"],
                    "publish_date": plan["publish_date_unix"],
                    "guid": plan["guid"],
                },
                retry_transient=False,
            )
            post_id = response.get("post_id") if isinstance(response, dict) else response
            if type(post_id) is not int or post_id <= 0:
                raise VkHistoryReleaseBlocked("VK returned no exact positive postponed post ID")
            record["post_id"] = post_id
            record["state"] = "vk_accepted_postponed_pending_admin_postflight"
        except (VkHistoryReleaseBlocked, VkApiError, VkWriteError) as ex:
            record["state"] = "unknown_or_rejected_vk_provider_response_NO_RETRY"
            record["error_type"] = type(ex).__name__
            record["error_code"] = getattr(ex, "code", None)
            _journal_update(journal_path, record)
            raise
        finally:
            writer.close()
        record["updated_utc"] = datetime.now(UTC).isoformat()
        _journal_update(journal_path, record)
        return dict(
            post_id=record["post_id"],
            url=f"https://vk.com/wall{OWNER}_{record['post_id']}",
            schedule_moscow=SLOT.isoformat(),
            state=record["state"],
            journal=str(journal_path),
            provider_writes_attempted=1,
        )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("operation", choices=("validate", "execute"))
    p.add_argument("--plan", type=Path, default=PLAN)
    p.add_argument(
        "--journal",
        type=Path,
        default=Path(
            r"C:\Users\Fedor\Projects\video-channel-manager\data\operator\milovi-cake\history-vk-20261108-1400.json"
        ),
    )
    p.add_argument("--data-dir", type=Path, default=Path(r"C:\Users\Fedor\Projects\video-channel-manager\data"))
    p.add_argument("--confirmation", default="")
    args = p.parse_args()
    if args.operation == "validate":
        plan = load_plan(args.plan)
        result = {
            "valid": True,
            "wall_not_native_article": True,
            "owner": OWNER,
            "time": SLOT.isoformat(),
            "message_sha256": plan["message_sha256"],
            "provider_writes": 0,
        }
    else:
        result = schedule_once(
            plan_path=args.plan, journal_path=args.journal, data_dir=args.data_dir, confirmation=args.confirmation
        )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
