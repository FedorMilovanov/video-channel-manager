"""Editorial and mutation-safety acceptance tests for existing Telegram message 1619."""
from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
import json
import re

import pytest

from video_channel_manager.lordchrist_telegraph_publisher import (
    DEFAULT_QUEUE_PATH, _find_item, build_telegraph_payload, load_telegraph_queue,
)
from video_channel_manager import lordchrist_peasants1525_inplace as old
from video_channel_manager import lordchrist_peasants1525_readability as ux

ROOT = Path(__file__).resolve().parents[1]
MEDIA_BASE = (
    "https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/"
    + ux.BASE_MEDIA_SHA
)


def _real_item_and_page():
    queue = load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)
    item = _find_item(queue, old.PUBLICATION_ID)
    return item, build_telegraph_payload(ROOT, item, media_base_url=MEDIA_BASE)


def test_real_article_no_longer_jumps_to_bottom():
    _, baseline = _real_item_and_page()
    changed, count = ux.improve_nodes(baseline)
    assert count == 11
    assert len(changed.nodes) == len(baseline.nodes)
    assert changed.title == baseline.title
    assert changed.inline_media_urls == baseline.inline_media_urls
    assert changed.cover_url == baseline.cover_url
    s = changed.compact_content_json
    assert "Непривычные названия можно нажать:" not in s
    assert "Нажатие на выделенный термин" not in s
    assert "справочный словарь" in s
    assert old.PAGE_URL + "#" not in s
    assert "Мемминген" in s
    assert "Лютер" in s
    assert "Десятина" in s


def test_native_telegram_popup_links_are_balanced_and_keep_original_article_link():
    item, _ = _real_item_and_page()
    markup = ux.rich_html_for_existing_post(item.channel_post)
    names = re.findall(r'<a href="#([a-z]+)">', markup)
    footnotes = re.findall(r'<tg-reference name="([a-z]+)">', markup)
    assert sorted(names) == sorted(footnotes)
    assert len(names) == 6
    assert old.PAGE_URL in markup
    assert "1525 ГОД: НЕМЕЦКИЕ КРЕСТЬЯНЕ" in markup
    assert "Мы желаем иметь право и власть" in markup
    assert "Полный иллюстрированный очерк" in markup
    assert "кликабельный словарь" not in markup
    assert len(markup.encode("utf-8")) < 32768


def test_footnote_builder_fails_closed_when_editorial_text_changes():
    item, _ = _real_item_and_page()
    broken = SimpleNamespace(**vars(item.channel_post))
    broken.lead_paragraphs = ("Совершенно иная редакция.",)
    with pytest.raises(ValueError, match="anchor is absent or ambiguous"):
        ux.rich_html_for_existing_post(broken)


def test_node_rewriter_fails_closed_if_links_are_not_exact():
    _, baseline = _real_item_and_page()
    baseline.nodes = [dict(tag="p", children=["No glossary here"])]
    with pytest.raises(ValueError, match="Glossary link count drifted"):
        ux.improve_nodes(baseline)


def test_claimed_page_state_does_not_perform_any_provider_mutation(monkeypatch):
    item, baseline = _real_item_and_page()
    args = Namespace(
        stage="prepare-page", repo_root=ROOT, ledger=Path("state.json"),
        publication_id=old.PUBLICATION_ID, media_base_url=MEDIA_BASE,
        run_id="445566", run_attempt=1, github_sha="f" * 40,
    )
    entry = {
        "peasants1525_glossary_v2_revision": {
            "state": "verified", "page_provider_effect": "verified",
            "telegram_provider_effect": "verified",
        }
    }
    ledger = {"entries": {old.PUBLICATION_ID: entry}}
    monkeypatch.setattr(ux, "_require_execution_context", lambda args: None)
    monkeypatch.setattr(
        old, "_target", lambda args: (Path("state.json"), ledger, entry, item, baseline)
    )
    checks = []
    monkeypatch.setattr(old, "_proof_reconciled_page", lambda page: checks.append("page"))
    monkeypatch.setattr(old, "_post_readback", lambda *args: checks.append("post"))
    monkeypatch.setattr(old, "_prove_owner", lambda *args, **kwargs: checks.append("owner"))
    monkeypatch.setattr(old, "_telegram_authority", lambda args: checks.append("authority"))
    monkeypatch.setattr(ux, "save_ledger", lambda path, data: checks.append("saved"))
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "test-token")
    out = ux.execute(args)
    assert out["claim_persist_required"]
    assert checks == ["page", "post", "owner", "authority", "saved"]
    assert entry[ux.RECEIPT_KEY]["state"] == "page_claimed"
    with pytest.raises(RuntimeError, match="already claimed"):
        ux.execute(args)


def test_exact_message_edit_is_rich_and_never_sends_new_message(monkeypatch):
    item, baseline = _real_item_and_page()
    target, _ = ux.improve_nodes(baseline)
    rich = ux.rich_html_for_existing_post(item.channel_post)
    args = Namespace(
        stage="edit-telegram", repo_root=ROOT, ledger=Path("state.json"),
        publication_id=old.PUBLICATION_ID, media_base_url=MEDIA_BASE,
        run_id="445566", run_attempt=1, github_sha="f" * 40,
    )
    entry = {
        "peasants1525_glossary_v2_revision": {
            "state": "verified", "page_provider_effect": "verified",
            "telegram_provider_effect": "verified",
        },
        ux.RECEIPT_KEY: {
            "state": "telegram_claimed", "run_id": args.run_id,
            "run_attempt": args.run_attempt, "github_sha": args.github_sha,
            "page_url": old.PAGE_URL, "message_id": old.MESSAGE_ID,
            "target_page_sha256": ux._digest(target.compact_content_json),
            "target_post_sha256": ux._digest(rich),
        },
    }
    ledger = {"entries": {old.PUBLICATION_ID: entry}}
    monkeypatch.setattr(ux, "_require_execution_context", lambda args: None)
    monkeypatch.setattr(
        old, "_target", lambda args: (Path("state.json"), ledger, entry, item, baseline)
    )
    monkeypatch.setattr(old, "_proof_reconciled_page", lambda page: None)
    monkeypatch.setattr(old, "_post_readback", lambda *args: None)
    monkeypatch.setattr(
        old, "_telegram_authority",
        lambda args: ("fake-token", SimpleNamespace(chat_id=ux.CHAT_ID)),
    )
    monkeypatch.setattr(ux, "save_ledger", lambda path, data: None)
    calls = []
    class FakeTransport:
        def post_json(self, url, payload):
            calls.append((url, payload))
            return {
                "ok": True,
                "result": {
                    "message_id": old.MESSAGE_ID,
                    "chat": {"id": ux.CHAT_ID},
                    "rich_message": {
                        "blocks": [
                            {"type": "paragraph", "text": [
                                {"type": "reference_link", "reference_name": "swabia"},
                                {"type": "reference", "name": "articles"},
                                {"type": "reference_link", "reference_name": "dependency"},
                            ]}
                        ]
                    },
                },
            }
    monkeypatch.setattr(ux, "HttpxLiveTransport", FakeTransport)
    result = ux.execute(args)
    assert result["message_id"] == 1619
    assert len(calls) == 1
    url, payload = calls[0]
    assert url.endswith("/editMessageText")
    assert payload["message_id"] == 1619
    assert "text" not in payload and "parse_mode" not in payload
    assert payload["rich_message"] == {"html": rich}
    assert entry[ux.RECEIPT_KEY]["state"] == "verified"
