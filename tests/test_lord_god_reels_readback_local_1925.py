"""Offline safety tests for the versioned local Lord God Instagram readback."""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/instagram/lord_god_reels_readback_local_1925.py"
SLOT_ID = "lord-god-strength.2026-11-12.yt-SyioCn3HBTI.reel-v1"
CAPTION = "An offline demonstration caption, no live posts"
ACCOUNT = "17841433845016161"


@pytest.fixture
def monitor(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("local_1925", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    rows = [
        {
            "publication_key": SLOT_ID if day == 12 else f"other-{day}",
            "scheduled_at_moscow": f"2026-11-{day:02d}T19:00:00+03:00",
            "source_youtube_id": "SyioCn3HBTI" if day == 12 else "offline",
            "caption": CAPTION,
            "caption_sha256": "sha256:" + hashlib.sha256(CAPTION.encode()).hexdigest(),
        }
        for day in range(10, 22)
    ]
    release = tmp_path / "release.json"
    release.write_text(json.dumps({"instagram_account_id": ACCOUNT, "items": rows}), encoding="utf8")
    conn = sqlite3.connect(repo / "data/video_manager.db")
    conn.execute(
        "CREATE TABLE instagram_publications (publication_key TEXT, account_id TEXT, status TEXT, "
        "provider_container_id TEXT, provider_media_id TEXT, attempt_count INTEGER, "
        "last_error_code TEXT, published_at TEXT)"
    )
    conn.commit()
    conn.close()

    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 11, 12, 19, 25, tzinfo=tz)

    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "REPO", repo)
    monkeypatch.setattr(module, "RELEASE", release)
    monkeypatch.setattr(module, "dt", SimpleNamespace(datetime=Clock, timezone=dt.timezone, timedelta=dt.timedelta))
    monkeypatch.setattr(module, "get", lambda *args, **kwargs: pytest.fail("Provider GET not mocked by this test"))
    return module


def insert_ledger(m, status, media=None, account=ACCOUNT):
    conn = sqlite3.connect(m.REPO / "data/video_manager.db")
    conn.execute(
        "INSERT INTO instagram_publications VALUES (?,?,?,?,?,?,?,?)",
        (SLOT_ID, account, status, "fake-container", media, 1, None, None),
    )
    conn.commit()
    conn.close()


@pytest.mark.parametrize(
    "status,expected",
    [
        (None, "NO_LEDGER_WRITE_NO_PUBLICATION_PROVEN"),
        ("terminal_failure", "LEDGER_ONLY_NOT_PROVIDER_VERIFIED"),
        ("publish_unknown", "AMBIGUOUS_PROVIDER_EFFECT_NO_RETRY"),
    ],
)
def test_missing_or_unverified_exit_nonzero(monitor, status, expected):
    if status is not None:
        insert_ledger(monitor, status)
    with pytest.raises(SystemExit) as exc:
        monitor.main()
    assert exc.value.code == 2
    report = json.loads((monitor.ROOT / "operator-logs/readback-2026-11-12.json").read_text(encoding="utf8"))
    assert report["verification"] == expected
    assert report["provider_writes"] == 0


def test_published_ledger_without_meta_proof_is_failure(monitor, monkeypatch):
    insert_ledger(monitor, "published", "12345")
    monkeypatch.setattr(monitor, "get_token", lambda: "fake")
    monkeypatch.setattr(monitor, "verify_provider_receipt", lambda *a: None)
    with pytest.raises(SystemExit) as exc:
        monitor.main()
    assert exc.value.code == 2
    data = json.loads((monitor.ROOT / "operator-logs/readback-2026-11-12.json").read_text())
    assert data["verification"] == "META_ID_OR_CAPTION_UNVERIFIED"


