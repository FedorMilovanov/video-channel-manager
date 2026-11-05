"""Durable, one-shot corrective publication for previously issued Charnock articles.

Original Telegraph URLs, publication IDs, and Telegram message IDs are immutable.
A separate corrected page may be created, then the *same* Telegram post edited.
Each external mutation requires a committed state claim; ambiguous results are
never replayed. No disposable Telegraph accounts are created.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from video_channel_manager.lordchrist_telegraph_publisher import (
    DEFAULT_BINDING_PATH,
    DEFAULT_LEDGER_PATH,
    DEFAULT_PROFILE_PATH,
    DEFAULT_QUEUE_PATH,
    DEFAULT_TELEGRAM_API_BASE,
    HttpxLiveTransport,
    _find_item,
    build_telegraph_payload,
    ensure_telegraph_token,
    load_telegraph_queue,
    publish_telegraph_page,
    render_channel_post,
    save_ledger,
)
from video_channel_manager.lordchrist_charnock_reschedule import _proof_page
from video_channel_manager.lordchrist_telegraph_staged import _ledger, _require_execution_context
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_target_binding import load_target_binding

MAP_PATH = Path("docs/audits/2026-11-04-charnock-publication-link-replacement-map.json")
CHARNOCK_PREFIX = "lordchrist-telegraph-charnock-"
CORRECTION_STATES = {"page_claimed", "page_created", "telegram_claimed", "corrected"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _read_original_post(message_id: int, prior_url: str) -> None:
    """Public read only: refuse editing an already changed post."""
    response = httpx.get(f"https://t.me/lordchrist/{message_id}?embed=1", timeout=20, follow_redirects=True)
    response.raise_for_status()
    body = response.text
    if f'data-post="lordchrist/{message_id}"' not in body or prior_url not in body:
        raise RuntimeError("Existing Telegram post or old link was not proved live; no mutation")


def _confirm_public_edit(message_id: int, corrected_url: str, *, attempts: int = 7, delay_seconds: float = 5.0) -> None:
    """Allow bounded Telegram web propagation after a confirmed edit; never edit twice."""
    if attempts < 1 or delay_seconds < 0:
        raise ValueError("Invalid public readback retry limits")
    for number in range(attempts):
        try:
            _read_original_post(message_id, corrected_url)
            return
        except (RuntimeError, httpx.HTTPError) as exc:
            if number + 1 == attempts:
                raise RuntimeError(
                    "Telegram edit was acknowledged but public readback is not yet verified; "
                    "reconcile the original edit, never replay editMessageText"
                ) from exc
            time.sleep(delay_seconds)


def _target(args: argparse.Namespace, ledger: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], Any, Any]:
    if not args.publication_id.startswith(CHARNOCK_PREFIX):
        raise RuntimeError("Only Charnock correction IDs are in scope")
    registry = json.loads((args.repo_root / MAP_PATH).read_text(encoding="utf-8"))
    matches = [t for t in registry["targets"] if t["publication_id"] == args.publication_id]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one historical correction target")
    target = matches[0]
    prior = ledger["entries"].get(args.publication_id)
    if not isinstance(prior, dict):
        raise RuntimeError("Existing historical published receipt required")
    if (
        prior.get("telegraph_url") != target["previous_telegraph_url"]
        or prior.get("telegram_message_id") != target["previous_telegram_message_id"]
        or prior.get("article_sha256") != target["previous_published_article_sha256"]
    ):
        raise RuntimeError("Historical published identity differs from audited correction map")
    items = load_telegraph_queue(args.repo_root / args.queue, args.repo_root)
    item = _find_item(items, args.publication_id)
    if not item.is_ready or item.channel_post is None or item.cover_path is None:
        raise RuntimeError("Corrected article and channel post must be ready")
    if item.article_blob != target["corrected_document_git_blob_sha"]:
        raise RuntimeError("Corrected article blob differs from audited target")
    payload = build_telegraph_payload(args.repo_root, item, media_base_url=args.media_base_url)
    return prior, target, item, payload


def _claimed(args: argparse.Namespace, prior: dict[str, Any], state: str, payload: Any) -> dict[str, Any]:
    receipt = prior.get("correction")
    if not isinstance(receipt, dict) or receipt.get("state") != state:
        raise RuntimeError("Exact correction stage not claimed; no replay")
    if (
        receipt.get("run_id") != args.run_id
        or receipt.get("github_sha") != args.github_sha
        or receipt.get("run_attempt") != 1
        or receipt.get("article_sha256") != payload.article_sha256
        or receipt.get("cover_sha256") != payload.cover_sha256
    ):
        raise RuntimeError("Correction intent identity or reviewed payload changed")
    return receipt


def execute(args: argparse.Namespace) -> dict[str, Any]:
    _require_execution_context(args)
    ledger_path, ledger = _ledger(args)
    prior, target, item, payload = _target(args, ledger)
    original_url = target["previous_telegraph_url"]
    original_id = target["previous_telegram_message_id"]

    if args.stage == "prepare-page":
        if "correction" in prior:
            raise RuntimeError("Correction identity already exists; no replay")
        _read_original_post(original_id, original_url)
        prior["correction"] = {
            "state": "page_claimed",
            "publication_id": args.publication_id,
            "run_id": args.run_id,
            "run_attempt": args.run_attempt,
            "github_sha": args.github_sha,
            "original_telegraph_url": original_url,
            "original_telegram_message_id": original_id,
            "article_sha256": payload.article_sha256,
            "cover_sha256": payload.cover_sha256,
            "provider_effect": "unknown_until_reconciled",
            "page_claimed_at_utc": _now(),
        }
        save_ledger(ledger_path, ledger)
        return {"stage": args.stage, "publication_id": args.publication_id}

    if args.stage == "send-page":
        receipt = _claimed(args, prior, "page_claimed", payload)
        token = os.environ.get("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "").strip()
        if not token:
            raise RuntimeError("A retained Telegraph author token is required")
        transport = HttpxLiveTransport()
        ensure_telegraph_token(transport, explicit_token=token)
        revised = replace(payload, title=f"{payload.title} — исправленное издание")
        url, page_path = publish_telegraph_page(transport, revised, access_token=token, allow_split=False)
        if url == original_url or not url.startswith("https://telegra.ph/"):
            raise RuntimeError("New correction must use a distinct real Telegraph URL")
        receipt.update(
            state="page_created",
            provider_effect="verified",
            new_telegraph_url=url,
            new_telegraph_path=page_path,
            page_created_at_utc=_now(),
        )
        save_ledger(ledger_path, ledger)
        return {"stage": args.stage, "publication_id": args.publication_id, "url": url}

    if args.stage == "prepare-telegram":
        receipt = _claimed(args, prior, "page_created", payload)
        page_url = receipt.get("new_telegraph_url")
        if not isinstance(page_url, str) or not page_url.startswith("https://telegra.ph/"):
            raise RuntimeError("Verified new public page receipt required")
        _proof_page(
            {"verified_telegraph_url": page_url}, replace(payload, title=f"{payload.title} — исправленное издание")
        )
        _read_original_post(original_id, original_url)
        receipt.update(
            state="telegram_claimed",
            telegram_provider_effect="unknown_until_reconciled",
            telegram_claimed_at_utc=_now(),
        )
        save_ledger(ledger_path, ledger)
        return {"stage": args.stage, "publication_id": args.publication_id}

    if args.stage == "edit-telegram":
        receipt = _claimed(args, prior, "telegram_claimed", payload)
        new_url = receipt.get("new_telegraph_url")
        if not isinstance(new_url, str) or new_url == original_url:
            raise RuntimeError("Invalid separately published correction URL")
        _proof_page(
            {"verified_telegraph_url": new_url}, replace(payload, title=f"{payload.title} — исправленное издание")
        )
        profile = load_channel_profile(args.repo_root / DEFAULT_PROFILE_PATH)
        binding = load_target_binding(args.repo_root / DEFAULT_BINDING_PATH, profile=profile)
        token = os.environ.get(profile.bot_token_env, "").strip()
        if not token or prior.get("telegram_chat_id") != binding.chat_id:
            raise RuntimeError("Missing bot credential or historical channel identity mismatch")
        _read_original_post(original_id, original_url)
        rendered = render_channel_post(item.channel_post, new_url)
        base = f"{DEFAULT_TELEGRAM_API_BASE}/bot{token}"
        transport = HttpxLiveTransport()
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
            raise RuntimeError("Bot or channel binding mismatch")
        edited = transport.post_json(
            f"{base}/editMessageText",
            {
                "chat_id": binding.chat_id,
                "message_id": original_id,
                "text": rendered.html_text,
                "parse_mode": "HTML",
                "link_preview_options": {
                    "is_disabled": False,
                    "url": new_url,
                    "prefer_large_media": True,
                    "show_above_text": False,
                },
            },
        )
        if not edited.get("ok") or not isinstance(edited.get("result"), dict):
            raise RuntimeError("Telegram editMessageText rejected the correction")
        message = edited["result"]
        if int(message.get("message_id", -1)) != original_id:
            raise RuntimeError("Telegram returned a different message ID; manual reconciliation required")
        if int((message.get("chat") or {}).get("id", 0)) != binding.chat_id:
            raise RuntimeError("Telegram returned a different channel identity")
        urls = {
            entity.get("url")
            for entity in (message.get("entities") or [])
            if isinstance(entity, dict) and entity.get("type") == "text_link"
        }
        if new_url not in urls:
            raise RuntimeError("Telegram edit receipt does not contain the corrected article link")
        _confirm_public_edit(original_id, new_url)
        receipt.update(
            state="corrected",
            telegram_provider_effect="verified",
            telegram_message_id=original_id,
            corrected_at_utc=_now(),
            telegram_link_preview_large_media=bool(
                (message.get("link_preview_options") or {}).get("prefer_large_media")
            ),
        )
        save_ledger(ledger_path, ledger)
        return {"stage": args.stage, "publication_id": args.publication_id, "url": new_url, "message_id": original_id}

    if args.stage == "reconcile-telegram":
        # Read-only recovery of an edit already acknowledged by Telegram but not
        # durably verified because public widget readback lagged. No Bot API call.
        receipt = prior.get("correction")
        original_run_id = getattr(args, "original_run_id", None)
        if not isinstance(original_run_id, str) or not re.fullmatch(r"[1-9][0-9]*", original_run_id):
            raise RuntimeError("Exact original correction run ID required for reconciliation")
        if not isinstance(receipt, dict) or receipt.get("state") != "telegram_claimed":
            raise RuntimeError("Only a previously claimed ambiguous Telegram edit can be reconciled")
        if (
            receipt.get("run_id") != original_run_id
            or receipt.get("run_attempt") != 1
            or receipt.get("publication_id") != args.publication_id
            or receipt.get("original_telegram_message_id") != original_id
            or receipt.get("original_telegraph_url") != original_url
            or receipt.get("article_sha256") != payload.article_sha256
            or receipt.get("cover_sha256") != payload.cover_sha256
            or receipt.get("provider_effect") != "verified"
            or receipt.get("telegram_provider_effect") != "unknown_until_reconciled"
            or not isinstance(receipt.get("github_sha"), str)
            or not re.fullmatch(r"[a-f0-9]{40}", receipt["github_sha"])
        ):
            raise RuntimeError("Original correction claim or immutable content does not match")
        corrected_url = receipt.get("new_telegraph_url")
        if not isinstance(corrected_url, str) or not corrected_url.startswith("https://telegra.ph/"):
            raise RuntimeError("Durable corrected Telegraph page receipt missing")
        if corrected_url == original_url:
            raise RuntimeError("Correction cannot link the historical original page")
        _proof_page(
            {"verified_telegraph_url": corrected_url},
            replace(payload, title=f"{payload.title} — исправленное издание"),
        )
        _read_original_post(original_id, corrected_url)
        receipt.update(
            state="corrected",
            telegram_provider_effect="verified_public_readback",
            telegram_message_id=original_id,
            corrected_at_utc=_now(),
            reconciliation_run_id=args.run_id,
            reconciled_from_run_id=original_run_id,
        )
        save_ledger(ledger_path, ledger)
        return {
            "stage": args.stage,
            "publication_id": args.publication_id,
            "url": corrected_url,
            "message_id": original_id,
        }

    raise ValueError(f"Unsupported corrective publication stage {args.stage!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m video_channel_manager.lordchrist_telegraph_corrections")
    parser.add_argument(
        "stage", choices=("prepare-page", "send-page", "prepare-telegram", "edit-telegram", "reconcile-telegram")
    )
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE_PATH)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    parser.add_argument("--publication-id", required=True)
    parser.add_argument("--media-base-url", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", type=int, required=True)
    parser.add_argument("--github-sha", required=True)
    parser.add_argument("--original-run-id")
    args = parser.parse_args(argv)
    print(json.dumps(execute(args), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
