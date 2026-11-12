"""Offline invariants for the native strictly GET-only Reel readback."""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/instagram/lord_god_reels_windows_readback_20261113.py"


@pytest.fixture
def wrapper():
    sys.path.insert(0, str(SOURCE.parent))
    try:
        spec = importlib.util.spec_from_file_location("lord_god_reel_receipt_test", SOURCE)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.path.remove(str(SOURCE.parent))


def test_safe_preflight_reuses_original_core(wrapper, monkeypatch):
    actions = []
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.setattr(wrapper, "validate_deployment", lambda: actions.append("SHA"))
    monkeypatch.setattr(wrapper, "read_dedicated_token", lambda: "offline-secret")
    monkeypatch.setitem(
        sys.modules,
        "lord_god_reels_readback_cloud_20261112",
        SimpleNamespace(main=lambda: actions.append(wrapper.os.environ["LORD_GOD_REELS_PROOF_MODE"]) or 0),
    )
    assert wrapper.execute(preflight=True) == 0
    assert actions == ["SHA", "preflight"]


@pytest.mark.parametrize(
    "moment,expect",
    [
        ((2026, 11, 12, 20, 10), "approved"),
        ((2026, 11, 22, 20, 10), "approved"),
        ((2026, 11, 13, 20, 4), "20:05"),
        ((2026, 11, 13, 21, 16), "20:05"),
    ],
)
def test_release_dates_and_hours_are_bounded(wrapper, monkeypatch, moment, expect):
    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(*moment, tzinfo=tz)

    monkeypatch.setattr(wrapper.dt, "datetime", Clock)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    with pytest.raises(RuntimeError, match=expect):
        wrapper.execute()


def test_actions_environment_is_refused(wrapper, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(RuntimeError, match="GitHub Actions"):
        wrapper.execute(preflight=True)


def test_pinned_source_and_immutable_manifest(wrapper, monkeypatch, tmp_path):
    core = tmp_path / "core.py"
    core.write_text("offline GET only", encoding="utf8")
    helper = tmp_path / "helper.py"
    helper.write_text("offline helper", encoding="utf8")
    plan = tmp_path / "plan.json"
    plan.write_text("frozen test", encoding="utf8")
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "executors": [
                    {
                        "path": "scripts/instagram/lord_god_reels_readback_cloud_20261112.py",
                        "provider_write_capable": False,
                        "sha256": hashlib.sha256(core.read_bytes()).hexdigest(),
                    },
                    {
                        "path": "scripts/instagram/lord_god_quote_windows_runner_20261113.py",
                        "provider_write_capable": True,
                        "sha256": hashlib.sha256(helper.read_bytes()).hexdigest(),
                    },
                ]
            }
        ),
        encoding="utf8",
    )
    monkeypatch.setattr(wrapper, "PROOF", core)
    monkeypatch.setattr(wrapper, "CREDENTIAL_READER", helper)
    monkeypatch.setattr(wrapper, "PLAN", plan)
    monkeypatch.setattr(wrapper, "REGISTRY", registry)
    monkeypatch.setattr(wrapper, "PLAN_SHA256", hashlib.sha256(plan.read_bytes()).hexdigest())
    wrapper.validate_deployment()
    core.write_text("changed", encoding="utf8")
    with pytest.raises(RuntimeError, match="SHA-256"):
        wrapper.validate_deployment()


def test_missing_provider_receipt_is_nonzero(wrapper, monkeypatch):
    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 13, 20, 10, tzinfo=tz)

    monkeypatch.setattr(wrapper.dt, "datetime", Clock)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.setattr(wrapper, "validate_deployment", lambda: None)
    monkeypatch.setattr(wrapper, "read_dedicated_token", lambda: "offline-secret")
    monkeypatch.setitem(
        sys.modules,
        "lord_god_reels_readback_cloud_20261112",
        SimpleNamespace(main=lambda: 2 if wrapper.os.environ["LORD_GOD_REELS_PROOF_MODE"] == "scheduled" else 0),
    )
    assert wrapper.execute() == 2
