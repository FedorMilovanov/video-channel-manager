from __future__ import annotations

import importlib.util
import zoneinfo
from datetime import timedelta, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(module_name: str, file_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / file_name)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _forbid_provider(*args: object, **kwargs: object) -> None:
    raise AssertionError("Retired VK scheduler reached provider code or token storage")


def test_retired_article_base_rejects_all_entrypoints_before_provider_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load("retired_article_guard_test", "schedule_lord_god_article_wave.py")
    assert module._WAVE6_RETIRED_EXECUTOR is True
    monkeypatch.setattr(module, "VkApiClient", _forbid_provider)
    monkeypatch.setattr(module, "VkTokenStore", _forbid_provider)
    monkeypatch.setattr(module.httpx, "Client", _forbid_provider)

    with pytest.raises(RuntimeError, match="VK_RETIRED_ARTICLE_SCHEDULER_BLOCKED"):
        module.run(tmp_path, mode="plan")
    with pytest.raises(RuntimeError, match="VK_RETIRED_ARTICLE_SCHEDULER_BLOCKED"):
        module.main()
    with pytest.raises(RuntimeError, match="VK_RETIRED_ARTICLE_SCHEDULER_BLOCKED"):
        module.post_once(object(), {})
    with pytest.raises(RuntimeError, match="VK_RETIRED_ARTICLE_SCHEDULER_BLOCKED"):
        module.execute_scope(
            mode="apply",
            policy={},
            client=object(),
            settings=None,
            report={},
            journal={},
            journal_path=tmp_path / "journal.json",
            output_dir=tmp_path,
        )
    assert not (tmp_path / "data").exists()


def test_retired_article_photo_adapter_refuses_imported_install_and_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load("retired_article_photo_guard_test", "schedule_lord_god_article_wave_current.py")
    assert module._WAVE6_RETIRED_EXECUTOR is True
    monkeypatch.setattr(module, "load_guarded_module", _forbid_provider)
    monkeypatch.setattr(module.httpx, "Client", _forbid_provider)

    with pytest.raises(RuntimeError, match="VK_RETIRED_ARTICLE_SCHEDULER_BLOCKED"):
        module.main()
    with pytest.raises(RuntimeError, match="VK_RETIRED_ARTICLE_SCHEDULER_BLOCKED"):
        module.install_explicit_photo_flow(object())


def test_retired_wall_tail_module_denies_tokens_reads_and_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Windows Python installations need not have an IANA tzdata bundle. Keep
    # this import-only regression offline and do not change the global resolver.
    with patch.object(zoneinfo, "ZoneInfo", return_value=timezone(timedelta(hours=3))):
        module = _load("retired_wall_tail_guard_test", "schedule_lord_god_wall_tail.py")
    assert module._WAVE6_RETIRED_EXECUTOR is True
    monkeypatch.setattr(module, "VkTokenStore", _forbid_provider)
    monkeypatch.setattr(module, "VkApiClient", _forbid_provider)

    with pytest.raises(RuntimeError, match="VK_RETIRED_WALL_TAIL_BLOCKED"):
        module.run(tmp_path, execute=False)
    with pytest.raises(RuntimeError, match="VK_RETIRED_WALL_TAIL_BLOCKED"):
        module.main()
    with pytest.raises(RuntimeError, match="VK_RETIRED_WALL_TAIL_BLOCKED"):
        module.post_once(object(), {})
    with pytest.raises(RuntimeError, match="VK_RETIRED_WALL_TAIL_BLOCKED"):
        module.wall_snapshot(object())
    with pytest.raises(RuntimeError, match="VK_RETIRED_WALL_TAIL_BLOCKED"):
        module.exact_video(object(), "-60805374_456239548")
    assert not (tmp_path / "data").exists()

    # Historical policy checks stay importable without opening a client.
    assert module.PROJECT_KEY == "lord-god-strength"
    assert module.COMMUNITY_ID == 60805374


def test_retired_wall_tail_current_import_does_not_monkeypatch_zoneinfo() -> None:
    old = zoneinfo.ZoneInfo
    module = _load("retired_wall_tail_current_guard_test", "schedule_lord_god_wall_tail_current.py")
    assert module._WAVE6_RETIRED_EXECUTOR is True
    assert zoneinfo.ZoneInfo is old
