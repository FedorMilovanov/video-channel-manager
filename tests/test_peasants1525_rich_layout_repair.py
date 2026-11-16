"""Regression tests for spacing, explanatory popups and the original Instant View CTA."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import peasants1525_rich_layout_repair as repair
from video_channel_manager import lordchrist_peasants1525_inplace as old
from video_channel_manager import lordchrist_peasants1525_readability as previous
from video_channel_manager.lordchrist_telegraph_publisher import (
    DEFAULT_QUEUE_PATH,
    _find_item,
    load_telegraph_queue,
)

ROOT = Path(__file__).resolve().parents[1]


def _item():
    return _find_item(
        load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT),
        old.PUBLICATION_ID,
    )


def _args(stage: str) -> Namespace:
    return Namespace(
        stage=stage,
        repo_root=ROOT,
        ledger=Path("state.json"),
        publication_id=old.PUBLICATION_ID,
        media_base_url="https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/" + old.ORIGINAL_GITHUB_SHA,
        run_id="123456789",
        run_attempt=1,
        github_sha="a" * 40,
    )


def _prior(item):
    previous_rich = previous.rich_html_for_existing_post(item.channel_post)
    return {
        "state": "verified",
        "page_provider_effect": "verified",
        "telegram_provider_effect": "verified",
        "target_post_sha256": repair._hash(previous_rich),
        "page_url": old.PAGE_URL,
        "message_id": old.MESSAGE_ID,
    }


def _fixture(monkeypatch, stage: str):
    item = _item()
    args = _args(stage)
    entry = {previous.RECEIPT_KEY: _prior(item)}
    ledger = {"entries": {old.PUBLICATION_ID: entry}}
    monkeypatch.setattr(repair, "_require_execution_context", lambda _: None)
    monkeypatch.setattr(
        old,
        "_target",
        lambda _: (Path("state.json"), ledger, entry, item, SimpleNamespace()),
    )
    monkeypatch.setattr(previous, "improve_nodes", lambda _: (SimpleNamespace(), 11))
    monkeypatch.setattr(old, "_proof_reconciled_page", lambda _: None)
    monkeypatch.setattr(
        old,
        "_telegram_authority",
        lambda _: ("fake-token", SimpleNamespace(chat_id=previous.CHAT_ID)),
    )
    saved = []
    monkeypatch.setattr(repair, "save_ledger", lambda path, data: saved.append((path, data)))
    return args, ledger, entry, saved


def test_uses_block_level_paragraphs_and_separate_read_more_link():
    markup = repair.render(_item().channel_post)
    assert markup.count("<p>") == 6
    assert markup.count("</p>") == 6
    assert "<p><b>1525 ГОД:" in markup
    assert "<blockquote>" in markup
    assert "<blockquote expandable>" in markup
    assert markup.count("<br><br>") == 4
    assert markup.index("Полный иллюстрированный очерк") < markup.index(repair.ARTICLE_LABEL)
    assert markup.index(repair.ARTICLE_LABEL) < markup.index("<tg-reference")
    assert f'href="{old.PAGE_URL}"' in markup


def test_only_four_historical_term_popups_not_pastor_or_luther():
    markup = repair.render(_item().channel_post)
    assert repair.REFERENCE_KEYS == ("swabia", "articles", "dependency", "memmingen")
    for key in repair.REFERENCE_KEYS:
        assert markup.count(f'href="#{key}"') == 1
        assert markup.count(f'name="{key}"') == 1
    assert 'href="#pastor"' not in markup
    assert 'href="#luther"' not in markup
    assert 'name="pastor"' not in markup
    assert 'name="luther"' not in markup
    assert "пастора." in markup
    assert "Мартина Лютера" in markup


def test_button_is_direct_to_same_existing_instant_view_article():
    button = repair.article_button()
    assert len(button["inline_keyboard"]) == 1
    assert button["inline_keyboard"][0][0]["url"] == old.PAGE_URL
    assert "INSTANT VIEW" in button["inline_keyboard"][0][0]["text"]


def test_renderer_fails_closed_on_unapproved_geographical_change():
    spec = _item().channel_post
    different = SimpleNamespace(**vars(spec))
    different.lead_paragraphs = (
        "Неизвестное место без географического контекста.",
        spec.lead_paragraphs[1],
    )
    with pytest.raises(ValueError, match="first mention"):
        repair.render(different)


def test_claim_does_not_touch_telegram_and_does_not_replay(monkeypatch):
    args, ledger, entry, saved = _fixture(monkeypatch, "claim")
    result = repair.execute(args)
    assert result == {"stage": "claim", "message_id": 1619}
    assert entry[repair.RECEIPT_KEY]["state"] == "claimed"
    assert len(saved) == 1
    with pytest.raises(RuntimeError, match="already claimed"):
        repair.execute(args)


def test_edit_uses_only_existing_message_and_requires_button_readback(monkeypatch):
    args, ledger, entry, saved = _fixture(monkeypatch, "edit")
    markup = repair.render(_item().channel_post)
    entry[repair.RECEIPT_KEY] = {
        "state": "claimed",
        "run_id": args.run_id,
        "run_attempt": args.run_attempt,
        "github_sha": args.github_sha,
        "post_sha256": repair._hash(markup),
        "message_id": old.MESSAGE_ID,
    }
    calls = []

    class FakeTransport:
        def post_json(self, url, body):
            calls.append((url, body))
            return {
                "ok": True,
                "result": {
                    "message_id": 1619,
                    "chat": {"id": previous.CHAT_ID},
                    "rich_message": {
                        "blocks": [
                            {"type": "paragraph", "text": "intro"},
                            {"type": "paragraph", "text": "lead 1"},
                            {"type": "paragraph", "text": "lead 2"},
                            {"type": "block_quote", "text": "quote"},
                            {"type": "paragraph", "text": "credit"},
                            {"type": "expandable_block_quote", "text": "body"},
                            {"type": "paragraph", "text": "CTA"},
                            {
                                "type": "paragraph",
                                "text": (
                                    "swabia articles dependency memmingen "
                                    + old.PAGE_URL
                                ),
                            },
                        ]
                    },
                    "reply_markup": repair.article_button(),
                },
            }

    monkeypatch.setattr(repair, "HttpxLiveTransport", FakeTransport)
    output = repair.execute(args)
    assert output["message_id"] == 1619
    assert len(calls) == 1
    url, payload = calls[0]
    assert url.endswith("/editMessageText")
    assert payload["message_id"] == 1619
    assert "sendMessage" not in url
    assert payload["rich_message"] == {"html": markup}
    assert payload["reply_markup"] == repair.article_button()
    assert entry[repair.RECEIPT_KEY]["state"] == "verified"
    assert len(saved) == 1


def test_missing_article_button_never_records_success(monkeypatch):
    args, ledger, entry, saved = _fixture(monkeypatch, "edit")
    entry[repair.RECEIPT_KEY] = {
        "state": "claimed",
        "run_id": args.run_id,
        "run_attempt": 1,
        "github_sha": args.github_sha,
        "post_sha256": repair._hash(repair.render(_item().channel_post)),
        "message_id": old.MESSAGE_ID,
    }

    class FakeTransport:
        def post_json(self, _url, _body):
            return {
                "ok": True,
                "result": {
                    "message_id": 1619,
                    "chat": {"id": previous.CHAT_ID},
                    "rich_message": {
                        "blocks": [
                            {"type": "paragraph", "text": "swabia articles dependency memmingen"}
                        ] * 8
                    },
                    "reply_markup": {"inline_keyboard": []},
                },
            }

    monkeypatch.setattr(repair, "HttpxLiveTransport", FakeTransport)
    with pytest.raises(RuntimeError, match="readback failed"):
        repair.execute(args)
    assert entry[repair.RECEIPT_KEY]["state"] == "claimed"
    assert saved == []
