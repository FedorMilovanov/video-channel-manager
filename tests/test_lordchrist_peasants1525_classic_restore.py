"""Contract for compact original post 1619 and genuine Telegram link preview."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import pytest

from video_channel_manager import lordchrist_peasants1525_classic_restore as classic
from video_channel_manager import lordchrist_peasants1525_inplace as original
from video_channel_manager import lordchrist_peasants1525_readability as glossary
from video_channel_manager.lordchrist_telegraph_publisher import (
    DEFAULT_QUEUE_PATH,
    _find_item,
    load_telegraph_queue,
)

ROOT = Path(__file__).resolve().parents[1]


def _spec():
    queue = load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)
    return _find_item(queue, original.PUBLICATION_ID).channel_post


def _args(stage: str):
    return Namespace(
        stage=stage,
        ledger=Path("ledger.json"),
        repo_root=ROOT,
        publication_id=original.PUBLICATION_ID,
        media_base_url=(
            "https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/" + original.ORIGINAL_GITHUB_SHA
        ),
        run_id="438234",
        run_attempt=1,
        github_sha="f" * 40,
    )


def _fixture(monkeypatch, stage: str):
    spec = _spec()
    args = _args(stage)
    entry = {
        classic.PREVIOUS_RECEIPT_KEY: {
            "state": "verified",
            "provider_effect": "verified",
            "post_sha256": classic.PREVIOUS_POST_SHA256,
            "page_url": original.PAGE_URL,
            "message_id": original.MESSAGE_ID,
        }
    }
    ledger = {"entries": {original.PUBLICATION_ID: entry}}
    monkeypatch.setattr(classic, "_require_execution_context", lambda _: None)
    monkeypatch.setattr(
        original,
        "_target",
        lambda _: (Path("ledger.json"), ledger, entry, SimpleNamespace(channel_post=spec), object()),
    )
    monkeypatch.setattr(glossary, "improve_nodes", lambda _: (object(), 11))
    monkeypatch.setattr(original, "_proof_reconciled_page", lambda _: None)
    monkeypatch.setattr(original, "_post_readback", lambda: None)
    monkeypatch.setattr(
        original,
        "_telegram_authority",
        lambda _: ("FAKE", SimpleNamespace(chat_id=glossary.CHAT_ID)),
    )
    writes = []
    monkeypatch.setattr(classic, "save_ledger", lambda path, data: writes.append(path))
    return args, entry, writes


def test_compact_post_restores_normal_html_and_native_expandable_quote():
    result = classic.render(_spec())
    assert "<blockquote expandable>" in result
    assert "<blockquote>" in result
    assert result.count("<blockquote") == 2
    assert result.count("\n\n") == 9
    assert "<tg-reference" not in result
    assert "<p>" not in result
    assert "<br>" not in result
    assert classic.CTA_TEXT in result
    assert result.endswith(classic.CTA_TEXT + "</a>")
    assert "Полный иллюстрированный очерк" not in result
    assert "ИНСТАНТ" not in result
    assert "пастора." in result
    assert "Мартина Лютера." in result


def test_four_clickable_historical_terms_point_to_valid_existing_article_fragments():
    rendered = classic.render(_spec())
    assert len(classic.TERM_ANCHORS) == 4
    for url in classic.term_links():
        assert rendered.count(f'href="{url}"') == 1
    assert rendered.count(f'href="{original.PAGE_URL}"') == 1
    assert rendered.count("<a href=") == 5
    assert 'href="#pastor"' not in rendered
    assert 'href="#luther"' not in rendered


def test_edit_requires_approved_editorial_source():
    args = _args("edit")
    assert len(classic.term_links()) == 4
    record = {"state": "claimed", "message_id": original.MESSAGE_ID}
    with pytest.raises(RuntimeError, match="claim changed"):
        classic._receipt(args, {classic.RECEIPT_KEY: record}, classic.render(_spec()))


def test_claim_is_durable_and_nonreplayable(monkeypatch):
    args, entry, writes = _fixture(monkeypatch, "claim")
    result = classic.execute(args)
    assert result["message_id"] == 1619
    assert entry[classic.RECEIPT_KEY]["state"] == "claimed"
    assert len(writes) == 1
    with pytest.raises(RuntimeError, match="already claimed"):
        classic.execute(args)


def test_edit_replaces_rich_with_regular_html_and_requests_actual_preview(monkeypatch):
    args, entry, writes = _fixture(monkeypatch, "edit")
    markup = classic.render(_spec())
    entry[classic.RECEIPT_KEY] = {
        "state": "claimed",
        "run_id": args.run_id,
        "run_attempt": args.run_attempt,
        "github_sha": args.github_sha,
        "message_id": original.MESSAGE_ID,
        "target_sha256": classic._digest(markup),
    }
    calls = []

    class FakeTransport:
        def post_json(self, url, payload):
            calls.append((url, payload))
            links = [{"type": "text_link", "url": url} for url in classic.term_links()]
            links.append({"type": "text_link", "url": original.PAGE_URL})
            return {
                "ok": True,
                "result": {
                    "chat": {"id": glossary.CHAT_ID},
                    "message_id": original.MESSAGE_ID,
                    "text": (
                        "1525 ГОД: НЕМЕЦКИЕ КРЕСТЬЯНЕ ПОТРЕБОВАЛИ ПРАВА"
                        " ВЫБИРАТЬ ПРОПОВЕДНИКА\n"
                        "Швабии «Двенадцать статей» Меммингена"
                        " Мартина Лютера. Читать полную историческую статью"
                    ),
                    "entities": links + [{"type": "expandable_blockquote"}],
                },
            }

    monkeypatch.setattr(classic, "HttpxLiveTransport", FakeTransport)
    result = classic.execute(args)
    assert result["format"] == "classic"
    assert entry[classic.RECEIPT_KEY]["provider_effect"] == "verified"
    assert len(writes) == 1
    assert len(calls) == 1
    url, payload = calls[0]
    assert url.endswith("/editMessageText")
    assert payload["message_id"] == 1619
    assert "rich_message" not in payload
    assert payload["text"] == markup
    assert payload["parse_mode"] == "HTML"
    assert payload["reply_markup"] == {"inline_keyboard": []}
    assert payload["link_preview_options"] == {
        "is_disabled": False,
        "url": original.PAGE_URL,
        "prefer_large_media": True,
        "show_above_text": False,
    }


def test_percent_encoded_anchors_pass_provider_readback(monkeypatch):
    args, entry, writes = _fixture(monkeypatch, "edit")
    entry[classic.RECEIPT_KEY] = {
        "state": "claimed",
        "run_id": args.run_id,
        "run_attempt": 1,
        "github_sha": args.github_sha,
        "message_id": 1619,
        "target_sha256": classic._digest(classic.render(_spec())),
    }

    class FakeTransport:
        def post_json(self, url, payload):
            links = [
                {
                    "type": "text_link",
                    "url": (original.PAGE_URL + "#" + quote(fragment)),
                }
                for _phrase, _prefix, _visible, fragment in classic.TERM_ANCHORS
            ]
            return {
                "ok": True,
                "result": {
                    "message_id": 1619,
                    "chat": {"id": glossary.CHAT_ID},
                    "text": ("Швабии «Двенадцать статей» Меммингена Мартина Лютера. Читать полную историческую статью"),
                    "entities": links
                    + [
                        {"type": "text_link", "url": original.PAGE_URL},
                        {"type": "expandable_blockquote"},
                    ],
                },
            }

    monkeypatch.setattr(classic, "HttpxLiveTransport", FakeTransport)
    assert classic.execute(args)["term_links"] == 4


def test_missing_native_expandable_quote_fails_closed(monkeypatch):
    args, entry, writes = _fixture(monkeypatch, "edit")
    entry[classic.RECEIPT_KEY] = {
        "state": "claimed",
        "run_id": args.run_id,
        "run_attempt": 1,
        "github_sha": args.github_sha,
        "message_id": 1619,
        "target_sha256": classic._digest(classic.render(_spec())),
    }

    class FakeTransport:
        def post_json(self, url, payload):
            return {
                "ok": True,
                "result": {
                    "message_id": 1619,
                    "chat": {"id": glossary.CHAT_ID},
                    "text": ("Швабии «Двенадцать статей» Меммингена Мартина Лютера. Читать полную историческую статью"),
                    "entities": [
                        {"type": "text_link", "url": href} for href in classic.term_links() + (original.PAGE_URL,)
                    ],
                },
            }

    monkeypatch.setattr(classic, "HttpxLiveTransport", FakeTransport)
    with pytest.raises(RuntimeError, match="readback failed"):
        classic.execute(args)
    assert writes == []
