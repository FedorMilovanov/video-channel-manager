"""Offline safety contracts for the four Lord God Instagram photo posts."""

from __future__ import annotations

import importlib.util
import io
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
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    class FixedDateTime:
        @staticmethod
        def now(tz):
            return datetime(2026, 11, 12, hour, minute, tzinfo=tz)

    monkeypatch.setenv("LORD_GOD_PAGE_TOKEN", "dummy-token-value-" * 4)
    monkeypatch.setenv("LORD_GOD_CLOUD_MODE", mode)
    monkeypatch.setattr(module, "datetime", FixedDateTime)
    monkeypatch.setattr(module, "verify_identity", lambda token: None)
    monkeypatch.setattr(module, "media_verified", lambda item: "https://example.invalid/safe-image.jpg")
    monkeypatch.setattr(module, "first_scheduled_run_for_day", lambda day: True)


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
    assert "  schedule:" not in workflow
    assert "    - cron:" not in workflow
    assert "  workflow_dispatch:" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "LORD_GOD_CLOUD_MODE: preflight" in workflow


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


def _set_scheduled_github_context(monkeypatch, *, run_id="111", attempt="1", cron="45 9 12-15 11 *"):
    monkeypatch.setenv("GITHUB_REPOSITORY", "FedorMilovanov/video-channel-manager")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", attempt)
    monkeypatch.setenv("GITHUB_EVENT_SCHEDULE", cron)
    monkeypatch.setenv("GITHUB_RUN_ID", run_id)
    monkeypatch.setenv("LORD_GOD_CLOUD_GITHUB_TOKEN", "offline-test-github-token-1234567")


def _gh_run(identifier, when):
    return {
        "id": identifier,
        "event": "schedule",
        "head_branch": "main",
        "created_at": when,
    }


def test_first_github_run_may_attempt_once(publisher, monkeypatch, capsys):
    _set_scheduled_github_context(monkeypatch, run_id="111")
    runs = [
        _gh_run(222, "2026-11-12T10:10:00Z"),
        _gh_run(111, "2026-11-12T09:45:00Z"),
    ]
    requests = []

    def offline_open(request, timeout):
        assert timeout == 30
        assert request.get_method() == "GET"
        assert request.full_url.startswith("https://api.github.com/repos/")
        assert "created=2026-11-12" in request.full_url
        assert "event=schedule" in request.full_url
        assert request.get_header("Authorization") == "Bearer offline-test-github-token-1234567"
        requests.append(request)
        return io.BytesIO(json.dumps({"total_count": 2, "workflow_runs": runs}).encode())

    monkeypatch.setattr(publisher, "urlopen", offline_open)
    assert publisher.first_scheduled_run_for_day("2026-11-12") is True
    assert len(requests) == 1
    assert "FIRST_SCHEDULED_RUN_WRITE_ELIGIBLE" in capsys.readouterr().out


def test_backup_skips_if_primary_was_created_even_if_primary_failed(publisher, monkeypatch, capsys):
    _set_scheduled_github_context(monkeypatch, run_id="222", cron="10 10 12-15 11 *")
    runs = [
        _gh_run(222, "2026-11-12T10:10:00Z"),
        _gh_run(111, "2026-11-12T09:45:00Z"),
    ]
    monkeypatch.setattr(
        publisher,
        "urlopen",
        lambda request, timeout: io.BytesIO(json.dumps({"total_count": 2, "workflow_runs": runs}).encode()),
    )
    assert publisher.first_scheduled_run_for_day("2026-11-12") is False
    assert "LATER_SCHEDULED_RUN_READ_ONLY_SKIP" in capsys.readouterr().out


def test_backup_can_own_day_only_if_primary_run_never_existed(publisher, monkeypatch):
    _set_scheduled_github_context(monkeypatch, run_id="222", cron="10 10 12-15 11 *")
    runs = [_gh_run(222, "2026-11-12T10:10:00Z")]
    monkeypatch.setattr(
        publisher,
        "urlopen",
        lambda request, timeout: io.BytesIO(json.dumps({"total_count": 1, "workflow_runs": runs}).encode()),
    )
    assert publisher.first_scheduled_run_for_day("2026-11-12") is True


@pytest.mark.parametrize("attempt", ["2", "3", "", "0"])
def test_rerunning_original_schedule_never_posts(publisher, monkeypatch, attempt):
    _set_scheduled_github_context(monkeypatch, run_id="111", attempt=attempt)
    monkeypatch.setattr(publisher, "urlopen", lambda *a, **k: pytest.fail("Unapproved GitHub API lookup"))
    with pytest.raises(RuntimeError, match="Unapproved cloud workflow invocation"):
        publisher.first_scheduled_run_for_day("2026-11-12")


