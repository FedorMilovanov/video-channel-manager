#!/usr/bin/env python3
"""Recover the already-saved first VK wall photo without another save call."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore

from lord_god_article_wave_v3.common import ACCOUNT_ALIAS, COMMUNITY_ID
from lord_god_article_wave_v3.mutations import (
    recover_saved_photo_token,
    set_journal_stage,
    unexpected_saved_photo_owner,
)
from lord_god_article_wave_v3.photo_wave_v4 import (
    PHOTO_DECISION_SET_ID,
    build_photo_policy,
    load_photo_journal,
)


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
        raise RuntimeError(
            "Expected exactly one recoverable photo_save_unknown operation; "
            f"found {len(recoverable)}"
        )

    operation_id, entry = recoverable[0]
    operation_by_id: dict[str, dict[str, Any]] = {
        str(item["operation_id"]): item for item in policy["operations"]
    }
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
    if (
        community.ref.remote_id != str(COMMUNITY_ID)
        or not community.metadata.get("managed_by_token")
    ):
        raise RuntimeError("Stored token does not manage VK community 60805374")

    token = recover_saved_photo_token(
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
    )

    print(
        json.dumps(
            {
                "status": "recovered",
                "operation_id": operation_id,
                "stage": "photo_saved",
                "photo_owner_id": current_user.user_id,
                "photo_token_present": True,
                "vk_read_methods": ["users.get", "groups.get", "photos.get"],
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
