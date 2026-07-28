#!/usr/bin/env python3
"""Dry-run or execute the guarded August 2026 VK postponed-post wave."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.wall_content_audit import fetch_wall_posts
from video_channel_manager.platforms.vk.wall_wave import (
    build_wall_wave_preflight,
    comparable_preflight,
    sha256_bytes,
    validate_wall_wave_policy,
    verify_source_audit_bundle,
    verify_wall_wave_postflight,
    wall_post_id,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-audit-bundle", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--account", default="legendary-poet")
    parser.add_argument("--community", type=int, default=235216998)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--write-delay", type=float, default=1.0)
    parser.add_argument("--output-dir", type=Path)
    return parser


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _write_manifest(bundle_dir: Path, metadata: dict[str, Any]) -> None:
    files = []
    for path in sorted(bundle_dir.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != "manifest.json":
            files.append(
                {
                    "name": path.name,
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256_file(path),
                }
            )
    _atomic_json(bundle_dir / "manifest.json", {**metadata, "files": files})


def _package(bundle_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(bundle_dir.iterdir(), key=lambda item: item.name):
            if path.is_file():
                archive.write(path, arcname=path.name)


def _sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def _verify_required_urls(policy: dict[str, Any]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    required_urls = sorted(
        {
            str(operation["required_url"]).strip()
            for operation in policy["operations"]
            if str(operation.get("required_url") or "").strip()
        }
    )
    with httpx.Client(
        timeout=30.0, follow_redirects=True, headers={"User-Agent": "video-channel-manager/0.1"}
    ) as client:
        for url in required_urls:
            response = client.get(url)
            final_url = str(response.url)
            canonical_marker = f'<link rel="canonical" href="{url}"'
            body = response.text
            accepted = (
                response.status_code == 200
                and final_url.rstrip("/") == url.rstrip("/")
                and canonical_marker in body
                and "Выхожу один я на дорогу" in body
            )
            records.append(
                {
                    "url": url,
                    "status_code": response.status_code,
                    "final_url": final_url,
                    "canonical_found": canonical_marker in body,
                    "article_title_found": "Выхожу один я на дорогу" in body,
                    "status": "verified" if accepted else "blocked",
                }
            )
    blocked = [item for item in records if item["status"] != "verified"]
    result = {
        "schema_name": "video-manager.vk-wall-wave-url-verification",
        "schema_version": 1,
        "status": "verified" if not blocked else "blocked",
        "checked_at": datetime.now(UTC).isoformat(),
        "urls": records,
    }
    if blocked:
        raise ValueError(f"Required article URL is not deployed with its canonical article page: {blocked}")
    return result


def _wall_snapshot(client: VkApiClient, community_id: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return (
        fetch_wall_posts(client, community_id=community_id, filter_name="owner"),
        fetch_wall_posts(client, community_id=community_id, filter_name="postponed"),
    )


def _plan_markdown(policy: dict[str, Any], preflight: dict[str, Any]) -> str:
    state_by_id = {
        str(item["operation_id"]): str(item["state"]) for item in preflight["states"] if isinstance(item, dict)
    }
    lines = [
        "# VK wall wave — August 2026",
        "",
        f"- Decision set: `{policy['decision_set_id']}`",
        f"- Policy: `{policy['policy_sha256']}`",
        f"- Community: `{policy['community_id']}`",
        f"- Approved postponed posts: **{len(policy['operations'])}**",
        f"- Ready: **{preflight['ready']}**",
        f"- Already applied: **{preflight['already_applied']}**",
        f"- Conflicts: **{preflight['conflicts']}**",
        "",
        "| Moscow time | Video | State |",
        "|---|---|---|",
    ]
    for operation in policy["operations"]:
        lines.append(
            f"| {operation['publish_at']} | `{operation['video_id']}` · {operation['video_title']} | "
            f"`{state_by_id[operation['operation_id']]}` |"
        )
    return "\n".join(lines).rstrip() + "\n"


def _operation_states(preflight: dict[str, Any]) -> dict[str, str]:
    return {
        str(item["operation_id"]): str(item["state"]) for item in preflight.get("states", []) if isinstance(item, dict)
    }


def run(args: argparse.Namespace) -> Path:
    if args.community <= 0:
        raise ValueError("--community must be a positive VK community ID")
    if args.write_delay < 0:
        raise ValueError("--write-delay cannot be negative")

    policy = _load_json(args.policy)
    validate_wall_wave_policy(policy)
    if int(policy["community_id"]) != args.community:
        raise ValueError("--community differs from the VK wall wave policy")

    settings = get_settings()
    output_dir = args.output_dir or settings.data_dir / "handoffs"
    output_dir.mkdir(parents=True, exist_ok=True)
    mode = "apply" if args.execute else "dry-run"
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    bundle_name = f"vk-wall-wave-{mode}-{stamp}"
    bundle_dir = output_dir / bundle_name
    zip_path = output_dir / f"{bundle_name}.zip"
    bundle_dir.mkdir(parents=True, exist_ok=False)

    status = "started"
    error: str | None = None
    source_verification: dict[str, Any] | None = None
    url_verification: dict[str, Any] | None = None
    preflight: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None

    try:
        source_bundle = args.source_audit_bundle.resolve(strict=True)
        _, source_verification = verify_source_audit_bundle(source_bundle, policy)
        shutil.copy2(args.policy, bundle_dir / "00-wall-wave-policy.json")
        shutil.copy2(source_bundle, bundle_dir / "01-source-wall-audit.zip")
        _atomic_json(bundle_dir / "02-source-verification.json", source_verification)

        store = VkTokenStore(settings.data_dir)
        client = VkApiClient(token_store=store, account_alias=args.account, api_version=settings.vk_api_version)
        community = client.get_community(str(args.community))
        if int(community.ref.channel_id) != args.community or not bool(community.metadata.get("managed_by_token")):
            raise ValueError("The VK token does not manage the exact wall wave community")

        published_posts, postponed_posts = _wall_snapshot(client, args.community)
        _atomic_json(bundle_dir / "03-live-published-posts.json", published_posts)
        _atomic_json(bundle_dir / "04-live-postponed-posts.json", postponed_posts)
        preflight = build_wall_wave_preflight(
            policy,
            published_posts=published_posts,
            postponed_posts=postponed_posts,
        )
        _atomic_json(bundle_dir / "05-preflight.json", preflight)
        (bundle_dir / "06-plan-review.md").write_text(_plan_markdown(policy, preflight), encoding="utf-8")

        print(
            "VK WALL WAVE PREFLIGHT\n"
            f"  policy: {policy['policy_sha256']}\n"
            f"  total operations: {preflight['total_operations']}\n"
            f"  ready: {preflight['ready']}\n"
            f"  already applied: {preflight['already_applied']}\n"
            f"  conflicts: {preflight['conflicts']}"
        )
        if preflight["conflicts"]:
            raise ValueError(f"VK wall wave preflight conflicts: {preflight['global_conflicts']}")

        url_verification = _verify_required_urls(policy)
        _atomic_json(bundle_dir / "07-required-url-verification.json", url_verification)

        if not args.execute:
            result = {
                "schema_name": "video-manager.vk-wall-wave-result",
                "schema_version": 1,
                "status": "dry_run_completed",
                "mode": "dry-run",
                "community_id": args.community,
                "decision_set_id": policy["decision_set_id"],
                "policy_sha256": policy["policy_sha256"],
                "remote_writes": 0,
                "ready": preflight["ready"],
                "already_applied": preflight["already_applied"],
                "completed_at": datetime.now(UTC).isoformat(),
            }
            _atomic_json(bundle_dir / "08-result.json", result)
            status = "dry_run_completed"
        else:
            lock_path = settings.data_dir / "locks" / f"vk-{args.account}-{args.community}.lock"
            with local_vk_write_lock(
                lock_path,
                account=args.account,
                community_id=args.community,
                operation="apply-vk-wall-wave-202608",
            ):
                locked_published, locked_postponed = _wall_snapshot(client, args.community)
                locked_preflight = build_wall_wave_preflight(
                    policy,
                    published_posts=locked_published,
                    postponed_posts=locked_postponed,
                )
                if locked_preflight["conflicts"] or comparable_preflight(locked_preflight) != comparable_preflight(
                    preflight
                ):
                    raise RuntimeError("Locked VK wall wave re-preflight differs from the confirmed preflight")
                locked_url_verification = _verify_required_urls(policy)
                if locked_url_verification["status"] != "verified":
                    raise RuntimeError("Required article URL changed before the locked execution")

                states = _operation_states(locked_preflight)
                result = {
                    "schema_name": "video-manager.vk-wall-wave-result",
                    "schema_version": 1,
                    "status": "running",
                    "mode": "apply",
                    "community_id": args.community,
                    "decision_set_id": policy["decision_set_id"],
                    "policy_sha256": policy["policy_sha256"],
                    "started_at": datetime.now(UTC).isoformat(),
                    "operations": [],
                }
                _atomic_json(bundle_dir / "08-result.json", result)

                for operation in policy["operations"]:
                    operation_id = str(operation["operation_id"])
                    if states[operation_id] == "already_applied":
                        journal_item = {
                            "operation_id": operation_id,
                            "video_id": operation["video_id"],
                            "status": "already_applied",
                        }
                    else:
                        response = client._call(
                            "wall.post",
                            params={
                                "owner_id": -args.community,
                                "from_group": True,
                                "message": str(operation["message"]),
                                "attachments": str(operation["attachment"]),
                                "publish_date": int(operation["publish_date"]),
                            },
                        )
                        journal_item = {
                            "operation_id": operation_id,
                            "video_id": operation["video_id"],
                            "publish_date": operation["publish_date"],
                            "post_id": wall_post_id(response),
                            "status": "scheduled_pending_postflight",
                        }
                    result["operations"].append(journal_item)
                    _atomic_json(bundle_dir / "08-result.json", result)
                    _sleep(args.write_delay)

                final_published, final_postponed = _wall_snapshot(client, args.community)
                _atomic_json(bundle_dir / "09-final-published-posts.json", final_published)
                _atomic_json(bundle_dir / "10-final-postponed-posts.json", final_postponed)
                postflight = build_wall_wave_preflight(
                    policy,
                    published_posts=final_published,
                    postponed_posts=final_postponed,
                    minimum_future_seconds=0,
                )
                _atomic_json(bundle_dir / "11-postflight.json", postflight)
                verification = verify_wall_wave_postflight(policy, postflight)
                _atomic_json(bundle_dir / "12-independent-verification.json", verification)
                result["status"] = "completed"
                result["completed_at"] = datetime.now(UTC).isoformat()
                result["operation_statuses"] = dict(Counter(str(item["status"]) for item in result["operations"]))
                _atomic_json(bundle_dir / "08-result.json", result)
            status = "completed"

        (bundle_dir / "README.txt").write_text(
            "VK WALL WAVE — AUGUST 2026\n\n"
            f"Status: {status}\n"
            f"Mode: {mode}\n"
            f"Decision set: {policy['decision_set_id']}\n"
            f"Policy: {policy['policy_sha256']}\n"
            "Approved operations: 12 postponed posts.\n"
            "The 15 marker-only source records are excluded from this wave.\n",
            encoding="utf-8",
        )
    except Exception as exc:
        status = "failed"
        error = str(exc)
        _atomic_json(
            bundle_dir / "ERROR.json",
            {"status": status, "mode": mode, "error": error, "created_at": datetime.now(UTC).isoformat()},
        )
    finally:
        _write_manifest(
            bundle_dir,
            {
                "schema_name": "video-manager.vk-wall-wave-handoff",
                "schema_version": 1,
                "created_at": datetime.now(UTC).isoformat(),
                "status": status,
                "mode": mode,
                "decision_set_id": str(policy.get("decision_set_id") or ""),
                "community_id": args.community,
                "policy_sha256": policy.get("policy_sha256"),
                "source_verification_status": source_verification.get("status") if source_verification else None,
                "url_verification_status": url_verification.get("status") if url_verification else None,
                "ready": preflight.get("ready") if preflight else None,
                "already_applied": preflight.get("already_applied") if preflight else None,
                "conflicts": preflight.get("conflicts") if preflight else None,
                "verification_status": verification.get("status") if verification else None,
                "error": error,
            },
        )
        _package(bundle_dir, zip_path)
        shutil.rmtree(bundle_dir, ignore_errors=True)

    print(zip_path)
    if status == "failed":
        raise RuntimeError(error or "VK wall wave failed")
    return zip_path


def main() -> int:
    args = _parser().parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError, httpx.HTTPError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(2) from exc
