"""Accept four mini-articles and one classic, in-place Telegram edit (no Rich Messages)."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

from video_channel_manager import lordchrist_peasants1525_term_pages as terms
from video_channel_manager import lordchrist_peasants1525_inplace as original
from video_channel_manager.lordchrist_telegraph_publisher import (
    DEFAULT_QUEUE_PATH,
    _find_item,
    load_telegraph_queue,
)

ROOT = Path(__file__).resolve().parents[1]


def _spec():
    queue = load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)
    return _find_item(queue, original.PUBLICATION_ID).channel_post


def _urls():
    return {k: f"https://telegra.ph/History-1525-{k}-11-16" for k in terms.PAGE_KEYS}


def test_exact_four_brief_pages_with_existing_primary_sources():
    assert terms.PAGE_KEYS == ("swabia", "articles", "dependency", "memmingen")
    for key in terms.PAGE_KEYS:
        title, meaning, detail = terms.PAGES[key]
        nodes = terms.page_nodes(key)
        assert title and meaning and detail
        assert len(nodes) == 4
        assert nodes[0]["children"] == [meaning]
        assert nodes[1]["children"] == [detail]
        assert original.PAGE_URL in str(nodes)
        assert terms.SOURCE_URL in str(nodes)
        assert len(meaning) + len(detail) < 800


def test_short_pages_are_not_jumps_to_bottom_of_long_article():
    for key in terms.PAGE_KEYS:
        assert not any("#" in str(node) and original.PAGE_URL in str(node) for node in terms.page_nodes(key))


def test_normal_telegram_post_preserves_quotes_paragraphs_and_article_at_bottom():
    markup = terms.render_post(_spec(), _urls())
    assert markup.startswith("<b>1525 ГОД:")
    assert "Юг современной Германии" in markup
    assert markup.count("\n\n") == 9
    assert markup.count("<blockquote") == 2
    assert "<blockquote expandable>" in markup
    assert "Лютера" in markup
    assert "пастора" in markup
    assert markup.count("<a href=") == 5
    assert "<tg-reference" not in markup
    assert "<tg-button" not in markup
    assert "Полный иллюстрированный очерк" not in markup
    assert markup.endswith("Читать полную иллюстрированную статью</a>")
    for key, url in _urls().items():
        assert markup.count(f'href="{url}"') == 1, key
    assert f'href="{original.PAGE_URL}"' in markup


def test_invalid_or_incomplete_links_fail_closed():
    spec = _spec()
    with pytest.raises(ValueError, match="four"):
        terms.render_post(spec, {"swabia": "https://telegra.ph/only-one"})
    bad = _urls()
    bad["memmingen"] = "https://wrong.domain/incorrect"
    with pytest.raises(ValueError, match="Invalid"):
        terms.render_post(spec, bad)


def test_owner_and_stage_receipts_never_allow_accidental_replay():
    args = Namespace(run_id="12345", run_attempt=1, github_sha="f" * 40)
    entry = {
        terms.RECEIPT_KEY: {
            "schema": 1,
            "run_id": "12345",
            "run_attempt": 1,
            "github_sha": "f" * 40,
            "source_page": original.PAGE_URL,
        }
    }
    assert terms._owner(args, entry)["schema"] == 1
    args.run_id = "98765"
    with pytest.raises(RuntimeError, match="another execution"):
        terms._owner(args, entry)


def test_claim_only_writes_ledger_and_never_creates_page(monkeypatch):
    spec = _spec()
    args = Namespace(
        stage="claim-page", key="swabia",
        run_id="12345", run_attempt=1, github_sha="f" * 40,
    )
    ledger = {"entries": {}}
    entry = {}
    writes = []
    monkeypatch.setattr(terms, "_require_execution_context", lambda _: None)
    monkeypatch.setattr(
        terms,
        "_context",
        lambda _: (Path("ledger.json"), ledger, entry, spec),
    )
    monkeypatch.setattr(original, "_prove_owner", lambda *a, **k: None)
    monkeypatch.setattr(original, "_telegram_authority", lambda _: ("token", SimpleNamespace()))
    monkeypatch.setattr(original, "_post_readback", lambda *a, **k: None)
    monkeypatch.setattr(terms, "_persist", lambda p, l: writes.append((p, l)))
    result = terms.execute(args)
    assert result["key"] == "swabia"
    assert entry[terms.RECEIPT_KEY]["pages"]["swabia"]["state"] == "claimed"
    assert len(writes) == 1
    with pytest.raises(RuntimeError):
        terms.execute(args)


def test_claim_next_page_requires_prior_verified_and_checks_public_page(monkeypatch):
    spec = _spec()
    args = Namespace(
        stage="claim-page", key="articles",
        run_id="12345", run_attempt=1, github_sha="f" * 40,
    )
    receipt = {
        "schema": 1, "run_id": "12345", "run_attempt": 1,
        "github_sha": "f" * 40, "source_page": original.PAGE_URL,
        "pages": {"swabia": {"state": "claimed"}},
    }
    entry = {terms.RECEIPT_KEY: receipt}
    monkeypatch.setattr(terms, "_require_execution_context", lambda _: None)
    monkeypatch.setattr(terms, "_context", lambda _: (Path("ledger"), {}, entry, spec))
    with pytest.raises(RuntimeError, match="order"):
        terms.execute(args)


def test_telegram_mutation_requires_exact_claim_and_five_verified_links(monkeypatch):
    spec = _spec()
    args = Namespace(stage="edit-telegram", key="all", run_id="12345", run_attempt=1, github_sha="f" * 40)
    receipt = {
        "schema": 1, "run_id": "12345", "run_attempt": 1,
        "github_sha": "f" * 40, "source_page": original.PAGE_URL,
        "state": "creating", "pages": {},
    }
    entry = {terms.RECEIPT_KEY: receipt}
    monkeypatch.setattr(terms, "_require_execution_context", lambda _: None)
    monkeypatch.setattr(terms, "_context", lambda _: (Path("ledger"), {}, entry, spec))
    with pytest.raises(RuntimeError, match="claim absent"):
        terms.execute(args)
