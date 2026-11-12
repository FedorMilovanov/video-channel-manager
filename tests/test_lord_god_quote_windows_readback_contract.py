"""Offline contract for independent native GET-only IMAGE proof."""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/instagram/lord_god_quote_windows_readback_20261113.py"


@pytest.fixture
def reader():
    script_dir = str(PATH.parent)
    sys.path.insert(0, script_dir)
    try:
        spec = importlib.util.spec_from_file_location("lord_god_native_photo_readback_contract", PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.path.remove(script_dir)


def test_independent_preflight_is_read_only(reader, monkeypatch):
    calls = []
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.setattr(reader, "validate_deployed_bytes", lambda: calls.append("publisher_sha"))
    monkeypatch.setattr(reader, "validate_readback_source", lambda: calls.append("readback_sha"))
    monkeypatch.setattr(reader, "read_dedicated_token", lambda: "offline-token")
    monkeypatch.setitem(
        sys.modules,
        "lord_god_quote_receipt_readonly_20261112",
        SimpleNamespace(main=lambda: calls.append(("original", reader.os.environ["LORD_GOD_QUOTE_RECEIPT_MODE"])) or 0),
    )
    assert reader.execute(preflight=True) == 0
    assert calls == ["publisher_sha", "readback_sha", ("original", "preflight")]


def test_native_schedule_enforces_moscow_hour(reader, monkeypatch):
    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 13, 13, 55, tzinfo=tz)

    monkeypatch.setattr(reader.dt, "datetime", Clock)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    with pytest.raises(RuntimeError, match="before 14:00"):
        reader.execute()


def test_native_schedule_enforces_approved_dates(reader, monkeypatch):
    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 16, 14, 10, tzinfo=tz)

    monkeypatch.setattr(reader.dt, "datetime", Clock)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    with pytest.raises(RuntimeError, match="approved IMAGE"):
        reader.execute()


def test_get_only_source_sha_and_plan_are_pinned(reader, monkeypatch, tmp_path):
    program = tmp_path / "readback.py"
    program.write_bytes(b"verified readback")
    plan = tmp_path / "approved-plan.json"
    plan.write_bytes(b"approved")
    registry = tmp_path / "registry.json"
    sha = hashlib.sha256(program.read_bytes()).hexdigest()
    registry.write_text(
        json.dumps(
            {
                "executors": [
                    {
                        "path": "scripts/instagram/lord_god_quote_receipt_readonly_20261112.py",
                        "provider_write_capable": False,
                        "sha256": sha,
                    }
                ]
            }
        ),
        encoding="utf8",
    )
    monkeypatch.setattr(reader, "READBACK_PATH", program)
    monkeypatch.setattr(reader, "REGISTRY", registry)
    monkeypatch.setattr(reader, "PLAN", plan)
    monkeypatch.setattr(reader, "PLAN_SHA256", hashlib.sha256(plan.read_bytes()).hexdigest())
    reader.validate_readback_source()
    program.write_bytes(b"altered")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        reader.validate_readback_source()


def test_refuses_unsafe_provider_or_github_actions(reader, monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(RuntimeError, match="GitHub Actions"):
        reader.execute(preflight=True)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    plan = tmp_path / "approved-plan.json"
    plan.write_bytes(b"approved")
    registry = tmp_path / "registry.json"
    source = tmp_path / "readback.py"
    source.write_bytes(b"only get")
    registry.write_text(
        json.dumps(
            {
                "executors": [
                    {
                        "path": "scripts/instagram/lord_god_quote_receipt_readonly_20261112.py",
                        "provider_write_capable": True,
                        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    }
                ]
            }
        ),
        encoding="utf8",
    )
    monkeypatch.setattr(reader, "PLAN", plan)
    monkeypatch.setattr(reader, "PLAN_SHA256", hashlib.sha256(plan.read_bytes()).hexdigest())
    monkeypatch.setattr(reader, "REGISTRY", registry)
    monkeypatch.setattr(reader, "READBACK_PATH", source)
    with pytest.raises(RuntimeError, match="GET-only"):
        reader.validate_readback_source()


def test_native_schedule_calls_original_scheduled_without_post(reader, monkeypatch):
    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 13, 14, 5, tzinfo=tz)

    monkeypatch.setattr(reader.dt, "datetime", Clock)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.setattr(reader, "validate_deployed_bytes", lambda: None)
    monkeypatch.setattr(reader, "validate_readback_source", lambda: None)
    monkeypatch.setattr(reader, "read_dedicated_token", lambda: "offline-token")
    monkeypatch.setitem(
        sys.modules,
        "lord_god_quote_receipt_readonly_20261112",
        SimpleNamespace(main=lambda: 2 if reader.os.environ["LORD_GOD_QUOTE_RECEIPT_MODE"] == "scheduled" else 0),
    )
    assert reader.execute() == 2
