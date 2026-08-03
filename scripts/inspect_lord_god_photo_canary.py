from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore

from lord_god_article_wave_v3.common import (
    ACCOUNT_ALIAS,
    OWNER_ID,
    canonical_text,
    normalize_url,
    read_json,
)
from lord_god_article_wave_v3.photo_wave_v5 import (
    PHOTO_DECISION_SET_ID,
    build_photo_policy,
)
from lord_god_article_wave_v3.wall import (
    photo_identity_from_token,
    post_reference,
    wall_snapshot,
)


def text_sha256(value: object) -> str:
    text = canonical_text(value)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def inspect(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    output_dir = repo / "data" / "vk-wall" / PHOTO_DECISION_SET_ID
    journal_path = output_dir / "photo-journal-v4.json"
    journal = read_json(journal_path, None)
    if not isinstance(journal, dict):
        raise RuntimeError(f"Invalid or missing journal: {journal_path}")
    operations = journal.get("operations")
    if not isinstance(operations, dict):
        raise RuntimeError("Journal operations map is invalid")

    candidates = [
        (operation_id, entry)
        for operation_id, entry in operations.items()
        if isinstance(entry, dict)
        and entry.get("stage") == "wall_post_accepted_unverified"
        and isinstance(entry.get("post_id"), int)
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"Expected exactly one wall_post_accepted_unverified operation; found={len(candidates)}")
    operation_id, entry = candidates[0]

    policy = build_photo_policy(repo)
    policy_operations = {str(item["operation_id"]): item for item in policy["operations"] if isinstance(item, dict)}
    operation = policy_operations.get(str(operation_id))
    if not isinstance(operation, dict):
        raise RuntimeError("Journal operation is not present in the active v5 policy")

    settings = get_settings()
    client = VkApiClient(
        token_store=VkTokenStore(settings.data_dir),
        account_alias=ACCOUNT_ALIAS,
        api_version=settings.vk_api_version,
        max_attempts=4,
    )
    published, postponed = wall_snapshot(client)
    post_id = int(entry["post_id"])
    matches: list[dict[str, Any]] = []
    for queue, posts in (("published", published), ("postponed", postponed)):
        for post in posts:
            if post.get("owner_id") == OWNER_ID and post.get("id") == post_id:
                matches.append(post_reference(post, queue))

    if len(matches) != 1:
        return {
            "status": "not_exactly_one_post",
            "operation_id": operation_id,
            "post_id": post_id,
            "matches": len(matches),
            "vk_write_methods": [],
        }

    reference = matches[0]
    expected_photo_identity = photo_identity_from_token(entry.get("photo_token"))
    article_url = normalize_url(operation["url"])
    message_matches = reference["message"] == canonical_text(operation["message"])
    date_matches = reference["date"] == operation["publish_date"]
    url_matches = article_url in reference["text_urls"]
    has_photo = bool(reference["has_photo"])
    photo_identity_matches = expected_photo_identity is not None and expected_photo_identity in reference["photo_identities"]

    return {
        "status": "inspected",
        "operation_id": operation_id,
        "post_id": post_id,
        "queue": reference["queue"],
        "vk_url": reference["url"],
        "expected_publish_date": operation["publish_date"],
        "actual_publish_date": reference["date"],
        "date_matches": date_matches,
        "message_matches": message_matches,
        "expected_message_sha256": text_sha256(operation["message"]),
        "actual_message_sha256": text_sha256(reference["message"]),
        "article_url": article_url,
        "article_url_in_text": url_matches,
        "has_photo": has_photo,
        "expected_photo_identity": expected_photo_identity,
        "actual_photo_identities": reference["photo_identities"],
        "photo_identity_matches": photo_identity_matches,
        "only_photo_identity_differs": (
            message_matches and date_matches and url_matches and has_photo and not photo_identity_matches
        ),
        "vk_write_methods": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(inspect(args.repo), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
