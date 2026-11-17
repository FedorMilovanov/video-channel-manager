"""#662: protect retired VK token evidence from local file mutation.

Uses synthetic credentials in pytest tmp_path. No network or live token reads.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore


@pytest.mark.parametrize(
    "alias",
    ["default", "DEFAULT", " DeFaUlT ", "legendary-poet", "LEGENDARY-POET", " LeGeNdArY-PoEt "],
)
def test_cannot_create_retired_token_under_legacy_alias(tmp_path: Path, alias: str) -> None:
    store = VkTokenStore(tmp_path)
    with pytest.raises(ValueError, match="quarantined") as captured:
        store.save_token(alias, VkAccessToken(access_token="synthetic-canary"))
    assert "synthetic-canary" not in str(captured.value)
    assert not store.token_dir.exists()
    assert not store.registry_path.exists()


@pytest.mark.parametrize("alias", ["default", "DEFAULT", " legendary-poet ", "LeGeNdArY-PoEt"])
def test_retired_alias_cannot_be_deleted_or_overwritten(tmp_path: Path, alias: str) -> None:
    store = VkTokenStore(tmp_path)
    # Seed an offline historical evidence fixture *without* save_token.
    # The store must retain readable evidence but reject any write/delete.
    path = store.token_path("default")
    path.parent.mkdir(parents=True, exist_ok=True)
    original = json.dumps(VkAccessToken(access_token="synthetic-retired-evidence").model_dump(mode="json"))
    path.write_text(original, encoding="utf-8")

    with pytest.raises(ValueError, match="quarantined"):
        store.save_token(alias, VkAccessToken(access_token="synthetic-replacement"))
    with pytest.raises(ValueError, match="quarantined"):
        store.delete_token(alias)
    assert path.read_text(encoding="utf-8") == original
    assert store.load_token("default").access_token == "synthetic-retired-evidence"
    assert list(path.parent.iterdir()) == [path]


def test_offline_forensic_read_only_remains_available(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    path = store.token_path("legendary-poet")
    path.parent.mkdir(parents=True, exist_ok=True)
    original = json.dumps(VkAccessToken(access_token="synthetic-forensic").model_dump(mode="json"))
    path.write_text(original, encoding="utf-8")
    assert store.load_token("legendary-poet").access_token == "synthetic-forensic"
    assert path.read_text(encoding="utf-8") == original


def test_new_reviewed_alias_still_supports_save_load_and_delete(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    path = store.save_token("synthetic-reviewed-community", VkAccessToken(access_token="new-synthetic-key"))
    assert path.is_file()
    assert store.load_token("synthetic-reviewed-community").access_token == "new-synthetic-key"
    store.delete_token("synthetic-reviewed-community")
    assert not path.exists()
