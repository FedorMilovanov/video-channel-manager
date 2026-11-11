"""Offline safety contracts for the four Lord God Instagram photo posts."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/instagram/lord_god_quote_cloud_20261111.py"


@pytest.fixture
def publisher():
    spec = importlib.util.spec_from_file_location("lord_god_cloud_contract", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configure(monkeypatch, module, mode="scheduled", hour=12, minute=46):
    class FixedDateTime:
        @staticmethod
        def now(tz):
            return datetime(2026, 11, 12, hour, minute, tzinfo=tz)

    monkeypatch.setenv("LORD_GOD_PAGE_TOKEN", "dummy-token-value-" * 4)
    monkeypatch.setenv("LORD_GOD_CLOUD_MODE", mode)
    monkeypatch.setattr(module, "datetime", FixedDateTime)
    monkeypatch.setattr(module, "verify_identity", lambda token: None)
    monkeypatch.setattr(module, "media_verified", lambda item: "https://example.invalid/safe-image.jpg")


def test_four_frozen_slots(publisher):
    assert [(r["id"], r["date"], r["time"]) for r in publisher.read_plan()] == [
        ("01-charnock", "2026-11-12", "12:45"),
        ("02-owen", "2026-11-13", "12:45"),
        ("03-bunyan", "2026-11-14", "12:45"),
        ("04-watson", "2026-11-15", "12:45"),
    ]


@pytest.mark.parametrize("field,invalid", [("date", "2026-11-11"), ("time", "12:30")])
def test_mismatched_plan_fails_closed(publisher, monkeypatch, tmp_path, field, invalid):
    plan = json.loads(publisher.PLAN.read_text(encoding="utf-8"))
    plan["items"][0][field] = invalid
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    monkeypatch.setattr(publisher, "PLAN", path)
    with pytest.raises(RuntimeError):
        publisher.read_plan()


@pytest.mark.parametrize("hour,minute", [(12, 44), (14, 0), (23, 59)])
def test_outside_publication_window_never_posts(publisher, monkeypatch, hour, minute):
    configure(monkeypatch, publisher, hour=hour, minute=minute)
    monkeypatch.setattr(publisher, "request_json", lambda *a, **kw: pytest.fail("Unexpected provider call"))
    with pytest.raises(RuntimeError, match="Outside 12:45-14:00"):
        publisher.main()


def test_manual_dispatch_is_read_only(publisher, monkeypatch, capsys):
    configure(monkeypatch, publisher, mode="preflight")
    monkeypatch.setattr(publisher, "find_published", lambda *a: None)
    monkeypatch.setattr(publisher, "request_json", lambda *a, **kw: pytest.fail("Unexpected provider POST"))
    publisher.main()
    output = capsys.readouterr().out
    assert "PREFLIGHT_OK_NO_POST" in output
    assert output.count("PREFLIGHT ") == 4


def test_already_published_never_reposts(publisher, monkeypatch, capsys):
    configure(monkeypatch, publisher)
    monkeypatch.setattr(publisher, "find_published", lambda *a: {"id": "12345"})
    monkeypatch.setattr(publisher, "request_json", lambda *a, **kw: pytest.fail("Duplicate POST attempted"))
    publisher.main()
    assert "ALREADY_PUBLISHED_SKIP" in capsys.readouterr().out


def test_single_publish_with_provider_readback(publisher, monkeypatch, capsys):
    configure(monkeypatch, publisher)
    monkeypatch.setattr(publisher, "find_published", lambda *a: None)
    caption = publisher.read_plan()[0]["caption"]
    calls = []

    def provider(endpoint, token, *, data=None):
        calls.append((endpoint, data))
        if endpoint.endswith("/media") and data is not None:
            return {"id": "12345"}
        if endpoint == "12345?fields=status_code":
            return {"status_code": "FINISHED"}
        if endpoint.endswith("/media_publish"):
            return {"id": "67890"}
        if endpoint.startswith("67890?"):
            return {
                "id": "67890",
                "caption": caption,
                "media_type": "IMAGE",
                "permalink": "https://instagram.com/p/test",
                "timestamp": "2026-11-12T09:46:00+00:00",
            }
        pytest.fail(f"Unexpected call {endpoint}")

    monkeypatch.setattr(publisher, "request_json", provider)
    publisher.main()
    assert len([data for _, data in calls if data is not None]) == 2
    assert "PUBLISHED_CONFIRMED" in capsys.readouterr().out


@pytest.mark.parametrize(
    "bad_field,bad_value",
    [
        ("id", "99999"),
        ("media_type", "VIDEO"),
        ("permalink", ""),
        ("permalink", "https://not-instagram.example/p/test"),
        ("timestamp", "2026-11-13T09:46:00+00:00"),
        ("timestamp", ""),
        ("caption", "not the approved caption"),
    ],
)
def test_incomplete_provider_photo_readback_never_claims_success(publisher, monkeypatch, capsys, bad_field, bad_value):
    configure(monkeypatch, publisher)
    monkeypatch.setattr(publisher, "find_published", lambda *a: None)
    caption = publisher.read_plan()[0]["caption"]
    writes = []

    def provider(endpoint, token, *, data=None):
        if endpoint.endswith("/media") and data is not None:
            writes.append("container")
            return {"id": "12345"}
        if endpoint == "12345?fields=status_code":
            return {"status_code": "FINISHED"}
        if endpoint.endswith("/media_publish"):
            writes.append("publish")
            return {"id": "67890"}
        if endpoint.startswith("67890?"):
            details = {
                "id": "67890",
                "caption": caption,
                "media_type": "IMAGE",
                "permalink": "https://www.instagram.com/p/test/",
                "timestamp": "2026-11-12T09:46:00+00:00",
            }
            details[bad_field] = bad_value
            return details
        pytest.fail(f"Unexpected provider request {endpoint}")

    monkeypatch.setattr(publisher, "request_json", provider)
    with pytest.raises(RuntimeError, match="do not retry"):
        publisher.main()
    output = capsys.readouterr().out
    assert "MEDIA_PUBLISH_ID_UNCONFIRMED" in output
    assert "PUBLISHED_CONFIRMED" not in output
    assert writes == ["container", "publish"]


def test_ambiguous_response_does_not_retry_in_same_run(publisher, monkeypatch):
    configure(monkeypatch, publisher)
    monkeypatch.setattr(publisher, "find_published", lambda *a: None)
    requests = []

    def provider(endpoint, token, *, data=None):
        if endpoint.endswith("/media") and data is not None:
            return {"id": "12345"}
        if endpoint == "12345?fields=status_code":
            return {"status_code": "FINISHED"}
        if endpoint.endswith("/media_publish"):
            requests.append(endpoint)
            raise RuntimeError("Meta ambiguous response")
        pytest.fail(f"Unexpected call {endpoint}")

    monkeypatch.setattr(publisher, "request_json", provider)
    with pytest.raises(RuntimeError, match="Meta ambiguous response"):
        publisher.main()
    assert requests == [publisher.INSTAGRAM_ACCOUNT + "/media_publish"]


def test_cloud_cron_primary_backup_and_no_manual_provider_writes():
    workflow = (
        Path(__file__).resolve().parents[1] / ".github/workflows/lord-god-instagram-quote-cloud-20261111.yml"
    ).read_text(encoding="utf-8")
    assert workflow.count("    - cron:") == 2
    assert "cron: '45 9 12-15 11 *'" in workflow  # 12:45 Moscow, primary
    assert "cron: '10 10 12-15 11 *'" in workflow  # 13:10 Moscow, backup
    assert "cancel-in-progress: false" in workflow
    assert "github.event_name == 'schedule' && 'scheduled' || 'preflight'" in workflow


def _valid_meta_photo(caption):
    return {
        "id": "123456789012345",
        "caption": caption,
        "media_type": "IMAGE",
        "permalink": "https://www.instagram.com/p/approved-post/",
        "timestamp": "2026-11-12T09:46:00+00:00",
    }


def test_paged_provider_feed_finds_existing_photo(publisher, monkeypatch):
    caption = publisher.read_plan()[0]["caption"]
    cursor = "opaque/+=="
    calls = []

    def provider(endpoint, token, *, data=None):
        assert data is None
        calls.append(endpoint)
        if len(calls) == 1:
            return {
                "data": [{"id": "222", "caption": "Different post"}],
                "paging": {
                    "next": "https://example.invalid/ignore-this-untrusted-url?access_token=never-log",
                    "cursors": {"after": cursor},
                },
            }
        if len(calls) == 2:
            return {"data": [_valid_meta_photo(caption)]}
        pytest.fail("Unexpected third provider call")

    monkeypatch.setattr(publisher, "request_json", provider)
    result = publisher.find_published("dummy-token", caption)
    assert result is not None
    assert result["id"] == "123456789012345"
    assert calls[0].startswith(publisher.INSTAGRAM_ACCOUNT + "/media?")
    assert "after=opaque%2F%2B%3D%3D" in calls[1]
    assert "example.invalid" not in calls[1]
    assert "access_token=" not in calls[1]


@pytest.mark.parametrize(
    "first_response",
    [
        {},
        {"data": {"not": "a list"}},
        {"data": [False]},
        {"data": [{}], "paging": "not a dictionary"},
        {"data": [{}], "paging": {"next": "https://example.invalid"}},
        {"data": [{}], "paging": {"next": "https://example.invalid", "cursors": "bad"}},
        {"data": [], "paging": {"next": "https://example.invalid", "cursors": {"after": "cursor"}}},
    ],
)
def test_incomplete_provider_feed_blocks_publishing(publisher, monkeypatch, first_response):
    monkeypatch.setattr(publisher, "request_json", lambda *a, **kw: first_response)
    with pytest.raises(RuntimeError, match="do not publish"):
        publisher.find_published("dummy-token", "caption")


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", "invalid-media-id"),
        ("media_type", "REELS"),
        ("permalink", "http://www.instagram.com/p/post/"),
        ("permalink", "https://evil.example/p/post/"),
        ("timestamp", None),
    ],
)
def test_existing_caption_requires_valid_provider_proof(publisher, monkeypatch, field, value):
    photo = _valid_meta_photo("same caption")
    photo[field] = value
    monkeypatch.setattr(publisher, "request_json", lambda *a, **kw: {"data": [photo]})
    with pytest.raises(RuntimeError, match="Matching photo has incomplete Meta proof"):
        publisher.find_published("dummy-token", "same caption")


def test_duplicate_caption_across_pages_blocks_all_provider_posts(publisher, monkeypatch):
    configure(monkeypatch, publisher)
    caption = publisher.read_plan()[0]["caption"]
    calls = []

    def provider(endpoint, token, *, data=None):
        assert data is None, "Provider POST must never be sent on duplicates"
        calls.append(endpoint)
        if len(calls) == 1:
            return {
                "data": [_valid_meta_photo(caption)],
                "paging": {"next": "https://example.invalid/page2", "cursors": {"after": "page2"}},
            }
        return {"data": [dict(_valid_meta_photo(caption), id="987654321012345")]}

    monkeypatch.setattr(publisher, "request_json", provider)
    with pytest.raises(RuntimeError, match="Duplicate approved photo caption"):
        publisher.main()
    assert len(calls) == 2


def test_too_many_media_pages_aborts_without_publishing(publisher, monkeypatch):
    calls = []

    def provider(endpoint, token, *, data=None):
        assert data is None
        calls.append(endpoint)
        n = len(calls)
        return {
            "data": [{"id": str(n), "caption": "another post"}],
            "paging": {"next": "https://example.invalid/page", "cursors": {"after": f"cursor{n}"}},
        }

    monkeypatch.setattr(publisher, "request_json", provider)
    with pytest.raises(RuntimeError, match="exceeds safe verification limit"):
        publisher.find_published("dummy-token", "approved caption")
    assert len(calls) == 5


def test_repeated_provider_cursor_aborts(publisher, monkeypatch):
    calls = []

    def provider(endpoint, token, *, data=None):
        assert data is None
        calls.append(endpoint)
        return {
            "data": [{"id": "123", "caption": "other"}],
            "paging": {"next": "https://example.invalid/p", "cursors": {"after": "repeated"}},
        }

    monkeypatch.setattr(publisher, "request_json", provider)
    with pytest.raises(RuntimeError, match="cursor invalid"):
        publisher.find_published("dummy-token", "caption")
    assert len(calls) == 2
