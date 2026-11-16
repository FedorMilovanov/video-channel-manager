"""Restore paragraph spacing and full-article access in original @lordchrist #1619.

This one-shot repair edits an existing Telegram message only. No new message,
no Telegraph edit, and no automatic retry after an unknown provider outcome.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager import lordchrist_peasants1525_inplace as original
from video_channel_manager import lordchrist_peasants1525_readability as previous
from video_channel_manager.lordchrist_telegraph_publisher import (
    DEFAULT_TELEGRAM_API_BASE,
    HttpxLiveTransport,
    save_ledger,
)
from video_channel_manager.lordchrist_telegraph_staged import _require_execution_context

_WAVE6_RETIRED_EXECUTOR = True
if __name__ == "__main__":
    raise SystemExit("Retired: ordinary Telegraph glossary links replace the old RichMessage layout; never replay")

RECEIPT_KEY = "peasants1525_rich_layout_repair_v1"
REFERENCE_KEYS = ("swabia", "articles", "dependency", "memmingen")
ARTICLE_LABEL = "⚡ ЧИТАТЬ ПОЛНУЮ СТАТЬЮ · INSTANT VIEW"
QUOTE_LEAD = "Полный иллюстрированный очерк, подлинные страницы 1525 года и справочный словарь:"


def _hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def render(spec: Any) -> str:
    """Use real Rich HTML block tags; whitespace alone is not a paragraph."""
    esc = html.escape
    if len(spec.lead_paragraphs) != 2 or len(spec.expandable_points) != 4:
        raise ValueError("Reviewed post structure has drifted")

    first, second = (esc(p) for p in spec.lead_paragraphs)
    if first.count("Крестьяне Швабии") != 1 or first.count("составили «Двенадцать статей»:") != 1:
        raise ValueError("Geographical or historical first mention changed")

    first = first.replace("Крестьяне Швабии", 'Крестьяне <a href="#swabia">Швабии</a>')
    first = first.replace(
        "составили «Двенадцать статей»:",
        'составили <a href="#articles">«Двенадцать статей»</a>:',
    )

    digest = []
    for idx, point in enumerate(spec.expandable_points):
        lead, body = esc(point.lead), esc(point.body)
        if idx == 1:
            if body.count("личной зависимости") != 1:
                raise ValueError("Personal-dependency glossary anchor changed")
            body = body.replace(
                "личной зависимости",
                '<a href="#dependency">личной зависимости</a>',
            )
        if idx == 2:
            if body.count("архив Меммингена") != 1:
                raise ValueError("Memmingen glossary anchor changed")
            body = body.replace(
                "архив Меммингена",
                'архив <a href="#memmingen">Меммингена</a>',
            )
        digest.append(f"• <b>{lead}</b> {body}")

    url = esc(original.PAGE_URL, quote=True)
    parts = [
        f"<p><b>{esc(spec.headline)}</b></p>",
        f"<p>{first}</p>",
        f"<p>{second}</p>",
        f"<blockquote>{esc(spec.quote_text)}</blockquote>",
        f"<p>— <i>{esc(spec.quote_attribution)}</i></p>",
        (
            "<blockquote expandable>"
            f"<b>{esc(spec.expandable_header)}</b><br><br>" + "<br><br>".join(digest) + "</blockquote>"
        ),
        f"<p>{esc(QUOTE_LEAD)}</p>",
        f'<p><a href="{url}"><b>{esc(ARTICLE_LABEL)} →</b></a></p>',
    ]
    for key, definition in previous.DEFINITIONS:
        if key in REFERENCE_KEYS:
            parts.append(f'<tg-reference name="{key}">{esc(definition)}</tg-reference>')

    markup = "\n".join(parts)
    for term in ("#pastor", "#luther", 'name="pastor"', 'name="luther"'):
        if term in markup:
            raise ValueError("Unnecessary everyday-word footnote resurfaced")
    for key in REFERENCE_KEYS:
        if markup.count(f'href="#{key}"') != 1 or markup.count(f'name="{key}"') != 1:
            raise ValueError(f"Rich reference count drifted: {key}")
    if markup.count(original.PAGE_URL) != 1 or markup.count("</p>") != 6:
        raise ValueError("Paragraph or article-CTA structure drifted")
    if markup.count("<br><br>") != 4 or markup.count("<blockquote") != 2:
        raise ValueError("Quoted text or digest spacing drifted")
    if len(markup.encode("utf-8")) > 32768:
        raise ValueError("Telegram Rich HTML ceiling exceeded")
    return markup


def article_button() -> dict[str, Any]:
    return {"inline_keyboard": [[{"text": "⚡ ПОЛНАЯ СТАТЬЯ · INSTANT VIEW", "url": original.PAGE_URL}]]}


def _context(args: argparse.Namespace) -> tuple[Path, dict[str, Any], dict[str, Any], str]:
    state_path, ledger, entry, item, baseline = original._target(args)
    prior = entry.get(previous.RECEIPT_KEY)
    source_markup = previous.rich_html_for_existing_post(item.channel_post)
    if (
        not isinstance(prior, dict)
        or prior.get("state") != "verified"
        or prior.get("page_provider_effect") != "verified"
        or prior.get("telegram_provider_effect") != "verified"
        or prior.get("target_post_sha256") != _hash(source_markup)
        or prior.get("page_url") != original.PAGE_URL
        or prior.get("message_id") != original.MESSAGE_ID
    ):
        raise RuntimeError("Previously published rich edition is not exactly verified")

    unchanged_page, _ = previous.improve_nodes(baseline)
    original._proof_reconciled_page(unchanged_page)
    return state_path, ledger, entry, render(item.channel_post)


def _receipt(args: argparse.Namespace, entry: dict[str, Any], markup: str) -> dict[str, Any]:
    receipt = entry.get(RECEIPT_KEY)
    if not isinstance(receipt, dict) or any(
        (
            receipt.get("state") != "claimed",
            receipt.get("run_id") != args.run_id,
            receipt.get("run_attempt") != 1,
            args.run_attempt != 1,
            receipt.get("github_sha") != args.github_sha,
            receipt.get("post_sha256") != _hash(markup),
            receipt.get("message_id") != original.MESSAGE_ID,
        )
    ):
        raise RuntimeError("Original one-shot claim mismatch: no edit/retry")
    return receipt


def execute(args: argparse.Namespace) -> dict[str, Any]:
    _require_execution_context(args)
    state_path, ledger, entry, markup = _context(args)
    if args.stage == "claim":
        if RECEIPT_KEY in entry:
            raise RuntimeError("Rich-layout repair already claimed; never replay")
        original._telegram_authority(args)
        entry[RECEIPT_KEY] = {
            "state": "claimed",
            "run_id": args.run_id,
            "run_attempt": 1,
            "github_sha": args.github_sha,
            "message_id": original.MESSAGE_ID,
            "page_url": original.PAGE_URL,
            "post_sha256": _hash(markup),
            "provider_effect": "unknown_until_verified",
            "claimed_at_utc": datetime.now(UTC).isoformat(),
        }
        save_ledger(state_path, ledger)
        return {"stage": "claim", "message_id": original.MESSAGE_ID}

    if args.stage != "edit":
        raise RuntimeError("Unknown repair stage")
    receipt = _receipt(args, entry, markup)
    bot_token, binding = original._telegram_authority(args)
    if binding.chat_id != previous.CHAT_ID:
        raise RuntimeError("Live channel identity differs from #1619")
    transport = HttpxLiveTransport()
    result = transport.post_json(
        f"{DEFAULT_TELEGRAM_API_BASE}/bot{bot_token}/editMessageText",
        {
            "chat_id": binding.chat_id,
            "message_id": original.MESSAGE_ID,
            "rich_message": {"html": markup},
            "reply_markup": article_button(),
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
        or (message.get("chat") or {}).get("id") != previous.CHAT_ID
    ):
        raise RuntimeError("Telegram update receipt not confirmed: do not replay")
    blocks = (message.get("rich_message") or {}).get("blocks") or []
    serialized = json.dumps(blocks, ensure_ascii=False)
    keyboard = (message.get("reply_markup") or {}).get("inline_keyboard") or []
    if (
        len(blocks) < 7
        or not all(key in serialized for key in REFERENCE_KEYS)
        or any(key in serialized for key in ('"pastor"', '"luther"'))
        or not any(button.get("url") == original.PAGE_URL for row in keyboard for button in row)
    ):
        raise RuntimeError("Rich paragraph, popup or article-button readback failed: no retry")
    receipt.update(
        state="verified",
        provider_effect="verified",
        verified_at_utc=datetime.now(UTC).isoformat(),
        rich_block_count=len(blocks),
        instant_view_button_url=original.PAGE_URL,
    )
    save_ledger(state_path, ledger)
    return {
        "stage": "edit",
        "message_id": original.MESSAGE_ID,
        "rich_blocks": len(blocks),
        "button_url": original.PAGE_URL,
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
