#!/usr/bin/env python3
"""Recover the already-saved first VK wall photo without another save call."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore

from lord_god_article_wave_v3.common import (
    ACCOUNT_ALIAS,
    COMMUNITY_ID,
    JPEG_HEIGHT,
    JPEG_WIDTH,
)
from lord_god_article_wave_v3.mutations import (
    set_journal_stage,
    unexpected_saved_photo_owner,
)
from lord_god_article_wave_v3.photo_wave_v4 import (
    PHOTO_DECISION_SET_ID,
    build_photo_policy,
    load_photo_journal,
)
from lord_god_article_wave_v3.wall import photo_token

_RECOVERY_WINDOW_SECONDS = 10 * 60


def _photo_has_expected_dimensions(photo: dict[str, Any]) -> bool:
    if photo.get("width") == JPEG_WIDTH and photo.get("height") == JPEG_HEIGHT:
        return True
    orig = photo.get("orig_photo")
    if isinstance(orig, dict) and orig.get("width") == JPEG_WIDTH and orig.get("height") == JPEG_HEIGHT:
        return True
    sizes = photo.get("sizes")
    if not isinstance(sizes, list):
        return False
    return any(
        isinstance(item, dict) and item.get("width") == JPEG_WIDTH and item.get("height") == JPEG_HEIGHT
        for item in sizes
    )


def recover_saved_photo_token_from_all(
    read_client: VkApiClient,
    entry: dict[str, Any],
    *,
    current_user_id: int,
) -> str:
    owner_id = unexpected_saved_photo_owner(entry)
    if owner_id != current_user_id:
        raise RuntimeError("Unexpected-owner photo recovery is allowed only for the current token user")
    try:
        reference_time = datetime.fromisoformat(str(entry["updated_at"])).timestamp()
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("Photo recovery journal has no valid updated_at") from exc

    response = read_client._call(
        "photos.getAll",
        params={
            "owner_id": current_user_id,
            "extended": False,
            "offset": 0,
            "count": 200,
            "photo_sizes": True,
            "no_service_albums": False,
            "need_hidden": True,
            "skip_hidden": False,
        },
    )
    items = response.get("items") if isinstance(response, dict) else None
    photos = [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []

    same_owner = 0
    with_valid_id_and_date = 0
    within_window = 0
    expected_dimensions = 0
    candidates: list[dict[str, Any]] = []

    for photo in photos:
        if photo.get("owner_id") != current_user_id:
            continue
        same_owner += 1

        photo_id = photo.get("id")
        photo_date = photo.get("date")
        if not isinstance(photo_id, int) or photo_id <= 0 or not isinstance(photo_date, int):
            continue
        with_valid_id_and_date += 1

        if abs(float(photo_date) - reference_time) > _RECOVERY_WINDOW_SECONDS:
            continue
        within_window += 1

        if not _photo_has_expected_dimensions(photo):
            continue
        expected_dimensions += 1
        candidates.append(photo)

    if len(candidates) != 1:
        raise RuntimeError(
            "Saved-photo recovery did not find exactly one recent 1200x630 photo "
            "through photos.getAll; "
            f"candidates={len(candidates)}; photos_seen={len(photos)}; "
            f"same_owner={same_owner}; valid_id_and_date={with_valid_id_and_date}; "
            f"within_window={within_window}; expected_dimensions={expected_dimensions}"
        )

    token = photo_token(candidates[0])
    if not token:
        raise RuntimeError("Recovered wall photo has no usable attachment token")
    return token


def run(repo: Path) -> int:
    repo = repo.resolve()
    os.environ["VCM_DATA_DIR"] = str(repo / "data")

    policy = build_photo_policy(repo)
    output_dir = repo / "data" / "vk-wall" / PHOTO_DECISION_SET_ID
    journal_path = output_dir / "photo-journal-v4.json"
    journal = load_photo_journal(journal_path, policy)

    operations = journal["operations"]
    recoverable = [
        (operation_id, entry)
        for operation_id, entry in operations.items()
        if unexpected_saved_photo_owner(entry) is not None
    ]
    if len(recoverable) != 1:
        raise RuntimeError(f"Expected exactly one recoverable photo_save_unknown operation; found {len(recoverable)}")

    operation_id, entry = recoverable[0]
    operation_by_id: dict[str, dict[str, Any]] = {str(item["operation_id"]): item for item in policy["operations"]}
    operation = operation_by_id.get(str(operation_id))
    if operation is None:
        raise RuntimeError("Recoverable journal operation is absent from photo policy")

    settings = get_settings()
    token_store = VkTokenStore(settings.data_dir)
    read_client = VkApiClient(
        token_store=token_store,
        account_alias=ACCOUNT_ALIAS,
        api_version=settings.vk_api_version,
        max_attempts=4,
    )
    current_user = read_client.get_current_user()
    community = read_client.get_community(COMMUNITY_ID)
    if community.ref.remote_id != str(COMMUNITY_ID) or not community.metadata.get("managed_by_token"):
        raise RuntimeError("Stored token does not manage VK community 60805374")

    token = recover_saved_photo_token_from_all(
        read_client,
        entry,
        current_user_id=current_user.user_id,
    )
    set_journal_stage(
        journal,
        journal_path,
        operation,
        "photo_saved",
        photo_token=token,
        recovered_from="photo_save_unknown",
        recovered_owner_id=current_user.user_id,
        recovered_via="photos.getAll",
    )

    print(
        json.dumps(
            {
                "status": "recovered",
                "operation_id": operation_id,
                "stage": "photo_saved",
                "photo_owner_id": current_user.user_id,
                "photo_token_present": True,
                "recovered_via": "photos.getAll",
                "vk_read_methods": ["users.get", "groups.get", "photos.getAll"],
                "vk_write_methods": [],
                "journal": str(journal_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    return run(args.repo)


if __name__ == "__main__":
    raise SystemExit(main())
