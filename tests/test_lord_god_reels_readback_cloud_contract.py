"""Offline, GET-only contracts for Instagram Lord God Reels cloud readback."""

from __future__ import annotations

import hashlib
import importlib.util
import io
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/instagram/lord_god_reels_readback_cloud_20261112.py"


@pytest.fixture
def proof():
    spec = importlib.util.spec_from_file_location("lord_god_reels_readback_cloud_contract", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row_for_12(proof):
    return next(item for item in proof.plan_items() if item["date"] == "2026-11-12")


def _meta_row(proof, *, date="2026-11-12", media_id="1234567890123456"):
    item = _row_for_12(proof)
    assert len(item["caption_sha256"]) == 64
    # The test needs the actual secret-free digest; fake caption bytes are patched into
    # the approved record to make matching end-to-end deterministic and fully offline.
    caption = "Offline demonstration text — no actual user caption."
    item["caption_sha256"] = hashlib.sha256(caption.encode("utf-8")).hexdigest()
    media = {
        "id": media_id,
        "caption": caption,
        "media_type": "VIDEO",
        "media_product_type": "REELS",
        "permalink": "https://www.instagram.com/reel/controlled-test/",
        "timestamp": date + "T16:05:00+0000",
    }
    return item, media


def test_frozen_source_manifest(proof):
    rows = proof.plan_items()
    assert len(rows) == 12
    assert rows[0]["date"] == "2026-11-10"
    assert rows[1]["source_youtube_id"] == "DdhIRg80hyo"
    assert rows[2]["source_youtube_id"] == "SyioCn3HBTI"
    assert rows[-1]["date"] == "2026-11-21"
    assert len({row["caption_sha256"] for row in rows}) == 12
    assert all("publication_key" not in row for row in rows)


def test_readback_source_uses_get_only(proof, monkeypatch):
    calls = []

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            self.close()

    def fake_open(request, timeout):
        calls.append(request)
        assert timeout == 30
        assert request.get_method() == "GET"
        assert request.full_url.startswith("https://graph.facebook.com/v26.0/")
        assert "access_token=" not in request.full_url
        assert request.get_header("Authorization") == "Bearer offline-test-token"
        return FakeResponse(b'{"id":"1457892317403899"}')

    monkeypatch.setattr(proof, "urlopen", fake_open)
    result = proof.graph_get("offline-test-token", "me", params={"fields": "id"})
    assert result["id"] == proof.PAGE_ID
    assert len(calls) == 1


def test_exact_caption_and_moscow_date_verifies(proof):
    item, media = _meta_row(proof)
    result = proof.verify_item(item, [media])
    assert result["state"] == "PROVIDER_CONFIRMED"
    assert result["media_id"] == "1234567890123456"


def test_nonmatching_caption_does_not_confirm(proof):
    item, media = _meta_row(proof)
    media["caption"] = "different"
    assert proof.verify_item(item, [media])["state"] == "NOT_PUBLISHED"


def test_reused_caption_on_two_posts_fails(proof):
    item, media = _meta_row(proof)
    second = dict(media, id="9999999999999999")
    with pytest.raises(RuntimeError, match="DUPLICATE_CAPTION"):
        proof.verify_item(item, [media, second])


@pytest.mark.parametrize(
    "change",
    [
        {"media_product_type": "FEED"},
        {"id": ""},
        {"permalink": "http://instagram.com/reel/test"},
        {"permalink": "https://not-instagram.example/post"},
    ],
)
def test_incomplete_provider_evidence_fails(proof, change):
    item, media = _meta_row(proof)
    media.update(change)
    with pytest.raises(RuntimeError, match="MEDIA_ID_TYPE_OR_PERMALINK"):
        proof.verify_item(item, [media])


def test_date_mismatch_not_success(proof):
    item, media = _meta_row(proof, date="2026-11-13")
    with pytest.raises(RuntimeError, match="MATCHED_CAPTION_WRONG_DATE"):
        proof.verify_item(item, [media])


def test_manual_preflight_is_read_only(proof, monkeypatch, capsys):
    monkeypatch.setenv("LORD_GOD_PAGE_TOKEN", "offline-test-token-" * 4)
    monkeypatch.setenv("LORD_GOD_REELS_PROOF_MODE", "preflight")
    monkeypatch.setattr(proof, "check_identity", lambda token: None)
    monkeypatch.setattr(proof, "list_recent_media", lambda token: [])
    assert proof.main() == 0
    assert "CLOUD_READBACK_READY_NO_PROVIDER_WRITES" in capsys.readouterr().out


def test_scheduled_missing_reel_fails_visible(proof, monkeypatch, capsys):
    class FixedDateTime:
        @staticmethod
        def now(tz):
            return datetime(2026, 11, 12, 19, 42, tzinfo=tz)

    monkeypatch.setenv("LORD_GOD_PAGE_TOKEN", "offline-test-token-" * 4)
    monkeypatch.setenv("LORD_GOD_REELS_PROOF_MODE", "scheduled")
    monkeypatch.setattr(proof, "datetime", FixedDateTime)
    monkeypatch.setattr(proof, "check_identity", lambda token: None)
    monkeypatch.setattr(proof, "list_recent_media", lambda token: [])
    assert proof.main() == 2
    assert "REEL_MISSING_ON_META 2026-11-12 SyioCn3HBTI" in capsys.readouterr().out


def test_cloud_workflow_has_only_readonly_crons():
    text = (ROOT / ".github/workflows/lord-god-reels-cloud-readback-20261112.yml").read_text(encoding="utf-8")
    assert text.count("    - cron:") == 2
    assert "cron: '40 16 12-21 11 *'" in text
    assert "cron: '10 17 12-21 11 *'" in text
    assert "LORD_GOD_REELS_PROOF_MODE:" in text
    assert "cancel-in-progress: false" in text
    assert "/media_publish" not in text


def test_reels_meta_feed_paging_reads_next_page_with_encoded_cursor(proof, monkeypatch):
    requests = []

    def fake_get(token, path, *, params=None):
        assert token == "offline-token"
        assert path == proof.INSTAGRAM_ID + "/media"
        requests.append(dict(params))
        if len(requests) == 1:
            return {
                "data": [{"id": "111"}],
                "paging": {
                    "next": "https://not-meta.example/untrusted-path?access_token=do-not-follow",
                    "cursors": {"after": "opaque/+=="},
                },
            }
        assert params["after"] == "opaque/+=="
        return {"data": [{"id": "222"}], "paging": {"cursors": {"after": "not-next"}}}

    monkeypatch.setattr(proof, "graph_get", fake_get)
    result = proof.list_recent_media("offline-token")
    assert [row["id"] for row in result] == ["111", "222"]
    assert len(requests) == 2
    assert "after" not in requests[0]


@pytest.mark.parametrize(
    "response,expected_error",
    [
        ({}, "did not return data array"),
        ({"data": {"invalid": "shape"}}, "did not return data array"),
        ({"data": ["unexpected scalar"]}, "malformed record"),
        ({"data": [{}], "paging": "invalid"}, "pagination malformed"),
        ({"data": [{}], "paging": {"next": "https://fake.example/p"}}, "incomplete or looping"),
        (
            {"data": [{}], "paging": {"next": "https://fake.example/p", "cursors": "not-a-dict"}},
            "cursors malformed",
        ),
        (
            {"data": [], "paging": {"next": "https://fake.example/p", "cursors": {"after": "cursor"}}},
            "incomplete or looping",
        ),
    ],
)
def test_reels_meta_malformed_pagination_fails_closed(proof, monkeypatch, response, expected_error):
    calls = []

    def fake_get(token, path, *, params=None):
        calls.append((path, params))
        return response

    monkeypatch.setattr(proof, "graph_get", fake_get)
    with pytest.raises(RuntimeError, match=expected_error):
        proof.list_recent_media("offline-token")
    assert len(calls) == 1


def test_reels_meta_repeated_cursor_never_becomes_false_negative(proof, monkeypatch):
    calls = []

    def fake_get(token, path, *, params=None):
        calls.append(params)
        return {
            "data": [{"id": str(len(calls))}],
            "paging": {"next": "https://not-meta.example/loop", "cursors": {"after": "repeated"}},
        }

    monkeypatch.setattr(proof, "graph_get", fake_get)
    with pytest.raises(RuntimeError, match="incomplete or looping"):
        proof.list_recent_media("offline-token")
    assert len(calls) == 2


def test_reels_meta_feed_over_five_pages_is_not_reported_as_missing(proof, monkeypatch):
    requests = []

    def fake_get(token, path, *, params=None):
        requests.append(params)
        number = len(requests)
        return {
            "data": [{"id": str(number)}],
            "paging": {"next": "https://not-meta.example/next", "cursors": {"after": f"cursor{number}"}},
        }

    monkeypatch.setattr(proof, "graph_get", fake_get)
    with pytest.raises(RuntimeError, match="exceeds five-page verification bound"):
        proof.list_recent_media("offline-token")
    assert len(requests) == 5


def test_reels_meta_last_page_without_next_is_complete(proof, monkeypatch):
    monkeypatch.setattr(
        proof,
        "graph_get",
        lambda token, path, *, params=None: {
            "data": [{"id": "first"}],
            "paging": {"cursors": {"after": "opaque-no-next"}},
        },
    )
    assert proof.list_recent_media("offline-token") == [{"id": "first"}]
