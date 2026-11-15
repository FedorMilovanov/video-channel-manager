from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

import video_channel_manager.lordchrist_history01_inplace as revision


def _args(stage: str) -> Namespace:
    return Namespace(
        stage=stage,
        repo_root=Path("."),
        ledger=Path("ledger.json"),
        publication_id=revision.PUBLICATION_ID,
        media_base_url="https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/" + "a" * 40,
        run_id="1234",
        run_attempt=1,
        github_sha="a" * 40,
    )


def _fixture(stage: str):
    args = _args(stage)
    payload = SimpleNamespace(article_sha256="sha256:article", cover_sha256="sha256:cover")
    item = SimpleNamespace(channel_post=SimpleNamespace(headline="НОВЫЙ ЗАГОЛОВОК"))
    entry = {
        "history01_inplace_revision": {
            "state": "page_claimed",
            "run_id": args.run_id,
            "run_attempt": 1,
            "github_sha": args.github_sha,
            "article_sha256": payload.article_sha256,
            "cover_sha256": payload.cover_sha256,
        }
    }
    ledger = {"entries": {revision.PUBLICATION_ID: entry}}
    return args, ledger, entry, item, payload


def _patch_base(monkeypatch, args, ledger, entry, item, payload):
    monkeypatch.setattr(revision, "_require_execution_context", lambda _: None)
    monkeypatch.setattr(
        revision,
        "_target",
        lambda _: (Path("ledger.json"), ledger, entry, item, payload),
    )
    saved = []
    monkeypatch.setattr(revision, "save_ledger", lambda path, data: saved.append(data))
    return saved


def test_page_ownership_fails_closed_on_wrong_title(monkeypatch):
    monkeypatch.setattr(
        revision,
        "_api_post",
        lambda *_: {
            "path": revision.PAGE_PATH,
            "url": revision.PAGE_URL,
            "title": "Other unreviewed page",
            "can_edit": True,
        },
    )
    with pytest.raises(RuntimeError, match="prior title"):
        revision._prove_owner("retained-secret")


def test_page_ownership_fails_closed_without_edit_rights(monkeypatch):
    monkeypatch.setattr(
        revision,
        "_api_post",
        lambda *_: {
            "path": revision.PAGE_PATH,
            "url": revision.PAGE_URL,
            "title": revision.OLD_TITLE,
            "can_edit": False,
        },
    )
    with pytest.raises(RuntimeError, match="cannot edit"):
        revision._prove_owner("retained-secret")


def test_prepare_claim_is_read_only(monkeypatch):
    args, ledger, entry, item, payload = _fixture("prepare-page")
    entry.clear()
    saved = _patch_base(monkeypatch, args, ledger, entry, item, payload)
    checks = []
    monkeypatch.setattr(revision, "_prove_owner", lambda token: checks.append("owner"))
    monkeypatch.setattr(revision, "_telegram_authority", lambda _: checks.append("telegram"))
    monkeypatch.setattr(revision, "_post_readback", lambda *_: checks.append("post"))
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "temporary-secret")
    result = revision.execute(args)
    assert result["owned"] is True
    assert checks == ["owner", "telegram", "post"]
    assert entry["history01_inplace_revision"]["state"] == "page_claimed"
    assert saved == [ledger]


def test_page_revision_always_targets_existing_path(monkeypatch):
    args, ledger, entry, item, payload = _fixture("edit-page")
    _patch_base(monkeypatch, args, ledger, entry, item, payload)
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "temporary-secret")
    monkeypatch.setattr(revision, "_prove_owner", lambda _: None)
    monkeypatch.setattr(revision, "_post_readback", lambda *_: None)
    monkeypatch.setattr(revision, "_proof_page", lambda *_: None)
    monkeypatch.setattr(revision, "HttpxLiveTransport", lambda: object())
    called = []

    def edit(transport, payload_arg, **kwargs):
        called.append(kwargs)
        return revision.PAGE_URL, revision.PAGE_PATH

    monkeypatch.setattr(revision, "publish_telegraph_page", edit)
    revision.execute(args)
    assert len(called) == 1
    assert called[0]["existing_path"] == revision.PAGE_PATH
    assert called[0]["allow_split"] is False
    assert entry["history01_inplace_revision"]["state"] == "page_verified"


def test_telegram_stage_uses_edit_message_text_only(monkeypatch):
    args, ledger, entry, item, payload = _fixture("edit-telegram")
    entry["history01_inplace_revision"]["state"] = "telegram_claimed"
    _patch_base(monkeypatch, args, ledger, entry, item, payload)
    monkeypatch.setattr(revision, "_proof_page", lambda *_: None)
    monkeypatch.setattr(revision, "_post_readback", lambda *_: None)
    monkeypatch.setattr(
        revision,
        "_telegram_authority",
        lambda _: ("fake-bot-secret", SimpleNamespace(chat_id=-1001295216957)),
    )
    monkeypatch.setattr(
        revision, "render_channel_post", lambda spec, url: SimpleNamespace(html_text="NEW", telegraph_url=url)
    )
    calls = []

    class FakeTransport:
        def post_json(self, url, body):
            calls.append((url, body))
            return {
                "ok": True,
                "result": {
                    "message_id": revision.MESSAGE_ID,
                    "chat": {"id": -1001295216957},
                },
            }

    monkeypatch.setattr(revision, "HttpxLiveTransport", FakeTransport)
    result = revision.execute(args)
    assert result["message_id"] == 1585
    assert len(calls) == 1
    url, body = calls[0]
    assert url.endswith("/editMessageText")
    assert body["message_id"] == 1585
    assert body["link_preview_options"]["url"] == revision.PAGE_URL
    assert entry["history01_inplace_revision"]["state"] == "verified"


def test_claim_must_match_run_exactly(monkeypatch):
    args, ledger, entry, item, payload = _fixture("edit-page")
    entry["history01_inplace_revision"]["github_sha"] = "b" * 40
    _patch_base(monkeypatch, args, ledger, entry, item, payload)
    with pytest.raises(RuntimeError, match="another execution"):
        revision.execute(args)
