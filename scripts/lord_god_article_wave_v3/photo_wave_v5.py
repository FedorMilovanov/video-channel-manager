from __future__ import annotations

from pathlib import Path
from typing import Any

from . import photo_wave_v4 as base
from .common import canonical_sha

PHOTO_DECISION_SET_ID = "lord-god-article-photo-wave-v5-202608"
PHOTO_SCHEMA_VERSION = 5

_original_build_photo_policy = base.build_photo_policy


def build_photo_policy(repo: Path) -> dict[str, Any]:
    policy = _original_build_photo_policy(repo)
    base_policy_sha = str(policy["base_policy_sha256"])
    source_contract_sha = str(policy["source_contract_sha256"])
    guid_seed = base_policy_sha.removeprefix("sha256:")[:16]

    policy["schema_version"] = PHOTO_SCHEMA_VERSION
    policy["decision_set_id"] = PHOTO_DECISION_SET_ID
    for operation in policy["operations"]:
        ordinal = int(operation["ordinal"])
        operation["guid"] = f"lgp5-{ordinal:02d}-{guid_seed}"

    identity = {
        "schema_version": PHOTO_SCHEMA_VERSION,
        "decision_set_id": PHOTO_DECISION_SET_ID,
        "base_policy_sha256": base_policy_sha,
        "source_contract_sha256": source_contract_sha,
        "attachment_mode": policy["attachment_mode"],
        "asset_mode": policy["asset_mode"],
        "operations": [
            {
                "operation_id": item["operation_id"],
                "source_operation_id": item["source_operation_id"],
                "guid": item["guid"],
                "article_url": item["url"],
                "image_url": item["image_url"],
                "message_sha256": item["message_sha256"],
                "publish_date": item["publish_date"],
            }
            for item in policy["operations"]
        ],
    }
    execution_sha = canonical_sha(identity)
    policy["policy_sha256"] = execution_sha
    policy["execution_contract_sha256"] = execution_sha
    return policy


def fresh_photo_journal(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": base.PHOTO_JOURNAL_SCHEMA,
        "schema_version": PHOTO_SCHEMA_VERSION,
        "decision_set_id": PHOTO_DECISION_SET_ID,
        "policy_sha256": policy["policy_sha256"],
        "execution_contract_sha256": policy["execution_contract_sha256"],
        "operations": {},
    }


# Reuse the already-tested photo executor while replacing every execution identity
# before its first runtime call. The abandoned v4 directory and journal are never read.
base.PHOTO_DECISION_SET_ID = PHOTO_DECISION_SET_ID
base.build_photo_policy = build_photo_policy
base.fresh_photo_journal = fresh_photo_journal

execute_scope = base.execute_scope
load_photo_journal = base.load_photo_journal
run = base.run
main = base.main
guarded_main = base.guarded_main