def test_verified_meta_only_success_and_no_report_overwrite(monitor, monkeypatch):
    insert_ledger(monitor, "published", "12345")
    monkeypatch.setattr(monitor, "get_token", lambda: "fake")
    monkeypatch.setattr(
        monitor,
        "verify_provider_receipt",
        lambda *a: {
            "permalink": "https://www.instagram.com/reel/offline/",
            "provider_timestamp": "2026-11-12T16:03:00+00:00",
        },
    )
    monitor.main()
    report_path = monitor.ROOT / "operator-logs/readback-2026-11-12.json"
    before = report_path.read_bytes()
    assert json.loads(before)["verification"] == "VERIFIED_PUBLISHED_BY_META"
    with pytest.raises(RuntimeError, match="already recorded"):
        monitor.main()
    assert report_path.read_bytes() == before


def test_wrong_account_cannot_pass(monitor):
    insert_ledger(monitor, "published", "12345", account="wrong-account")
    with pytest.raises(SystemExit) as exc:
        monitor.main()
    assert exc.value.code == 2
    report = json.loads((monitor.ROOT / "operator-logs/readback-2026-11-12.json").read_text())
    assert report["verification"] == "CRITICAL_WRONG_ACCOUNT_LEDGER"


@pytest.mark.parametrize("paging", [None, [], False, "", {"next": ""}, {"next": None}])
def test_invalid_paging_blocks_readback(monitor, monkeypatch, paging):
    monkeypatch.setattr(monitor, "get", lambda url, token: {"data": [], "paging": paging})
    with pytest.raises(RuntimeError, match="malformed|invalid"):
        monitor.list_meta_media("fake-token")


def test_untrusted_meta_next_url_never_followed(monitor, monkeypatch):
    urls = []

    def fake_get(url, token):
        urls.append(url)
        if len(urls) == 1:
            return {
                "data": [{"id": "1"}],
                "paging": {
                    "next": "https://attacker.example/leak?access_token=unsafe",
                    "cursors": {"after": "opaque/+/="},
                },
            }
        return {"data": [{"id": "2"}]}

    monkeypatch.setattr(monitor, "get", fake_get)
    assert len(monitor.list_meta_media("fake-token")) == 2
    assert len(urls) == 2
    assert all(url.startswith("https://graph.facebook.com/") for url in urls)
    assert "after=opaque%2F%2B%2F%3D" in urls[1]


def test_exact_provider_caption_timestamp_and_type(monitor, monkeypatch):
    row = json.loads(monitor.RELEASE.read_text())["items"][2]
    monkeypatch.setattr(
        monitor,
        "get",
        lambda url, token: (
            {
                "id": monitor.PAGE,
                "instagram_business_account": {"id": monitor.ACCOUNT, "username": "thelordgodismystrength"},
            }
            if "instagram_business_account" in url
            else {"id": monitor.PAGE}
        ),
    )
    monkeypatch.setattr(
        monitor,
        "list_meta_media",
        lambda token: [
            {
                "id": "12345",
                "caption": CAPTION,
                "permalink": "https://www.instagram.com/reel/offline/",
                "media_product_type": "REELS",
                "media_type": "VIDEO",
                "timestamp": "2026-11-12T16:01:00+00:00",
            }
        ],
    )
    assert monitor.verify_provider_receipt("fake-token", "12345", row) is not None


def test_duplicate_caption_fails_closed(monitor, monkeypatch):
    row = json.loads(monitor.RELEASE.read_text())["items"][2]
    monkeypatch.setattr(
        monitor,
        "get",
        lambda url, token: (
            {
                "id": monitor.PAGE,
                "instagram_business_account": {"id": monitor.ACCOUNT, "username": "thelordgodismystrength"},
            }
            if "instagram_business_account" in url
            else {"id": monitor.PAGE}
        ),
    )
    monkeypatch.setattr(
        monitor,
        "list_meta_media",
        lambda token: [
            {"id": "12345", "caption": CAPTION},
            {"id": "54321", "caption": CAPTION},
        ],
    )
    with pytest.raises(RuntimeError, match="Duplicate provider"):
        monitor.verify_provider_receipt("fake-token", "12345", row)
