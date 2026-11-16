"""Restore original compact Telegram post 1619 with its real Instant View preview.

No new posts, no Telegraph mutations, no unknown-outcome retries.
Native RichMessage footnote popovers and standard-message link previews cannot
be relied on simultaneously. Terms link to verified glossary anchors on the
unchanged historical article, while classic Telegram formatting keeps the
normal message width and the native expandable quote.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote
from typing import Any

from video_channel_manager import lordchrist_peasants1525_inplace as original
from video_channel_manager import lordchrist_peasants1525_readability as glossary
from video_channel_manager.lordchrist_telegraph_publisher import (
    DEFAULT_TELEGRAM_API_BASE,
    HttpxLiveTransport,
    render_channel_post,
    save_ledger,
)
from video_channel_manager.lordchrist_telegraph_staged import _require_execution_context

RECEIPT_KEY = "peasants1525_classic_instant_view_v1"
PREVIOUS_RECEIPT_KEY = "peasants1525_rich_layout_repair_v1"
PREVIOUS_POST_SHA256 = "sha256:c9e1446157cd6150b448ed4af7a28fa1294a32e03246c7b7e2e49fbf5a710bd6"
TERM_ANCHORS = (
    ("Крестьяне Швабии", "Крестьяне ", "Швабии", "Швабия"),
    ("составили «Двенадцать статей»:", "составили ", "«Двенадцать статей»", "Двенадцать-статей"),
    ("личной зависимости", "", "личной зависимости", "Личная-зависимость"),
    ("архив Меммингена", "архив ", "Меммингена", "Мемминген"),
)
CTA_TEXT = "📖 Читать полную историческую статью →"


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def term_links() -> tuple[str, ...]:
    return tuple(original.PAGE_URL + "#" + fragment for _, _, _, fragment in TERM_ANCHORS)


def render(spec: Any) -> str:
    """Return ordinary Telegram HTML, *not* rich_message HTML."""
    if len(spec.lead_paragraphs) != 2 or len(spec.expandable_points) != 4:
        raise RuntimeError("Editorial publication structure changed")

    generated = render_channel_post(spec, original.PAGE_URL).html_text
    previous_cta = (
        html.escape(spec.cta_prefix)
        + '\n<a href="'
        + html.escape(original.PAGE_URL, quote=True)
        + '">'
        + html.escape(spec.cta_link_label)
        + " →</a>"
    )
    if generated.count(previous_cta) != 1 or not generated.endswith(previous_cta):
        raise RuntimeError("Approved original call-to-action has drifted")
    body = generated[: -len(previous_cta)].rstrip()
    for entire, prefix, visible, fragment in TERM_ANCHORS:
        before = html.escape(entire)
        if body.count(before) != 1:
            raise RuntimeError(f"Term anchor not unique: {entire}")
        href = html.escape(original.PAGE_URL + "#" + fragment, quote=True)
        after = html.escape(prefix) + f'<a href="{href}">{html.escape(visible)}</a>'
        body = body.replace(before, after, 1)

    # Make the Telegra.ph URL the final link so Telegram can attach its genuine
    # article/Instant View preview; do not simulate "INSTANT VIEW" in button text.
    body += f'\n\n<a href="{html.escape(original.PAGE_URL, quote=True)}">{html.escape(CTA_TEXT)}</a>'
    if body.count(original.PAGE_URL) != len(TERM_ANCHORS) + 1:
        raise RuntimeError("Expected four glossary links and exactly one article CTA")
    if "<tg-reference" in body or "<p>" in body or "<br>" in body:
        raise RuntimeError("Rich-only markup leaked into ordinary Telegram HTML")
    if "<blockquote expandable>" not in body or body.count("<blockquote") != 2:
        raise RuntimeError("Native expandable quotation was lost")
    if body.count("\n\n") != 9:
        raise RuntimeError("Message paragraph spacing changed")
    if not body.endswith(html.escape(CTA_TEXT) + "</a>"):
        raise RuntimeError("Article must be the very last line")
    if len(body.encode("utf-8")) > 4096:
        raise RuntimeError("Ordinary Telegram message exceeds 4096-byte safe budget")
    return body


def _context(args: argparse.Namespace) -> tuple[Path, dict[str, Any], dict[str, Any], str]:
    path, ledger, entry, item, initial_page = original._target(args)
    prior = entry.get(PREVIOUS_RECEIPT_KEY)
    if (
        not isinstance(prior, dict)
        or prior.get("state") != "verified"
        or prior.get("provider_effect") != "verified"
        or prior.get("post_sha256") != PREVIOUS_POST_SHA256
        or prior.get("message_id") != original.MESSAGE_ID
        or prior.get("page_url") != original.PAGE_URL
    ):
        raise RuntimeError("Exact previous original-post repair is not verified")
    page, removed = glossary.improve_nodes(initial_page)
    if removed != glossary.ANCHORED_LINKS:
        raise RuntimeError("Existing historical article source drift")
    original._proof_reconciled_page(page)
    return path, ledger, entry, render(item.channel_post)


def _receipt(args: argparse.Namespace, entry: dict[str, Any], text: str) -> dict[str, Any]:
    record = entry.get(RECEIPT_KEY)
    if (
        not isinstance(record, dict)
        or record.get("state") != "claimed"
        or record.get("run_id") != args.run_id
        or record.get("run_attempt") != args.run_attempt
        or args.run_attempt != 1
        or record.get("github_sha") != args.github_sha
        or record.get("message_id") != original.MESSAGE_ID
        or record.get("target_sha256") != _digest(text)
    ):
        raise RuntimeError("Original one-time claim changed; no replay")
    return record


def execute(args: argparse.Namespace) -> dict[str, Any]:
    _require_execution_context(args)
    state_path, ledger, entry, text = _context(args)

    if args.stage == "claim":
        if RECEIPT_KEY in entry:
            raise RuntimeError("Restoration was already claimed; no replay")
        original._post_readback()
        original._telegram_authority(args)
        entry[RECEIPT_KEY] = {
            "state": "claimed",
            "run_id": args.run_id,
            "run_attempt": args.run_attempt,
            "github_sha": args.github_sha,
            "message_id": original.MESSAGE_ID,
            "target_sha256": _digest(text),
            "preview_url": original.PAGE_URL,
            "provider_effect": "unknown_until_verified",
            "claimed_at_utc": datetime.now(UTC).isoformat(),
        }
        save_ledger(state_path, ledger)
        return {"stage": args.stage, "message_id": original.MESSAGE_ID}

    if args.stage != "edit":
        raise RuntimeError("Unexpected classic-restoration stage")

    record = _receipt(args, entry, text)
    bot_token, binding = original._telegram_authority(args)
    if binding.chat_id != glossary.CHAT_ID:
        raise RuntimeError("Telegram chat id does not match original post")

    result = HttpxLiveTransport().post_json(
        f"{DEFAULT_TELEGRAM_API_BASE}/bot{bot_token}/editMessageText",
        {
            "chat_id": binding.chat_id,
            "message_id": original.MESSAGE_ID,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": []},
            "link_preview_options": {
                "is_disabled": False,
                "url": original.PAGE_URL,
                "prefer_large_media": True,
                "show_above_text": False,
            },
        },
    )
    message = result.get("result")
    if (
        result.get("ok") is not True
        or not isinstance(message, dict)
        or message.get("message_id") != original.MESSAGE_ID
        or (message.get("chat") or {}).get("id") != binding.chat_id
    ):
        raise RuntimeError("Original message edit response ambiguous; never retry")

    # The provider response is authoritative for the current *message type*.
    # Full Instant View rendering is client-side and must be visually checked.
    rendered = message.get("text")
    entities = message.get("entities") or []
    entity_urls = {unquote(x.get("url", "")) for x in entities if x.get("type") == "text_link"}
    if (
        message.get("rich_message") is not None
        or not isinstance(rendered, str)
        or original.PAGE_URL not in entity_urls
        or not set(term_links()).issubset(entity_urls)
        or "Читать полную историческую статью" not in rendered
        or "«Двенадцать статей»" not in rendered
        or "Швабии" not in rendered
        or "Меммингена" not in rendered
        or "Мартина Лютера" not in rendered
        or not any(x.get("type") == "expandable_blockquote" for x in entities)
    ):
        raise RuntimeError("Telegram classic-format and glossary readback failed: no replay")

    record.update(
        state="verified",
        provider_effect="verified",
        verified_at_utc=datetime.now(UTC).isoformat(),
        entity_count=len(entities),
        checked_classic_message=True,
        link_preview_requested=True,
    )
    save_ledger(state_path, ledger)
    return {
        "stage": args.stage,
        "message_id": original.MESSAGE_ID,
        "format": "classic",
        "term_links": len(term_links()),
        "article_url": original.PAGE_URL,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("claim", "edit"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--publication-id", default=original.PUBLICATION_ID)
    parser.add_argument("--media-base-url", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", type=int, required=True)
    parser.add_argument("--github-sha", required=True)
    print(json.dumps(execute(parser.parse_args()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
