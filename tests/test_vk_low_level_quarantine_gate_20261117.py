"""Issue #662: direct low-level VK clients must also obey legacy quarantine.

Provider-inert tests. Never load or print live tokens, never send an API request.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from video_channel_manager.platforms.vk.client import VkApiClient
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.thumbnails import VkThumbnailWriter
from video_channel_manager.platforms.vk.writer import VkVideoWriter


class ForbiddenStoreAccess:
    def validate_alias(self, alias: str) -> str:
        pytest.fail("Retired alias reached the token store")


@pytest.mark.parametrize("factory", [VkApiClient, VkVideoWriter, VkThumbnailWriter])
@pytest.mark.parametrize("alias", ["default", "DEFAULT", "legendary-poet", "LeGeNdArY-PoEt"])
def test_direct_provider_constructor_rejects_retired_alias_before_store(factory, alias: str) -> None:
    with pytest.raises(ValueError, match="quarantined"):
        factory(token_store=ForbiddenStoreAccess(), account_alias=alias)


@pytest.mark.parametrize(
    ("factory", "operation"),
    [
        (VkApiClient, lambda c: c._call("users.get")),
        (VkVideoWriter, lambda c: c.assert_token_scopes("video")),
        (VkThumbnailWriter, lambda c: c._token_value()),
    ],
)
def test_mutated_alias_still_rejected_before_token_read(tmp_path: Path, factory, operation) -> None:
    client = factory(token_store=VkTokenStore(tmp_path), account_alias="safe-synthetic")
    try:
        client.account_alias = "DEFAULT"
        with pytest.raises(ValueError, match="quarantined"):
            operation(client)
    finally:
        client.close()
