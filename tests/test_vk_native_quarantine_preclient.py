"""Issue #662: native VK uploads must stop before any quarantined token access."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import video_channel_manager.wave_engine.vk_video_provider as module


@pytest.mark.parametrize("alias", ["legendary-poet", "default", "  legendary-poet  "])
def test_quarantined_native_video_alias_fails_before_settings_or_client(
    tmp_path, monkeypatch: pytest.MonkeyPatch, alias: str
) -> None:
    def must_not_read_settings():
        pytest.fail("Quarantined VK alias reached settings / credential access")

    monkeypatch.setattr(module, "get_settings", must_not_read_settings)
    with pytest.raises(ValueError, match="quarantined"):
        module.VkNativeVideoUploadAdapter(
            repository_root=tmp_path,
            journal_directory=tmp_path,
            account_alias=alias,
            writer=object(),
        )


def test_distinct_approved_alias_can_reach_normal_nonprovider_initialization(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    class FakeStore:
        def __init__(self, data_dir):
            calls.append("store_created")

        def get_account(self, alias: str):
            calls.append(alias)
            return SimpleNamespace(communities=[SimpleNamespace(community_id=60805374)])

    monkeypatch.setattr(module, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))
    monkeypatch.setattr(module, "VkTokenStore", FakeStore)
    writer = object()
    adapter = module.VkNativeVideoUploadAdapter(
        repository_root=tmp_path,
        journal_directory=tmp_path,
        account_alias="vk-lord-god-community-key",
        writer=writer,
    )
    assert adapter.account_alias == "vk-lord-god-community-key"
    assert adapter.writer is writer
    assert adapter._community_ids == {60805374}
    assert calls == ["store_created", "vk-lord-god-community-key"]
