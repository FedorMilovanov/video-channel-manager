"""Incident recovery: eight original posts deleted, never repeat the 2026-11-05 burst."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from video_channel_manager import lordchrist_charnock_reschedule as m

ARTICLE = "lordchrist-telegraph-charnock-06"
URL = "https://telegra.ph/Reviewed-Charnock-11-05"
DATE = "2026-11-10"
MESSAGE = 1596
CHAT = -1001295216957
SHA = "a" * 40
PAYLOAD_SHA = "sha256:reviewed"


def _at_noon() -> datetime:
    return datetime(2026, 11, 10, 12, 0, tzinfo=m.MOSCOW)


def setup(monkeypatch: pytest.MonkeyPatch, root: Path, *, existing_reissue: str | None = None):
    content = b"reviewed article bytes"
    blob = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
    source = {
        "publication_id": ARTICLE,
        "scheduled_on_moscow": DATE,
        "article_git_blob_sha": blob,
        "source_article_sha256": PAYLOAD_SHA,
        "verified_telegraph_url": URL,
        "deleted_telegram_message_id": MESSAGE,
    }
    (root / m.MANIFEST).parent.mkdir(parents=True, exist_ok=True)
    (root / m.MANIFEST).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "channel": "@lordchrist",
                "timezone": "Europe/Moscow",
                "release_time": "12:00",
                "items": [source]
                + [
                    {**source, "scheduled_on_moscow": f"2026-12-{j:02d}", "publication_id": f"other-{j}"}
                    for j in range(1, 8)
                ],
            }
        ),
        encoding="utf-8",
    )
    file = root / "article.json"
    file.write_bytes(content)
    item = SimpleNamespace(
        is_ready=True,
        article_path=Path("article.json"),
        article_blob=blob,
        scheduled_on=_at_noon().date(),
        channel_post=object(),
    )
    original = {
        "state": "published",
        "provider_effect": "verified",
        "telegram_message_id": MESSAGE,
        "telegram_chat_id": CHAT,
        "telegraph_url": URL,
        "article_sha256": PAYLOAD_SHA,
        "github_sha": SHA,
    }
    if existing_reissue:
        original["scheduled_reissue"] = {
            "state": existing_reissue,
            "provider_effect": "verified_by_api" if existing_reissue == "sent" else "may_exist_until_reconciled",
            "run_id": "421",
            "run_attempt": 1,
            "github_sha": SHA,
            "source_article_sha256": PAYLOAD_SHA,
            "telegraph_url": URL,
            "scheduled_on_moscow": DATE,
            "new_message_id": 1701,
        }
    ledger = {"entries": {ARTICLE: original}}
    args = argparse.Namespace(
        stage="prepare",
        repo_root=root,
        ledger=root / "ledger.json",
        publication_id=ARTICLE,
        run_id="421",
        run_attempt=1,
        github_sha=SHA,
        now=None,
    )

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return _at_noon()

    monkeypatch.setattr(m, "datetime", Clock)
    monkeypatch.setattr(m, "_require_execution_context", lambda _: None)
    monkeypatch.setattr(m, "_ledger", lambda _: (args.ledger, ledger))
    monkeypatch.setattr(m, "load_telegraph_queue", lambda *_: [item])
    monkeypatch.setattr(m, "_find_item", lambda *_: item)
    monkeypatch.setattr(
        m, "build_telegraph_payload", lambda *a, **k: SimpleNamespace(article_sha256=PAYLOAD_SHA, title="Reviewed")
    )
    monkeypatch.setattr(m, "save_ledger", lambda *a: None)
    monkeypatch.setattr(m, "_prove_owner_deletion", lambda *_: None)
    monkeypatch.setattr(m, "_proof_page", lambda *_: None)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    return args, ledger, original, source


def test_article_13_quote_gaps_block_scheduled_release_before_any_provider_call(monkeypatch, tmp_path):
    args, _, original, _ = setup(monkeypatch, tmp_path)
    manifest_path = tmp_path / m.MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["items"][0]["publication_id"] = "lordchrist-telegraph-charnock-13"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    args.publication_id = "lordchrist-telegraph-charnock-13"
    monkeypatch.setattr(m, "_prove_owner_deletion", lambda *_: pytest.fail("No provider read during editorial HOLD"))
    for stage in ("prepare", "send"):
        args.stage = stage
        with pytest.raises(RuntimeError, match="TELEGRAM SEND HOLD"):
            m.execute(args)
        assert "scheduled_reissue" not in original


def test_refuses_manual_publishing_even_with_correct_future_date(monkeypatch, tmp_path):
    args, _, _, _ = setup(monkeypatch, tmp_path)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    # GitHub CI supplies the real repository owner's actor by default.
    # Explicitly simulate a different actor to exercise this negative gate.
    monkeypatch.setenv("GITHUB_ACTOR", "unapproved-external-actor")
    with pytest.raises(RuntimeError, match="owner-only dispatch"):
        m.execute(args)


def test_refuses_wrong_day_and_any_non_noon_hour(monkeypatch, tmp_path):
    args, ledger, _, _ = setup(monkeypatch, tmp_path)
    with pytest.raises(RuntimeError, match="allowed only"):
        m._select_due(args, ledger, now=datetime(2026, 11, 10, 7, tzinfo=m.MOSCOW))
    with pytest.raises(RuntimeError, match="due today"):
        m._select_due(args, ledger, now=datetime(2026, 11, 13, 12, tzinfo=m.MOSCOW))


def test_claim_preserves_original_and_prevents_duplicate(monkeypatch, tmp_path):
    args, ledger, original, _ = setup(monkeypatch, tmp_path)
    got = m.execute(args)
    assert got["stage"] == "claimed"
    assert original["telegram_message_id"] == MESSAGE
    assert original["telegraph_url"] == URL
    assert original["scheduled_reissue"]["state"] == "claimed"
    with pytest.raises(RuntimeError, match="already exists"):
        m.execute(args)


def test_original_live_message_blocks_new_claim(monkeypatch, tmp_path):
    args, _, original, _ = setup(monkeypatch, tmp_path)
    monkeypatch.setattr(m, "_prove_owner_deletion", lambda *_: (_ for _ in ()).throw(RuntimeError("still visible")))
    with pytest.raises(RuntimeError, match="still visible"):
        m.execute(args)
    assert "scheduled_reissue" not in original


def test_immutable_source_blob_and_page_mismatch_blocks_claim(monkeypatch, tmp_path):
    args, ledger, original, _ = setup(monkeypatch, tmp_path)
    (tmp_path / "article.json").write_bytes(b"new unreviewed content")
    with pytest.raises(RuntimeError, match="bytes changed"):
        m._select_due(args, ledger, now=_at_noon())
    assert "scheduled_reissue" not in original


@pytest.mark.parametrize(("stage", "receipt"), [("prepare", None), ("send", "claimed")])
def test_changed_authored_heading_blocks_claim_and_send_without_mutation(monkeypatch, tmp_path, stage, receipt):
    real_proof = m._proof_page
    args, ledger, original, _ = setup(monkeypatch, tmp_path, existing_reissue=receipt)
    args.stage = stage
    payload = SimpleNamespace(
        article_sha256=PAYLOAD_SHA,
        title="Reviewed",
        author_name="A",
        author_url="https://example.invalid/author",
        nodes=[{"tag": "h3", "attrs": {"id": "reviewed"}, "children": ["Heading"]}],
    )
    page = {
        "path": URL.removeprefix("https://telegra.ph/"),
        "url": URL,
        "title": payload.title,
        "author_name": payload.author_name,
        "author_url": payload.author_url,
        "content": [{"tag": "h3", "attrs": {"id": "changed"}, "children": ["Heading"]}],
    }
    monkeypatch.setattr(m, "_proof_page", real_proof)
    monkeypatch.setattr(m, "build_telegraph_payload", lambda *a, **k: payload)
    monkeypatch.setattr(
        m.httpx,
        "get",
        lambda *a, **k: SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"ok": True, "result": page}),
    )
    monkeypatch.setattr(m, "HttpxLiveTransport", lambda: pytest.fail("Telegram must not be contacted"))
    monkeypatch.setattr(m, "save_ledger", lambda *a: pytest.fail("Ledger must not be written"))
    before = copy.deepcopy(ledger)
    with pytest.raises(RuntimeError, match="entire reviewed latest"):
        m.execute(args)
    assert ledger == before
    if receipt is None:
        assert "scheduled_reissue" not in original
    else:
        assert original["scheduled_reissue"]["state"] == "claimed"


def test_one_verified_telegram_send_and_no_replay(monkeypatch, tmp_path):
    args, ledger, original, _ = setup(monkeypatch, tmp_path, existing_reissue="claimed")
    args.stage = "send"
    monkeypatch.setenv("LORDCHRIST_TELEGRAM_BOT_TOKEN", "test-only-token")
    monkeypatch.setattr(
        m,
        "load_channel_profile",
        lambda *_: SimpleNamespace(bot_token_env="LORDCHRIST_TELEGRAM_BOT_TOKEN"),
    )
    monkeypatch.setattr(
        m,
        "load_target_binding",
        lambda *a, **k: SimpleNamespace(bot_id=8716602202, chat_id=CHAT),
    )
    monkeypatch.setattr(
        m,
        "render_channel_post",
        lambda *a, **k: SimpleNamespace(html_text="Reviewed", visible_char_count=92),
    )
    calls = []

    class Transport:
        def read_json(self, url, body):
            if url.endswith("/getMe"):
                return {"ok": True, "result": {"id": 8716602202, "username": "preaching_mp3_bot"}}
            if url.endswith("/getChat"):
                return {"ok": True, "result": {"id": CHAT, "username": "lordchrist", "type": "channel"}}
            raise AssertionError(url)

        def post_json(self, url, body):
            calls.append((url, body))
            return {
                "ok": True,
                "result": {
                    "message_id": 1701,
                    "chat": {"id": CHAT},
                    "entities": [{"type": "text_link", "url": URL}],
                },
            }

    monkeypatch.setattr(m, "HttpxLiveTransport", Transport)
    assert m.execute(args)["message_id"] == 1701
    assert original["telegram_message_id"] == MESSAGE
    assert original["scheduled_reissue"]["state"] == "sent"
    assert calls[0][0].endswith("/sendMessage")
    assert calls[0][1]["link_preview_options"]["url"] == URL
    with pytest.raises(RuntimeError, match="already attempted"):
        m.execute(args)
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("effect", "message_id"),
    [
        ("may_exist_until_reconciled", 1701),
        ("unverified", 1701),
        (None, 1701),
        ("verified_by_api", MESSAGE),
        ("verified_by_api", True),
        ("verified_by_api", 0),
    ],
)
def test_verify_requires_api_ack_and_distinct_numeric_id_before_any_public_read(
    monkeypatch, tmp_path, effect, message_id
):
    args, ledger, original, _ = setup(monkeypatch, tmp_path, existing_reissue="sent")
    args.stage = "verify"
    receipt = original["scheduled_reissue"]
    receipt["provider_effect"] = effect
    receipt["new_message_id"] = message_id
    snapshot = copy.deepcopy(ledger)
    monkeypatch.setattr(m, "_prove_new_public_post", lambda **_: pytest.fail("No provider readback on invalid receipt"))
    monkeypatch.setattr(m, "save_ledger", lambda *a: pytest.fail("No durable ledger write on invalid receipt"))
    with pytest.raises(RuntimeError, match="provider-acknowledged"):
        m.execute(args)
    assert ledger == snapshot


def test_verification_requires_public_readback_and_no_resend(monkeypatch, tmp_path):
    args, ledger, original, _ = setup(monkeypatch, tmp_path, existing_reissue="sent")
    args.stage = "verify"
    calls = []

    class Response:
        text = f'<div data-post="lordchrist/1701"><a href="{URL}">Read article</a></div>'

        def raise_for_status(self):
            pass

    def public_get(url, **kwargs):
        calls.append(url)
        return Response()

    monkeypatch.setattr(m.httpx, "get", public_get)
    monkeypatch.setattr(m, "HttpxLiveTransport", lambda: pytest.fail("Unexpected provider send"))
    assert m.execute(args)["stage"] == "verified"
    assert original["scheduled_reissue"]["state"] == "verified"
    assert calls == ["https://t.me/lordchrist/1701?embed=1"]


def test_verification_failure_keeps_sent_without_replay(monkeypatch, tmp_path):
    args, _, original, _ = setup(monkeypatch, tmp_path, existing_reissue="sent")
    args.stage = "verify"
    calls = []
    delays = []
    monkeypatch.setattr(m.time, "sleep", delays.append)

    def stale(url, **kwargs):
        calls.append(url)
        return SimpleNamespace(text="Unavailable", raise_for_status=lambda: None)

    monkeypatch.setattr(m.httpx, "get", stale)
    monkeypatch.setattr(m, "HttpxLiveTransport", lambda: pytest.fail("Never replay sendMessage"))
    with pytest.raises(RuntimeError, match="reconcile the existing send receipt"):
        m.execute(args)
    assert original["scheduled_reissue"]["state"] == "sent"
    assert calls == ["https://t.me/lordchrist/1701?embed=1"] * len(m.NEW_POST_PUBLIC_READBACK_DELAYS)
    assert delays == list(m.NEW_POST_PUBLIC_READBACK_DELAYS[1:])


def test_no_write_before_live_schedule_and_no_forged_clock(monkeypatch, tmp_path):
    args, _, _, _ = setup(monkeypatch, tmp_path)
    args.now = "2026-11-10T12:00:00+03:00"
    with pytest.raises(RuntimeError, match="Forged clock forbidden"):
        m.execute(args)
    args.stage = "preview"
    result = m.execute(args)
    assert result["date"] == DATE
    assert result["article_sha256"] == PAYLOAD_SHA


def test_telegraph_readback_normalization_preserves_all_words_and_nodes():
    source = [
        {"tag": "h3", "children": ["Heading"]},
        {"tag": "blockquote", "children": ["A", {"tag": "em", "children": ["B"]}, " C", " D", {"tag": "br"}, "E"]},
    ]
    provider = [
        {"tag": "h3", "attrs": {"id": "Heading"}, "children": ["Heading"]},
        {"tag": "blockquote", "children": ["A", {"tag": "em", "children": ["B"]}, " C D", {"tag": "br"}, "E"]},
    ]
    assert m._normalized_telegraph_node(source) == m._normalized_telegraph_node(provider)
    provider[1]["children"][-1] = "Changed"
    assert m._normalized_telegraph_node(source) != m._normalized_telegraph_node(provider)


def test_telegra_ph_api_must_match_entire_last_reviewed_page(monkeypatch):
    source = {"verified_telegraph_url": URL}
    document = SimpleNamespace(
        title="Reviewed",
        author_name="Господь Бог",
        author_url="https://t.me/lordchrist",
        nodes=[{"tag": "p", "children": ["Full approved text"]}],
    )

    def fake_page(url, **kwargs):
        assert url == "https://api.telegra.ph/getPage/Reviewed-Charnock-11-05?return_content=true"
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "ok": True,
                "result": {
                    "path": "Reviewed-Charnock-11-05",
                    "url": URL,
                    "title": "Reviewed",
                    "author_name": "Господь Бог",
                    "author_url": "https://t.me/lordchrist",
                    "content": [{"tag": "p", "children": ["Full approved text"]}],
                },
            },
        )

    monkeypatch.setattr(m.httpx, "get", fake_page)
    m._proof_page(source, document)
    document.nodes[0]["children"] = ["A different revision"]
    with pytest.raises(RuntimeError, match="entire reviewed latest"):
        m._proof_page(source, document)


@pytest.mark.parametrize("field", ["path", "url", "title", "author_name", "author_url"])
def test_page_proof_refuses_wrong_or_missing_identity(monkeypatch, field):
    source = {"verified_telegraph_url": URL}
    payload = SimpleNamespace(
        title="Reviewed",
        author_name="Господь Бог",
        author_url="https://t.me/lordchrist",
        nodes=[{"tag": "p", "children": ["Exact"]}],
    )
    page = {
        "path": "Reviewed-Charnock-11-05",
        "url": URL,
        "title": payload.title,
        "author_name": payload.author_name,
        "author_url": payload.author_url,
        "content": payload.nodes,
    }
    monkeypatch.setattr(
        m.httpx,
        "get",
        lambda *a, **k: SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"ok": True, "result": page}),
    )
    m._proof_page(source, payload)
    page[field] = "unexpected"
    with pytest.raises(RuntimeError, match="entire reviewed latest"):
        m._proof_page(source, payload)
    del page[field]
    with pytest.raises(RuntimeError, match="entire reviewed latest"):
        m._proof_page(source, payload)


def test_normalized_page_digest_checks_json_types_and_only_provider_normalizations():
    reviewed = [{"tag": "h3", "children": ["A", " B"]}, {"tag": "img", "attrs": {"src": "https://a", "v": 1}}]
    live = [
        {"tag": "h3", "attrs": {"id": "A-B"}, "children": ["A B"]},
        {"tag": "img", "attrs": {"src": "https://a", "v": 1}},
    ]
    assert m._normalized_telegraph_digest(live) == m._normalized_telegraph_digest(reviewed)
    live[1]["attrs"]["v"] = True
    assert m._normalized_telegraph_node(live) == m._normalized_telegraph_node(reviewed)
    assert m._normalized_telegraph_digest(live) != m._normalized_telegraph_digest(reviewed)
    live[1]["attrs"]["v"] = float("nan")
    with pytest.raises(RuntimeError, match="Malformed normalized Telegraph"):
        m._normalized_telegraph_digest(live)


def test_normalization_does_not_erase_attribute_values_or_mutate_input():
    reviewed = [
        {
            "tag": "h3",
            "attrs": {"id": "authored-id", "data": ["one", "two"], "nested": {"tag": "h3", "attrs": {"id": "x"}}},
            "children": ["A", " B"],
        }
    ]
    original = copy.deepcopy(reviewed)
    normalized = m._normalized_telegraph_node(reviewed)
    assert reviewed == original
    assert normalized[0]["attrs"] == {"data": ["one", "two"], "nested": {"tag": "h3", "attrs": {"id": "x"}}}
    assert normalized[0]["children"] == ["A B"]

    altered = copy.deepcopy(reviewed)
    altered[0]["attrs"]["data"] = ["onetwo"]
    assert m._normalized_telegraph_digest(reviewed) != m._normalized_telegraph_digest(altered)
    altered = copy.deepcopy(reviewed)
    altered[0]["attrs"]["nested"]["attrs"]["id"] = "changed"
    assert m._normalized_telegraph_digest(reviewed) != m._normalized_telegraph_digest(altered)
    assert m._normalized_telegraph_digest([{"tag": "h3", "attrs": {}}]) != m._normalized_telegraph_digest(
        [{"tag": "h3"}]
    )
    # An authored heading ID is indistinguishable from a provider-generated one.
    altered = copy.deepcopy(reviewed)
    altered[0]["attrs"]["id"] = "another-heading-id"
    assert m._normalized_telegraph_digest(reviewed) == m._normalized_telegraph_digest(altered)


def test_page_proof_refuses_python_equal_but_json_distinct_attributes(monkeypatch):
    source = {"verified_telegraph_url": URL}
    nodes = [{"tag": "p", "attrs": {"hidden": 1}, "children": ["Exact"]}]
    payload = SimpleNamespace(title="Reviewed", author_name="A", author_url="https://a", nodes=nodes)
    page = {
        "path": "Reviewed-Charnock-11-05",
        "url": URL,
        "title": payload.title,
        "author_name": payload.author_name,
        "author_url": payload.author_url,
        "content": [{"tag": "p", "attrs": {"hidden": True}, "children": ["Exact"]}],
    }
    monkeypatch.setattr(
        m.httpx,
        "get",
        lambda *a, **k: SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"ok": True, "result": page}),
    )
    with pytest.raises(RuntimeError, match="entire reviewed latest"):
        m._proof_page(source, payload)


def test_delayed_public_telegram_message_is_verified_without_second_send(monkeypatch, tmp_path):
    args, _, original, _ = setup(monkeypatch, tmp_path, existing_reissue="sent")
    args.stage = "verify"
    attempts = []
    delays = []

    def delayed(url, **kwargs):
        attempts.append((url, kwargs))
        if len(attempts) < 4:
            return SimpleNamespace(text="Temporarily unavailable", raise_for_status=lambda: None)
        return SimpleNamespace(
            text=f'<div data-post="lordchrist/1701"><a href="{URL}">Full article</a></div>',
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(m.httpx, "get", delayed)
    monkeypatch.setattr(m.time, "sleep", delays.append)
    monkeypatch.setattr(m, "HttpxLiveTransport", lambda: pytest.fail("No Telegram writes on verify"))
    assert m.execute(args)["stage"] == "verified"
    assert original["scheduled_reissue"]["new_message_id"] == 1701
    assert original["scheduled_reissue"]["state"] == "verified"
    assert len(attempts) == 4
    assert delays == [2, 4, 8]


def test_public_verification_recovers_from_temporary_http_failure(monkeypatch, tmp_path):
    args, _, original, _ = setup(monkeypatch, tmp_path, existing_reissue="sent")
    args.stage = "verify"
    reads = []

    def public_get(url, **kwargs):
        reads.append(url)
        if len(reads) == 1:
            raise m.httpx.TimeoutException("Telegram widget did not respond")
        return SimpleNamespace(
            text=f'<div data-post="lordchrist/1701"><a href="{URL}">Full article</a></div>',
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(m.httpx, "get", public_get)
    monkeypatch.setattr(m.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(m, "HttpxLiveTransport", lambda: pytest.fail("No provider call after acknowledged send"))
    assert m.execute(args)["stage"] == "verified"
    assert len(reads) == 2
    assert original["scheduled_reissue"]["state"] == "verified"


def test_public_verification_refuses_wrong_telegraph_revision(monkeypatch, tmp_path):
    args, _, original, _ = setup(monkeypatch, tmp_path, existing_reissue="sent")
    args.stage = "verify"
    calls = []

    def wrong_url(url, **kwargs):
        calls.append(url)
        return SimpleNamespace(
            text='<div data-post="lordchrist/1701"><a href="https://telegra.ph/Old-stale-revision">Old</a></div>',
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(m.httpx, "get", wrong_url)
    monkeypatch.setattr(m.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(m, "HttpxLiveTransport", lambda: pytest.fail("Never repeat provider send"))
    with pytest.raises(RuntimeError, match="reconcile the existing send receipt"):
        m.execute(args)
    assert original["scheduled_reissue"]["state"] == "sent"
    assert len(calls) == len(m.NEW_POST_PUBLIC_READBACK_DELAYS)


def test_redundant_schedule_readback_is_idempotent_and_fail_closed(monkeypatch, tmp_path):
    _, ledger, original, source = setup(monkeypatch, tmp_path)
    assert m.scheduled_reissue_preflight_status(ledger, source) == "unclaimed"
    original["scheduled_reissue"] = {
        "state": "verified",
        "provider_effect": "verified",
        "new_message_id": 1701,
        "scheduled_on_moscow": source["scheduled_on_moscow"],
        "original_deleted_message_id": source["deleted_telegram_message_id"],
        "source_article_sha256": source["source_article_sha256"],
        "telegraph_url": source["verified_telegraph_url"],
    }
    assert m.scheduled_reissue_preflight_status(ledger, source) == "verified"
    original["scheduled_reissue"]["state"] = "sent"
    with pytest.raises(RuntimeError, match="reconcile without resend"):
        m.scheduled_reissue_preflight_status(ledger, source)
    original["scheduled_reissue"]["state"] = "verified"
    original["scheduled_reissue"]["telegraph_url"] = "https://telegra.ph/Other-revision"
    with pytest.raises(RuntimeError, match="reconcile without resend"):
        m.scheduled_reissue_preflight_status(ledger, source)
    del ledger["entries"][ARTICLE]
    with pytest.raises(RuntimeError, match="original publication receipt missing"):
        m.scheduled_reissue_preflight_status(ledger, source)


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("state", "unknown"),
        ("provider_effect", "unverified"),
        ("telegram_message_id", MESSAGE + 1),
        ("telegram_chat_id", CHAT + 1),
        ("telegraph_url", "https://telegra.ph/Wrong-original"),
        ("article_sha256", "sha256:wrong-original"),
    ],
)
def test_verified_reissue_does_not_hide_damaged_original_receipt(monkeypatch, tmp_path, field, wrong):
    _, ledger, original, source = setup(monkeypatch, tmp_path)
    original["scheduled_reissue"] = {
        "state": "verified",
        "provider_effect": "verified",
        "new_message_id": 1701,
        "scheduled_on_moscow": source["scheduled_on_moscow"],
        "original_deleted_message_id": source["deleted_telegram_message_id"],
        "source_article_sha256": source["source_article_sha256"],
        "telegraph_url": source["verified_telegraph_url"],
    }
    assert m.scheduled_reissue_preflight_status(ledger, source) == "verified"
    original[field] = wrong
    snapshot = copy.deepcopy(ledger)
    with pytest.raises(RuntimeError, match="reconcile without resend"):
        m.scheduled_reissue_preflight_status(ledger, source)
    assert ledger == snapshot


@pytest.mark.parametrize("replacement_message_id", [MESSAGE, 0, True])
def test_terminal_reissue_requires_distinct_real_new_message_id(monkeypatch, tmp_path, replacement_message_id):
    _, ledger, original, source = setup(monkeypatch, tmp_path)
    original["scheduled_reissue"] = {
        "state": "verified",
        "provider_effect": "verified",
        "new_message_id": replacement_message_id,
        "scheduled_on_moscow": source["scheduled_on_moscow"],
        "original_deleted_message_id": source["deleted_telegram_message_id"],
        "source_article_sha256": source["source_article_sha256"],
        "telegraph_url": source["verified_telegraph_url"],
    }
    snapshot = copy.deepcopy(ledger)
    with pytest.raises(RuntimeError, match="reconcile without resend"):
        m.scheduled_reissue_preflight_status(ledger, source)
    assert ledger == snapshot


def test_late_same_day_readback_finishes_without_any_second_send(monkeypatch, tmp_path):
    args, ledger, original, _ = setup(monkeypatch, tmp_path, existing_reissue="sent")
    args.stage = "verify"
    late = datetime(2026, 11, 10, 14, 2, tzinfo=m.MOSCOW)

    class AfterWindowClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return late

    monkeypatch.setattr(m, "datetime", AfterWindowClock)
    reads = []

    def read_public(url, **kwargs):
        reads.append(url)
        return SimpleNamespace(
            text=f'<div data-post="lordchrist/1701"><a href="{URL}">Read article</a></div>',
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(m.httpx, "get", read_public)
    monkeypatch.setattr(m, "HttpxLiveTransport", lambda: pytest.fail("No POST permitted after 13:59"))
    assert m.execute(args)["stage"] == "verified"
    assert original["scheduled_reissue"]["state"] == "verified"
    assert reads == ["https://t.me/lordchrist/1701?embed=1"]

    # Late duplicate verification may not rewrite even the protected state.
    with pytest.raises(RuntimeError, match="existing sent receipt"):
        m.execute(args)


def test_post_window_lease_still_blocks_prepare_and_send(monkeypatch, tmp_path):
    args, ledger, original, _ = setup(monkeypatch, tmp_path, existing_reissue="sent")
    late = datetime(2026, 11, 10, 14, 1, tzinfo=m.MOSCOW)
    for stage in ("prepare", "send"):
        args.stage = stage
        with pytest.raises(RuntimeError, match="allowed only between"):
            m._select_due(args, ledger, now=late)
    assert original["scheduled_reissue"]["state"] == "sent"
    args.stage = "verify"
    original["scheduled_reissue"]["state"] = "claimed"
    with pytest.raises(RuntimeError, match="existing sent receipt"):
        m._select_due(args, ledger, now=late)
    original["scheduled_reissue"]["state"] = "sent"
    with pytest.raises(RuntimeError, match="allowed only between"):
        m._select_due(args, ledger, now=datetime(2026, 11, 10, 11, 59, tzinfo=m.MOSCOW))
    with pytest.raises(RuntimeError, match="due today"):
        m._select_due(args, ledger, now=datetime(2026, 11, 11, 14, 2, tzinfo=m.MOSCOW))


def test_send_refuses_if_network_preflight_crosses_1400(monkeypatch, tmp_path):
    args, _, original, _ = setup(monkeypatch, tmp_path, existing_reissue="claimed")
    args.stage = "send"
    monkeypatch.setenv("LORDCHRIST_TELEGRAM_BOT_TOKEN", "test-only-token")
    monkeypatch.setattr(
        m,
        "load_channel_profile",
        lambda *_: SimpleNamespace(bot_token_env="LORDCHRIST_TELEGRAM_BOT_TOKEN"),
    )
    monkeypatch.setattr(
        m,
        "load_target_binding",
        lambda *a, **k: SimpleNamespace(bot_id=8716602202, chat_id=CHAT),
    )
    monkeypatch.setattr(
        m, "render_channel_post", lambda *a, **k: SimpleNamespace(html_text="Reviewed", visible_char_count=92)
    )
    clock = [_at_noon()]

    class AdvanceClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]

    monkeypatch.setattr(m, "datetime", AdvanceClock)

    class SlowReads:
        def read_json(self, url, body):
            if url.endswith("/getMe"):
                return {"ok": True, "result": {"id": 8716602202, "username": "preaching_mp3_bot"}}
            if url.endswith("/getChat"):
                clock[0] = datetime(2026, 11, 10, 14, 0, tzinfo=m.MOSCOW)
                return {"ok": True, "result": {"id": CHAT, "username": "lordchrist", "type": "channel"}}
            raise AssertionError(url)

        def post_json(self, *_):
            pytest.fail("Provider POST must never start after the live Moscow window")

    monkeypatch.setattr(m, "HttpxLiveTransport", SlowReads)
    with pytest.raises(RuntimeError, match="send window expired before provider POST"):
        m.execute(args)
    assert original["scheduled_reissue"]["state"] == "claimed"


def test_owner_dispatch_requires_real_event_payload_and_exact_approved_future_id(monkeypatch, tmp_path):
    article = "lordchrist-telegraph-charnock-09"
    args = argparse.Namespace(publication_id=article)
    event_file = tmp_path / "github-event.json"
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_ACTOR", "FedorMilovanov")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_file))
    good = {"inputs": {"publication_id": article, "confirm": m.OWNER_DISPATCH_CONFIRM}}
    event_file.write_text(json.dumps(good), encoding="utf-8")
    m._require_approved_recovery_trigger(args)

    for invalid_id in ("06", "07", "08", "13"):
        args.publication_id = "lordchrist-telegraph-charnock-" + invalid_id
        with pytest.raises(RuntimeError, match="cannot restore"):
            m._require_approved_recovery_trigger(args)
    args.publication_id = article

    monkeypatch.setenv("GITHUB_ACTOR", "another-actor")
    with pytest.raises(RuntimeError, match="owner-only"):
        m._require_approved_recovery_trigger(args)
    monkeypatch.setenv("GITHUB_ACTOR", "FedorMilovanov")

    bad = [
        {"inputs": {"publication_id": article, "confirm": "other"}},
        {"inputs": {"publication_id": "lordchrist-telegraph-charnock-10", "confirm": m.OWNER_DISPATCH_CONFIRM}},
        {"inputs": {}},
        {"not_inputs": True},
    ]
    for payload in bad:
        event_file.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(RuntimeError, match="inputs do not bind"):
            m._require_approved_recovery_trigger(args)
    event_file.write_text("{broken", encoding="utf-8")
    with pytest.raises(RuntimeError, match="invalid GitHub dispatch payload"):
        m._require_approved_recovery_trigger(args)
    monkeypatch.delenv("GITHUB_EVENT_PATH")
    with pytest.raises(RuntimeError, match="Missing authenticated"):
        m._require_approved_recovery_trigger(args)


def test_disallow_unreviewed_event_types(monkeypatch):
    args = argparse.Namespace(publication_id="lordchrist-telegraph-charnock-09")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    m._require_approved_recovery_trigger(args)
    monkeypatch.setenv("GITHUB_ACTOR", "FedorMilovanov")
    for name in ("push", "pull_request", "repository_dispatch", "workflow_run"):
        monkeypatch.setenv("GITHUB_EVENT_NAME", name)
        with pytest.raises(RuntimeError, match="owner-only"):
            m._require_approved_recovery_trigger(args)
