"""One-shot accessibility correction of existing LordChrist post #1619 and Telegraph page.

This tool NEVER sends a new message or creates a new page. Each individual
provider mutation is preceded by a durable ledger claim on the state branch.
Unknown outcomes are not replayed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import os
import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.lordchrist_telegraph_publisher import (
    DEFAULT_TELEGRAM_API_BASE,
    MAX_TELEGRAPH_CONTENT_UTF8_BYTES,
    HttpxLiveTransport,
    publish_telegraph_page,
    render_channel_post,
    save_ledger,
)
from video_channel_manager.lordchrist_telegraph_staged import _require_execution_context
from video_channel_manager import lordchrist_peasants1525_inplace as old

RECEIPT_KEY = "peasants1525_reader_ux_v1"
BASE_MEDIA_SHA = old.ORIGINAL_GITHUB_SHA
CHAT_ID = -1001295216957
ANCHORED_LINKS = 11

DEFINITIONS = (
    ("swabia", "Швабия — историческая область Центральной Европы. В 1525 году её земли входили в Священную Римскую империю, преимущественно на юге современной Германии."),
    ("articles", "«Двенадцать статей» — составленный в 1525 году свод двенадцати требований швабских крестьян к церковным и светским властям. Статья здесь означает пункт документа."),
    ("pastor", "Пастор — служитель местной христианской общины, проповедующий и осуществляющий пастырское попечение. Первым требованием было право общины самой избирать и при необходимости отстранять его."),
    ("dependency", "Личная зависимость — правовые ограничения свободы крестьянина в отношениях с господином. Её формы различались; это не точная копия позднейшего российского крепостного права."),
    ("memmingen", "Мемминген — город на юге нынешней Германии (Бавария), в 1525 году вольный имперский город, где был составлен известный свод требований."),
    ("luther", "Мартин Лютер — немецкий реформатор. В 1525 году сначала призвал к миру и осудил злоупотребления господ, а позднее резко выступил против вооружённых восставших."),
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _children_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_children_text(x) for x in value)
    if isinstance(value, dict):
        return _children_text(value.get("children", []))
    return ""


def improve_nodes(baseline: Any) -> tuple[Any, int]:
    """Keep all facsimiles, primary-source links, headings and citations intact.

    Only remove same-page links which force the reader to scroll to the glossary;
    shorten two self-referential instructions which would otherwise be misleading.
    """
    nodes = copy.deepcopy(baseline.nodes)
    removed = 0

    def clean(node: Any) -> Any:
        nonlocal removed
        if isinstance(node, list):
            result: list[Any] = []
            for child in node:
                rewritten = clean(child)
                if isinstance(rewritten, list):
                    result.extend(rewritten)
                else:
                    result.append(rewritten)
            return result
        if not isinstance(node, dict):
            return node
        if (
            node.get("tag") == "a"
            and isinstance(node.get("attrs"), dict)
            and str(node["attrs"].get("href", "")).startswith(old.PAGE_URL + "#")
        ):
            removed += 1
            return clean(node.get("children", []))
        if "children" in node:
            node["children"] = clean(node["children"])
        return node

    nodes = clean(nodes)
    if removed != ANCHORED_LINKS:
        raise ValueError(f"Glossary link count drifted: expected {ANCHORED_LINKS}, found {removed}")

    first, second = 0, 0
    for node in nodes:
        if not isinstance(node, dict) or node.get("tag") != "p":
            continue
        pieces = node.get("children")
        if not isinstance(pieces, list):
            continue
        for idx, piece in enumerate(pieces):
            if not isinstance(piece, str):
                continue
            if "Непривычные названия можно нажать:" in piece:
                first += 1
                prefix = piece.split("Непривычные названия можно нажать:", 1)[0]
                node["children"] = [
                    *pieces[:idx],
                    prefix + "Пояснения к терминам даны по ходу текста; в конце оставлен справочный словарь.",
                ]
                break
            if "Нажатие на выделенный термин в статье ведёт к его определению здесь." in piece:
                second += 1
                node["children"][idx] = piece.replace(
                    "Нажатие на выделенный термин в статье ведёт к его определению здесь.",
                    "Это справочный словарь: основные пояснения уже даны непосредственно в статье.",
                )
    if (first, second) != (1, 1):
        raise ValueError(f"Expected both misleading scroll instructions, found {(first, second)}")
    if any(
        isinstance(node, dict) and old.PAGE_URL + "#" in json.dumps(node, ensure_ascii=False)
        for node in nodes
    ):
        raise ValueError("Same-page glossary links remain after rewrite")
    compact = json.dumps(nodes, ensure_ascii=False, separators=(",", ":"))
    length = len(compact.encode("utf-8"))
    if length > MAX_TELEGRAPH_CONTENT_UTF8_BYTES:
        raise ValueError("Improved page exceeds Telegraph byte limit")
    improved = replace(
        baseline,
        nodes=nodes,
        compact_content_json=compact,
        content_utf8_bytes=length,
    )
    return improved, removed


def rich_html_for_existing_post(spec: Any) -> str:
    """Preserve approved editorial body, while linking six terms to native popups."""
    text = render_channel_post(spec, old.PAGE_URL).html_text
    substitutions = (
        ("Крестьяне Швабии", 'Крестьяне <a href="#swabia">Швабии</a>'),
        ("составили «Двенадцать статей»:", 'составили <a href="#articles">«Двенадцать статей»</a>:'),
        ("Первым пунктом было право общины выбирать пастора.", 'Первым пунктом было право общины выбирать <a href="#pastor">пастора</a>.'),
        ("личной зависимости", '<a href="#dependency">личной зависимости</a>'),
        ("архив Меммингена", 'архив <a href="#memmingen">Меммингена</a>'),
        ("Мартина Лютера", 'Мартина <a href="#luther">Лютера</a>'),
    )
    for original, replacement in substitutions:
        if text.count(original) != 1:
            raise ValueError(f"Rich footnote anchor is absent or ambiguous: {original}")
        text = text.replace(original, replacement, 1)
    old_cta = html.escape(spec.cta_prefix)
    if text.count(old_cta) != 1:
        raise ValueError("Historical article CTA changed")
    text = text.replace(
        old_cta,
        "Полный иллюстрированный очерк, подлинные страницы 1525 года и справочный словарь:",
        1,
    )
    for key, definition in DEFINITIONS:
        text += f'\n<tg-reference name="{key}">{html.escape(definition)}</tg-reference>'
    keys = re.findall(r'<a href="#([a-z]+)">', text)
    definitions = re.findall(r'<tg-reference name="([a-z]+)">', text)
    if len(keys) != len(DEFINITIONS) or sorted(keys) != sorted(definitions):
        raise ValueError("Unbalanced rich message footnotes")
    if len(text.encode("utf-8")) > 32768:
        raise ValueError("Rich message too large")
    return text


def _context(args: argparse.Namespace) -> tuple[Any, dict[str, Any], dict[str, Any], Any, Any, Any, str]:
    state_path, ledger, entry, item, baseline = old._target(args)
    prior = entry.get("peasants1525_glossary_v2_revision")
    if (
        not isinstance(prior, dict)
        or prior.get("state") != "verified"
        or prior.get("page_provider_effect") != "verified"
        or prior.get("telegram_provider_effect") != "verified"
    ):
        raise RuntimeError("Previous publication revision is not verified")
    target, removed = improve_nodes(baseline)
    if removed != ANCHORED_LINKS:
        raise RuntimeError("Glossary removal mismatch")
    rich = rich_html_for_existing_post(item.channel_post)
    return state_path, ledger, entry, item, baseline, target, rich


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _claim(args: argparse.Namespace, entry: dict[str, Any], stage: str, target: Any, rich: str) -> dict[str, Any]:
    rec = entry.get(RECEIPT_KEY)
    if not isinstance(rec, dict):
        raise RuntimeError("Readability revision is not durably claimed")
    if (
        rec.get("state") != stage
        or rec.get("run_id") != args.run_id
        or rec.get("run_attempt") != args.run_attempt
        or rec.get("github_sha") != args.github_sha
        or args.run_attempt != 1
        or rec.get("target_page_sha256") != _digest(target.compact_content_json)
        or rec.get("target_post_sha256") != _digest(rich)
        or rec.get("page_url") != old.PAGE_URL
        or rec.get("message_id") != old.MESSAGE_ID
    ):
        raise RuntimeError("Readability receipt or original claim identity changed")
    return rec


def execute(args: argparse.Namespace) -> dict[str, Any]:
    _require_execution_context(args)
    path, ledger, entry, item, baseline, target, rich = _context(args)
    token = os.environ.get("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "").strip()

    if args.stage == "prepare-page":
        if RECEIPT_KEY in entry:
            raise RuntimeError("Readability revision already claimed, never automatically replay")
        old._proof_reconciled_page(baseline)
        old._post_readback(item.channel_post.headline)
        old._prove_owner(token, expected_title=baseline.title)
        old._telegram_authority(args)
        entry[RECEIPT_KEY] = {
            "state": "page_claimed",
            "run_id": args.run_id,
            "run_attempt": args.run_attempt,
            "github_sha": args.github_sha,
            "page_url": old.PAGE_URL,
            "message_id": old.MESSAGE_ID,
            "target_page_sha256": _digest(target.compact_content_json),
            "target_post_sha256": _digest(rich),
            "page_provider_effect": "unknown_until_verified",
            "telegram_provider_effect": "not_attempted",
            "claimed_at_utc": _now(),
        }
        save_ledger(path, ledger)
        return {"stage": args.stage, "claim_persist_required": True}

    if args.stage == "edit-page":
        receipt = _claim(args, entry, "page_claimed", target, rich)
        old._proof_reconciled_page(baseline)
        old._prove_owner(token, expected_title=baseline.title)
        transport = HttpxLiveTransport()
        url, page_path = publish_telegraph_page(
            transport, target, access_token=token, existing_path=old.PAGE_PATH, allow_split=False,
        )
        if (url, page_path) != (old.PAGE_URL, old.PAGE_PATH):
            raise RuntimeError("The editing API returned a different Telegraph page")
        old._proof_reconciled_page(target)
        receipt.update(
            state="page_verified", page_provider_effect="verified", page_verified_at_utc=_now()
        )
        save_ledger(path, ledger)
        return {"stage": args.stage, "page_url": old.PAGE_URL}

    if args.stage == "prepare-telegram":
        receipt = _claim(args, entry, "page_verified", target, rich)
        old._proof_reconciled_page(target)
        old._post_readback(item.channel_post.headline)
        old._telegram_authority(args)
        receipt.update(
            state="telegram_claimed",
            telegram_provider_effect="unknown_until_verified",
            telegram_claimed_at_utc=_now(),
        )
        save_ledger(path, ledger)
        return {"stage": args.stage, "claim_persist_required": True}

    if args.stage == "edit-telegram":
        receipt = _claim(args, entry, "telegram_claimed", target, rich)
        old._proof_reconciled_page(target)
        old._post_readback(item.channel_post.headline)
        bot_token, binding = old._telegram_authority(args)
        if binding.chat_id != CHAT_ID:
            raise RuntimeError("Original Telegram channel identity changed")
        transport = HttpxLiveTransport()
        result = transport.post_json(
            f"{DEFAULT_TELEGRAM_API_BASE}/bot{bot_token}/editMessageText",
            {
                "chat_id": CHAT_ID,
                "message_id": old.MESSAGE_ID,
                "rich_message": {"html": rich},
                "link_preview_options": {
                    "is_disabled": False,
                    "url": old.PAGE_URL,
                    "prefer_large_media": True,
                    "show_above_text": False,
                },
            },
        )
        msg = result.get("result")
        if (
            result.get("ok") is not True
            or not isinstance(msg, dict)
            or msg.get("message_id") != old.MESSAGE_ID
            or (msg.get("chat") or {}).get("id") != CHAT_ID
        ):
            raise RuntimeError("Telegram response did not confirm original message identity")
        serialized = json.dumps(msg.get("rich_message") or {}, ensure_ascii=False)
        if not all(x in serialized for x in ("reference", "reference_link", "swabia", "articles", "dependency")):
            raise RuntimeError("Rich response lacks expected footnote structures; do not retry")
        receipt.update(
            state="verified", telegram_provider_effect="verified", verified_at_utc=_now(),
        )
        save_ledger(path, ledger)
        return {"stage": args.stage, "message_id": old.MESSAGE_ID, "url": old.PAGE_URL}

    raise RuntimeError("Unsupported readability stage")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "stage", choices=("prepare-page", "edit-page", "prepare-telegram", "edit-telegram")
    )
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--publication-id", default=old.PUBLICATION_ID)
    parser.add_argument("--media-base-url", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", type=int, required=True)
    parser.add_argument("--github-sha", required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
