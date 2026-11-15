from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

import video_channel_manager.lordchrist_peasants1525_inplace as revision


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
        "peasants1525_glossary_v2_revision": {
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
    assert entry["peasants1525_glossary_v2_revision"]["state"] == "page_claimed"
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
    assert entry["peasants1525_glossary_v2_revision"]["state"] == "page_verified"


def test_telegram_stage_uses_edit_message_text_only(monkeypatch):
    args, ledger, entry, item, payload = _fixture("edit-telegram")
    entry["peasants1525_glossary_v2_revision"]["state"] = "telegram_claimed"
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
    assert result["message_id"] == 1619
    assert len(calls) == 1
    url, body = calls[0]
    assert url.endswith("/editMessageText")
    assert body["message_id"] == 1619
    assert body["link_preview_options"]["url"] == revision.PAGE_URL
    assert entry["peasants1525_glossary_v2_revision"]["state"] == "verified"


def test_claim_must_match_run_exactly(monkeypatch):
    args, ledger, entry, item, payload = _fixture("edit-page")
    entry["peasants1525_glossary_v2_revision"]["github_sha"] = "b" * 40
    _patch_base(monkeypatch, args, ledger, entry, item, payload)
    with pytest.raises(RuntimeError, match="another execution"):
        revision.execute(args)


def test_authenticated_telegraph_read_accepts_valid_result_and_redacts_errors(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True, "result": {"path": revision.PAGE_PATH}}

    calls = []

    def post(url, *, data, timeout, follow_redirects):
        calls.append((url, data, timeout, follow_redirects))
        return FakeResponse()

    monkeypatch.setattr(revision.httpx, "post", post)
    assert revision._api_post("https://api.telegra.ph/getPage/test", {"access_token": "secret"}) == {
        "path": revision.PAGE_PATH
    }
    assert len(calls) == 1 and calls[0][1]["access_token"] == "secret"

    class DeniedResponse(FakeResponse):
        def json(self):
            return {"ok": False, "error": "MAY_INCLUDE_SECRET_TOKEN"}

    monkeypatch.setattr(revision.httpx, "post", lambda *_args, **_kwargs: DeniedResponse())
    with pytest.raises(RuntimeError, match="rejected") as excinfo:
        revision._api_post("https://api.telegra.ph/getPage/test", {"access_token": "secret"})
    assert "MAY_INCLUDE_SECRET_TOKEN" not in str(excinfo.value)


def test_owner_proof_uses_account_page_list_when_can_edit_is_omitted(monkeypatch):
    calls = []

    def api(url, form):
        calls.append(url)
        if "/getPage/" in url:
            return {
                "path": revision.PAGE_PATH,
                "url": revision.PAGE_URL,
                "title": revision.OLD_TITLE,
            }
        return {"pages": [{"path": "unrelated"}, {"path": revision.PAGE_PATH}]}

    monkeypatch.setattr(revision, "_api_post", api)
    revision._prove_owner("secret")
    assert len(calls) == 2 and calls[-1].endswith("/getPageList")


def test_owner_proof_rejects_unlisted_page(monkeypatch):
    def api(url, form):
        if "/getPage/" in url:
            return {
                "path": revision.PAGE_PATH,
                "url": revision.PAGE_URL,
                "title": revision.OLD_TITLE,
            }
        return {"pages": [{"path": "other-article"}]}

    monkeypatch.setattr(revision, "_api_post", api)
    with pytest.raises(RuntimeError, match="ownership not proved"):
        revision._prove_owner("secret")


def test_public_post_readback_requires_same_id_link_and_headline(monkeypatch):
    class Response:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    text = (
        f'<div data-post="lordchrist/{revision.MESSAGE_ID}">'
        f'<b>НОВЫЙ ЗАГОЛОВОК</b><a href="{revision.PAGE_URL}">Читать статью</a></div>'
    )
    monkeypatch.setattr(revision.httpx, "get", lambda *_a, **_k: Response(text))
    revision._post_readback("НОВЫЙ ЗАГОЛОВОК")
    with pytest.raises(RuntimeError, match="headline"):
        revision._post_readback("СТАРЫЙ ЗАГОЛОВОК")
    monkeypatch.setattr(revision.httpx, "get", lambda *_a, **_k: Response(text.replace("1619", "1620")))
    with pytest.raises(RuntimeError, match="identity"):
        revision._post_readback()


def test_telegram_authority_checks_bound_bot_and_channel(monkeypatch):
    args = _args("prepare-page")
    monkeypatch.setattr(revision, "load_channel_profile", lambda *_: SimpleNamespace(bot_token_env="FAKE_BOT_TOKEN"))
    binding = SimpleNamespace(chat_id=-1001295216957, bot_id=8716602202)
    monkeypatch.setattr(revision, "load_target_binding", lambda *_a, **_k: binding)
    monkeypatch.setenv("FAKE_BOT_TOKEN", "not-a-real-token")

    class Transport:
        def read_json(self, url, params):
            if url.endswith("/getMe"):
                return {"ok": True, "result": {"id": 8716602202, "username": "preaching_mp3_bot"}}
            return {
                "ok": True,
                "result": {"id": -1001295216957, "username": "lordchrist", "type": "channel"},
            }

    monkeypatch.setattr(revision, "HttpxLiveTransport", Transport)
    token, found = revision._telegram_authority(args)
    assert token == "not-a-real-token" and found.chat_id == -1001295216957
    monkeypatch.delenv("FAKE_BOT_TOKEN")
    with pytest.raises(RuntimeError, match="bot secret"):
        revision._telegram_authority(args)


def test_prepare_telegram_requires_verified_page_and_persists_claim(monkeypatch):
    args, ledger, entry, item, payload = _fixture("prepare-telegram")
    entry["peasants1525_glossary_v2_revision"]["state"] = "page_verified"
    saved = _patch_base(monkeypatch, args, ledger, entry, item, payload)
    checks = []
    monkeypatch.setattr(revision, "_proof_page", lambda *_: checks.append("page"))
    monkeypatch.setattr(revision, "_telegram_authority", lambda *_: checks.append("telegram"))
    monkeypatch.setattr(revision, "_post_readback", lambda *_: checks.append("post"))
    result = revision.execute(args)
    assert result["message_id"] == revision.MESSAGE_ID
    assert checks == ["page", "telegram", "post"]
    assert entry["peasants1525_glossary_v2_revision"]["state"] == "telegram_claimed"
    assert saved == [ledger]


def test_1525_glossary_links_resolve_to_in_page_heading_ids():
    """Telegra.ph generates heading IDs by replacing spaces with hyphens."""
    import re
    from urllib.parse import unquote, urlsplit

    root = Path(__file__).resolve().parents[1]
    markdown = (
        root / "content/telegram/lordchrist/telegraph-v1/history/peasants-1525-glossary-v2.md"
    ).read_text(encoding="utf-8")
    headings = set(re.findall(r"^## (.+)$", markdown, flags=re.M))
    glossary_links = re.findall(r"\]\((https://telegra.ph/[^)]*#[^)]*)\)", markdown)
    assert len(glossary_links) >= 10
    assert len(set(glossary_links)) >= 10
    for url in glossary_links:
        assert urlsplit(url).path == "/" + revision.PAGE_PATH
        expected_heading = unquote(urlsplit(url).fragment).replace("-", " ")
        assert expected_heading in headings, expected_heading


def test_1525_original_identity_cannot_be_changed_by_revision(monkeypatch):
    args = _args("prepare-page")
    assert revision.MESSAGE_ID == 1619
    assert revision.PAGE_PATH.endswith("-11-15")
    monkeypatch.setattr(revision, "_ledger", lambda *_: (
        Path("ledger.json"),
        {"entries": {revision.PUBLICATION_ID: {
            "state": "published",
            "provider_effect": "verified",
            "telegram_provider_effect": "verified",
            "telegram_message_id": revision.MESSAGE_ID + 1,
        }}},
    ))
    with pytest.raises(RuntimeError, match="identity changed"):
        revision._target(args)


def test_existing_page_edit_never_uses_create_or_send_message():
    root = Path(__file__).resolve().parents[1]
    runner = (root / "scripts/peasants1525-glossary-inplace-release.sh").read_text(encoding="utf-8")
    assert "prepare-page" in runner and "edit-page" in runner
    assert "prepare-telegram" in runner and "edit-telegram" in runner
    assert "video_channel_manager.lordchrist_peasants1525_inplace" in runner
    assert "lordchrist-telegraph-peasants-1525-20261115" in runner
    executable_lines = "\n".join(line for line in runner.splitlines() if not line.strip().startswith("#"))
    assert "sendMessage" not in executable_lines and "createPage" not in executable_lines
