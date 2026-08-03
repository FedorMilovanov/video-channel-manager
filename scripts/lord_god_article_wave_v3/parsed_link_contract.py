from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .common import (
    DECISION_SET_ID,
    canonical_sha,
    load_policy,
    normalize_url,
    now_iso,
    read_json,
    write_json,
)

DELIVERY_CONTRACT_PATH = Path(
    "content/policies/lord-god-article-wave-v3-link-card-delivery-contract-v3.json"
)
EXPECTED_DELIVERY_CONTRACT_SHA = (
    "sha256:5b39a2a9f7edf2f970ad3fa561499f3fa3e0c6f0510893ad45cc07967490df37"
)
SUPERSEDED_V2_CONTRACT_SHA = (
    "sha256:23ed39ed344d3429140e9bafaaee4aabd8509d0701a916c608ef8d64e68daa96"
)
SUPERSEDED_FAILURE_MARKER = "link_photo_sizing_rule"
LINK_PARSE_METHOD = "wall.parseAttachedLink"
WRITE_METHOD = "wall.post"


def load_delivery_contract(repo: Path) -> dict[str, Any]:
    path = repo / DELIVERY_CONTRACT_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Parsed link-card delivery contract root must be an object")
    expected = {
        "schema_name": "video-manager.vk-lord-god-article-link-card-delivery-contract",
        "schema_version": 3,
        "decision_set_id": DECISION_SET_ID,
        "base_policy_sha256": (
            "sha256:f0175b4783e6eb8b449a4558bef662b53bd95b583deb71a01ce7edfd1202dcc7"
        ),
        "source_contract_sha256": (
            "sha256:659912a978d7b8442a9a8106783aa12eec81c2facdc1127f6cf21ead01dffac6"
        ),
        "attachment_mode": "parsed-external-link-card",
        "asset_mode": "remote-open-graph-only",
        "link_preparation_method": LINK_PARSE_METHOD,
        "write_method": WRITE_METHOD,
        "attachment_value": "exact-article-url",
        "link_title_source": "parsed-link-title",
        "link_photo_id_source": "parsed-link-photo-owner-id-and-id",
        "allowed_attachment_types": ["link"],
        "required_link_attachments": 1,
        "require_link_title_match": True,
        "require_link_description_match": True,
        "require_link_preview_photo": True,
        "separate_vk_photo": False,
        "vk_photo_api_calls": 0,
        "prepared_jpeg_assets": 0,
        "guid_mode": "contract-bound-sha256",
        "journal_schema_version": 3,
        "postflight_requires_exact_schedule": True,
        "postflight_requires_exact_text": True,
        "supersedes_delivery_contract_sha256": SUPERSEDED_V2_CONTRACT_SHA,
        "superseded_failure_code": 100,
        "superseded_failure_marker": SUPERSEDED_FAILURE_MARKER,
    }
    for key, value in expected.items():
        if raw.get(key) != value:
            raise ValueError(f"Parsed link-card delivery contract mismatch: {key}")
    actual = canonical_sha(
        {key: value for key, value in raw.items() if key != "contract_sha256"}
    )
    if raw.get("contract_sha256") != actual or actual != EXPECTED_DELIVERY_CONTRACT_SHA:
        raise ValueError("Parsed link-card delivery contract digest mismatch")
    return raw