@pytest.mark.parametrize(
    "listing",
    [
        {},
        {"total_count": 0, "workflow_runs": []},
        {"total_count": 101, "workflow_runs": []},
        {"total_count": 2, "workflow_runs": [_gh_run(111, "2026-11-12T09:45:00Z")]},
        {"total_count": 1, "workflow_runs": [_gh_run(222, "2026-11-12T10:10:00Z")]},
        {"total_count": 1, "workflow_runs": [_gh_run(111, "2026-11-13T09:45:00Z")]},
        {"total_count": 1, "workflow_runs": [dict(_gh_run(111, "2026-11-12T09:45:00Z"), event="push")]},
    ],
)
def test_untrusted_or_incomplete_run_registry_blocks_provider_post(publisher, monkeypatch, listing):
    _set_scheduled_github_context(monkeypatch, run_id="111")
    monkeypatch.setattr(
        publisher,
        "urlopen",
        lambda request, timeout: io.BytesIO(json.dumps(listing).encode()),
    )
    with pytest.raises(RuntimeError, match="do not publish"):
        publisher.first_scheduled_run_for_day("2026-11-12")


def test_second_run_never_calls_provider_post_even_when_photo_missing(publisher, monkeypatch, capsys):
    configure(monkeypatch, publisher)
    monkeypatch.setattr(publisher, "find_published", lambda *a: None)
    monkeypatch.setattr(publisher, "first_scheduled_run_for_day", lambda day: False)
    monkeypatch.setattr(publisher, "request_json", lambda *a, **k: pytest.fail("No provider POST allowed"))
    publisher.main()
    assert "POST_START" not in capsys.readouterr().out


def test_workflow_has_actions_read_token_and_schedule_context():
    workflow = (
        Path(__file__).resolve().parents[1] / ".github/workflows/lord-god-instagram-quote-cloud-20261111.yml"
    ).read_text(encoding="utf-8")
    assert "  actions: read" in workflow
    assert "  contents: read" in workflow
    assert "LORD_GOD_CLOUD_GITHUB_TOKEN: ${{ github.token }}" in workflow
    assert "GITHUB_EVENT_SCHEDULE: ${{ github.event.schedule || 'manual' }}" in workflow
    assert "cancel-in-progress: false" in workflow


@pytest.mark.parametrize(
    "malformed",
    [
        None,
        False,
        [],
        "",
        {"next": None},
        {"next": False},
        {"next": 0},
        {"next": ""},
        {"next": []},
        {"next": {}},
        {"next": "https://example.invalid/p", "cursors": None},
        {"next": "https://example.invalid/p", "cursors": []},
    ],
)
def test_explicit_malformed_paging_must_fail_closed_without_post(publisher, monkeypatch, malformed):
    monkeypatch.setattr(publisher, "request_json", lambda *args, **kwargs: {"data": [], "paging": malformed})
    with pytest.raises(RuntimeError, match="do not publish"):
        publisher.find_published("offline-token", "approved caption")


@pytest.mark.parametrize("terminal", [{}, {"cursors": {"after": "unused"}}])
def test_terminal_paging_without_next_is_accepted(publisher, monkeypatch, terminal):
    monkeypatch.setattr(publisher, "request_json", lambda *args, **kwargs: {"data": [], "paging": terminal})
    assert publisher.find_published("offline-token", "approved caption") is None


def test_approved_quote_plan_caption_tamper_blocked_by_whole_file_hash(publisher, monkeypatch, tmp_path):
    plan = json.loads(publisher.PLAN.read_text(encoding="utf8"))
    plan["items"][0]["caption"] += " unauthorized offline change"
    path = tmp_path / "modified-caption.json"
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf8")
    monkeypatch.setattr(publisher, "PLAN", path)
    with pytest.raises(RuntimeError, match="Frozen approved quote plan SHA-256 mismatch"):
        publisher.read_plan()


