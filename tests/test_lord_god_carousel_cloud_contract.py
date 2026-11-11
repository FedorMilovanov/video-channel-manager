"""Offline contracts for the six source-bound Lord God Instagram carousels."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/instagram/lord_god_carousel_cloud_20261116.py"


@pytest.fixture
def publisher():
    spec = importlib.util.spec_from_file_location("lord_god_carousel_cloud_contract", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def configure(monkeypatch, mod, *, day=16, hour=12, minute=47, mode="scheduled", event="schedule"):
    class FixedDateTime:
        @staticmethod
        def now(tz):
            return datetime(2026, 11, day, hour, minute, tzinfo=tz)

    monkeypatch.setattr(mod, "datetime", FixedDateTime)
    monkeypatch.setenv("LORD_GOD_PAGE_TOKEN", "dummy_test_secret_" * 4)
    monkeypatch.setenv("LORD_GOD_CLOUD_MODE", mode)
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    monkeypatch.setattr(mod, "validate_identity", lambda token: None)
    monkeypatch.setattr(mod, "media_url", lambda data: "https://example.invalid/immutable.jpg")


def test_six_exact_days_and_thirty_frozen_assets(publisher):
    items, assets = publisher.validated_plan()
    assert [(p["id"], p["date"], p["time"]) for p in items] == [
        ("01-heart", "2026-11-16", "12:45"),
        ("02-congresses", "2026-11-17", "12:45"),
        ("03-peter4", "2026-11-18", "12:45"),
        ("04-christ", "2026-11-19", "12:45"),
        ("05-jude", "2026-11-20", "12:45"),
        ("06-spirits", "2026-11-21", "12:45"),
    ]
    assert len(assets) == 30
    assert all(len(p["slides"]) == 5 for p in items)


@pytest.mark.parametrize("field,value", [("date", "2026-11-11"), ("time", "12:30"), ("surface", "image")])
def test_plan_mutations_are_rejected(publisher, monkeypatch, tmp_path, field, value):
    plan = json.loads(publisher.PLAN.read_text(encoding="utf-8"))
    plan["items"][0][field] = value
    path = tmp_path / "invalid_plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    monkeypatch.setattr(publisher, "PLAN", path)
    with pytest.raises(RuntimeError):
        publisher.validated_plan()


@pytest.mark.parametrize("hour,minute", [(12, 44), (14, 0), (23, 59)])
def test_schedule_window_rejects_provider_writes(publisher, monkeypatch, hour, minute):
    configure(monkeypatch, publisher, hour=hour, minute=minute)
    monkeypatch.setattr(publisher, "api", lambda *a, **k: pytest.fail("Unexpected provider POST"))
    with pytest.raises(RuntimeError, match="Outside"):
        publisher.main()


def test_manual_dispatch_is_get_only(publisher, monkeypatch, capsys):
    configure(monkeypatch, publisher, mode="preflight", event="workflow_dispatch")
    monkeypatch.setattr(publisher, "find_existing", lambda *a: None)
    monkeypatch.setattr(publisher, "api", lambda *a, **k: pytest.fail("Unexpected Meta API"))
    publisher.main()
    text = capsys.readouterr().out
    assert text.count("PREFLIGHT ") == 6
    assert "PREFLIGHT_OK_NO_POST" in text


def test_scheduled_mode_requires_real_schedule_event(publisher, monkeypatch):
    configure(monkeypatch, publisher, mode="scheduled", event="workflow_dispatch")
    monkeypatch.setattr(publisher, "api", lambda *a, **k: pytest.fail("Unexpected provider call"))
    with pytest.raises(RuntimeError, match="genuine scheduled GitHub event"):
        publisher.main()


def test_already_published_skips_every_write(publisher, monkeypatch, capsys):
    configure(monkeypatch, publisher)
    monkeypatch.setattr(publisher, "find_existing", lambda *a: {"id": "1234", "permalink": "https://instagram.com/p/x"})
    monkeypatch.setattr(publisher, "api", lambda *a, **k: pytest.fail("Unexpected duplicate POST"))
    publisher.main()
    assert "ALREADY_PUBLISHED_SKIP" in capsys.readouterr().out


def test_five_children_one_parent_one_publish(publisher, monkeypatch, capsys):
    configure(monkeypatch, publisher)
    monkeypatch.setattr(publisher, "find_existing", lambda *a: None)
    monkeypatch.setattr(publisher, "poll_finished", lambda *a: None)
    caption = publisher.validated_plan()[0][0]["caption"]
    calls = []

    def provider(token, endpoint, *, data=None):
        calls.append((endpoint, data))
        if endpoint.endswith("/media") and data and data.get("is_carousel_item") == "true":
            return {"id": str(2000 + len([x for x in calls if x[1] and x[1].get("is_carousel_item")]))}
        if endpoint.endswith("/media") and data and data.get("media_type") == "CAROUSEL":
            assert len(data["children"].split(",")) == 5
            return {"id": "5000"}
        if endpoint.endswith("/media_publish"):
            assert data == {"creation_id": "5000"}
            return {"id": "6000"}
        if endpoint.startswith("6000?"):
            return {
                "id": "6000",
                "caption": caption,
                "media_type": "CAROUSEL_ALBUM",
                "permalink": "https://www.instagram.com/p/example/",
            }
        pytest.fail(f"Unexpected endpoint: {endpoint}")

    monkeypatch.setattr(publisher, "api", provider)
    publisher.main()
    assert len([x for x in calls if x[1] and x[1].get("is_carousel_item")]) == 5
    assert len([x for x in calls if x[1] and x[1].get("media_type") == "CAROUSEL"]) == 1
    assert len([x for x in calls if x[0].endswith("/media_publish")]) == 1
    assert "PUBLISHED_CONFIRMED" in capsys.readouterr().out


def test_ambiguous_publish_is_not_retried(publisher, monkeypatch):
    configure(monkeypatch, publisher)
    monkeypatch.setattr(publisher, "find_existing", lambda *a: None)
    monkeypatch.setattr(publisher, "poll_finished", lambda *a: None)
    attempts = []

    def provider(token, endpoint, *, data=None):
        if endpoint.endswith("/media") and data and data.get("is_carousel_item"):
            return {"id": str(3000 + len(attempts))}
        if endpoint.endswith("/media") and data and data.get("media_type") == "CAROUSEL":
            return {"id": "5000"}
        if endpoint.endswith("/media_publish"):
            attempts.append(endpoint)
            raise RuntimeError("Meta response ambiguous")
        pytest.fail(f"Unexpected endpoint: {endpoint}")

    monkeypatch.setattr(publisher, "api", provider)
    with pytest.raises(RuntimeError, match="ambiguous"):
        publisher.main()
    assert attempts == [publisher.INSTAGRAM + "/media_publish"]


def test_only_two_crons_and_readonly_manual_dispatch():
    yml = (ROOT / ".github/workflows/lord-god-instagram-carousel-cloud-20261116.yml").read_text(encoding="utf-8")
    assert yml.count("    - cron:") == 2
    assert "cron: '45 9 16-21 11 *'" in yml
    assert "cron: '10 10 16-21 11 *'" in yml
    assert "cancel-in-progress: false" in yml
    assert "github.event_name == 'schedule' && 'scheduled' || 'preflight'" in yml