def load_parsed_policy(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    base = load_policy(repo)
    contract = load_delivery_contract(repo)
    if contract["base_policy_sha256"] != base["policy_sha256"]:
        raise ValueError("Delivery contract does not bind the current base policy")
    if contract["source_contract_sha256"] != base["source_contract_sha256"]:
        raise ValueError("Delivery contract does not bind the current source contract")
    effective = copy.deepcopy(base)
    effective["attachment_mode"] = contract["attachment_mode"]
    effective["asset_mode"] = contract["asset_mode"]
    effective["delivery_contract_sha256"] = contract["contract_sha256"]
    return effective, contract


def execution_identity(
    policy: dict[str, Any],
    contract: dict[str, Any],
) -> str:
    return canonical_sha(
        {
            "base_execution_contract_sha256": policy["execution_contract_sha256"],
            "delivery_contract_sha256": contract["contract_sha256"],
            "link_preparation_method": contract["link_preparation_method"],
            "operations": [
                {
                    "operation_id": operation["operation_id"],
                    "message_sha256": operation["message_sha256"],
                    "article_url": normalize_url(operation["url"]),
                    "publish_date": operation["publish_date"],
                }
                for operation in policy["operations"]
            ],
        }
    )


def contract_guid(
    operation: dict[str, Any],
    policy: dict[str, Any],
    contract: dict[str, Any],
) -> str:
    digest = execution_identity(policy, contract).split(":", 1)[1]
    return f"lgaw3p-{int(operation['ordinal']):02d}-{digest[:23]}"


def fresh_journal(
    policy: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_name": "video-manager.vk-lord-god-article-parsed-link-journal",
        "schema_version": 3,
        "decision_set_id": DECISION_SET_ID,
        "policy_sha256": policy["policy_sha256"],
        "source_contract_sha256": policy["source_contract_sha256"],
        "delivery_contract_sha256": contract["contract_sha256"],
        "parsed_link_execution_contract_sha256": execution_identity(policy, contract),
        "operations": {},
    }


def load_journal(
    path: Path,
    policy: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    expected = fresh_journal(policy, contract)
    journal = read_json(path, expected)
    if not isinstance(journal, dict):
        raise RuntimeError("Invalid local parsed link-card journal")
    operations = journal.get("operations")
    if not isinstance(operations, dict):
        raise RuntimeError("Invalid parsed link-card journal operations map")
    identity_keys = (
        "schema_name",
        "schema_version",
        "decision_set_id",
        "policy_sha256",
        "source_contract_sha256",
        "delivery_contract_sha256",
        "parsed_link_execution_contract_sha256",
    )
    if any(journal.get(key) != expected[key] for key in identity_keys):
        stages = {
            str(value.get("stage") or "")
            for value in operations.values()
            if isinstance(value, dict)
        }
        if stages - {""}:
            raise RuntimeError(
                "Parsed link-card journal belongs to another execution contract "
                "and contains operation state"
            )
        return expected
    return journal


def set_stage(
    journal: dict[str, Any],
    journal_path: Path,
    operation: dict[str, Any],
    stage: str,
    **values: object,
) -> dict[str, Any]:
    operations = journal["operations"]
    operation_id = str(operation["operation_id"])
    entry = operations.get(operation_id)
    if not isinstance(entry, dict):
        entry = {
            "operation_id": operation_id,
            "article_url": normalize_url(operation["url"]),
            "publish_date": operation["publish_date"],
            "message_sha256": operation["message_sha256"],
        }
        operations[operation_id] = entry
    entry.update({"stage": stage, "updated_at": now_iso(), **values})
    journal["updated_at"] = now_iso()
    write_json(journal_path, journal)
    return entry


def observe_superseded_v2(
    path: Path,
    policy: dict[str, Any],
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_name": "video-manager.vk-lord-god-article-v2-rejection-observation",
        "schema_version": 1,
        "generated_at": now_iso(),
        "journal_path": str(path),
        "journal_present": path.is_file(),
        "superseded_delivery_contract_sha256": SUPERSEDED_V2_CONTRACT_SHA,
        "superseded_failure_code": 100,
        "superseded_failure_marker": SUPERSEDED_FAILURE_MARKER,
        "safe_to_supersede": True,
        "observed_operations": [],
    }
    if not path.is_file():
        return report
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError("Superseded v2 journal is not an object")
    operations = raw.get("operations")
    if not isinstance(operations, dict):
        raise RuntimeError("Superseded v2 journal has no operations map")

    first_operation_id = str(policy["operations"][0]["operation_id"])
    for operation_id, value in operations.items():
        if not isinstance(value, dict):
            raise RuntimeError("Superseded v2 journal contains an invalid entry")
        stage = str(value.get("stage") or "")
        post_id = value.get("post_id")
        error = str(value.get("error") or "")
        accepted = (
            operation_id == first_operation_id
            and stage == "wall_post_rejected"
            and post_id in (None, "")
            and "VK API 100" in error
            and SUPERSEDED_FAILURE_MARKER in error
        )
        report["observed_operations"].append(
            {
                "operation_id": operation_id,
                "stage": stage,
                "post_id": post_id,
                "error": error,
                "accepted_superseded_rejection": accepted,
            }
        )
        if not accepted:
            report["safe_to_supersede"] = False

    if len(operations) > 1:
        report["safe_to_supersede"] = False
    if not report["safe_to_supersede"]:
        raise RuntimeError(
            "Superseded v2 journal contains state that cannot be safely superseded"
        )
    return report
