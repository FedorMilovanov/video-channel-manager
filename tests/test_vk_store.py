from __future__ import annotations

from pathlib import Path

from video_channel_manager.platforms.vk.models import VkAccessToken, VkAccount, VkUserIdentity
from video_channel_manager.platforms.vk.store import VkTokenStore


def test_vk_token_and_registry_are_separate(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token("synthetic-registered", VkAccessToken(access_token="super-secret-value"))
    store.save_account(
        VkAccount(
            alias="synthetic-registered",
            token_file=str(store.token_path("synthetic-registered")),
            user=VkUserIdentity(user_id=42, display_name="Legendary Poet"),
        )
    )

    assert store.load_token("synthetic-registered").access_token == "super-secret-value"
    assert store.list_accounts()[0].user.user_id == 42
    assert "super-secret-value" not in store.registry_path.read_text(encoding="utf-8")


def test_vk_token_store_finds_aliases_sharing_same_access_token(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token("synthetic-first", VkAccessToken(access_token="shared-token"))
    store.save_token("synthetic-second", VkAccessToken(access_token="shared-token"))
    store.save_token("other", VkAccessToken(access_token="different-token"))

    assert store.aliases_sharing_access_token("synthetic-second") == ("synthetic-first", "synthetic-second")
    assert store.aliases_sharing_access_token("other") == ("other",)
