"""One scheduled replacement only for each owner-deleted Charnock Telegram post.

This does not create/edit Telegraph pages, reset the original receipt or offer
a manual live bypass. The immutable incident manifest binds each calendar slot,
reviewed article bytes, original removed message and verified article URL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from video_channel_manager.lordchrist_telegraph_publisher import (
    DEFAULT_BINDING_PATH,
    DEFAULT_PROFILE_PATH,
    DEFAULT_QUEUE_PATH,
    DEFAULT_TELEGRAM_API_BASE,
    HttpxLiveTransport,
    _find_item,
    build_telegraph_payload,
    load_telegraph_queue,
    render_channel_post,
    save_ledger,
)
from video_channel_manager.lordchrist_telegraph_staged import _ledger, _require_execution_context
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_target_binding import load_target_binding

MOSCOW = ZoneInfo("Europe/Moscow")
MANIFEST = Path("content/telegram/lordchrist/telegraph-v1/charnock/charnock-reschedule-2026.json")
LIVE_WINDOW_HOUR = (12, 13)


def _select_due(
    args: argparse.Namespace, ledger: dict[str, Any], *, now: datetime
) -> tuple[dict[str, Any], Any, Any, dict[str, Any]]:
    local = now.astimezone(MOSCOW)
    if local.hour not in LIVE_WINDOW_HOUR:
        raise RuntimeError("Charnock release is allowed only between 12:00 and 13:59 Moscow")
    manifest = json.loads((args.repo_root / MANIFEST).read_text(encoding="utf-8"))
    if (
        manifest.get("schema_version") != 1
        or manifest.get("channel") != "@lordchrist"
        or manifest.get("timezone") != "Europe/Moscow"
        or manifest.get("release_time") != "12:00"
        or len(manifest.get("items", [])) != 8
    ):
        raise RuntimeError("Unreviewed or malformed incident reschedule manifest")
    matches = [x for x in manifest["items"] if x["scheduled_on_moscow"] == local.date().isoformat()]
    if len(matches) != 1:
        raise RuntimeError("Exactly one reviewed Charnock edition must be due today")
    entry = matches[0]
    if entry["publication_id"] != args.publication_id:
        raise RuntimeError("Requested article is not the sole due Charnock article")
    queue = load_telegraph_queue(args.repo_root / DEFAULT_QUEUE_PATH, args.repo_root)
    item = _find_item(queue, args.publication_id)
    if not item.is_ready or item.scheduled_on != local.date() or item.channel_post is None:
        raise RuntimeError("Actual editorial queue date/status differs from incident manifest")
    if item.article_blob != entry["article_git_blob_sha"] or item.article_path is None:
        raise RuntimeError("Latest reviewed article is not the approved immutable Git blob")
    data = (args.repo_root / item.article_path).read_bytes()
    actual = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    if actual != entry["article_git_blob_sha"]:
        raise RuntimeError("Article file bytes changed since approval")
    original = ledger.get("entries", {}).get(args.publication_id)
    if not isinstance(original, dict):
        raise RuntimeError("Original published receipt is absent")
    if (
        original.get("state") != "published"
        or original.get("provider_effect") != "verified"
        or original.get("telegram_message_id") != entry["deleted_telegram_message_id"]
        or original.get("telegraph_url") != entry["verified_telegraph_url"]
        or original.get("article_sha256") != entry["source_article_sha256"]
    ):
        raise RuntimeError("Source ledger identity does not match verified source delivery")
    # The original creation commit is retained for deterministic historical URLs.
    source_sha = original.get("github_sha")
    if not isinstance(source_sha, str) or len(source_sha) != 40:
        raise RuntimeError("Original publication commit missing")
    media_url = "https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/" + source_sha
    payload = build_telegraph_payload(args.repo_root, item, media_base_url=media_url)
    if payload.article_sha256 != entry["source_article_sha256"]:
        raise RuntimeError("Corrected source is not byte-identical to its verified Telegraph edition")
    return entry, item, payload, original


def _readback_existing_post(*, message_id: int) -> bool:
    response = httpx.get(f"https://t.me/lordchrist/{message_id}?embed=1", timeout=15, follow_redirects=True)
    response.raise_for_status()
    return f'data-post="lordchrist/{message_id}"' in response.text


def _prove_owner_deletion(entry: dict[str, Any]) -> None:
    if not _readback_existing_post(message_id=1595):
        raise RuntimeError("Known-good channel readback unavailable; cannot confirm original deletion")
    if _readback_existing_post(message_id=int(entry["deleted_telegram_message_id"])):
        raise RuntimeError("Original Telegram message is still visible; refuse duplicate release")


def _normalized_telegraph_node(value: Any) -> Any:
    """Telegra.ph adds heading anchors and merges adjacent text children on readback."""
    if isinstance(value, list):
        joined: list[Any] = []
        for child in (_normalized_telegraph_node(item) for item in value):
            if isinstance(child, str) and joined and isinstance(joined[-1], str):
                joined[-1] += child
            else:
                joined.append(child)
        return joined
    if isinstance(value, dict):
        normalized = {key: _normalized_telegraph_node(child) for key, child in value.items()}
        attrs = normalized.get("attrs")
        if normalized.get("tag") in ("h3", "h4") and isinstance(attrs, dict):
            attrs.pop("id", None)
            if not attrs:
                normalized.pop("attrs")
        return normalized
    return value


def _proof_page(entry: dict[str, Any], payload: Any) -> None:
    url = entry["verified_telegraph_url"]
    if not isinstance(url, str) or not url.startswith("https://telegra.ph/"):
        raise RuntimeError("Untrusted Telegraph edition URL")
    path = url.removeprefix("https://telegra.ph/")
    if not path or "/" in path or "?" in path or "#" in path:
        raise RuntimeError("Untrusted Telegraph edition path")
    response = httpx.get(
        f"https://api.telegra.ph/getPage/{path}?return_content=true",
        timeout=20,
    )
    response.raise_for_status()
    document = response.json()
    page = document.get("result")
    if (
        not document.get("ok")
        or not isinstance(page, dict)
        or page.get("title") != payload.title
        or _normalized_telegraph_node(page.get("content")) != _normalized_telegraph_node(payload.nodes)
    ):
        raise RuntimeError("Public Telegraph page is not the entire reviewed latest article edition")


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.stage != "preview":
        _require_execution_context(args)
        if os.environ.get("GITHUB_EVENT_NAME") != "schedule" or args.now is not None:
            raise RuntimeError("Live recovery is schedule-only; no manual/forged clock release")
    now = datetime.fromisoformat(args.now) if args.stage == "preview" and args.now else datetime.now(tz=MOSCOW)
    ledger_path, ledger = _ledger(args)
    source, item, payload, original = _select_due(args, ledger, now=now)
    if args.stage == "preview":
        return {
            "publication_id": args.publication_id,
            "date": source["scheduled_on_moscow"],
            "article_sha256": payload.article_sha256,
            "source_url": source["verified_telegraph_url"],
            "old_message_id": source["deleted_telegram_message_id"],
            "already_claimed": "scheduled_reissue" in original,
        }

    if args.stage == "prepare":
        if "scheduled_reissue" in original:
            raise RuntimeError("Scheduled reissue intent already exists; never replay")
        _prove_owner_deletion(source)
        _proof_page(source, payload)
        original["scheduled_reissue"] = {
            "state": "claimed",
            "provider_effect": "may_exist_until_reconciled",
            "run_id": args.run_id,
            "run_attempt": args.run_attempt,
            "github_sha": args.github_sha,
            "scheduled_on_moscow": source["scheduled_on_moscow"],
            "original_deleted_message_id": source["deleted_telegram_message_id"],
            "source_article_sha256": payload.article_sha256,
            "telegraph_url": source["verified_telegraph_url"],
            "claimed_at_moscow": now.astimezone(MOSCOW).isoformat(),
        }
        save_ledger(ledger_path, ledger)
        return {"stage": "claimed", "publication_id": args.publication_id}

    receipt = original.get("scheduled_reissue")
    if not isinstance(receipt, dict):
        raise RuntimeError("No durable reissue intent; cannot contact provider")
    if (
        receipt.get("run_id") != args.run_id
        or receipt.get("run_attempt") != 1
        or receipt.get("github_sha") != args.github_sha
        or receipt.get("source_article_sha256") != payload.article_sha256
        or receipt.get("telegraph_url") != source["verified_telegraph_url"]
        or receipt.get("scheduled_on_moscow") != source["scheduled_on_moscow"]
    ):
        raise RuntimeError("Reissue intent/reviewed payload drift; fail closed")

    if args.stage == "send":
        if receipt.get("state") != "claimed":
            raise RuntimeError("Send-once already attempted; no replay")
        _prove_owner_deletion(source)
        _proof_page(source, payload)
        profile = load_channel_profile(args.repo_root / DEFAULT_PROFILE_PATH)
        binding = load_target_binding(args.repo_root / DEFAULT_BINDING_PATH, profile=profile)
        token = os.environ.get(profile.bot_token_env, "").strip()
        if not token or binding.chat_id != -1001295216957 or original.get("telegram_chat_id") != binding.chat_id:
            raise RuntimeError("Missing Telegram token or canonical channel binding mismatch")
        transport = HttpxLiveTransport()
        base = f"{DEFAULT_TELEGRAM_API_BASE}/bot{token}"
        me = transport.read_json(f"{base}/getMe", {})
        chat = transport.read_json(f"{base}/getChat", {"chat_id": binding.chat_id})
        if (
            not me.get("ok")
            or int((me.get("result") or {}).get("id", 0)) != binding.bot_id
            or (me.get("result") or {}).get("username") != "preaching_mp3_bot"
            or not chat.get("ok")
            or int((chat.get("result") or {}).get("id", 0)) != binding.chat_id
            or (chat.get("result") or {}).get("username") != "lordchrist"
            or (chat.get("result") or {}).get("type") != "channel"
        ):
            raise RuntimeError("Telegram bot/channel authentication mismatched")
        rendered = render_channel_post(item.channel_post, source["verified_telegraph_url"])
        if not 1 <= rendered.visible_char_count <= 4096:
            raise RuntimeError("Rendered announcement must fit one Telegram L1 message")
        sent = transport.post_json(
            f"{base}/sendMessage",
            {
                "chat_id": binding.chat_id,
                "text": rendered.html_text,
                "parse_mode": "HTML",
                "link_preview_options": {
                    "is_disabled": False,
                    "url": source["verified_telegraph_url"],
                    "prefer_large_media": True,
                    "show_above_text": False,
                },
            },
        )
        result = sent.get("result")
        if not sent.get("ok") or not isinstance(result, dict):
            raise RuntimeError("Telegram provider did not acknowledge a durable new message")
        new_id = int(result.get("message_id", 0))
        if (
            new_id <= 0
            or new_id == source["deleted_telegram_message_id"]
            or int((result.get("chat") or {}).get("id", 0)) != binding.chat_id
        ):
            raise RuntimeError("Telegram provider acknowledged a mismatched message identity")
        urls = {
            e.get("url") for e in result.get("entities", []) if isinstance(e, dict) and e.get("type") == "text_link"
        }
        if source["verified_telegraph_url"] not in urls:
            raise RuntimeError("Telegram receipt lacked exact immutable corrected article link")
        receipt.update(
            state="sent",
            provider_effect="verified_by_api",
            new_message_id=new_id,
            sent_at_moscow=now.astimezone(MOSCOW).isoformat(),
        )
        save_ledger(ledger_path, ledger)
        return {"stage": "sent", "publication_id": args.publication_id, "message_id": new_id}

    if args.stage == "verify":
        if receipt.get("state") != "sent":
            raise RuntimeError("Only a confirmed send can be read back")
        new_id = receipt.get("new_message_id")
        if not isinstance(new_id, int) or new_id <= 0:
            raise RuntimeError("Missing provider-acknowledged replacement message identity")
        response = httpx.get(
            f"https://t.me/lordchrist/{new_id}?embed=1",
            timeout=20,
            follow_redirects=True,
        )
        response.raise_for_status()
        if (
            f'data-post="lordchrist/{new_id}"' not in response.text
            or source["verified_telegraph_url"] not in response.text
        ):
            raise RuntimeError("New Telegram message is not publicly verified; do not retry send")
        receipt.update(
            state="verified", provider_effect="verified", verified_at_moscow=now.astimezone(MOSCOW).isoformat()
        )
        save_ledger(ledger_path, ledger)
        return {"stage": "verified", "publication_id": args.publication_id, "message_id": new_id}

    raise ValueError(f"Unsupported Charnock scheduled stage {args.stage!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m video_channel_manager.lordchrist_charnock_reschedule")
    parser.add_argument("stage", choices=("preview", "prepare", "send", "verify"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--publication-id", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-attempt", type=int, default=0)
    parser.add_argument("--github-sha", default="")
    parser.add_argument("--now", help="Only in provider-free preview; never accepted for live stages")
    args = parser.parse_args(argv)
    print(json.dumps(execute(args), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
