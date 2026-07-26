from __future__ import annotations

from pathlib import Path

from video_channel_manager.platforms.vk.models import VkAccessToken, VkAccount, VkUserIdentity
from video_channel_manager.platforms.vk.store import VkTokenStore


def test_vk_token_and_registry_are_separate(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token("legendary-poet", VkAccessToken(access_token="super-secret-value"))
    store.save_account(
        VkAccount(
            alias="legendary-poet",
            token_file=str(store.token_path("legendary-poet")),
            user=VkUserIdentity(user_id=42, display_name="Legendary Poet"),
        )
    )

    assert store.load_token("legendary-poet").access_token == "super-secret-value"
    assert store.list_accounts()[0].user.user_id == 42
    assert "super-secret-value" not in store.registry_path.read_text(encoding="utf-8")
