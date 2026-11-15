"""One-shot in-place editorial glossary correction for an existing 1525-history page.

Never creates a page or Telegram message. Every provider mutation follows a
durable, pushed ledger claim; ambiguous outcomes are not retried.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from video_channel_manager.lordchrist_charnock_reschedule import _proof_page
from video_channel_manager.lordchrist_telegraph_publisher import (
    DEFAULT_BINDING_PATH,
    DEFAULT_PROFILE_PATH,
    DEFAULT_QUEUE_PATH,
    DEFAULT_TELEGRAM_API_BASE,
    HttpxLiveTransport,
    _find_item,
    build_telegraph_payload,
    load_telegraph_queue,
    publish_telegraph_page,
    render_channel_post,
    save_ledger,
)
from video_channel_manager.lordchrist_telegraph_staged import _ledger, _require_execution_context
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_target_binding import load_target_binding

PUBLICATION_ID = "lordchrist-telegraph-peasants-1525-20261115"
PAGE_PATH = "1525-pochemu-nemeckie-krestyane-trebovali-prava-vybirat-propovednika-11-15"
PAGE_URL = "https://telegra.ph/" + PAGE_PATH
OLD_TITLE = "1525: почему немецкие крестьяне требовали права выбирать проповедника"
MESSAGE_ID = 1619
EXPECTED_ARTICLE_BLOB = "c223fff62512072f101b1d378dd4f1cad08450e4"
EXPECTED_COVER_BLOB = "60a3e79ce0a7105b1e61844d2ea3b7fd785aaa4a"
READBACK_DELAYS = (0, 2, 4, 8, 16, 30)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _api_post(url: str, form: dict[str, str]) -> dict[str, Any]:
    """Only POST credentials; redact provider errors and never print secrets."""
    try:
        response = httpx.post(url, data=form, timeout=20, follow_redirects=False)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError):
        raise RuntimeError("Telegraph authenticated read failed") from None
    if not isinstance(data, dict) or data.get("ok") is not True:
        raise RuntimeError("Telegraph authenticated read rejected") from None
    result = data.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Telegraph authenticated read lacked a result")
    return result


def _prove_owner(token: str) -> None:
    if not token:
        raise RuntimeError("Existing Telegraph author secret required")
    page = _api_post(
        "https://api.telegra.ph/getPage/" + PAGE_PATH,
        {"access_token": token, "return_content": "false"},
    )
    if page.get("path") != PAGE_PATH or page.get("url") != PAGE_URL:
        raise RuntimeError("Target Telegraph page identity differs")
    if page.get("title") != OLD_TITLE:
        raise RuntimeError("Telegraph page no longer has the approved prior title")
    if page.get("can_edit") is True:
        return
    if page.get("can_edit") is False:
        raise RuntimeError("Retained Telegraph account cannot edit the target page")

    # Telegraph sometimes omits can_edit; prove ownership via that account's page list.
    offset = 0
    while offset < 4000:
        data = _api_post(
            "https://api.telegra.ph/getPageList",
            {"access_token": token, "offset": str(offset), "limit": "200"},
        )
        pages = data.get("pages")
        if not isinstance(pages, list):
            raise RuntimeError("Telegraph page list malformed")
        if any(isinstance(p, dict) and p.get("path") == PAGE_PATH for p in pages):
            return
        offset += len(pages)
        if len(pages) < 200:
            break
    raise RuntimeError("Target page ownership not proved by retained account")


def _post_readback(expected_headline: str | None = None) -> None:
    try:
        resp = httpx.get(
            f"https://t.me/lordchrist/{MESSAGE_ID}?embed=1",
            timeout=20,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except httpx.HTTPError:
        raise RuntimeError("Cannot verify existing public Telegram message") from None
    body = html.unescape(resp.text)
    if f'data-post="lordchrist/{MESSAGE_ID}"' not in body or PAGE_URL not in body:
        raise RuntimeError("Existing message identity or linked article changed")
    if expected_headline and expected_headline not in re.sub(r"<[^>]*>", " ", body):
        raise RuntimeError("Corrected Telegram headline not verified in public readback")


def _telegram_authority(args: argparse.Namespace) -> tuple[str, Any]:
    profile = load_channel_profile(args.repo_root / DEFAULT_PROFILE_PATH)
    binding = load_target_binding(args.repo_root / DEFAULT_BINDING_PATH, profile=profile)
    token = os.environ.get(profile.bot_token_env, "").strip()
    if not token:
        raise RuntimeError("Existing Telegram bot secret required")
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
        raise RuntimeError("Telegram bot/channel identity differs")
    return token, binding


def _target(args: argparse.Namespace) -> tuple[Path, dict[str, Any], dict[str, Any], Any, Any]:
    if args.publication_id != PUBLICATION_ID:
        raise RuntimeError("Only the exact 1525-history glossary revision is allowed")
    state_path, ledger = _ledger(args)
    entry = ledger["entries"].get(PUBLICATION_ID)
    if not isinstance(entry, dict):
        raise RuntimeError("Original publication receipt is absent")
    if (
        entry.get("state") != "published"
        or entry.get("provider_effect") != "verified"
        or entry.get("telegram_provider_effect") != "verified"
        or entry.get("telegram_message_id") != MESSAGE_ID
        or entry.get("telegram_chat_id") != -1001295216957
        or entry.get("telegraph_url") != PAGE_URL
        or entry.get("telegraph_path") != PAGE_PATH
        or entry.get("article_sha256") != "sha256:aa2895347a90cc0e0699a5951204318726913d241b5ac313db914462ccab2a2f"
        or entry.get("cover_sha256") != "sha256:1c3a7cd2386645412e81097dc18481f7de8544fc1d21b28d943a0e5c204ab579"
    ):
        raise RuntimeError("Previously published article or exact channel identity changed")
    items = load_telegraph_queue(args.repo_root / DEFAULT_QUEUE_PATH, args.repo_root)
    item = _find_item(items, PUBLICATION_ID)
    if not item.is_ready or item.channel_post is None:
        raise RuntimeError("Approved correction article or channel post is not ready")
    if item.article_blob != EXPECTED_ARTICLE_BLOB or item.cover_blob != EXPECTED_COVER_BLOB:
        raise RuntimeError("Correction bytes differ from exact editorial approval")
    payload = build_telegraph_payload(args.repo_root, item, media_base_url=args.media_base_url)
    if len(payload.nodes) < 20:
        raise RuntimeError("Incomplete correction content")
    return state_path, ledger, entry, item, payload


def _claimed(args: argparse.Namespace, entry: dict[str, Any], expected: str, payload: Any) -> dict[str, Any]:
    receipt = entry.get("peasants1525_glossary_v2_revision")
    if not isinstance(receipt, dict) or receipt.get("state") != expected:
        raise RuntimeError("One-shot revision stage is not durably claimed")
    if (
        receipt.get("run_id") != args.run_id
        or receipt.get("run_attempt") != 1
        or receipt.get("github_sha") != args.github_sha
        or receipt.get("article_sha256") != payload.article_sha256
        or receipt.get("cover_sha256") != payload.cover_sha256
    ):
        raise RuntimeError("Revision claim belongs to another execution")
    return receipt


def execute(args: argparse.Namespace) -> dict[str, Any]:
    _require_execution_context(args)
    path, ledger, entry, item, payload = _target(args)
    token = os.environ.get("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "").strip()

    if args.stage == "prepare-page":
        if "peasants1525_glossary_v2_revision" in entry:
            raise RuntimeError("Revision already claimed or performed; never replay")
        _prove_owner(token)
        _telegram_authority(args)
        _post_readback()
        entry["peasants1525_glossary_v2_revision"] = {
            "state": "page_claimed",
            "run_id": args.run_id,
            "run_attempt": args.run_attempt,
            "github_sha": args.github_sha,
            "page_url": PAGE_URL,
            "message_id": MESSAGE_ID,
            "article_sha256": payload.article_sha256,
            "cover_sha256": payload.cover_sha256,
            "page_provider_effect": "unknown_until_reconciled",
            "claimed_at_utc": _now(),
        }
        save_ledger(path, ledger)
        return {"stage": args.stage, "owned": True, "url": PAGE_URL}

    if args.stage == "edit-page":
        receipt = _claimed(args, entry, "page_claimed", payload)
        _prove_owner(token)
        _post_readback()
        transport = HttpxLiveTransport()
        url, result_path = publish_telegraph_page(
            transport,
            payload,
            access_token=token,
            existing_path=PAGE_PATH,
            allow_split=False,
        )
        if (url, result_path) != (PAGE_URL, PAGE_PATH):
            raise RuntimeError("Telegraph returned a different page identity")
        _proof_page({"verified_telegraph_url": PAGE_URL}, payload)
        receipt.update(
            state="page_verified",
            page_provider_effect="verified",
            page_verified_at_utc=_now(),
        )
        save_ledger(path, ledger)
        return {"stage": args.stage, "url": PAGE_URL}

    if args.stage == "prepare-telegram":
        receipt = _claimed(args, entry, "page_verified", payload)
        _proof_page({"verified_telegraph_url": PAGE_URL}, payload)
        _telegram_authority(args)
        _post_readback()
        receipt.update(
            state="telegram_claimed",
            telegram_provider_effect="unknown_until_reconciled",
            telegram_claimed_at_utc=_now(),
        )
        save_ledger(path, ledger)
        return {"stage": args.stage, "message_id": MESSAGE_ID}

    if args.stage == "edit-telegram":
        receipt = _claimed(args, entry, "telegram_claimed", payload)
        _proof_page({"verified_telegraph_url": PAGE_URL}, payload)
        bot_token, binding = _telegram_authority(args)
        _post_readback()
        rendered = render_channel_post(item.channel_post, PAGE_URL)
        transport = HttpxLiveTransport()
        api_base = f"{DEFAULT_TELEGRAM_API_BASE}/bot{bot_token}"
        updated = transport.post_json(
            f"{api_base}/editMessageText",
            {
                "chat_id": binding.chat_id,
                "message_id": MESSAGE_ID,
                "text": rendered.html_text,
                "parse_mode": "HTML",
                "link_preview_options": {
                    "is_disabled": False,
                    "url": PAGE_URL,
                    "prefer_large_media": True,
                    "show_above_text": False,
                },
            },
        )
        response = updated.get("result") or {}
        if (
            not updated.get("ok")
            or not isinstance(response, dict)
            or int(response.get("message_id", 0)) != MESSAGE_ID
            or int((response.get("chat") or {}).get("id", 0)) != binding.chat_id
        ):
            raise RuntimeError("Telegram update receipt did not match the existing post")
        for delay in READBACK_DELAYS:
            if delay:
                import time

                time.sleep(delay)
            try:
                _post_readback(item.channel_post.headline)
                break
            except RuntimeError:
                continue
        else:
            raise RuntimeError("Telegram edit was sent once but public readback is inconclusive; do not retry")
        receipt.update(
            state="verified",
            telegram_provider_effect="verified",
            message_id=MESSAGE_ID,
            verified_at_utc=_now(),
        )
        save_ledger(path, ledger)
        return {"stage": args.stage, "message_id": MESSAGE_ID, "url": PAGE_URL, "headline": item.channel_post.headline}

    raise RuntimeError("Unsupported in-place revision stage")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("prepare-page", "edit-page", "prepare-telegram", "edit-telegram"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--publication-id", default=PUBLICATION_ID)
    parser.add_argument("--media-base-url", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", type=int, required=True)
    parser.add_argument("--github-sha", required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
