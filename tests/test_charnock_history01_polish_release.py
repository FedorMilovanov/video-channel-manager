from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import charnock_history01_polish_release as revision


def _environment(monkeypatch):
    for name, value in {
        "GITHUB_RUN_ID": "123456",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REPOSITORY": "FedorMilovanov/video-channel-manager",
        "GITHUB_ACTOR": "FedorMilovanov",
        "LORDCHRIST_TELEGRAPH_ACCESS_TOKEN": "fake-token",
    }.items():
        monkeypatch.setenv(name, value)


def _set_target(monkeypatch, entry):
    ledger = {"entries": {revision.PUB: entry}}
    payload = SimpleNamespace(
        title=revision.TITLE,
        article_sha256="sha256:new-article",
        cover_sha256="sha256:unchanged-cover",
    )
    monkeypatch.setattr(revision, "load_target", lambda *_: (ledger, entry, payload))
    return ledger, payload


def test_ownership_requires_exact_page_title(monkeypatch):
    monkeypatch.setattr(
        revision,
        "api_post",
        lambda *_: {
            "path": revision.PAGE_PATH,
            "url": revision.PAGE_URL,
            "title": "Wrong edition",
            "can_edit": True,
        },
    )
    with pytest.raises(RuntimeError, match="identity changed"):
        revision.verify_owner("secret")


def test_ownership_falls_back_to_author_page_list(monkeypatch):
    calls = []

    def fake_api(url, data):
        calls.append(url)
        if "/getPage/" in url:
            return {"path": revision.PAGE_PATH, "url": revision.PAGE_URL, "title": revision.TITLE}
        return {"pages": [{"path": "other"}, {"path": revision.PAGE_PATH}]}

    monkeypatch.setattr(revision, "api_post", fake_api)
    revision.verify_owner("secret")
    assert len(calls) == 2 and calls[1].endswith("getPageList")


def test_ownership_rejects_nonowner(monkeypatch):
    monkeypatch.setattr(
        revision,
        "api_post",
        lambda *_: {
            "path": revision.PAGE_PATH,
            "url": revision.PAGE_URL,
            "title": revision.TITLE,
            "can_edit": False,
        },
    )
    with pytest.raises(RuntimeError, match="cannot edit"):
        revision.verify_owner("secret")


def test_prepare_commits_a_claim_without_provider_mutation(monkeypatch, tmp_path):
    _environment(monkeypatch)
    entry = {}
    ledger, payload = _set_target(monkeypatch, entry)
    proofs = []
    monkeypatch.setattr(revision, "verify_owner", lambda token: proofs.append(token))
    monkeypatch.setattr(revision, "publish_telegraph_page", lambda *_a, **_k: pytest.fail("must not edit"))
    path = tmp_path / "ledger.json"
    result = revision.execute("prepare", Path("."), path, "https://example.org")
    assert result["state"] == "page_claimed"
    assert proofs == ["fake-token"]
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["entries"][revision.PUB][revision.LEDGER_KEY]["state"] == "page_claimed"
    assert ledger["entries"][revision.PUB][revision.LEDGER_KEY]["article_sha256"] == payload.article_sha256
    with pytest.raises(RuntimeError, match="already claimed"):
        revision.execute("prepare", Path("."), path, "https://example.org")


def test_apply_edits_existing_page_exactly_once(monkeypatch, tmp_path):
    _environment(monkeypatch)
    entry = {
        revision.LEDGER_KEY: {
            "state": "page_claimed",
            "run_id": "123456",
            "run_attempt": 1,
            "github_sha": "a" * 40,
            "article_sha256": "sha256:new-article",
            "cover_sha256": "sha256:unchanged-cover",
            "url": revision.PAGE_URL,
        }
    }
    _set_target(monkeypatch, entry)
    monkeypatch.setattr(revision, "verify_owner", lambda *_: None)
    monkeypatch.setattr(revision, "HttpxLiveTransport", lambda: object())
    monkeypatch.setattr(revision, "_proof_page", lambda *_a, **_k: None)
    effects = []

    def edit_page(_transport, _payload, **kwargs):
        effects.append(kwargs)
        return revision.PAGE_URL, revision.PAGE_PATH

    monkeypatch.setattr(revision, "publish_telegraph_page", edit_page)
    path = tmp_path / "ledger.json"
    result = revision.execute("apply", Path("."), path, "https://example.org")
    assert result == {"state": "verified", "url": revision.PAGE_URL}
    assert len(effects) == 1
    assert effects[0]["existing_path"] == revision.PAGE_PATH
    assert effects[0]["allow_split"] is False
    assert entry[revision.LEDGER_KEY]["provider_effect"] == "verified"


def test_apply_fails_closed_on_changed_run(monkeypatch, tmp_path):
    _environment(monkeypatch)
    entry = {
        revision.LEDGER_KEY: {
            "state": "page_claimed",
            "run_id": "another-run",
            "run_attempt": 1,
            "github_sha": "a" * 40,
            "article_sha256": "sha256:new-article",
            "cover_sha256": "sha256:unchanged-cover",
            "url": revision.PAGE_URL,
        }
    }
    _set_target(monkeypatch, entry)
    with pytest.raises(RuntimeError, match="different run"):
        revision.execute("apply", Path("."), tmp_path / "ledger.json", "https://example.org")


def test_invalid_execution_context_disallows_any_mutation(monkeypatch, tmp_path):
    _environment(monkeypatch)
    entry = {}
    _set_target(monkeypatch, entry)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    with pytest.raises(RuntimeError, match="one-shot context"):
        revision.execute("prepare", Path("."), tmp_path / "ledger.json", "https://example.org")


def test_load_target_uses_real_canonical_queue_and_manifest(tmp_path):
    root = Path(__file__).resolve().parents[1]
    entry = {
        "history01_inplace_revision": {
            "state": "verified",
            "page_url": revision.PAGE_URL,
            "message_id": 1585,
            "page_provider_effect": "verified",
            "telegram_provider_effect": "verified",
        }
    }
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps({"entries": {revision.PUB: entry}}), encoding="utf-8")
    loaded, target, payload = revision.load_target(
        root, ledger_path, "https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/main"
    )
    assert target is entry or target == entry
    assert loaded["entries"][revision.PUB]["history01_inplace_revision"]["state"] == "verified"
    assert payload.title == revision.TITLE
    assert payload.content_utf8_bytes < 64_000