def test_local_photo_claim_is_durable_and_unique(publisher, monkeypatch, tmp_path):
    import hashlib
    import sqlite3

    database = tmp_path / "video_manager.db"
    sqlite3.connect(database).close()
    monkeypatch.setenv("LORD_GOD_LOCAL_LEDGER_DB", str(database))
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    item = publisher.read_plan()[1]
    publisher.claim_local_photo_once(item, item["date"])
    with sqlite3.connect(database) as conn:
        rows = conn.execute("SELECT state,item_id,caption_sha256 FROM instagram_lord_god_quote_attempts").fetchall()
    assert rows == [("CLAIMED", "02-owen", hashlib.sha256(item["caption"].encode()).hexdigest())]
    with pytest.raises(RuntimeError, match="already claimed"):
        publisher.claim_local_photo_once(item, item["date"])
    publisher.finalize_local_photo(item, item["date"], "123456789", "https://www.instagram.com/p/offline/")
    with sqlite3.connect(database) as conn:
        assert conn.execute("SELECT state,media_id FROM instagram_lord_god_quote_attempts").fetchone() == (
            "VERIFIED",
            "123456789",
        )
    with pytest.raises(RuntimeError, match="already claimed"):
        publisher.claim_local_photo_once(item, item["date"])


def test_local_claim_refuses_nonexistent_ledger_and_github(publisher, monkeypatch, tmp_path):
    import sqlite3

    item = publisher.read_plan()[1]
    database = tmp_path / "video_manager.db"
    monkeypatch.setenv("LORD_GOD_LOCAL_LEDGER_DB", str(database))
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    with pytest.raises(RuntimeError, match="Local publisher ledger"):
        publisher.claim_local_photo_once(item, item["date"])
    sqlite3.connect(database).close()
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(RuntimeError, match="GitHub Actions"):
        publisher.claim_local_photo_once(item, item["date"])


def test_local_mode_claim_precedes_first_meta_post(publisher, monkeypatch):
    configure(monkeypatch, publisher, mode="local_scheduled", hour=12, minute=47)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.setattr(publisher, "find_published", lambda *args: None)
    calls = []
    monkeypatch.setattr(publisher, "claim_local_photo_once", lambda item, day: calls.append("CLAIM"))
    monkeypatch.setattr(publisher, "finalize_local_photo", lambda *args: calls.append("VERIFIED"))
    caption = publisher.read_plan()[0]["caption"]

    def fake_request(endpoint, token, *, data=None):
        if data is not None:
            assert calls[0] == "CLAIM"
        if endpoint.endswith("/media") and data is not None:
            calls.append("CONTAINER")
            return {"id": "12345"}
        if endpoint == "12345?fields=status_code":
            return {"status_code": "FINISHED"}
        if endpoint.endswith("/media_publish"):
            calls.append("PUBLISH")
            return {"id": "67890"}
        if endpoint.startswith("67890?"):
            return {
                "id": "67890",
                "caption": caption,
                "media_type": "IMAGE",
                "permalink": "https://www.instagram.com/p/offline/",
                "timestamp": "2026-11-12T09:47:00Z",
            }
        pytest.fail("Unexpected Meta API call")

    monkeypatch.setattr(publisher, "request_json", fake_request)
    publisher.main()
    assert calls == ["CLAIM", "CONTAINER", "PUBLISH", "VERIFIED"]


def test_ambiguous_local_post_never_retries(publisher, monkeypatch, tmp_path):
    import sqlite3

    database = tmp_path / "video_manager.db"
    sqlite3.connect(database).close()
    monkeypatch.setenv("LORD_GOD_LOCAL_LEDGER_DB", str(database))
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    configure(monkeypatch, publisher, mode="local_scheduled", hour=12, minute=48)
    monkeypatch.setattr(publisher, "find_published", lambda *args: None)
    attempts = []

    def fake_request(endpoint, token, *, data=None):
        if endpoint.endswith("/media") and data:
            attempts.append(endpoint)
            raise RuntimeError("Ambiguous Meta response")
        pytest.fail("Unexpected Meta request")

    monkeypatch.setattr(publisher, "request_json", fake_request)
    with pytest.raises(RuntimeError, match="Ambiguous Meta response"):
        publisher.main()
    with sqlite3.connect(database) as conn:
        assert conn.execute("SELECT state FROM instagram_lord_god_quote_attempts").fetchone() == ("CLAIMED",)
    with pytest.raises(RuntimeError, match="already claimed"):
        publisher.main()
    assert len(attempts) == 1


def test_github_actions_mode_is_read_only_even_on_legacy_schedule(publisher, monkeypatch):
    configure(monkeypatch, publisher, mode="scheduled")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(publisher, "request_json", lambda *args, **kwargs: pytest.fail("Provider call"))
    with pytest.raises(RuntimeError, match="retired"):
        publisher.main()
