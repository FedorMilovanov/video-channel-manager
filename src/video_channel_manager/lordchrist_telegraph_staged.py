"""Fail-closed, durable-intent stages for the Lordchrist Telegraph release.

The GitHub workflow MUST push and verify the state branch between stages.
A provider timeout leaves a claimed intent that no subsequent run can replay.
This module never creates Telegraph accounts or retries public mutations.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.lordchrist_telegraph_publisher import (
    DEFAULT_BINDING_PATH,
    DEFAULT_LEDGER_PATH,
    DEFAULT_PROFILE_PATH,
    DEFAULT_QUEUE_PATH,
    HttpxLiveTransport,
    _find_item,
    build_telegraph_payload,
    ensure_telegraph_token,
    load_telegraph_queue,
    publish_channel_message,
    publish_telegraph_page,
    render_channel_post,
    save_ledger,
)
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_target_binding import load_target_binding

STATES = frozenset({"page_dispatch_claimed", "page_published", "telegram_dispatch_claimed", "published"})


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _require_execution_context(args: argparse.Namespace) -> None:
    """Disallow a rerun or a different GitHub workflow from replaying a claim."""
    env = os.environ
    if (
        env.get("GITHUB_REPOSITORY") != "FedorMilovanov/video-channel-manager"
        or env.get("GITHUB_REF") != "refs/heads/main"
        or env.get("GITHUB_RUN_ID") != args.run_id
        or env.get("GITHUB_SHA") != args.github_sha
        or env.get("GITHUB_RUN_ATTEMPT") != "1"
        or args.run_attempt != 1
        or not re.fullmatch(r"[0-9]+", args.run_id)
        or not re.fullmatch(r"[0-9a-f]{40}", args.github_sha)
    ):
        raise RuntimeError("Exact first-attempt current-main GitHub execution identity required")


def _release(args: argparse.Namespace) -> tuple[Any, Any]:
    root = args.repo_root.resolve()
    items = load_telegraph_queue(root / args.queue, root)
    item = _find_item(items, args.publication_id)
    if not item.is_ready or item.is_canary:
        raise RuntimeError("Exact ready non-canary Telegraph article required")
    payload = build_telegraph_payload(root, item, media_base_url=args.media_base_url)
    return item, payload


def _ledger(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    path = args.ledger if args.ledger.is_absolute() else args.repo_root / args.ledger
    if not path.is_file():
        raise RuntimeError("Durable state ledger must exist; refuse an implicit new ledger")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or data.get("schema_name") != "video-channel-manager.lordchrist-telegraph-ledger"
        or data.get("schema_version") != 1
        or data.get("project_key") != "lord-god-strength"
        or not isinstance(data.get("entries"), dict)
        or any(not isinstance(key, str) or not isinstance(value, dict) for key, value in data["entries"].items())
    ):
        raise RuntimeError("Durable Telegraph ledger schema, project or entry integrity mismatch")
    return path, data


def _checked_entry(args: argparse.Namespace, ledger: dict[str, Any], expected: str) -> dict[str, Any]:
    entry = ledger["entries"].get(args.publication_id)
    if not isinstance(entry, dict) or entry.get("state") != expected:
        raise RuntimeError(f"Expected exact durable state {expected}; no replay or skipped stage")
    if (
        entry.get("github_sha") != args.github_sha
        or entry.get("run_id") != args.run_id
        or entry.get("run_attempt") != 1
        or entry.get("publication_id") != args.publication_id
    ):
        raise RuntimeError("Durable intent belongs to another execution; no replay")
    return entry


def _verified_payload(entry: dict[str, Any], payload: Any) -> None:
    if entry.get("article_sha256") != payload.article_sha256 or entry.get("cover_sha256") != payload.cover_sha256:
        raise RuntimeError("Article or cover changed after durable intent; refuse public mutation")


def execute(args: argparse.Namespace) -> dict[str, Any]:
    _require_execution_context(args)
    path, ledger = _ledger(args)
    item, payload = _release(args)

    if args.stage == "prepare-page":
        if args.publication_id in ledger["entries"]:
            raise RuntimeError("Publication identity already exists in durable state; no reinitialization")
        entry = {
            "publication_id": args.publication_id,
            "state": "page_dispatch_claimed",
            "provider_effect": "unknown_until_reconciled",
            "run_id": args.run_id,
            "run_attempt": args.run_attempt,
            "github_sha": args.github_sha,
            "title": payload.title,
            "article_sha256": payload.article_sha256,
            "cover_sha256": payload.cover_sha256,
            "page_intent_at_utc": _now(),
        }
        ledger["entries"][args.publication_id] = entry
        save_ledger(path, ledger)
        return {"stage": args.stage, "publication_id": args.publication_id, "state": entry["state"]}

    if args.stage == "send-page":
        entry = _checked_entry(args, ledger, "page_dispatch_claimed")
        _verified_payload(entry, payload)
        token = os.environ.get("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "").strip()
        if not token:
            raise RuntimeError("Persistent Telegraph account token required; do not create a disposable account")
        transport = HttpxLiveTransport()
        ensure_telegraph_token(transport, explicit_token=token)
        url, page_path = publish_telegraph_page(transport, payload, access_token=token, allow_split=False)
        entry.update(
            state="page_published",
            provider_effect="verified",
            telegraph_url=url,
            telegraph_path=page_path,
            telegraph_updated_at_utc=_now(),
        )
        save_ledger(path, ledger)
        return {"stage": args.stage, "publication_id": args.publication_id, "telegraph_url": url}

    if args.stage == "prepare-telegram":
        entry = _checked_entry(args, ledger, "page_published")
        _verified_payload(entry, payload)
        if not entry.get("telegraph_url") or not entry.get("telegraph_path"):
            raise RuntimeError("Verified persisted Telegraph receipt required before Telegram")
        entry.update(
            state="telegram_dispatch_claimed",
            telegram_provider_effect="unknown_until_reconciled",
            telegram_intent_at_utc=_now(),
        )
        save_ledger(path, ledger)
        return {"stage": args.stage, "publication_id": args.publication_id, "state": entry["state"]}

    if args.stage == "send-telegram":
        entry = _checked_entry(args, ledger, "telegram_dispatch_claimed")
        _verified_payload(entry, payload)
        url = str(entry.get("telegraph_url") or "")
        if not url.startswith("https://telegra.ph/"):
            raise RuntimeError("Valid persisted Telegraph public URL required before Telegram")
        profile = load_channel_profile(args.repo_root / DEFAULT_PROFILE_PATH)
        binding = load_target_binding(args.repo_root / DEFAULT_BINDING_PATH, profile=profile)
        bot_token = os.environ.get(profile.bot_token_env, "").strip()
        if not bot_token:
            raise RuntimeError(f"Missing configured Telegram bot credential: {profile.bot_token_env}")
        if item.channel_post is None:
            raise RuntimeError("No reviewed Telegram channel post")
        rendered = render_channel_post(item.channel_post, url)
        transport = HttpxLiveTransport()
        receipt = publish_channel_message(
            transport,
            bot_token=bot_token,
            expected_bot_id=binding.bot_id,
            expected_chat_id=binding.chat_id,
            rendered_post=rendered,
            preview_refresh_delay_seconds=0,
        )
        entry.update(
            state="published",
            telegram_provider_effect="verified",
            telegram_chat_id=receipt["chat_id"],
            telegram_message_id=receipt["message_id"],
            telegram_link_preview_large_media=receipt["link_preview_large_media"],
            telegram_published_at_utc=_now(),
        )
        save_ledger(path, ledger)
        return {
            "stage": args.stage,
            "publication_id": args.publication_id,
            "telegram_message_id": receipt["message_id"],
        }

    raise ValueError(f"Unsupported stage: {args.stage}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m video_channel_manager.lordchrist_telegraph_staged")
    parser.add_argument("stage", choices=("prepare-page", "send-page", "prepare-telegram", "send-telegram"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE_PATH)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    parser.add_argument("--publication-id", required=True)
    parser.add_argument("--media-base-url", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", type=int, required=True)
    parser.add_argument("--github-sha", required=True)
    args = parser.parse_args(argv)
    result = execute(args)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
