"""Regression proof: delayed GitHub cron must not verify a future Moscow slot."""

from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts" / "instagram"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        ("2026-11-11T16:40:00+00:00", None),
        ("2026-11-12T16:39:59+00:00", None),
        ("2026-11-12T16:40:00+00:00", "2026-11-12"),
        ("2026-11-13T17:10:00+00:00", "2026-11-13"),
        ("2026-11-13T22:32:00+00:00", "2026-11-13"),
        ("2026-11-14T16:39:59+00:00", "2026-11-13"),
        ("2026-11-14T16:40:00+00:00", "2026-11-14"),
        ("2026-11-21T16:40:00+00:00", "2026-11-21"),
        ("2026-11-22T16:39:59+00:00", "2026-11-21"),
        ("2026-11-22T16:40:00+00:00", None),
    ],
)
def test_reel_readback_follows_last_started_moscow_window(timestamp: str, expected: str | None) -> None:
    script = _load("lord_god_reels_readback_cloud_20261112")
    assert script.scheduled_receipt_date(dt.datetime.fromisoformat(timestamp)) == expected


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        ("2026-11-12T10:34:59+00:00", None),
        ("2026-11-12T10:35:00+00:00", "2026-11-12"),
        ("2026-11-13T22:08:00+00:00", "2026-11-13"),
        ("2026-11-14T10:34:59+00:00", "2026-11-13"),
        ("2026-11-14T10:35:00+00:00", "2026-11-14"),
        ("2026-11-15T10:35:00+00:00", "2026-11-15"),
        ("2026-11-16T10:34:59+00:00", "2026-11-15"),
        ("2026-11-16T10:35:00+00:00", None),
    ],
)
def test_photo_readback_follows_last_started_moscow_window(timestamp: str, expected: str | None) -> None:
    script = _load("lord_god_quote_receipt_readonly_20261112")
    assert script.scheduled_receipt_date(dt.datetime.fromisoformat(timestamp)) == expected


def test_readbacks_refuse_naive_clocks() -> None:
    naive = dt.datetime(2026, 11, 14, 1, 30)
    with pytest.raises(ValueError, match="timezone-aware"):
        _load("lord_god_reels_readback_cloud_20261112").scheduled_receipt_date(naive)
    with pytest.raises(ValueError, match="timezone-aware"):
        _load("lord_god_quote_receipt_readonly_20261112").scheduled_receipt_date(naive)


def test_real_delayed_reel_cron_selects_nov13_not_future_nov14(monkeypatch, capsys) -> None:
    script = _load("lord_god_reels_readback_cloud_20261112")

    class FixedNow(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 11, 13, 22, 32, tzinfo=dt.timezone.utc).astimezone(tz)

    monkeypatch.setattr(script, "datetime", FixedNow)
    monkeypatch.setattr(script, "check_identity", lambda token: None)
    monkeypatch.setattr(script, "list_recent_media", lambda token: [])
    monkeypatch.setenv("LORD_GOD_PAGE_TOKEN", "test-provider-inert-bearer-token-" * 2)
    monkeypatch.setenv("LORD_GOD_REELS_PROOF_MODE", "scheduled")
    assert script.main() == 2
    out = capsys.readouterr().out
    assert "REEL_MISSING_ON_META 2026-11-13 B8SjAuu4Glg" in out
    assert "REEL_MISSING_ON_META 2026-11-14" not in out


def test_delayed_photo_cron_does_not_check_upcoming_photo(monkeypatch, capsys) -> None:
    script = _load("lord_god_quote_receipt_readonly_20261112")

    class FixedNow(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 11, 13, 22, 32, tzinfo=dt.timezone.utc).astimezone(tz)

    monkeypatch.setattr(
        script,
        "dt",
        SimpleNamespace(datetime=FixedNow, date=dt.date, time=dt.time, timedelta=dt.timedelta),
    )
    monkeypatch.setattr(script, "verify_identity", lambda token: None)
    monkeypatch.setattr(script, "list_media", lambda token: [])
    monkeypatch.setenv("LORD_GOD_PAGE_TOKEN", "test-provider-inert-bearer-token-" * 2)
    monkeypatch.setenv("LORD_GOD_QUOTE_RECEIPT_MODE", "scheduled")
    assert script.main() == 2
    out = capsys.readouterr().out
    assert "IMAGE_MISSING_ON_META 02-owen 2026-11-13" in out
    assert "IMAGE_MISSING_ON_META 03-bunyan" not in out
