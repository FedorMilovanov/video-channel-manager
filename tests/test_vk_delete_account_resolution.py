from pathlib import Path

import pytest

from video_channel_manager.cli.vk_delete import _resolve_account_alias
from video_channel_manager.platforms.vk import VkAccessToken, VkAccountNotFoundError, VkTokenStore


def test_default_resolves_to_the_only_stored_vk_token(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token("legendary-poet", VkAccessToken(access_token="test-token"))

    assert _resolve_account_alias(store, "default") == "legendary-poet"


def test_explicit_stored_alias_is_preserved(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token("legendary-poet", VkAccessToken(access_token="test-token"))

    assert _resolve_account_alias(store, "legendary-poet") == "legendary-poet"


def test_ambiguous_default_does_not_choose_between_multiple_tokens(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token("first", VkAccessToken(access_token="first-token"))
    store.save_token("second", VkAccessToken(access_token="second-token"))

    with pytest.raises(VkAccountNotFoundError, match="Available stored aliases: first, second"):
        _resolve_account_alias(store, "default")
