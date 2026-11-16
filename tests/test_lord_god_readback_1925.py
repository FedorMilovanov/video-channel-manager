"""Regression tests for the production Lord God 19:25 safe reconciliation."""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import sqlite3
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/instagram/lord_god_reels_readback_local_1925.py"
spec = importlib.util.spec_from_file_location("lord_god_1925_safe", SCRIPT)
assert spec is not None and spec.loader is not None
postflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(postflight)


def approved_row() -> dict[str, str]:
    caption = "An exact approved caption"
    return {
        "publication_key": "lord-god-strength.exact-approved-key",
        "caption": caption,
        "caption_sha256": "sha256:" + hashlib.sha256(caption.encode()).hexdigest(),
    }


def ledger(*, account=None, status="publish_unknown", container="18110001234567890", media=None):
    return (account or postflight.ACCOUNT, status, container, media, 1, None, None)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (ledger(status="published"), "NOT_APPLICABLE"),
        (ledger(status="planned"), "NOT_APPLICABLE"),
        (ledger(status="terminal_failure"), "NOT_APPLICABLE"),
        (ledger(status="container_unknown"), "NOT_APPLICABLE"),
        (ledger(status="publish_unknown", container=None), "REFUSED_LEDGER_IDENTITY_OR_CONTAINER"),
        (ledger(status="published_unresolved", account="wrong-account"), "REFUSED_LEDGER_IDENTITY_OR_CONTAINER"),
        (ledger(status="publish_requested", media="already-has-media"), "REFUSED_LEDGER_IDENTITY_OR_CONTAINER"),
    ],
)
def test_unsafe_states_cannot_invoke_cli(tmp_path, monkeypatch, state, expected):
    def no_token():
        pytest.fail("Token must never be read for ineligible states")

    monkeypatch.setattr(postflight, "get_token", no_token)
    assert postflight.reconcile_ambiguous_ledger(approved_row(), state, tmp_path / "nothing.db") == expected


def test_bad_caption_hash_blocks_before_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(postflight, "get_token", lambda: pytest.fail("No token allowed"))
    row = approved_row()
    row["caption_sha256"] = "sha256:" + "0" * 64
    assert (
        postflight.reconcile_ambiguous_ledger(row, ledger(), tmp_path / "nothing.db") == "REFUSED_FROZEN_CAPTION_HASH"
    )


@pytest.mark.parametrize(
    ("exit_code", "expect"), [(0, "DISCOVERY_SUCCEEDED"), (2, "PROVIDER_PROOF_INSUFFICIENT_NO_RETRY")]
)
def test_exact_cli_is_get_only_and_kill_switch_forced(tmp_path, monkeypatch, exit_code, expect):
    repo = tmp_path / "repo"
    cli = repo / ".venv/Scripts/video-manager.exe"
    cli.parent.mkdir(parents=True)
    cli.write_bytes(b"test")
    db = repo / "data/video_manager.db"
    db.parent.mkdir()
    db.write_bytes(b"test")
    monkeypatch.setattr(postflight, "REPO", repo)
    monkeypatch.setattr(postflight, "get_token", lambda: "private-test-token")
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=exit_code)

    monkeypatch.setattr(postflight.subprocess, "run", fake_run)
    assert postflight.reconcile_ambiguous_ledger(approved_row(), ledger(), db) == expect
    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv == [
        str(cli),
        "instagram",
        "production",
        "reconcile",
        approved_row()["publication_key"],
        "--discover-published-media",
    ]
    assert "--execute" not in argv and "publish" not in argv
    assert kwargs["env"]["VCM_INSTAGRAM_WRITES_ENABLED"] == "false"
    assert kwargs["env"]["VCM_INSTAGRAM_ACCOUNT_ID"] == postflight.ACCOUNT
    assert kwargs["env"]["VCM_DATABASE_URL"].endswith("data/video_manager.db")
    assert kwargs["timeout"] == 120 and kwargs["cwd"] == str(repo)
    assert "private-test-token" not in argv


