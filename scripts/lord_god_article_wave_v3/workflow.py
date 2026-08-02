from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkApiError, VkTokenStore
from video_channel_manager.platforms.vk.lock import local_vk_write_lock

from .common import (
    ACCOUNT_ALIAS,
    COMMUNITY_ID,
    DECISION_SET_ID,
    OWNER_ID,
    load_policy,
    now_iso,
    validate_policy,
    write_json,
)
from .mutations import prepare_photo_token, submit_wall_post
from .sources import materialize_and_verify_sources, validate_materialized_asset
from .wall import (
    load_journal,
    preflight,
    state_fingerprint,
    verify_upload_server,
    wall_snapshot,
)


def review_markdown(policy: dict[str, Any], report: dict[str, Any]) -> str:
    states = {item["operation_id"]: item["state"] for item in report["states"]}
    lines = [
        "# Господь Бог — Сила Моя: 10 ежедневных статей",
        "",
        "- Время: ежедневно в 14:00 UTC+03:00.",
        "- Интервал до другого отложенного поста: не менее двух часов.",
        "- Изображение: отдельная проверенная фотография стены из OG-изображения.",
        "- Ссылка: точный публичный URL находится в тексте поста.",
        "- Порядок: Plan → Canary → ручная проверка → Apply.",
        "",
    ]
    for operation in policy["operations"]:
        lines.extend(
            [
                f"## {operation['ordinal']}. {operation['title']}",
                "",
                f"- Время: `{operation['publish_at']}`",
                f"- Статус: `{states[operation['operation_id']]}`",
                f"- Статья: {operation['url']}",
                f"- Изображение: {operation['image_url']}",
                f"- Источник: `{operation['source_path']}`",
                "",
                str(operation["message"]),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


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
        result_path = output_dir / "canary-result.json"
    elif mode == "apply":
        if states.get(canary_id) != "already_applied":
            raise RuntimeError("Apply requires the verified canary article post")
        selected = policy["operations"][1:]
        result_path = output_dir / "result.json"
    else:
        raise ValueError(f"Unsupported execution mode: {mode}")

    assets_by_id = {
        str(item["operation_id"]): item
        for item in assets_manifest["items"]
        if isinstance(item, dict)
    }
    result: dict[str, Any] = {
        "schema_name": "video-manager.vk-lord-god-article-wave-result",
        "schema_version": 3,
        "mode": mode,
        "status": "running",
        "policy_sha256": policy["policy_sha256"],
        "asset_manifest_sha256": assets_manifest["manifest_sha256"],
        "started_at": now_iso(),
        "operations": [],
    }
    write_json(result_path, result)

    lock_path = settings.data_dir / "locks" / f"vk-wall-{COMMUNITY_ID}.lock"
    with local_vk_write_lock(
        lock_path,
        account=ACCOUNT_ALIAS,
        community_id=COMMUNITY_ID,
        operation=f"{DECISION_SET_ID}-{mode}",
    ):
        locked_published, locked_postponed = wall_snapshot(read_client)
        locked = preflight(policy, locked_published, locked_postponed, journal)
        if locked["conflicts"] or state_fingerprint(locked) != state_fingerprint(report):
            raise RuntimeError("Locked preflight differs from reviewed preflight")
        locked_states = {item["operation_id"]: item["state"] for item in locked["states"]}

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
            photo = prepare_photo_token(
                operation=operation,
                jpeg=jpeg,
                read_client=read_client,
                mutation_client=mutation_client,
                journal=journal,
                journal_path=journal_path,
            )
            post_id, reference = submit_wall_post(
                operation=operation,
                photo_token_value=photo,
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
            output_dir / "canary-postflight.json"
            if mode == "canary"
            else output_dir / "postflight.json"
        )
        write_json(postflight_path, final)
        expected_applied = 1 if mode == "canary" else 10
        if final["conflicts"] or final["already_applied"] != expected_applied:
            raise RuntimeError(
                f"{mode.capitalize()} postflight verified "
                f"{final['already_applied']} of {expected_applied}"
            )
        if mode == "canary" and final["ready"] != 9:
            raise RuntimeError("Canary did not leave exactly nine ready posts")
        if mode == "apply" and final["ready"] != 0:
            raise RuntimeError("Apply left unscheduled article posts")

        verified_now = sum(
            1 for item in result["operations"] if item.get("status") == "verified"
        )
        result.update(
            {
                "status": "completed",
                "completed_at": now_iso(),
                "verified_operations": expected_applied,
                "verified_postponed": expected_applied,
                "verified_posts_with_wall_photos": expected_applied,
                "verified_operations_this_run": verified_now,
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
    return result


def run(repo: Path, *, mode: str) -> int:
    repo = repo.resolve()
    output_dir = repo / "data" / "vk-wall" / DECISION_SET_ID
    assets_dir = output_dir / "assets"
    output_dir.mkdir(parents=True, exist_ok=True)

    policy = load_policy(repo)
    validate_policy(policy)
    write_json(output_dir / "plan.json", policy)

    source_rows, assets_manifest = materialize_and_verify_sources(
        policy,
        assets_dir=assets_dir,
    )
    write_json(output_dir / "source-audit.json", assets_manifest)
    write_json(output_dir / "asset-manifest.json", assets_manifest)

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

    upload_server_check = verify_upload_server(read_client)
    write_json(output_dir / "vk-photo-preflight.json", upload_server_check)

    journal_path = output_dir / "journal.json"
    journal = load_journal(journal_path, policy)
    write_json(journal_path, journal)

    published, postponed = wall_snapshot(read_client)
    report = preflight(policy, published, postponed, journal)
    write_json(output_dir / "preflight.json", report)
    (output_dir / "plan-review.md").write_text(
        review_markdown(policy, report),
        encoding="utf-8",
    )

    summary = {
        "mode": mode,
        "policy_sha256": policy["policy_sha256"],
        "external_urls_checked": assets_manifest["external_urls_checked"],
        "source_pages_verified": assets_manifest["article_pages_verified"],
        "source_images_verified": assets_manifest["source_images_verified"],
        "pinned_source_files_verified": assets_manifest[
            "pinned_source_files_verified"
        ],
        "prepared_jpeg_assets": len(source_rows),
        "vk_wall_photo_upload_server_verified": upload_server_check["verified"],
        "operations": report["total_operations"],
        "ready": report["ready"],
        "already_applied": report["already_applied"],
        "conflicts": report["conflicts"],
        "postponed_wall_posts_seen": report["postponed_wall_posts"],
        "minimum_gap_minutes": report["minimum_gap_minutes"],
        "first_publish_at": policy["summary"]["first_publish_at"],
        "last_publish_at": policy["summary"]["last_publish_at"],
        "plan_review": str(output_dir / "plan-review.md"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if report["conflicts"]:
        raise RuntimeError("Article queue blocked: " + "; ".join(report["global_conflicts"]))

    if mode == "plan":
        print(
            "READ-ONLY ARTICLE PLAN COMPLETE. "
            "No photo upload, photo save, or wall post was sent."
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
                "verified_posts_with_wall_photos": result[
                    "verified_posts_with_wall_photos"
                ],
                "result_path": str(
                    output_dir
                    / ("canary-result.json" if mode == "canary" else "result.json")
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
