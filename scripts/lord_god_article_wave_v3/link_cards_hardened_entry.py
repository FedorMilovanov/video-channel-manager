from __future__ import annotations

import argparse
import json
import sys
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
    write_json,
)
from .wall import wall_snapshot


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
    report = core.preflight(
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