def test_cli_timeout_preserves_no_retry(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    cli = repo / ".venv/Scripts/video-manager.exe"
    cli.parent.mkdir(parents=True)
    cli.write_bytes(b"test")
    db = repo / "data/video_manager.db"
    db.parent.mkdir()
    db.write_bytes(b"test")
    monkeypatch.setattr(postflight, "REPO", repo)
    monkeypatch.setattr(postflight, "get_token", lambda: "private-test-token")

    def timeout(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 120)

    monkeypatch.setattr(postflight.subprocess, "run", timeout)
    assert postflight.reconcile_ambiguous_ledger(approved_row(), ledger(), db) == "RECONCILIATION_UNAVAILABLE_NO_RETRY"


def test_postflight_rereads_ledger_and_requires_meta_proof(tmp_path, monkeypatch):
    today = "2026-11-16"

    class FrozenClock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 11, 16, 19, 25, tzinfo=tz)

    monkeypatch.setattr(
        postflight, "dt", SimpleNamespace(datetime=FrozenClock, timezone=dt.timezone, timedelta=dt.timedelta)
    )
    repo = tmp_path / "repo"
    root = tmp_path / "wave"
    root.mkdir()
    db = repo / "data/video_manager.db"
    db.parent.mkdir(parents=True)
    row = {
        **approved_row(),
        "scheduled_at_moscow": today + "T19:00:00+03:00",
        "source_youtube_id": "exactSource",
    }
    items = [row] + [
        {**row, "scheduled_at_moscow": f"2026-11-{d:02d}T19:00:00+03:00"}
        for d in range(10, 22)
        if f"2026-11-{d:02d}" != today
    ]
    release = root / "release.json"
    content = json.dumps({"instagram_account_id": postflight.ACCOUNT, "items": items}).encode()
    release.write_bytes(content)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE instagram_publications("
            "publication_key TEXT PRIMARY KEY, account_id TEXT, status TEXT, "
            "provider_container_id TEXT, provider_media_id TEXT, attempt_count INT, "
            "last_error_code TEXT, published_at TEXT)"
        )
        conn.execute(
            "INSERT INTO instagram_publications VALUES (?,?,?,?,?,?,?,?)",
            (row["publication_key"], postflight.ACCOUNT, "publish_unknown", "18110001234567890", None, 1, None, None),
        )
    monkeypatch.setattr(postflight, "REPO", repo)
    monkeypatch.setattr(postflight, "ROOT", root)
    monkeypatch.setattr(postflight, "RELEASE", release)
    monkeypatch.setattr(postflight, "RELEASE_SHA256", hashlib.sha256(content).hexdigest())
    monkeypatch.setattr(postflight, "get_token", lambda: "private-test-token")
    proof_calls = []

    def fake_reconcile(_row, _found, _db):
        with sqlite3.connect(db) as conn:
            conn.execute(
                "UPDATE instagram_publications SET status='published', provider_media_id=? WHERE publication_key=?",
                ("18012345678901234", row["publication_key"]),
            )
        return "DISCOVERY_SUCCEEDED"

    def fake_meta_proof(token, media_id, source):
        proof_calls.append((token, media_id, source["publication_key"]))
        return {
            "permalink": "https://www.instagram.com/reel/Example123/",
            "provider_timestamp": "2026-11-16T16:02:00+00:00",
        }

    monkeypatch.setattr(postflight, "reconcile_ambiguous_ledger", fake_reconcile)
    monkeypatch.setattr(postflight, "verify_provider_receipt", fake_meta_proof)
    postflight.main()
    report = json.loads((root / "operator-logs" / ("readback-" + today + ".json")).read_text())
    assert report["verification"] == "VERIFIED_PUBLISHED_BY_META"
    assert report["evidence"]["safe_reconciliation"] == "DISCOVERY_SUCCEEDED"
    assert report["provider_writes"] == 0
    assert proof_calls == [("private-test-token", "18012345678901234", row["publication_key"])]


def test_late_due_slot_uses_same_evidence_gated_reconcile(tmp_path, monkeypatch):
    row = {**approved_row(), "scheduled_at_moscow": "2026-11-16T19:00:00+03:00"}
    all_rows = [row] + [
        {**row, "scheduled_at_moscow": f"2026-11-{day:02d}T19:00:00+03:00"} for day in range(10, 22) if day != 16
    ]
    frozen = tmp_path / "release.json"
    data = json.dumps({"instagram_account_id": postflight.ACCOUNT, "items": all_rows}).encode()
    frozen.write_bytes(data)
    monkeypatch.setattr(postflight, "RELEASE", frozen)
    monkeypatch.setattr(postflight, "RELEASE_SHA256", hashlib.sha256(data).hexdigest())
    monkeypatch.setattr(postflight, "REPO", tmp_path / "repo")
    calls = []
    monkeypatch.setattr(postflight, "_ledger_row", lambda db, key: ledger())
    monkeypatch.setattr(
        postflight,
        "reconcile_ambiguous_ledger",
        lambda item, status, db: calls.append((item["publication_key"], status[1])) or "DISCOVERY_SUCCEEDED",
    )
    assert postflight.reconcile_due_slot("2026-11-16") == "DISCOVERY_SUCCEEDED"
    assert calls == [(row["publication_key"], "publish_unknown")]

    monkeypatch.setattr(
        postflight, "_ledger_row", lambda db, key: ledger(status="published", media="18000000000000001")
    )
    monkeypatch.setattr(postflight, "get_token", lambda: "offline-secret")
    monkeypatch.setattr(
        postflight,
        "verify_provider_receipt",
        lambda token, media, item: {"permalink": "https://www.instagram.com/reel/exact/"},
    )
    assert postflight.reconcile_due_slot("2026-11-16") == "ALREADY_PUBLISHED"
    monkeypatch.setattr(postflight, "verify_provider_receipt", lambda token, media, item: None)
    assert postflight.reconcile_due_slot("2026-11-16") == "PUBLISHED_LEDGER_META_UNVERIFIED"
    assert len(calls) == 1
    monkeypatch.setattr(postflight, "RELEASE_SHA256", "0" * 64)
    with pytest.raises(RuntimeError, match="release SHA mismatch"):
        postflight.reconcile_due_slot("2026-11-16")
    assert len(calls) == 1
