"""Incident recovery: eight original posts deleted, never repeat the 2026-11-05 burst."""

from __future__ import annotations

import argparse
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


def test_refuses_manual_publishing_even_with_correct_future_date(monkeypatch, tmp_path):
    args, _, _, _ = setup(monkeypatch, tmp_path)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    with pytest.raises(RuntimeError, match="schedule-only"):
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
    monkeypatch.setattr(
        m.httpx, "get", lambda *a, **k: SimpleNamespace(text="Unavailable", raise_for_status=lambda: None)
    )
    with pytest.raises(RuntimeError, match="not publicly verified"):
        m.execute(args)
    assert original["scheduled_reissue"]["state"] == "sent"


def test_no_write_before_live_schedule_and_no_forged_clock(monkeypatch, tmp_path):
    args, _, _, _ = setup(monkeypatch, tmp_path)
    args.now = "2026-11-10T12:00:00+03:00"
    with pytest.raises(RuntimeError, match="schedule-only"):
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
    document = SimpleNamespace(title="Reviewed", nodes=[{"tag": "p", "children": ["Full approved text"]}])

    def fake_page(url, **kwargs):
        assert url == "https://api.telegra.ph/getPage/Reviewed-Charnock-11-05?return_content=true"
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "ok": True,
                "result": {
                    "title": "Reviewed",
                    "content": [{"tag": "p", "children": ["Full approved text"]}],
                },
            },
        )

    monkeypatch.setattr(m.httpx, "get", fake_page)
    m._proof_page(source, document)
    document.nodes[0]["children"] = ["A different revision"]
    with pytest.raises(RuntimeError, match="entire reviewed latest"):
        m._proof_page(source, document)
