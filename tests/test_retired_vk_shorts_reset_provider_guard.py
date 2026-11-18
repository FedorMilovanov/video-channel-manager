from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


RETIRED_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "vk_shorts_reset.py"
BLOCKED = "VK_SHORTS_RESET_RETIRED_PROVIDER_BLOCKED"


def _load_retired_base() -> ModuleType:
    spec = importlib.util.spec_from_file_location("vk_shorts_reset_import_guard_test", RETIRED_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_retired_vk_short_reset_import_remains_offline_but_cannot_construct_gateway(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Importing historical parsers must not revive their retired provider authority."""
    module = _load_retired_base()
    assert module._WAVE6_RETIRED_EXECUTOR is True
    assert module.API_BASE == "https://api.vk.ru/method"
    assert 9 not in module.READ_RETRY_CODES

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Retired code attempted token-store or HTTP initialization")

    # Guard assertions prove a genuine early refusal, not a network failure.
    monkeypatch.setattr(module, "VkTokenStore", forbidden)
    monkeypatch.setattr(module.httpx, "Client", forbidden)

    with pytest.raises(module.OperationError, match=BLOCKED):
        module.VkGateway("synthetic-only-token")
    with pytest.raises(module.OperationError, match=BLOCKED):
        module.load_token_and_gateway(tmp_path, "legacy-alias", 60805374)

    # Deliberately bypass constructor to verify both binary write boundaries
    # independently remain fail-closed if a downstream importer misuses the class.
    gateway = object.__new__(module.VkGateway)
    with pytest.raises(module.OperationError, match=BLOCKED):
        gateway._once("groups.getById", {"group_id": 60805374})
    with pytest.raises(module.OperationError, match=BLOCKED):
        gateway.upload_file_once("https://upload.example/secret", tmp_path / "missing.mp4")

    # Pure historical analysis helpers stay available without provider access.
    assert module.safe_title("  Проверка   истории  ") == "Проверка истории"
    assert module.EXPECTED_COMMUNITY == 60805374
