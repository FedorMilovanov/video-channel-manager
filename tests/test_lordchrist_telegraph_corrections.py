"""Safe one-shot correction semantics for historical Charnock Telegraph pages."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from video_channel_manager import lordchrist_telegraph_corrections as m

REAL_TARGET = m._target

ID = "lordchrist-telegraph-charnock-01b"
ORIGINAL = "https://telegra.ph/Old-Charnock-10-24"
CORRECTED = "https://telegra.ph/Corrected-Charnock-11-05"
SHA = "a" * 40
CHAT = -1001295216957
MESSAGE = 1582


@dataclass
class FakePayload:
    article_sha256: str = "sha256:new"
    cover_sha256: str = "sha256:cover"
    title: str = "Corrected Charnock"


def setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, state: str | None = None):
    original = {
        "publication_id": ID,
        "telegraph_url": ORIGINAL,
        "telegram_message_id": MESSAGE,
        "telegram_chat_id": CHAT,
        "article_sha256": "sha256:original",
    }
    payload = FakePayload()
    item = SimpleNamespace(channel_post=object())
    target = {"previous_telegraph_url": ORIGINAL, "previous_telegram_message_id": MESSAGE}
    ledger = {"entries": {ID: original}}
    if state:
        original["correction"] = {
            "state": state,
            "run_id": "456",
            "run_attempt": 1,
            "github_sha": SHA,
            "article_sha256": payload.article_sha256,
            "cover_sha256": payload.cover_sha256,
            "new_telegraph_url": CORRECTED,
            "new_telegraph_path": "Corrected-Charnock-11-05",
        }
    args = argparse.Namespace(
        stage="prepare-page",
        repo_root=tmp_path,
        queue=Path("queue.json"),
        ledger=tmp_path / "ledger.json",
        publication_id=ID,
        media_base_url="https://example.org",
        run_id="456",
        run_attempt=1,
        github_sha=SHA,
    )
    monkeypatch.setattr(m, "_require_execution_context", lambda _: None)
    monkeypatch.setattr(m, "_ledger", lambda _: (args.ledger, ledger))
    monkeypatch.setattr(m, "_target", lambda *_: (original, target, item, payload))
    monkeypatch.setattr(m, "_read_original_post", lambda *_: None)
    monkeypatch.setattr(m, "_proof_page", lambda *_: None)
    return args, ledger, original


def test_correction_claim_preserves_original_identity_and_refuses_replay(monkeypatch, tmp_path):
    args, ledger, original = setup(monkeypatch, tmp_path)
    result = m.execute(args)
    assert result["stage"] == "prepare-page"
    assert original["telegraph_url"] == ORIGINAL
    assert original["telegram_message_id"] == MESSAGE
    assert original["correction"]["state"] == "page_claimed"
    with pytest.raises(RuntimeError, match="already exists"):
        m.execute(args)


def test_corrected_page_created_exactly_once_without_split(monkeypatch, tmp_path):
    args, ledger, original = setup(monkeypatch, tmp_path, "page_claimed")
    args.stage = "send-page"
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(m, "HttpxLiveTransport", lambda: object())
    monkeypatch.setattr(m, "ensure_telegraph_token", lambda *a, **k: "test-token")
    calls = []

    def create(*a, **kw):
        calls.append(kw)
        return CORRECTED, "Corrected-Charnock-11-05"

    monkeypatch.setattr(m, "publish_telegraph_page", create)
    result = m.execute(args)
    assert result["url"] == CORRECTED
    assert len(calls) == 1
    assert calls[0]["allow_split"] is False
    assert original["telegraph_url"] == ORIGINAL
    assert original["correction"]["state"] == "page_created"
    with pytest.raises(RuntimeError, match="Exact correction stage not claimed"):
        m.execute(args)
    assert len(calls) == 1


def test_no_telegram_edit_without_its_own_durable_claim(monkeypatch, tmp_path):
    args, ledger, original = setup(monkeypatch, tmp_path, "page_created")
    args.stage = "edit-telegram"
    monkeypatch.setattr(m, "HttpxLiveTransport", lambda: pytest.fail("transport constructed"))
    with pytest.raises(RuntimeError, match="Exact correction stage not claimed"):
        m.execute(args)


def test_successful_edit_preserves_message_id_and_replaces_link(monkeypatch, tmp_path):
    args, ledger, original = setup(monkeypatch, tmp_path, "telegram_claimed")
    args.stage = "edit-telegram"
    monkeypatch.setenv("LORDCHRIST_TELEGRAM_BOT_TOKEN", "test-bot-token")
    monkeypatch.setattr(
        m, "load_channel_profile", lambda *_: SimpleNamespace(bot_token_env="LORDCHRIST_TELEGRAM_BOT_TOKEN")
    )
    monkeypatch.setattr(m, "load_target_binding", lambda *a, **k: SimpleNamespace(bot_id=123, chat_id=CHAT))
    monkeypatch.setattr(m, "render_channel_post", lambda *a, **k: SimpleNamespace(html_text="corrected"))
    calls = []

    class Transport:
        def read_json(self, url, payload):
            if url.endswith("/getMe"):
                return {"ok": True, "result": {"id": 123, "username": "preaching_mp3_bot"}}
            if url.endswith("/getChat"):
                return {"ok": True, "result": {"id": CHAT, "username": "lordchrist", "type": "channel"}}
            raise AssertionError(url)

        def post_json(self, url, payload):
            calls.append((url, payload))
            return {
                "ok": True,
                "result": {
                    "message_id": MESSAGE,
                    "chat": {"id": CHAT},
                    "entities": [{"type": "text_link", "url": CORRECTED}],
                    "link_preview_options": {"prefer_large_media": True},
                },
            }

    monkeypatch.setattr(m, "HttpxLiveTransport", Transport)
    result = m.execute(args)
    assert result["message_id"] == MESSAGE
    assert original["telegram_message_id"] == MESSAGE
    assert original["telegraph_url"] == ORIGINAL
    assert original["correction"]["state"] == "corrected"
    assert len(calls) == 1
    assert calls[0][0].endswith("/editMessageText")
    assert calls[0][1]["message_id"] == MESSAGE
    assert calls[0][1]["link_preview_options"]["url"] == CORRECTED


def test_correction_public_post_proof_requires_exact_live_identity_and_url(monkeypatch):
    seen = []

    class Response:
        text = f'<div data-post="lordchrist/{MESSAGE}"><a href="{ORIGINAL}">read</a></div>'

        def raise_for_status(self):
            seen.append("http-ok")

    def fetch(url, **kwargs):
        assert url in {f"https://t.me/lordchrist/{mid}?embed=1" for mid in (MESSAGE, MESSAGE + 1)}
        assert kwargs["follow_redirects"] is True
        return Response()

    monkeypatch.setattr(m.httpx, "get", fetch)
    m._read_original_post(MESSAGE, ORIGINAL)
    assert seen == ["http-ok"]

    with pytest.raises(RuntimeError, match="old link was not proved live"):
        m._read_original_post(MESSAGE, CORRECTED)

    with pytest.raises(RuntimeError, match="not proved live"):
        m._read_original_post(MESSAGE + 1, ORIGINAL)


def test_correction_target_uses_exact_audited_original_and_corrected_blob(monkeypatch, tmp_path):
    args, ledger, original = setup(monkeypatch, tmp_path)
    # Test the real _target, not setup's fast fake implementation.
    actual_target = REAL_TARGET
    monkeypatch.setattr(m, "_target", actual_target)
    map_path = tmp_path / m.MAP_PATH
    map_path.parent.mkdir(parents=True)
    target = {
        "publication_id": ID,
        "previous_telegraph_url": ORIGINAL,
        "previous_telegram_message_id": MESSAGE,
        "previous_published_article_sha256": "sha256:original",
        "corrected_document_git_blob_sha": "b" * 40,
    }
    import json

    map_path.write_text(json.dumps({"targets": [target]}), encoding="utf-8")
    item = SimpleNamespace(is_ready=True, channel_post=object(), cover_path=Path("cover.png"), article_blob="b" * 40)
    monkeypatch.setattr(m, "load_telegraph_queue", lambda *_: [item])
    monkeypatch.setattr(m, "_find_item", lambda *_: item)
    monkeypatch.setattr(m, "build_telegraph_payload", lambda *a, **kw: FakePayload())

    result = actual_target(args, ledger)
    assert result[0] is original
    assert result[1] == target
    assert result[2] is item

    original["telegram_message_id"] = 999
    with pytest.raises(RuntimeError, match="Historical published identity differs"):
        actual_target(args, ledger)
    original["telegram_message_id"] = MESSAGE

    item.article_blob = "unexpected"
    with pytest.raises(RuntimeError, match="Corrected article blob differs"):
        actual_target(args, ledger)
    item.article_blob = "b" * 40

    item.is_ready = False
    with pytest.raises(RuntimeError, match="Corrected article and channel post must be ready"):
        actual_target(args, ledger)


def test_correction_send_page_requires_retained_token_and_new_telegraph_url(monkeypatch, tmp_path):
    args, _ledger, original = setup(monkeypatch, tmp_path, "page_claimed")
    args.stage = "send-page"
    monkeypatch.delenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(m, "HttpxLiveTransport", lambda: pytest.fail("no provider call without token"))
    with pytest.raises(RuntimeError, match="retained Telegraph author token"):
        m.execute(args)

    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(m, "HttpxLiveTransport", object)
    monkeypatch.setattr(m, "ensure_telegraph_token", lambda *a, **kw: None)
    monkeypatch.setattr(m, "publish_telegraph_page", lambda *a, **kw: (ORIGINAL, "original"))
    with pytest.raises(RuntimeError, match="distinct real Telegraph URL"):
        m.execute(args)
    assert original["correction"]["state"] == "page_claimed"


def test_correction_prepare_telegram_needs_verified_page_and_old_post(monkeypatch, tmp_path):
    args, _ledger, original = setup(monkeypatch, tmp_path, "page_created")
    args.stage = "prepare-telegram"
    calls = []
    monkeypatch.setattr(m, "_proof_page", lambda *a: calls.append("verified-new-page"))
    monkeypatch.setattr(m, "_read_original_post", lambda *a: calls.append("verified-old-post"))
    assert m.execute(args)["stage"] == "prepare-telegram"
    assert calls == ["verified-new-page", "verified-old-post"]
    assert original["correction"]["state"] == "telegram_claimed"

    original["correction"]["state"] = "page_created"
    original["correction"]["new_telegraph_url"] = ORIGINAL.replace("https://", "http://")
    calls.clear()
    with pytest.raises(RuntimeError, match="Verified new public page receipt required"):
        m.execute(args)
    assert calls == []


def test_correction_claim_rejects_changed_immutable_context(monkeypatch, tmp_path):
    args, _ledger, original = setup(monkeypatch, tmp_path, "page_claimed")
    original["correction"]["github_sha"] = "f" * 40
    with pytest.raises(RuntimeError, match="Correction intent identity or reviewed payload changed"):
        m._claimed(args, original, "page_claimed", FakePayload())


def _reconciliation_fixture(monkeypatch, tmp_path):
    args, _ledger, original = setup(monkeypatch, tmp_path, "telegram_claimed")
    args.stage = "reconcile-telegram"
    args.original_run_id = "456"
    original["correction"].update(
        publication_id=ID,
        original_telegram_message_id=MESSAGE,
        original_telegraph_url=ORIGINAL,
        provider_effect="verified",
        telegram_provider_effect="unknown_until_reconciled",
    )
    return args, original


def test_delayed_public_readback_is_bounded_and_never_edits_again(monkeypatch):
    calls = []
    sleeps = []

    def read_post(message_id, url):
        assert message_id == MESSAGE
        assert url == CORRECTED
        calls.append(url)
        if len(calls) < 3:
            raise RuntimeError("Telegram web cache still old")

    monkeypatch.setattr(m, "_read_original_post", read_post)
    monkeypatch.setattr(m.time, "sleep", sleeps.append)
    monkeypatch.setattr(m, "HttpxLiveTransport", lambda: pytest.fail("never touch the provider"))
    m._confirm_public_edit(MESSAGE, CORRECTED, attempts=5, delay_seconds=0.5)
    assert len(calls) == 3
    assert sleeps == [0.5, 0.5]


def test_unconfirmed_public_readback_requires_read_only_reconciliation(monkeypatch):
    calls = []
    monkeypatch.setattr(m, "_read_original_post", lambda *a: (_ for _ in ()).throw(RuntimeError("stale")))
    monkeypatch.setattr(m.time, "sleep", lambda n: calls.append(n))
    with pytest.raises(RuntimeError, match="never replay editMessageText"):
        m._confirm_public_edit(MESSAGE, CORRECTED, attempts=3, delay_seconds=0)
    assert len(calls) == 2


def test_read_only_reconciliation_marks_proved_existing_edit_without_bot_api(monkeypatch, tmp_path):
    args, original = _reconciliation_fixture(monkeypatch, tmp_path)
    checks = []
    monkeypatch.setattr(m, "_proof_page", lambda *a: checks.append("full Telegraph readback"))
    monkeypatch.setattr(m, "_read_original_post", lambda *a: checks.append("existing Telegram message readback"))
    monkeypatch.setattr(m, "HttpxLiveTransport", lambda: pytest.fail("read-only reconciliation used Bot API"))
    result = m.execute(args)
    assert result["message_id"] == MESSAGE
    assert result["url"] == CORRECTED
    assert checks == ["full Telegraph readback", "existing Telegram message readback"]
    receipt = original["correction"]
    assert receipt["state"] == "corrected"
    assert receipt["telegram_provider_effect"] == "verified_public_readback"
    assert receipt["reconciled_from_run_id"] == "456"
    assert receipt["reconciliation_run_id"] == args.run_id
    assert original["telegram_message_id"] == MESSAGE
    assert original["telegraph_url"] == ORIGINAL
    with pytest.raises(RuntimeError, match="previously claimed ambiguous Telegram edit"):
        m.execute(args)


def test_read_only_reconciliation_rejects_unrelated_or_forged_claim(monkeypatch, tmp_path):
    args, original = _reconciliation_fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(m, "_proof_page", lambda *a: pytest.fail("unapproved claim contacted provider"))
    args.original_run_id = "999"
    with pytest.raises(RuntimeError, match="Original correction claim"):
        m.execute(args)
    args.original_run_id = "456"
    original["correction"]["cover_sha256"] = "forged"
    with pytest.raises(RuntimeError, match="Original correction claim"):
        m.execute(args)


def test_read_only_reconciliation_keeps_claim_when_public_link_is_stale(monkeypatch, tmp_path):
    args, original = _reconciliation_fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(m, "_proof_page", lambda *a: None)
    monkeypatch.setattr(m, "_read_original_post", lambda *a: (_ for _ in ()).throw(RuntimeError("public edit absent")))
    with pytest.raises(RuntimeError, match="public edit absent"):
        m.execute(args)
    assert original["correction"]["state"] == "telegram_claimed"
    assert original["correction"]["telegram_provider_effect"] == "unknown_until_reconciled"
