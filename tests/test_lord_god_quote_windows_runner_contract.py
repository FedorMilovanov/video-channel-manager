"""Offline contract for native photo scheduler."""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

RUNNER = Path(__file__).resolve().parents[1] / "scripts/instagram/lord_god_quote_windows_runner_20261113.py"


@pytest.fixture
def runner():
    spec = importlib.util.spec_from_file_location("lord_god_windows_quote_runner", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preflight_only_invokes_same_publisher_read_only(runner, monkeypatch, tmp_path):
    calls = []
    db = tmp_path / "video_manager.db"
    db.touch()
    monkeypatch.setattr(runner, "DATABASE", db)
    monkeypatch.setattr(runner, "validate_deployed_bytes", lambda: calls.append("validate"))
    monkeypatch.setattr(runner, "read_dedicated_token", lambda: "test-only-token")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.setitem(
        sys.modules,
        "lord_god_quote_cloud_20261111",
        SimpleNamespace(main=lambda: calls.append(("publisher", runner.os.environ["LORD_GOD_CLOUD_MODE"]))),
    )
    assert runner.execute(preflight=True) == 0
    assert calls == ["validate", ("publisher", "preflight")]
    assert runner.os.environ["LORD_GOD_LOCAL_LEDGER_DB"] == str(db)


def test_windows_runner_blocks_unapproved_dates(runner, monkeypatch):
    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 12, 12, 45, tzinfo=tz)

    monkeypatch.setattr(runner.dt, "datetime", Clock)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    with pytest.raises(RuntimeError, match="remaining approved"):
        runner.execute(preflight=False)


def test_windows_runner_refuses_actions_environment(runner, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(RuntimeError, match="GitHub Actions"):
        runner.execute(preflight=True)


def test_registry_validates_original_publisher_hash(runner, monkeypatch, tmp_path):
    source = tmp_path / "publisher.py"
    source.write_text("print('offline fixture')\n", encoding="utf8")
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "executors": [
                    {
                        "path": "scripts/instagram/lord_god_quote_cloud_20261111.py",
                        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                        "provider_write_capable": True,
                    }
                ]
            }
        ),
        encoding="utf8",
    )
    db = tmp_path / "db.sqlite3"
    db.touch()
    env = tmp_path / ".env"
    env.touch()
    monkeypatch.setattr(runner, "SOURCE", source)
    monkeypatch.setattr(runner, "REGISTRY", registry)
    monkeypatch.setattr(runner, "DATABASE", db)
    monkeypatch.setattr(runner, "ENV_FILE", env)
    runner.validate_deployed_bytes()
    source.write_text("modified", encoding="utf8")
    with pytest.raises(RuntimeError, match="SHA-256"):
        runner.validate_deployed_bytes()


def test_dedicated_token_cannot_use_other_account(runner, monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("OTHER_ACCOUNT_TOKEN=test-only\n", encoding="utf8")
    monkeypatch.setattr(runner, "ENV_FILE", env)
    with pytest.raises(RuntimeError, match="dedicated"):
        runner.read_dedicated_token()
    env.write_text("VCM_INSTAGRAM_ACCESS_TOKEN_LORD_GOD_STRENGTH=" + "A" * 40, encoding="utf8")
    assert runner.read_dedicated_token() == "A" * 40
