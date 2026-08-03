from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import httpx

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkApiError, VkTokenStore

from . import link_cards_hardened as core
from .common import (
    ACCOUNT_ALIAS,
    COMMUNITY_ID,
    DECISION_SET_ID,
    canonical_sha,
    canonical_text,
    normalize_url,
    write_json,
)
from .wall import wall_snapshot

DESCRIPTION_MATCH_MODE = "exact-or-vk-prefix-min-40"


def audit_sources(
    policy: dict[str, Any],
    contract: dict[str, Any],
    *,
    client_factory: Callable[..., httpx.Client] = httpx.Client,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Reject an OG image that changes between the two read-only audit passes."""
    rows, manifest = core.audit_sources(
        policy,
        contract,
        client_factory=client_factory,
    )
    for row in rows:
        first_sha = str(row.get("image_sha256") or "")
        dimension_sha = str(row.get("dimension_check_sha256") or "")
        if not first_sha or not dimension_sha or first_sha == dimension_sha:
            continue
        conflicts = row.setdefault("conflicts", [])
        if isinstance(conflicts, list):
            conflicts.append(
                {
                    "code": "og_image_changed_between_audit_passes",
                    "detail": f"first={first_sha}; dimensions={dimension_sha}",
                }
            )
        checks = row.get("checks")
        if isinstance(checks, dict):
            checks["og_image_dimensions_verified"] = False
        row["status"] = "conflict"

    global_conflicts = manifest.get("global_conflicts")
    if not isinstance(global_conflicts, list):
        global_conflicts = []
    conflict_count = sum(
        len(row.get("conflicts", []))
        for row in rows
        if isinstance(row.get("conflicts"), list)
    ) + len(global_conflicts)
    manifest.update(
        {
            "status": "verified" if conflict_count == 0 else "blocked",
            "og_image_dimensions_verified": sum(
                bool(row.get("checks", {}).get("og_image_dimensions_verified"))
                for row in rows
                if isinstance(row.get("checks"), dict)
            ),
            "conflicts": conflict_count,
            "conflicting_operations": sum(
                row.get("status") == "conflict" for row in rows
            ),
            "global_conflicts": global_conflicts,
            "items": rows,
        }
    )
    manifest["manifest_sha256"] = canonical_sha(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )
    return rows, manifest


def strict_description_matches(actual: object, expected: object) -> bool:
    """Allow only equality or a VK-truncated prefix of the audited OG text."""
    actual_text = canonical_text(actual)
    expected_text = canonical_text(expected)
    if not actual_text or not expected_text:
        return False
    if actual_text == expected_text:
        return True
    return len(actual_text) >= 40 and expected_text.startswith(actual_text)


def strict_exact_reference(
    operation: dict[str, Any],
    reference: dict[str, Any],
    expected_metadata: dict[str, str],
) -> bool:
    article_url = normalize_url(operation["url"])
    if reference["owner_id"] != core.OWNER_ID:
        return False
    if reference["date"] != operation["publish_date"]:
        return False
    if reference["message"] != canonical_text(operation["message"]):
        return False
    if article_url not in reference["text_urls"]:
        return False
    if reference["attachment_types"] != ["link"]:
        return False
    cards = reference["link_cards"]
    if not isinstance(cards, list) or len(cards) != 1:
        return False
    card = cards[0]
    if not isinstance(card, dict) or card.get("url") != article_url:
        return False
    if canonical_text(card.get("title")) != canonical_text(expected_metadata["title"]):
        return False
    if not strict_description_matches(
        card.get("description"),
        expected_metadata["description"],
    ):
        return False
    if not bool(card.get("has_preview_photo")):
        return False
    if reference["has_photo"]:
        return False
    return True


def strict_preflight(
    policy: dict[str, Any],
    contract: dict[str, Any],
    expectations: dict[str, dict[str, str]],
    published: list[dict[str, Any]],
    postponed: list[dict[str, Any]],
    journal: dict[str, Any],
    *,
    minimum_future_seconds: int = core.MIN_FUTURE_SECONDS,
) -> dict[str, Any]:
    by_url, postponed_refs = core.index_wall_hardened(published, postponed)
    journal_ops = journal["operations"]
    current = int(datetime.now(UTC).timestamp())
    states: list[dict[str, Any]] = []
    conflicts: list[str] = []

    for operation in policy["operations"]:
        operation_id = str(operation["operation_id"])
        article_url = normalize_url(operation["url"])
        entry = journal_ops.get(operation_id)
        entry = entry if isinstance(entry, dict) else {}
        stage = str(entry.get("stage") or "")
        references = by_url.get(article_url, [])
        exact = [
            reference
            for reference in references
            if strict_exact_reference(
                operation,
                reference,
                expectations[operation_id],
            )
        ]
        nearby = [
            reference
            for reference in postponed_refs
            if reference not in exact
            and isinstance(reference.get("date"), int)
            and abs(int(reference["date"]) - int(operation["publish_date"]))
            < core.MIN_GAP_SECONDS
        ]

        if len(exact) == 1 and len(references) == 1 and not nearby:
            state = "already_applied"
            detail = (
                "one exact post with one-way OG description matching, reviewed "
                "title, preview image, exact schedule, and no extra attachments exists"
            )
        elif references:
            state = "conflict"
            detail = "article URL already appears in a non-exact wall post"
        elif nearby:
            state = "conflict"
            detail = "another postponed post is within the two-hour safety gap"
        elif stage in core.LINK_CARD_BLOCKING_STAGES:
            state = "conflict"
            detail = f"hardened link-card journal requires reconciliation: {stage}"
        elif stage == "verified":
            state = "conflict"
            detail = "journal says verified but no strict exact wall post was found"
        elif int(operation["publish_date"]) <= current + minimum_future_seconds:
            state = "conflict"
            detail = "approved publication time is no longer safely in the future"
        else:
            state = "ready"
            detail = "article is absent and the surrounding time window is free"

        if state == "conflict":
            conflicts.append(f"{operation_id}: {detail}")
        states.append(
            {
                "operation_id": operation_id,
                "ordinal": operation["ordinal"],
                "article_title": operation["title"],
                "article_url": article_url,
                "publish_at": operation["publish_at"],
                "state": state,
                "detail": detail,
                "journal_stage": stage or None,
                "references": references,
                "nearby_postponed_posts": nearby,
            }
        )

    counts = Counter(item["state"] for item in states)
    return {
        "schema_name": (
            "video-manager.vk-lord-god-article-link-card-hardened-preflight"
        ),
        "schema_version": 2,
        "generated_at": core.now_iso(),
        "policy_sha256": policy["policy_sha256"],
        "source_contract_sha256": policy["source_contract_sha256"],
        "delivery_contract_sha256": contract["contract_sha256"],
        "link_card_execution_contract_sha256": core.execution_identity(
            policy, contract
        ),
        "attachment_mode": contract["attachment_mode"],
        "allowed_attachment_types": contract["allowed_attachment_types"],
        "required_link_attachments": contract["required_link_attachments"],
        "description_match_mode": DESCRIPTION_MATCH_MODE,
        "published_wall_posts": len(published),
        "postponed_wall_posts": len(postponed),
        "minimum_gap_minutes": core.MIN_GAP_SECONDS // 60,
        "total_operations": len(states),
        "ready": counts["ready"],
        "already_applied": counts["already_applied"],
        "conflicts": counts["conflict"],
        "global_conflicts": conflicts,
        "states": states,
    }


def verify_strict_postflight(
    *,
    mode: str,
    policy: dict[str, Any],
    contract: dict[str, Any],
    expectations: dict[str, dict[str, str]],
    read_client: VkApiClient,
    journal: dict[str, Any],
    output_dir: Path,
    result: dict[str, Any],
) -> dict[str, Any]:
    postflight_path = (
        output_dir / "link-card-canary-strict-postflight.json"
        if mode == "canary"
        else output_dir / "link-card-strict-postflight.json"
    )
    result_path = output_dir / (
        "link-card-canary-result.json"
        if mode == "canary"
        else "link-card-result.json"
    )
    try:
        published, postponed = wall_snapshot(read_client)
        final = strict_preflight(
            policy,
            contract,
            expectations,
            published,
            postponed,
            journal,
            minimum_future_seconds=0,
        )
        write_json(postflight_path, final)
    except Exception as exc:
        result.update(
            {
                "status": "strict_postflight_unknown",
                "description_match_mode": DESCRIPTION_MATCH_MODE,
                "strict_postflight": str(postflight_path),
                "strict_postflight_error": f"{type(exc).__name__}: {exc}",
            }
        )
        write_json(result_path, result)
        raise RuntimeError(
            f"{mode.capitalize()} strict link-card postflight outcome is unknown"
        ) from exc

    expected_applied = 1 if mode == "canary" else 10
    expected_ready = 9 if mode == "canary" else 0
    accepted = (
        final["conflicts"] == 0
        and final["already_applied"] == expected_applied
        and final["ready"] == expected_ready
    )
    if not accepted:
        result.update(
            {
                "status": "strict_postflight_failed",
                "description_match_mode": DESCRIPTION_MATCH_MODE,
                "strict_postflight": str(postflight_path),
                "strict_postflight_conflicts": final["conflicts"],
                "strict_postflight_already_applied": final["already_applied"],
                "strict_postflight_ready": final["ready"],
            }
        )
        write_json(result_path, result)
        raise RuntimeError(
            f"{mode.capitalize()} strict link-card postflight rejected the result"
        )

    result.update(
        {
            "description_match_mode": DESCRIPTION_MATCH_MODE,
            "strict_postflight_verified": True,
            "strict_postflight": str(postflight_path),
        }
    )
    write_json(result_path, result)
    return result


def run(repo: Path, *, mode: str) -> int:
    repo = repo.resolve()
    output_dir = repo / "data" / "vk-wall" / DECISION_SET_ID
    output_dir.mkdir(parents=True, exist_ok=True)

    policy, contract = core.load_hardened_policy(repo)
    write_json(output_dir / "link-card-plan.json", policy)
    write_json(output_dir / "link-card-delivery-contract.json", contract)

    source_rows, source_manifest = audit_sources(policy, contract)
    source_audit_path = output_dir / "link-card-source-audit.json"
    write_json(source_audit_path, source_manifest)
    expectations = core.build_link_expectations(source_rows)
    expected_source_summary = {
        "schema_version": 2,
        "status": "verified",
        "expected_external_resources": 40,
        "external_urls_checked": 40,
        "article_pages_verified": 10,
        "live_content_markers_verified": 10,
        "og_images_verified": 10,
        "og_image_dimensions_verified": 10,
        "pinned_source_files_verified": 10,
        "pinned_metadata_files_verified": 10,
        "live_metadata_matches_pinned_source": 10,
        "prepared_jpeg_assets": 0,
        "vk_photo_uploads_required": False,
        "conflicts": 0,
    }
    source_gate_errors = [
        f"{key}={source_manifest.get(key)!r}, expected {value!r}"
        for key, value in expected_source_summary.items()
        if source_manifest.get(key) != value
    ]
    if source_gate_errors:
        print(json.dumps(source_manifest, ensure_ascii=False, indent=2))
        raise RuntimeError(
            "Hardened link-card source audit blocked the queue: "
            + "; ".join(source_gate_errors)
            + f"; all findings are in {source_audit_path}"
        )

    settings = get_settings()
    read_client = VkApiClient(
        token_store=VkTokenStore(settings.data_dir),
        account_alias=ACCOUNT_ALIAS,
        api_version=settings.vk_api_version,
        max_attempts=4,
    )
    mutation_client = VkApiClient(
        token_store=VkTokenStore(settings.data_dir),
        account_alias=ACCOUNT_ALIAS,
        api_version=settings.vk_api_version,
        max_attempts=1,
    )
    community = read_client.get_community(COMMUNITY_ID)
    if (
        community.ref.remote_id != str(COMMUNITY_ID)
        or not community.metadata.get("managed_by_token")
    ):
        raise RuntimeError("Stored token does not manage VK community 60805374")

    legacy_observation = core.legacy.observe_legacy_photo_journal(
        output_dir / "journal.json"
    )
    write_json(
        output_dir / "legacy-photo-journal-observation.json",
        legacy_observation,
    )

    journal_path = output_dir / "link-card-journal-v2.json"
    journal = core.load_journal(journal_path, policy, contract)
    write_json(journal_path, journal)

    published, postponed = wall_snapshot(read_client)
    report = strict_preflight(
        policy,
        contract,
        expectations,
        published,
        postponed,
        journal,
    )
    preflight_path = output_dir / "link-card-preflight.json"
    write_json(preflight_path, report)
    review_path = output_dir / "link-card-plan-review.md"
    review_path.write_text(
        core.review_markdown(policy, contract, report, expectations),
        encoding="utf-8",
    )

    summary = {
        "mode": mode,
        "policy_sha256": policy["policy_sha256"],
        "source_contract_sha256": policy["source_contract_sha256"],
        "delivery_contract_sha256": contract["contract_sha256"],
        "link_card_execution_contract_sha256": core.execution_identity(
            policy, contract
        ),
        "attachment_mode": contract["attachment_mode"],
        "asset_mode": contract["asset_mode"],
        "description_match_mode": DESCRIPTION_MATCH_MODE,
        **{key: source_manifest[key] for key in expected_source_summary},
        "vk_photo_api_calls": 0,
        "legacy_photo_state_observed": legacy_observation[
            "remote_photo_may_exist"
        ],
        "operations": report["total_operations"],
        "ready": report["ready"],
        "already_applied": report["already_applied"],
        "conflicts": report["conflicts"],
        "postponed_wall_posts_seen": report["postponed_wall_posts"],
        "minimum_gap_minutes": report["minimum_gap_minutes"],
        "first_publish_at": policy["summary"]["first_publish_at"],
        "last_publish_at": policy["summary"]["last_publish_at"],
        "preflight": str(preflight_path),
        "source_audit": str(source_audit_path),
        "plan_review": str(review_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if report["conflicts"]:
        raise RuntimeError(
            "Hardened link-card article queue blocked: "
            + "; ".join(report["global_conflicts"])
        )

    if mode == "plan":
        print(
            "READ-ONLY HARDENED LINK-CARD PLAN COMPLETE. "
            "No photo upload, photo save, or wall post was sent."
        )
        return 0

    result = core.execute_scope(
        mode=mode,
        policy=policy,
        contract=contract,
        expectations=expectations,
        read_client=read_client,
        mutation_client=mutation_client,
        settings=settings,
        report=report,
        journal=journal,
        journal_path=journal_path,
        output_dir=output_dir,
    )
    result = verify_strict_postflight(
        mode=mode,
        policy=policy,
        contract=contract,
        expectations=expectations,
        read_client=read_client,
        journal=journal,
        output_dir=output_dir,
        result=result,
    )
    result_path = output_dir / (
        "link-card-canary-result.json"
        if mode == "canary"
        else "link-card-result.json"
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "mode": mode,
                "verified_operations": result["verified_operations"],
                "verified_hardened_link_cards": result[
                    "verified_hardened_link_cards"
                ],
                "verified_single_link_attachments": result[
                    "verified_single_link_attachments"
                ],
                "verified_link_titles": result["verified_link_titles"],
                "verified_link_descriptions": result[
                    "verified_link_descriptions"
                ],
                "verified_link_preview_photos": result[
                    "verified_link_preview_photos"
                ],
                "verified_posts_without_separate_photos": result[
                    "verified_posts_without_separate_photos"
                ],
                "description_match_mode": result["description_match_mode"],
                "strict_postflight_verified": result[
                    "strict_postflight_verified"
                ],
                "result_path": str(result_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--canary", action="store_true")
    modes.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    selected_mode = "canary" if args.canary else "apply" if args.execute else "plan"
    return run(args.repo, mode=selected_mode)


def guarded_main() -> None:
    try:
        raise SystemExit(main())
    except (
        httpx.HTTPError,
        json.JSONDecodeError,
        OSError,
        RuntimeError,
        ValueError,
        VkApiError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
