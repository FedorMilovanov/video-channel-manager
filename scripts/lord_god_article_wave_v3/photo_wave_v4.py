from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkApiError, VkTokenStore
from video_channel_manager.platforms.vk.lock import local_vk_write_lock

from .common import (
    ACCOUNT_ALIAS,
    COMMUNITY_ID,
    MOSCOW,
    OWNER_ID,
    canonical_sha,
    load_policy,
    now_iso,
    read_json,
    write_json,
)
from .mutations import prepare_photo_token, submit_wall_post
from .sources import materialize_and_verify_sources, validate_materialized_asset
from .wall import preflight, state_fingerprint, verify_upload_server, wall_snapshot
from .workflow import review_markdown

PHOTO_DECISION_SET_ID = "lord-god-article-photo-wave-v4-202608"
SCHEDULE_SHIFT_SECONDS = 24 * 60 * 60
PHOTO_JOURNAL_SCHEMA = "video-manager.vk-lord-god-article-photo-wave-journal"


def build_photo_policy(repo: Path) -> dict[str, Any]:
    base = load_policy(repo)
    policy = copy.deepcopy(base)
    base_policy_sha = str(base["policy_sha256"])
    source_contract_sha = str(base["source_contract_sha256"])

    policy["schema_name"] = "video-manager.vk-lord-god-article-photo-wave-policy"
    policy["schema_version"] = 4
    policy["decision_set_id"] = PHOTO_DECISION_SET_ID
    policy["attachment_mode"] = "explicit-wall-photo-plus-text-link"
    policy["asset_mode"] = "materialized-jpeg-1200x630"
    policy["base_policy_sha256"] = base_policy_sha

    for operation in policy["operations"]:
        ordinal = int(operation["ordinal"])
        slug = str(operation["id"])
        operation["source_operation_id"] = operation["operation_id"]
        operation["operation_id"] = (
            f"{PHOTO_DECISION_SET_ID}-{ordinal:02d}-{slug}"
        )
        operation["publish_date"] = int(operation["publish_date"]) + SCHEDULE_SHIFT_SECONDS
        operation["publish_at"] = datetime.fromtimestamp(
            int(operation["publish_date"]),
            tz=MOSCOW,
        ).isoformat()

    policy["summary"] = {
        **dict(policy.get("summary") or {}),
        "first_publish_at": policy["operations"][0]["publish_at"],
        "last_publish_at": policy["operations"][-1]["publish_at"],
    }
    identity = {
        "schema_version": 4,
        "decision_set_id": PHOTO_DECISION_SET_ID,
        "base_policy_sha256": base_policy_sha,
        "source_contract_sha256": source_contract_sha,
        "attachment_mode": policy["attachment_mode"],
        "asset_mode": policy["asset_mode"],
        "operations": [
            {
                "operation_id": item["operation_id"],
                "source_operation_id": item["source_operation_id"],
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
        "schema_name": PHOTO_JOURNAL_SCHEMA,
        "schema_version": 4,
        "decision_set_id": PHOTO_DECISION_SET_ID,
        "policy_sha256": policy["policy_sha256"],
        "execution_contract_sha256": policy["execution_contract_sha256"],
        "operations": {},
    }


def load_photo_journal(path: Path, policy: dict[str, Any]) -> dict[str, Any]:
    journal = read_json(path, fresh_photo_journal(policy))
    if not isinstance(journal, dict) or not isinstance(journal.get("operations"), dict):
        raise RuntimeError("Invalid photo-wave v4 journal")
    expected = fresh_photo_journal(policy)
    for key in (
        "schema_name",
        "schema_version",
        "decision_set_id",
        "policy_sha256",
        "execution_contract_sha256",
    ):
        if journal.get(key) != expected[key]:
            raise RuntimeError(
                "Photo-wave journal belongs to another execution contract; "
                "it will not be reused"
            )
    return journal


def execute_scope(
    *,
    mode: str,
    policy: dict[str, Any],
    read_client: VkApiClient,
    mutation_client: VkApiClient,
    settings: Any,
    report: dict[str, Any],
    journal: dict[str, Any],
    journal_path: Path,
    assets_manifest: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    if os.environ.get("VCM_ALLOW_WALL_POSTS") != "1":
        raise RuntimeError("Execution requires VCM_ALLOW_WALL_POSTS=1")

    states = {item["operation_id"]: item["state"] for item in report["states"]}
    canary = policy["operations"][0]
    canary_id = str(canary["operation_id"])
    if mode == "canary":
        selected = [canary]
        result_path = output_dir / "photo-v4-canary-result.json"
    elif mode == "apply":
        if states.get(canary_id) != "already_applied":
            raise RuntimeError("Apply requires the verified photo-wave v4 canary")
        selected = policy["operations"][1:]
        result_path = output_dir / "photo-v4-result.json"
    else:
        raise ValueError(f"Unsupported execution mode: {mode}")

    assets_by_id = {
        str(item["operation_id"]): item
        for item in assets_manifest["items"]
        if isinstance(item, dict)
    }
    result: dict[str, Any] = {
        "schema_name": "video-manager.vk-lord-god-article-photo-wave-result",
        "schema_version": 4,
        "mode": mode,
        "status": "running",
        "policy_sha256": policy["policy_sha256"],
        "asset_manifest_sha256": assets_manifest["manifest_sha256"],
        "started_at": now_iso(),
        "operations": [],
    }
    write_json(result_path, result)

    lock_path = settings.data_dir / "locks" / f"vk-wall-{COMMUNITY_ID}.lock"
    try:
        with local_vk_write_lock(
            lock_path,
            account=ACCOUNT_ALIAS,
            community_id=COMMUNITY_ID,
            operation=f"{PHOTO_DECISION_SET_ID}-{mode}",
        ):
            locked_published, locked_postponed = wall_snapshot(read_client)
            locked = preflight(policy, locked_published, locked_postponed, journal)
            if locked["conflicts"] or state_fingerprint(locked) != state_fingerprint(report):
                raise RuntimeError("Locked preflight differs from reviewed preflight")
            locked_states = {
                item["operation_id"]: item["state"] for item in locked["states"]
            }

            for operation in selected:
                operation_id = str(operation["operation_id"])
                if locked_states[operation_id] == "already_applied":
                    result["operations"].append(
                        {"operation_id": operation_id, "status": "already_applied"}
                    )
                    write_json(result_path, result)
                    continue
                if locked_states[operation_id] != "ready":
                    raise RuntimeError(f"Operation is not ready: {operation_id}")

                jpeg = validate_materialized_asset(operation, assets_by_id)
                photo_token = prepare_photo_token(
                    operation=operation,
                    jpeg=jpeg,
                    read_client=read_client,
                    mutation_client=mutation_client,
                    journal=journal,
                    journal_path=journal_path,
                )
                post_id, reference = submit_wall_post(
                    operation=operation,
                    photo_token_value=photo_token,
                    read_client=read_client,
                    mutation_client=mutation_client,
                    journal=journal,
                    journal_path=journal_path,
                )
                result["operations"].append(
                    {
                        "operation_id": operation_id,
                        "post_id": post_id,
                        "status": "verified",
                        "publish_at": operation["publish_at"],
                        "article_url_in_text": True,
                        "wall_photo_verified": bool(reference["has_photo"]),
                    }
                )
                write_json(result_path, result)
                print(
                    f"SCHEDULED {operation['ordinal']}/10 "
                    f"post={OWNER_ID}_{post_id} photo=yes url=yes"
                )
                time.sleep(1)

            final_published, final_postponed = wall_snapshot(read_client)
            final = preflight(
                policy,
                final_published,
                final_postponed,
                journal,
                minimum_future_seconds=0,
            )
            postflight_path = (
                output_dir / "photo-v4-canary-postflight.json"
                if mode == "canary"
                else output_dir / "photo-v4-postflight.json"
            )
            write_json(postflight_path, final)
            expected_applied = 1 if mode == "canary" else 10
            expected_ready = 9 if mode == "canary" else 0
            if (
                final["conflicts"]
                or final["already_applied"] != expected_applied
                or final["ready"] != expected_ready
            ):
                raise RuntimeError(
                    f"{mode.capitalize()} postflight is not exact: "
                    f"applied={final['already_applied']} ready={final['ready']} "
                    f"conflicts={final['conflicts']}"
                )

            result.update(
                {
                    "status": "completed",
                    "completed_at": now_iso(),
                    "verified_operations": expected_applied,
                    "verified_posts_with_wall_photos": expected_applied,
                    "verified_article_urls_in_text": expected_applied,
                    "conflicts": 0,
                    "first_publish_at": policy["summary"]["first_publish_at"],
                    "last_publish_at": (
                        canary["publish_at"]
                        if mode == "canary"
                        else policy["summary"]["last_publish_at"]
                    ),
                }
            )
            write_json(result_path, result)
    except Exception as exc:
        result.update(
            {
                "status": "blocked",
                "blocked_at": now_iso(),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        write_json(result_path, result)
        raise
    return result


def run(repo: Path, *, mode: str) -> int:
    repo = repo.resolve()
    output_dir = repo / "data" / "vk-wall" / PHOTO_DECISION_SET_ID
    assets_dir = output_dir / "assets"
    output_dir.mkdir(parents=True, exist_ok=True)

    policy = build_photo_policy(repo)
    write_json(output_dir / "photo-v4-plan.json", policy)

    source_rows, assets_manifest = materialize_and_verify_sources(
        policy,
        assets_dir=assets_dir,
    )
    write_json(output_dir / "photo-v4-source-audit.json", assets_manifest)
    write_json(output_dir / "photo-v4-asset-manifest.json", assets_manifest)
    if assets_manifest["status"] != "verified":
        raise RuntimeError("Photo source audit is blocked")

    settings = get_settings()
    token_store = VkTokenStore(settings.data_dir)
    read_client = VkApiClient(
        token_store=token_store,
        account_alias=ACCOUNT_ALIAS,
        api_version=settings.vk_api_version,
        max_attempts=4,
    )
    mutation_client = VkApiClient(
        token_store=token_store,
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

    upload_server_check = verify_upload_server(read_client)
    write_json(output_dir / "photo-v4-vk-photo-preflight.json", upload_server_check)

    journal_path = output_dir / "photo-journal-v4.json"
    journal = load_photo_journal(journal_path, policy)
    write_json(journal_path, journal)

    published, postponed = wall_snapshot(read_client)
    report = preflight(policy, published, postponed, journal)
    write_json(output_dir / "photo-v4-preflight.json", report)
    (output_dir / "photo-v4-plan-review.md").write_text(
        review_markdown(policy, report),
        encoding="utf-8",
    )

    summary = {
        "mode": mode,
        "decision_set_id": PHOTO_DECISION_SET_ID,
        "policy_sha256": policy["policy_sha256"],
        "external_urls_checked": assets_manifest["external_urls_checked"],
        "article_pages_verified": assets_manifest["article_pages_verified"],
        "source_images_verified": assets_manifest["source_images_verified"],
        "pinned_source_files_verified": assets_manifest[
            "pinned_source_files_verified"
        ],
        "pinned_metadata_files_verified": assets_manifest[
            "pinned_metadata_files_verified"
        ],
        "prepared_jpeg_assets": len(source_rows),
        "vk_wall_photo_upload_server_verified": upload_server_check["verified"],
        "operations": report["total_operations"],
        "ready": report["ready"],
        "already_applied": report["already_applied"],
        "conflicts": report["conflicts"],
        "first_publish_at": policy["summary"]["first_publish_at"],
        "last_publish_at": policy["summary"]["last_publish_at"],
        "journal": str(journal_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if report["conflicts"]:
        raise RuntimeError("Photo article queue is blocked: " + "; ".join(report["global_conflicts"]))

    if mode == "plan":
        print(
            "READ-ONLY PHOTO PLAN COMPLETE. "
            "Ten JPEG assets are prepared; no photo upload, photo save, or wall.post was sent."
        )
        return 0

    result = execute_scope(
        mode=mode,
        policy=policy,
        read_client=read_client,
        mutation_client=mutation_client,
        settings=settings,
        report=report,
        journal=journal,
        journal_path=journal_path,
        assets_manifest=assets_manifest,
        output_dir=output_dir,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "mode": mode,
                "verified_operations": result["verified_operations"],
                "result_path": str(
                    output_dir
                    / (
                        "photo-v4-canary-result.json"
                        if mode == "canary"
                        else "photo-v4-result.json"
                    )
                ),
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
    mode = "canary" if args.canary else "apply" if args.execute else "plan"
    return run(args.repo, mode=mode)


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
