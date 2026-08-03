#!/usr/bin/env python3
"""Read-only audit of the interrupted v5 VK photo wave before resuming it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore

from lord_god_article_wave_v3 import photo_wave_v5 as v5
from lord_god_article_wave_v3 import photo_wave_v5_compat as photo_wave_v5_compat  # noqa: F401
from lord_god_article_wave_v3 import photo_wave_v5_upload_retry as upload_retry
from lord_god_article_wave_v3.common import (
    ACCOUNT_ALIAS,
    BLOCKING_JOURNAL_STAGES,
    write_json,
)
from lord_god_article_wave_v3.wall import wall_snapshot


def _journal_entry(journal: dict[str, Any], operation_id: str) -> dict[str, Any]:
    operations = journal.get("operations")
    if not isinstance(operations, dict):
        return {}
    value = operations.get(operation_id)
    return value if isinstance(value, dict) else {}


def audit(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    output_dir = repo / "data" / "vk-wall" / v5.PHOTO_DECISION_SET_ID
    journal_path = output_dir / "photo-journal-v4.json"
    policy = v5.build_photo_policy(repo)
    journal = v5.load_photo_journal(journal_path, policy)
    policy_operations = policy["operations"]

    upload_retry.install()
    if v5.base.prepare_photo_token is not upload_retry.prepare_photo_token:
        raise RuntimeError("Safe v5 upload retry hook is not active")

    verified_post_ids: list[int] = []
    for operation in policy_operations[:7]:
        operation_id = str(operation["operation_id"])
        entry = _journal_entry(journal, operation_id)
        post_id = entry.get("post_id")
        if entry.get("stage") != "verified" or not isinstance(post_id, int):
            raise RuntimeError(f"Expected verified live operation: {operation_id}")
        posted_identity = str(entry.get("posted_photo_identity") or "")
        if not posted_identity.startswith("photo-60805374_"):
            raise RuntimeError(f"Verified operation lacks group-owned photo: {operation_id}")
        verified_post_ids.append(post_id)

    interrupted = policy_operations[7]
    interrupted_id = str(interrupted["operation_id"])
    interrupted_entry = _journal_entry(journal, interrupted_id)
    if interrupted_entry.get("stage") != "photo_upload_failed":
        raise RuntimeError("Operation 8 is not at the expected safe upload failure stage")
    if (
        interrupted_entry.get("post_id") not in (None, "")
        or interrupted_entry.get("photo_token")
        or isinstance(interrupted_entry.get("upload_payload"), dict)
    ):
        raise RuntimeError("Operation 8 contains evidence of a persistent VK mutation")

    for operation in policy_operations[8:]:
        operation_id = str(operation["operation_id"])
        entry = _journal_entry(journal, operation_id)
        if entry:
            raise RuntimeError(f"Expected untouched operation: {operation_id}")

    journal_operations = journal.get("operations")
    entries = journal_operations.values() if isinstance(journal_operations, dict) else []
    blocking = [
        str(entry.get("operation_id") or "")
        for entry in entries
        if isinstance(entry, dict) and entry.get("stage") in BLOCKING_JOURNAL_STAGES
    ]
    if blocking:
        raise RuntimeError("Blocking journal stages exist: " + ", ".join(blocking))

    settings = get_settings()
    read_client = VkApiClient(
        token_store=VkTokenStore(settings.data_dir),
        account_alias=ACCOUNT_ALIAS,
        api_version=settings.vk_api_version,
        max_attempts=4,
    )
    published, postponed = wall_snapshot(read_client)
    report = v5.preflight(
        policy,
        published,
        postponed,
        journal,
        minimum_future_seconds=0,
    )
    if (
        report["already_applied"] != 7
        or report["ready"] != 3
        or report["conflicts"] != 0
    ):
        raise RuntimeError(
            "Live resume state is not exact: "
            f"applied={report['already_applied']} ready={report['ready']} "
            f"conflicts={report['conflicts']}"
        )

    result = {
        "status": "ready_to_resume",
        "decision_set_id": v5.PHOTO_DECISION_SET_ID,
        "policy_sha256": policy["policy_sha256"],
        "verified_post_ids": verified_post_ids,
        "interrupted_operation_id": interrupted_id,
        "interrupted_stage": interrupted_entry["stage"],
        "already_applied": report["already_applied"],
        "ready": report["ready"],
        "conflicts": report["conflicts"],
        "safe_upload_max_attempts": upload_retry.SAFE_UPLOAD_MAX_ATTEMPTS,
        "safe_retry_scope": "fresh upload URL and temporary JPEG upload only",
        "photos_save_wall_photo_max_attempts": 1,
        "wall_post_max_attempts": 1,
        "vk_write_methods": [],
    }
    write_json(output_dir / "photo-v5-resume-audit.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(audit(args.repo), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
