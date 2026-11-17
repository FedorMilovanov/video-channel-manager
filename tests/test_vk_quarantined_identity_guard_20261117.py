"""Regression gates for a retired VK secret copied under a newly named alias (#662).

Only synthetic tmp_path credentials and MockTransport. No real token or provider access.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from video_channel_manager.platforms.vk.client import VkApiClient
from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.thumbnails import VkThumbnailWriter
from video_channel_manager.platforms.vk.writer import VkVideoWriter


def _seed_legacy(
    store: VkTokenStore, *, filename: str = "default.json", value: str = "retired-synthetic-secret"
) -> Path:
    """Seed historical evidence without calling the intentionally protected writer."""
    path = store.token_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(VkAccessToken(access_token=value, scopes=["video"]).model_dump_json(), encoding="utf-8")
    return path


@pytest.mark.parametrize("filename", ["default.json", "DEFAULT.JSON", "legendary-poet.json"])
def test_renamed_alias_cannot_save_retired_secret(tmp_path: Path, filename: str) -> None:
    store = VkTokenStore(tmp_path)
    legacy = _seed_legacy(store, filename=filename)
    before = legacy.read_bytes()

    with pytest.raises(ValueError, match="identity is quarantined") as captured:
        store.save_token("seemingly-safe-new-alias", VkAccessToken(access_token="retired-synthetic-secret"))

    assert "retired-synthetic-secret" not in str(captured.value)
    assert legacy.read_bytes() == before
    assert not store.token_path("seemingly-safe-new-alias").exists()
    assert not store.registry_path.exists()


@pytest.mark.parametrize(
    "factory,operation",
    [
        (VkApiClient, lambda client: client._call("users.get")),
        (VkVideoWriter, lambda client: client.assert_token_scopes("video")),
        (VkThumbnailWriter, lambda client: client._token_value()),
    ],
)
def test_renamed_token_is_blocked_before_any_provider_request(tmp_path: Path, factory: type, operation) -> None:
    store = VkTokenStore(tmp_path)
    _seed_legacy(store)
    # Simulate an old script copying the JSON directly and bypassing save_token.
    renamed = store.token_path("new-name-same-secret")
    renamed.write_text(
        VkAccessToken(access_token="retired-synthetic-secret", scopes=["video"]).model_dump_json(), encoding="utf-8"
    )
    calls = 0

    def forbidden_request(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        pytest.fail("VK credential identity must be rejected before HTTP")

    http_client = httpx.Client(transport=httpx.MockTransport(forbidden_request))
    client = factory(
        token_store=store,
        account_alias="new-name-same-secret",
        http_client=http_client,
        api_base_url="https://example.test/method",
    )
    try:
        with pytest.raises(ValueError, match="identity is quarantined") as captured:
            operation(client)
        assert "retired-synthetic-secret" not in str(captured.value)
        assert calls == 0
    finally:
        client.close()
        http_client.close()


def test_accepted_new_community_token_is_not_rejected_by_legacy_evidence(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    legacy = _seed_legacy(store)
    store.save_token(
        "reviewed-community-key",
        VkAccessToken(access_token="distinct-community-synthetic-secret", scopes=["video"]),
    )
    assert store.load_token_for_provider("reviewed-community-key").access_token == "distinct-community-synthetic-secret"
    assert store.load_token("default").access_token == "retired-synthetic-secret"
    assert legacy.is_file()


def test_malformed_legacy_evidence_fails_closed_without_leaking_content(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    legacy = store.token_dir / "default.json"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("malformed-legacy-secret-text-not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="Cannot validate quarantined VK credential identity") as captured:
        store.save_token("reviewed-key", VkAccessToken(access_token="distinct-synthetic-secret"))
    assert "malformed-legacy-secret-text-not-json" not in str(captured.value)
    assert not store.token_path("reviewed-key").exists()

    renamed = store.token_path("copied-alias")
    renamed.write_text(VkAccessToken(access_token="distinct-synthetic-secret").model_dump_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="Cannot validate quarantined VK credential identity"):
        store.load_token_for_provider("copied-alias")


def test_nonlegacy_tokens_work_when_no_legacy_file_exists(tmp_path: Path) -> None:
    store = VkTokenStore(tmp_path)
    store.save_token("new-community-only", VkAccessToken(access_token="synthetic-community-key"))
    assert store.load_token_for_provider("new-community-only").access_token == "synthetic-community-key"


@pytest.mark.parametrize("alias", ["default", "DEFAULT", "legendary-poet"])
def test_offline_forensic_load_remains_separate_from_provider_guard(tmp_path: Path, alias: str) -> None:
    store = VkTokenStore(tmp_path)
    _seed_legacy(store, filename=alias + ".json")
    assert store.load_token(alias).access_token == "retired-synthetic-secret"
    with pytest.raises(ValueError, match="quarantined"):
        store.load_token_for_provider(alias)
