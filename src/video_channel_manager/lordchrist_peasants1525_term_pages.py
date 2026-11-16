"""One-shot, ledger-gated Telegraph glossary pages and classic @lordchrist/1619.

Creates exactly four *short* Telegra.ph definitions under the SAME authorized
publisher as the longread; edits only the EXISTING Telegram post #1619, not a
new post. Every remote mutation requires a separately pushed intent. No
automatic replay after an ambiguous provider response.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from video_channel_manager import lordchrist_peasants1525_inplace as original
from video_channel_manager import lordchrist_peasants1525_readability as reviewed
from video_channel_manager.lordchrist_telegraph_publisher import (
    DEFAULT_TELEGRAM_API_BASE,
    HttpxLiveTransport,
    save_ledger,
)
from video_channel_manager.lordchrist_telegraph_staged import _require_execution_context

RECEIPT_KEY = "peasants1525_four_telegraph_definitions_v1"
PAGE_KEYS = ("swabia", "articles", "dependency", "memmingen")
SOURCE_URL = "https://stadtarchiv.memmingen.de/quellen/reformation-und-bauernaufstand/zwoelf-artikel-der-bauernschaft-augsburger-erstdruck.html"
PAGES = {
    "swabia": (
        "Швабия: где жили крестьяне 1525 года?",
        "Швабия — историческая область в юго-западной части немецких земель Центральной Европы. В 1525 году она входила в Священную Римскую империю, а не в современное единое государство Германия.",
        "Верхняя Швабия стала одним из центров Крестьянской войны. Сегодня эти земли относятся преимущественно к южной Германии. Поэтому речь идёт не о российских крестьянах.",
    ),
    "articles": (
        "«Двенадцать статей»: что это за документ?",
        "«Двенадцать статей» — свод двенадцати требований участников Крестьянской войны, составленный в 1525 году в Меммингене. Слово «статья» здесь означает отдельный пункт документа, а не газетную публикацию.",
        "Первый пункт требовал права христианской общины самой избирать и, при необходимости, отстранять пастора. Документ касался также десятины, повинностей и личной зависимости.",
    ),
    "dependency": (
        "Личная зависимость крестьян: что это значило?",
        "Личная зависимость — правовые ограничения свободы крестьянина в отношениях с землевладельцем или господином. Конкретные обязанности и права различались по территориям.",
        "В третьей из «Двенадцати статей» крестьяне ссылались на искупление Христом как на довод против личной несвободы. При этом они отдельно оговаривали необходимость повиновения законной власти. Не следует автоматически отождествлять эту систему с российским крепостным правом.",
    ),
    "memmingen": (
        "Мемминген: почему он важен в 1525 году?",
        "Мемминген — город в Швабии на юге современных немецких земель; ныне находится в Баварии. В 1525 году он имел статус вольного имперского города Священной Римской империи.",
        "Именно здесь были согласованы знаменитые «Двенадцать статей» — требования крестьян к церковным и светским властям. Городской архив Меммингена хранит материалы, позволяющие проверять их текст и историю печати.",
    ),
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _sha(value: Any) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    )


def page_nodes(key: str) -> list[dict[str, Any]]:
    title, meaning, context = PAGES[key]
    return [
        {"tag": "p", "children": [meaning]},
        {"tag": "p", "children": [context]},
        {
            "tag": "p",
            "children": [
                {"tag": "strong", "children": ["Подробнее: "]},
                {
                    "tag": "a",
                    "attrs": {"href": original.PAGE_URL},
                    "children": ["большая статья и изображения документов 1525 года"],
                },
            ],
        },
        {
            "tag": "p",
            "children": [
                {"tag": "a", "attrs": {"href": SOURCE_URL}, "children": ["Первоисточник: архив Меммингена"]},
            ],
        },
    ]


def validate_page(key: str, url: str) -> bool:
    if not (url.startswith("https://telegra.ph/") and len(url) < 300):
        return False
    path = url.removeprefix("https://telegra.ph/")
    try:
        response = httpx.get(
            "https://api.telegra.ph/getPage/" + path,
            params={"return_content": "true"},
            timeout=25,
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError):
        return False
    result = data.get("result") if data.get("ok") else None
    if not isinstance(result, dict) or result.get("url") != url or result.get("title") != PAGES[key][0]:
        return False
    # Telegra.ph serializes its own absolute links as root-relative paths and
    # adds target=_blank to external links. Normalize ONLY those two verified
    # provider transformations; keep exact text, node structure and URLs.
    nodes = result.get("content")
    if not isinstance(nodes, list) or len(nodes) != 4:
        return False

    def canonical(node: Any) -> Any:
        if isinstance(node, list):
            return [canonical(child) for child in node]
        if not isinstance(node, dict):
            return node
        item = {name: canonical(value) for name, value in node.items()}
        if item.get("tag") == "a":
            attrs = item.get("attrs")
            if not isinstance(attrs, dict) or not isinstance(attrs.get("href"), str):
                return item
            href = attrs["href"]
            if href.startswith("/") and not href.startswith("//"):
                attrs["href"] = "https://telegra.ph" + href
            if attrs["href"] == SOURCE_URL and attrs.get("target") == "_blank":
                attrs.pop("target")
        return item

    return canonical(nodes) == page_nodes(key)


ORIGINAL_FIRST_CLAIM = {
    "run_id": "43885156976",
    "github_sha": "bb158d16ab5c190df459f5a3f80668f070ca3821",
    "content_sha256": "sha256:4a21dd05b757b9352b594f91920e75106bb3ba8b8efb56b8d99bdc41f080126d",
}


def _wait_exact_page(key: str, url: str) -> bool:
    """Telegra.ph may return createPage before its public getPage replica is ready."""
    for delay in (0, 2, 5, 9, 15):
        if delay:
            time.sleep(delay)
        if validate_page(key, url):
            return True
    return False


def _find_one_owned_page(token: str, key: str) -> str:
    """Authenticated GET-like account listing; NEVER create a second page."""
    candidates: dict[str, str] = {}
    for offset in range(0, 4000, 200):
        response = httpx.post(
            "https://api.telegra.ph/getPageList",
            data={"access_token": token, "offset": str(offset), "limit": "200"},
            timeout=25,
        )
        response.raise_for_status()
        data = response.json()
        result = data.get("result") if data.get("ok") else None
        page_list = result.get("pages") if isinstance(result, dict) else None
        if not isinstance(page_list, list):
            raise RuntimeError("Publisher page listing unavailable; do not repeat createPage")
        for item in page_list:
            if not isinstance(item, dict) or item.get("title") != PAGES[key][0]:
                continue
            url = item.get("url")
            path = item.get("path")
            if not isinstance(url, str) or not isinstance(path, str) or url != "https://telegra.ph/" + path:
                raise RuntimeError("Glossary page listing identity not canonical")
            candidates[path] = url
        if len(page_list) < 200:
            break
    if len(candidates) != 1:
        raise RuntimeError(
            f"Expected exactly one owned '{key}' page after claimed attempt; found {len(candidates)}. "
            "Refuse any new createPage until account ownership is reconciled."
        )
    return next(iter(candidates.values()))


def render_post(spec: Any, urls: dict[str, str]) -> str:
    """Only ordinary Telegram HTML. Short side pages open via Instant View."""
    if set(urls) != set(PAGE_KEYS):
        raise ValueError("All four verified definition URLs are required")
    for key, url in urls.items():
        if not validate_url(url) or key not in PAGE_KEYS:
            raise ValueError("Invalid glossary URL")

    esc = html.escape
    if len(spec.lead_paragraphs) != 2 or len(spec.expandable_points) != 4:
        raise ValueError("Approved article editorial structure changed")

    lead1 = esc(spec.lead_paragraphs[0])
    lead2 = esc(spec.lead_paragraphs[1])

    def insert_exact(body: str, old: str, replace: str) -> str:
        if body.count(old) != 1:
            raise ValueError(f"Historical glossary term occurrence drifted: {old}")
        return body.replace(old, replace, 1)

    lead1 = insert_exact(lead1, "Крестьяне Швабии", f'Крестьяне <a href="{esc(urls["swabia"], quote=True)}">Швабии</a>')
    lead1 = insert_exact(
        lead1,
        "составили «Двенадцать статей»:",
        f'составили <a href="{esc(urls["articles"], quote=True)}">«Двенадцать статей»</a>:',
    )

    points = []
    for i, point in enumerate(spec.expandable_points):
        value = esc(point.body)
        if i == 1:
            value = insert_exact(
                value, "личной зависимости", f'<a href="{esc(urls["dependency"], quote=True)}">личной зависимости</a>'
            )
        if i == 2:
            value = insert_exact(
                value, "архив Меммингена", f'архив <a href="{esc(urls["memmingen"], quote=True)}">Меммингена</a>'
            )
        points.append("• <b>" + esc(point.lead) + "</b> " + value)

    lines = [
        "<b>" + esc(spec.headline) + "</b>",
        lead1,
        lead2,
        "<blockquote>" + esc(spec.quote_text) + "</blockquote>\n— <i>" + esc(spec.quote_attribution) + "</i>",
        "<blockquote expandable><b>" + esc(spec.expandable_header) + "</b>\n\n" + "\n\n".join(points) + "</blockquote>",
        '📖 <a href="' + esc(original.PAGE_URL, quote=True) + '">Читать полную иллюстрированную статью</a>',
    ]
    rendered = "\n\n".join(lines)
    if rendered.count("<a href=") != 5 or rendered.count("<blockquote") != 2:
        raise ValueError("Ordinary text link/quote structure changed")
    if "tg-reference" in rendered or "tg-button" in rendered or "pastor" in rendered:
        raise ValueError("Disallowed rich popup or trivial glossary link")
    if not rendered.endswith("Читать полную иллюстрированную статью</a>"):
        raise ValueError("Full article CTA must remain in last line")
    if len(esc(spec.headline)) > 140 or len(rendered.encode("utf-8")) > 4096:
        raise ValueError("Telegram ordinary text exceeds approved length")
    return rendered


def validate_url(url: str) -> bool:
    return url.startswith("https://telegra.ph/") and "/" not in url[19:] and len(url) < 300


def _context(args: argparse.Namespace) -> tuple[Path, dict[str, Any], dict[str, Any], Any]:
    state_path, ledger, entry, item, baseline = original._target(args)
    prior = entry.get("peasants1525_rich_layout_repair_v1")
    if not isinstance(prior, dict) or prior.get("state") != "verified" or prior.get("provider_effect") != "verified":
        raise RuntimeError("Previously edited post #1619 is not proven")
    reviewed_page, count = reviewed.improve_nodes(baseline)
    if count != 11:
        raise RuntimeError("Published source page revision differs")
    original._proof_reconciled_page(reviewed_page)
    return state_path, ledger, entry, item.channel_post


def _owner(args: argparse.Namespace, entry: dict[str, Any]) -> dict[str, Any]:
    receipt = entry.get(RECEIPT_KEY)
    if not isinstance(receipt, dict) or (
        receipt.get("run_id"),
        receipt.get("github_sha"),
        receipt.get("run_attempt"),
    ) != (args.run_id, args.github_sha, 1):
        raise RuntimeError("Revision belongs to another execution")
    if receipt.get("schema") != 1 or receipt.get("source_page") != original.PAGE_URL:
        raise RuntimeError("Stored reference content identity changed")
    return receipt


def _persist(state_path: Path, ledger: dict[str, Any]) -> None:
    save_ledger(state_path, ledger)


def execute(args: argparse.Namespace) -> dict[str, Any]:
    _require_execution_context(args)
    path, ledger, entry, spec = _context(args)
    stage = args.stage
    key = args.key
    receipt = entry.get(RECEIPT_KEY)

    if stage == "reconcile-swabia":
        if (
            key != "swabia"
            or not isinstance(receipt, dict)
            or receipt.get("schema") != 1
            or receipt.get("state") != "creating"
            or (receipt.get("run_id"), receipt.get("github_sha"), receipt.get("run_attempt"))
            != (ORIGINAL_FIRST_CLAIM["run_id"], ORIGINAL_FIRST_CLAIM["github_sha"], 1)
        ):
            raise RuntimeError("Only the original unconfirmed first page can be reconciled")
        pages_before = receipt.get("pages")
        first = pages_before.get("swabia") if isinstance(pages_before, dict) else None
        if (
            not isinstance(pages_before, dict)
            or not isinstance(first, dict)
            or set(pages_before) != {"swabia"}
            or first.get("state") != "claimed"
            or first.get("provider_effect") != "unknown_until_verified"
            or first.get("content_sha256") != ORIGINAL_FIRST_CLAIM["content_sha256"]
            or first.get("content_sha256") != _sha((PAGES[key], page_nodes(key)))
        ):
            raise RuntimeError("Original first-page intent or editorial content changed")
        token = os.environ.get("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "").strip()
        original._prove_owner(token, expected_title=_longread_title())
        url = _find_one_owned_page(token, "swabia")
        if not _wait_exact_page("swabia", url):
            raise RuntimeError(
                "Original owner page exists but content readback differs; preserve claim and investigate manually"
            )
        receipt["original_claim"] = {
            "run_id": receipt["run_id"],
            "github_sha": receipt["github_sha"],
            "claimed_at_utc": first["claimed_at_utc"],
        }
        receipt.update(
            run_id=args.run_id,
            github_sha=args.github_sha,
            run_attempt=1,
            reconciled_at_utc=_now(),
        )
        first.update(state="verified", provider_effect="verified", url=url, verified_at_utc=_now())
        _persist(path, ledger)
        return {"stage": stage, "key": "swabia", "url": url}

    if stage == "claim-page" and key == PAGE_KEYS[0] and receipt is None:
        original._prove_owner(
            os.environ.get("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "").strip(), expected_title=_longread_title()
        )
        original._telegram_authority(args)
        # Existing RichMessage previews do not consistently expose link URLs in
        # Telegram's public embed. The verified state receipt, exact channel
        # binding, bot getMe/getChat and one-shot editMessageText are authoritative.
        receipt = {
            "schema": 1,
            "run_id": args.run_id,
            "run_attempt": 1,
            "github_sha": args.github_sha,
            "source_page": original.PAGE_URL,
            "state": "creating",
            "pages": {},
            "created_at_utc": _now(),
        }
        entry[RECEIPT_KEY] = receipt
    else:
        receipt = _owner(args, entry)

    pages = receipt["pages"]
    if stage == "claim-page":
        if (
            key not in PAGE_KEYS
            or key in pages
            or any(
                previous not in pages or pages[previous].get("state") != "verified"
                for previous in PAGE_KEYS[: PAGE_KEYS.index(key)]
            )
        ):
            raise RuntimeError("Glossary creation order or idempotency mismatch")
        pages[key] = {
            "state": "claimed",
            "content_sha256": _sha((PAGES[key], page_nodes(key))),
            "provider_effect": "unknown_until_verified",
            "claimed_at_utc": _now(),
        }
        _persist(path, ledger)
        return {"stage": stage, "key": key, "state_persist_required": True}

    if stage == "create-page":
        page = pages.get(key)
        if key not in PAGE_KEYS or not isinstance(page, dict) or page.get("state") != "claimed":
            raise RuntimeError("No durable Telegra.ph createPage claim; no replay")
        if page.get("content_sha256") != _sha((PAGES[key], page_nodes(key))):
            raise RuntimeError("Historical reference text changed after claim")
        token = os.environ.get("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "").strip()
        if not token:
            raise RuntimeError("Existing Telegraph publisher secret missing")
        # Verify account can edit the original publication before every create.
        original._prove_owner(token, expected_title=_longread_title())
        response = httpx.post(
            "https://api.telegra.ph/createPage",
            data={
                "access_token": token,
                "title": PAGES[key][0],
                "author_name": "Господь Бог — Сила Моя",
                "author_url": "https://t.me/lordchrist",
                "content": json.dumps(page_nodes(key), ensure_ascii=False, separators=(",", ":")),
                "return_content": "false",
            },
            timeout=25,
        )
        response.raise_for_status()
        data = response.json()
        info = data.get("result") if data.get("ok") else None
        created_url = info.get("url") if isinstance(info, dict) else None
        if not isinstance(created_url, str) or not _wait_exact_page(key, created_url):
            raise RuntimeError("One-shot Telegraph page effect uncertain; manual reconciliation required")
        page.update(state="verified", provider_effect="verified", url=created_url, verified_at_utc=_now())
        _persist(path, ledger)
        return {"stage": stage, "key": key, "url": created_url}

    if stage == "claim-telegram":
        if key != "all" or receipt.get("state") != "creating" or receipt.get("telegram"):
            raise RuntimeError("Telegram one-shot claim already exists")
        urls = {k: pages[k]["url"] for k in PAGE_KEYS if k in pages and pages[k].get("state") == "verified"}
        if len(urls) != 4 or not all(validate_page(k, u) for k, u in urls.items()):
            raise RuntimeError("Four public glossary pages have not passed readback")
        # Existing RichMessage previews do not consistently expose link URLs in
        # Telegram's public embed. The verified state receipt, exact channel
        # binding, bot getMe/getChat and one-shot editMessageText are authoritative.
        original._telegram_authority(args)
        markup = render_post(spec, urls)
        receipt["telegram"] = {
            "state": "claimed",
            "post_sha256": _sha(markup),
            "provider_effect": "unknown_until_verified",
            "claimed_at_utc": _now(),
        }
        receipt["state"] = "telegram_claimed"
        _persist(path, ledger)
        return {"stage": stage, "message_id": original.MESSAGE_ID}

    if stage == "edit-telegram":
        if key != "all" or receipt.get("state") != "telegram_claimed":
            raise RuntimeError("Telegram claim absent or already used")
        telegram = receipt.get("telegram")
        urls = {k: pages[k]["url"] for k in PAGE_KEYS}
        markup = render_post(spec, urls)
        if (
            not isinstance(telegram, dict)
            or telegram.get("state") != "claimed"
            or telegram.get("post_sha256") != _sha(markup)
        ):
            raise RuntimeError("Durable Telegram claim digest changed")
        # Existing RichMessage previews do not consistently expose link URLs in
        # Telegram's public embed. The verified state receipt, exact channel
        # binding, bot getMe/getChat and one-shot editMessageText are authoritative.
        bot_token, binding = original._telegram_authority(args)
        result = HttpxLiveTransport().post_json(
            f"{DEFAULT_TELEGRAM_API_BASE}/bot{bot_token}/editMessageText",
            {
                "chat_id": binding.chat_id,
                "message_id": original.MESSAGE_ID,
                "text": markup,
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
        msg = result.get("result") if result.get("ok") is True else None
        if (
            not isinstance(msg, dict)
            or msg.get("message_id") != original.MESSAGE_ID
            or (msg.get("chat") or {}).get("id") != binding.chat_id
        ):
            raise RuntimeError("Telegram provider response uncertain; no retry")
        if msg.get("rich_message") is not None or not isinstance(msg.get("text"), str):
            raise RuntimeError("Expected ordinary Telegram text, not rich_message; no retry")
        urls_in_entities = {
            e.get("url") for e in msg.get("entities", []) if isinstance(e, dict) and e.get("type") == "text_link"
        }
        if not (set(urls.values()) | {original.PAGE_URL}).issubset(urls_in_entities):
            raise RuntimeError("Telegram provider failed to return five verified links; no retry")
        if not any(e.get("type") == "expandable_blockquote" for e in msg.get("entities", [])):
            raise RuntimeError("Expandable historical section not confirmed; no retry")
        telegram.update(state="verified", provider_effect="verified", verified_at_utc=_now())
        receipt.update(state="verified", verified_at_utc=_now())
        _persist(path, ledger)
        return {"stage": stage, "message_id": original.MESSAGE_ID, "links": urls, "article": original.PAGE_URL}

    raise RuntimeError("Invalid historical glossary stage/key")


def _longread_title() -> str:
    # The author-identity check must match the actual approved rewritten title.
    return "Швабия, 1525: немецкие крестьяне потребовали права выбирать проповедника"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "stage", choices=("reconcile-swabia", "claim-page", "create-page", "claim-telegram", "edit-telegram")
    )
    parser.add_argument("--key", required=True, choices=(*PAGE_KEYS, "all"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--publication-id", default=original.PUBLICATION_ID)
    parser.add_argument("--media-base-url", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", type=int, required=True)
    parser.add_argument("--github-sha", required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
