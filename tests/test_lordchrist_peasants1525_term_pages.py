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
        stage="claim-page",
        key="swabia",
        run_id="12345",
        run_attempt=1,
        github_sha="f" * 40,
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
    monkeypatch.setattr(terms, "_persist", lambda path, ledger: writes.append((path, ledger)))
    result = terms.execute(args)
    assert result["key"] == "swabia"
    assert entry[terms.RECEIPT_KEY]["pages"]["swabia"]["state"] == "claimed"
    assert len(writes) == 1
    with pytest.raises(RuntimeError):
        terms.execute(args)


def test_claim_next_page_requires_prior_verified_and_checks_public_page(monkeypatch):
    spec = _spec()
    args = Namespace(
        stage="claim-page",
        key="articles",
        run_id="12345",
        run_attempt=1,
        github_sha="f" * 40,
    )
    receipt = {
        "schema": 1,
        "run_id": "12345",
        "run_attempt": 1,
        "github_sha": "f" * 40,
        "source_page": original.PAGE_URL,
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
        "schema": 1,
        "run_id": "12345",
        "run_attempt": 1,
        "github_sha": "f" * 40,
        "source_page": original.PAGE_URL,
        "state": "creating",
        "pages": {},
    }
    entry = {terms.RECEIPT_KEY: receipt}
    monkeypatch.setattr(terms, "_require_execution_context", lambda _: None)
    monkeypatch.setattr(terms, "_context", lambda _: (Path("ledger"), {}, entry, spec))
    with pytest.raises(RuntimeError, match="claim absent"):
        terms.execute(args)


def test_published_mini_page_readback_matches_exact_four_blocks(monkeypatch):
    key = "swabia"
    url = "https://telegra.ph/History-1525-swabia-11-16"

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "ok": True,
                "result": {
                    "url": url,
                    "title": terms.PAGES[key][0],
                    "content": terms.page_nodes(key),
                },
            }

    monkeypatch.setattr(terms.httpx, "get", lambda *a, **k: FakeResponse())
    assert terms.validate_page(key, url)
    assert not terms.validate_page(key, "https://example.com/not-telegraph")


def test_one_shot_create_page_uses_the_retained_account_and_records_receipt(monkeypatch):
    key = "swabia"
    url = "https://telegra.ph/History-1525-swabia-11-16"
    args = Namespace(
        stage="create-page",
        key=key,
        run_id="12345",
        run_attempt=1,
        github_sha="f" * 40,
    )
    receipt = {
        "schema": 1,
        "run_id": "12345",
        "run_attempt": 1,
        "github_sha": "f" * 40,
        "source_page": original.PAGE_URL,
        "pages": {
            key: {
                "state": "claimed",
                "content_sha256": terms._sha((terms.PAGES[key], terms.page_nodes(key))),
            }
        },
    }
    entry = {terms.RECEIPT_KEY: receipt}
    monkeypatch.setattr(terms, "_require_execution_context", lambda _: None)
    monkeypatch.setattr(terms, "_context", lambda _: (Path("ledger"), {}, entry, _spec()))
    monkeypatch.setattr(original, "_prove_owner", lambda *a, **k: None)
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "approved-account-token")
    monkeypatch.setattr(terms, "validate_page", lambda k, u: k == key and u == url)
    writes = []
    monkeypatch.setattr(terms, "_persist", lambda *a: writes.append(True))
    requests = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True, "result": {"url": url}}

    def post(endpoint, **kwargs):
        requests.append((endpoint, kwargs))
        return FakeResponse()

    monkeypatch.setattr(terms.httpx, "post", post)
    result = terms.execute(args)
    assert result["url"] == url
    assert receipt["pages"][key]["state"] == "verified"
    assert len(writes) == 1 and len(requests) == 1
    endpoint, kwargs = requests[0]
    assert endpoint.endswith("/createPage")
    assert kwargs["data"]["access_token"] == "approved-account-token"
    assert kwargs["data"]["author_url"] == "https://t.me/lordchrist"
    with pytest.raises(RuntimeError, match="no replay"):
        terms.execute(args)


def test_telegram_claim_requires_four_verified_mini_pages(monkeypatch):
    urls = _urls()
    args = Namespace(stage="claim-telegram", key="all", run_id="12345", run_attempt=1, github_sha="f" * 40)
    receipt = {
        "schema": 1,
        "run_id": "12345",
        "run_attempt": 1,
        "github_sha": "f" * 40,
        "source_page": original.PAGE_URL,
        "state": "creating",
        "pages": {key: {"state": "verified", "url": url} for key, url in urls.items()},
    }
    entry = {terms.RECEIPT_KEY: receipt}
    monkeypatch.setattr(terms, "_require_execution_context", lambda _: None)
    monkeypatch.setattr(terms, "_context", lambda _: (Path("ledger"), {}, entry, _spec()))
    monkeypatch.setattr(terms, "validate_page", lambda k, u: urls[k] == u)
    monkeypatch.setattr(original, "_post_readback", lambda *a, **k: None)
    monkeypatch.setattr(original, "_telegram_authority", lambda _: ("token", SimpleNamespace()))
    writes = []
    monkeypatch.setattr(terms, "_persist", lambda *a: writes.append(True))
    result = terms.execute(args)
    assert result["message_id"] == 1619
    assert receipt["state"] == "telegram_claimed"
    assert receipt["telegram"]["post_sha256"] == terms._sha(terms.render_post(_spec(), urls))
    assert len(writes) == 1


