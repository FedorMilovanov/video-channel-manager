from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore

from lord_god_article_wave_v3.common import (
    ACCOUNT_ALIAS,
    OWNER_ID,
    now_iso,
    write_json,
)
from lord_god_article_wave_v3.mutations import set_journal_stage
from lord_god_article_wave_v3.photo_wave_v5 import (
    PHOTO_DECISION_SET_ID,
    build_photo_policy,
    group_wall_photo_identity,
    load_photo_journal,
    preflight,
    reference_matches_group_rehost,
)
from lord_god_article_wave_v3.wall import (
    photo_identity_from_token,
    post_reference,
    wall_snapshot,
)


def reconcile(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    output_dir = repo / "data" / "vk-wall" / PHOTO_DECISION_SET_ID
    journal_path = output_dir / "photo-journal-v4.json"
    policy = build_photo_policy(repo)
    journal = load_photo_journal(journal_path, policy)
    operations = journal["operations"]

    candidates = [
        (operation_id, entry)
        for operation_id, entry in operations.items()
        if isinstance(entry, dict)
        and entry.get("stage") == "wall_post_accepted_unverified"
        and isinstance(entry.get("post_id"), int)
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"Expected exactly one accepted-unverified canary; found={len(candidates)}")
    operation_id, entry = candidates[0]
    if "Accepted post has a different wall photo" not in str(entry.get("error") or ""):
        raise RuntimeError("Accepted-unverified journal reason is not the known VK photo rehost")

    policy_operations = {str(item["operation_id"]): item for item in policy["operations"] if isinstance(item, dict)}
    operation = policy_operations.get(str(operation_id))
    if not isinstance(operation, dict) or int(operation.get("ordinal") or 0) != 1:
        raise RuntimeError("Accepted-unverified operation is not the v5 canary")

    settings = get_settings()
    client = VkApiClient(
        token_store=VkTokenStore(settings.data_dir),
        account_alias=ACCOUNT_ALIAS,
        api_version=settings.vk_api_version,
        max_attempts=4,
    )
    published, postponed = wall_snapshot(client)
    post_id = int(entry["post_id"])
    raw_matches = [post for post in postponed if post.get("owner_id") == OWNER_ID and post.get("id") == post_id]
    if len(raw_matches) != 1:
        raise RuntimeError(f"Expected exactly one postponed post for accepted post_id; found={len(raw_matches)}")

    reference = post_reference(raw_matches[0], "postponed")
    if not reference_matches_group_rehost(operation, reference):
        raise RuntimeError("Accepted post does not match text, URL, time, and one group photo")

    expected_identity = photo_identity_from_token(entry.get("photo_token"))
    posted_identity = group_wall_photo_identity(reference)
    if expected_identity is None or posted_identity is None:
        raise RuntimeError("Photo identities are not usable for reconciliation")
    if expected_identity == posted_identity:
        raise RuntimeError("Photo identity did not change; rehost reconciliation is not required")

    set_journal_stage(
        journal,
        journal_path,
        operation,
        "verified",
        photo_token=str(entry["photo_token"]),
        posted_photo_identity=posted_identity,
        guid=str(entry.get("guid") or operation.get("guid") or operation_id),
        post_id=post_id,
        verification="vk-group-photo-rehost-inspected",
        reconciled_from="wall_post_accepted_unverified",
        reconciled_at=now_iso(),
        error=None,
    )

    report = preflight(
        policy,
        published,
        postponed,
        journal,
        minimum_future_seconds=0,
    )
    if report["already_applied"] != 1 or report["ready"] != 9 or report["conflicts"]:
        raise RuntimeError(
            "Reconciled preflight is not exact: "
            f"applied={report['already_applied']} ready={report['ready']} "
            f"conflicts={report['conflicts']}"
        )

    result = {
        "status": "reconciled",
        "decision_set_id": PHOTO_DECISION_SET_ID,
        "operation_id": operation_id,
        "post_id": post_id,
        "queue": reference["queue"],
        "publish_date": reference["date"],
        "article_url_in_text": True,
        "message_matches": True,
        "has_photo": True,
        "saved_photo_identity": expected_identity,
        "posted_photo_identity": posted_identity,
        "journal_stage": "verified",
        "already_applied": report["already_applied"],
        "ready": report["ready"],
        "conflicts": report["conflicts"],
        "vk_write_methods": [],
    }
    write_json(output_dir / "photo-v5-canary-reconciliation.json", result)
    write_json(output_dir / "photo-v4-canary-postflight.json", report)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(reconcile(args.repo), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