def test_telegram_edit_uses_only_existing_1619_and_returns_classic_entities(monkeypatch):
    urls = _urls()
    args = Namespace(stage="edit-telegram", key="all", run_id="12345", run_attempt=1, github_sha="f" * 40)
    markup = terms.render_post(_spec(), urls)
    receipt = {
        "schema": 1,
        "run_id": "12345",
        "run_attempt": 1,
        "github_sha": "f" * 40,
        "source_page": original.PAGE_URL,
        "state": "telegram_claimed",
        "pages": {key: {"state": "verified", "url": url} for key, url in urls.items()},
        "telegram": {"state": "claimed", "post_sha256": terms._sha(markup)},
    }
    entry = {terms.RECEIPT_KEY: receipt}
    monkeypatch.setattr(terms, "_require_execution_context", lambda _: None)
    monkeypatch.setattr(terms, "_context", lambda _: (Path("ledger"), {}, entry, _spec()))
    monkeypatch.setattr(original, "_post_readback", lambda *a, **k: None)
    monkeypatch.setattr(
        original,
        "_telegram_authority",
        lambda _: ("token", SimpleNamespace(chat_id=-1001295216957)),
    )
    writes, calls = [], []
    monkeypatch.setattr(terms, "_persist", lambda *a: writes.append(True))

    class FakeTransport:
        def post_json(self, url, payload):
            calls.append((url, payload))
            return {
                "ok": True,
                "result": {
                    "message_id": 1619,
                    "chat": {"id": -1001295216957},
                    "text": "Published article in regular Telegram text",
                    "entities": (
                        [{"type": "text_link", "url": u} for u in urls.values()]
                        + [{"type": "text_link", "url": original.PAGE_URL}]
                        + [{"type": "expandable_blockquote"}]
                    ),
                },
            }

    monkeypatch.setattr(terms, "HttpxLiveTransport", FakeTransport)
    result = terms.execute(args)
    assert result["message_id"] == 1619
    assert receipt["state"] == "verified"
    assert len(writes) == 1 and len(calls) == 1
    endpoint, payload = calls[0]
    assert endpoint.endswith("/editMessageText")
    assert payload["message_id"] == 1619
    assert payload["parse_mode"] == "HTML"
    assert payload["text"] == markup
    assert payload["reply_markup"] == {"inline_keyboard": []}
    assert payload["link_preview_options"]["url"] == original.PAGE_URL
    assert "rich_message" not in payload


def test_reconcile_original_claim_without_second_page_create(monkeypatch):
    key = "swabia"
    url = "https://telegra.ph/Shvabiya-gde-zhili-krestyane-1525-11-16"
    args = Namespace(
        stage="reconcile-swabia", key=key,
        run_id="987654321", run_attempt=1, github_sha="f" * 40,
    )
    first = {
        "state": "claimed",
        "provider_effect": "unknown_until_verified",
        "content_sha256": terms.ORIGINAL_FIRST_CLAIM["content_sha256"],
        "claimed_at_utc": "2026-11-16T14:27:02.022989+00:00",
    }
    receipt = {
        "schema": 1,
        "state": "creating",
        "run_id": terms.ORIGINAL_FIRST_CLAIM["run_id"],
        "github_sha": terms.ORIGINAL_FIRST_CLAIM["github_sha"],
        "run_attempt": 1,
        "source_page": original.PAGE_URL,
        "pages": {key: first},
    }
    entry = {terms.RECEIPT_KEY: receipt}
    writes = []
    monkeypatch.setattr(terms, "_require_execution_context", lambda _: None)
    monkeypatch.setattr(terms, "_context", lambda _: (Path("ledger"), {}, entry, _spec()))
    monkeypatch.setattr(original, "_prove_owner", lambda *a, **k: None)
    monkeypatch.setattr(terms, "_find_one_owned_page", lambda *a: url)
    monkeypatch.setattr(terms, "_wait_exact_page", lambda k, u: k == key and u == url)
    monkeypatch.setattr(terms, "_persist", lambda *a: writes.append(True))
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "retained-account")
    out = terms.execute(args)
    assert out == {"stage": "reconcile-swabia", "key": "swabia", "url": url}
    assert first["state"] == "verified" and first["url"] == url
    assert receipt["original_claim"]["run_id"] == terms.ORIGINAL_FIRST_CLAIM["run_id"]
    assert receipt["run_id"] == args.run_id
    assert receipt["github_sha"] == args.github_sha
    assert len(writes) == 1
    with pytest.raises(RuntimeError, match="Only the original"):
        terms.execute(args)


def test_authenticated_page_list_requires_exact_single_owner_page(monkeypatch):
    key = "swabia"
    url = "https://telegra.ph/Shvabiya-gde-zhili-krestyane-1525-11-16"

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "ok": True,
                "result": {
                    "pages": [
                        {"title": terms.PAGES[key][0], "path": url.removeprefix("https://telegra.ph/"), "url": url}
                    ]
                },
            }

    monkeypatch.setattr(terms.httpx, "post", lambda *a, **k: FakeResponse())
    assert terms._find_one_owned_page("retained-token", key) == url


def test_public_page_can_take_a_short_consistency_window(monkeypatch):
    calls = []
    waits = []

    def validate(key, url):
        calls.append((key, url))
        return len(calls) >= 3

    monkeypatch.setattr(terms, "validate_page", validate)
    monkeypatch.setattr(terms.time, "sleep", lambda seconds: waits.append(seconds))
    assert terms._wait_exact_page("swabia", "https://telegra.ph/History-1525-swabia-11-16")
    assert len(calls) == 3
    assert waits == [2, 5]
