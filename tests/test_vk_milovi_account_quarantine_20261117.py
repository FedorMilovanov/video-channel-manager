"""Issue #662: Milovi cannot probe a retired legacy credential during account discovery."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import video_channel_manager.platforms.vk.milovi_token_clip_rollout as rollout
import video_channel_manager.platforms.vk.milovi_issue323_continue as continuation
from video_channel_manager.platforms.vk.milovi_issue323_promotion_dispatch import (
    PromotionDispatchBlockedBeforeProvider,
)


class SyntheticStore:
    def __init__(self, aliases: list[str]) -> None:
        self.accounts = [SimpleNamespace(alias=alias) for alias in aliases]

    def list_accounts(self):
        return self.accounts

    def token_exists(self, alias: str) -> bool:
        return True


def test_resolver_never_constructs_client_for_quarantined_alias_even_if_registered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[str] = []
    probed: list[str] = []

    class Client:
        def __init__(self, *, account_alias: str, **_kwargs):
            created.append(account_alias)
            self.alias = account_alias

        def close(self) -> None:
            pass

    def prove(client: Client) -> None:
        probed.append(client.alias)

    monkeypatch.setattr(rollout, "VkApiClient", Client)
    monkeypatch.setattr(rollout, "_prove_target", prove)
    store = SyntheticStore(["default", "legendary-poet", "shared-vk-user", "milovi-cake"])

    alias, _client = rollout._resolve_account(store, "5.199")
    assert alias == "milovi-cake"
    assert created == ["milovi-cake"]
    assert probed == ["milovi-cake"]


def test_resolver_does_not_use_legacy_alias_when_no_other_account_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_client(**_kwargs):
        pytest.fail("Quarantined account must not reach client constructor")

    monkeypatch.setattr(rollout, "VkApiClient", forbidden_client)
    with pytest.raises(rollout.MiloviTokenRolloutBlocked, match="nonquarantined"):
        rollout._resolve_account(SyntheticStore(["legendary-poet", "default"]), "5.199")


def test_resolver_closes_failed_candidate_then_checks_only_next_safe_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[str] = []
    closed: list[str] = []

    class Client:
        def __init__(self, *, account_alias: str, **_kwargs):
            self.alias = account_alias
            created.append(self.alias)

        def close(self) -> None:
            closed.append(self.alias)

    def prove(client: Client) -> None:
        if client.alias == "milovi-cake":
            raise RuntimeError("not an owner")

    monkeypatch.setattr(rollout, "VkApiClient", Client)
    monkeypatch.setattr(rollout, "_prove_target", prove)
    alias, _client = rollout._resolve_account(SyntheticStore(["default", "shared-vk-user", "milovi-cake"]), "5.199")
    assert alias == "shared-vk-user"
    assert created == ["milovi-cake", "shared-vk-user"]
    assert closed == ["milovi-cake"]


@pytest.mark.parametrize("legacy_alias", ["default", "legendary-poet"])
def test_stale_promotion_journal_alias_is_blocked_before_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, legacy_alias: str
) -> None:
    def fail_settings():
        pytest.fail("Stale journal reached credentials")

    monkeypatch.setattr(continuation, "get_settings", fail_settings)
    with pytest.raises(PromotionDispatchBlockedBeforeProvider, match="quarantined"):
        continuation._dispatch_existing_intent(
            status_payload={
                "account_alias": legacy_alias,
                "community_id": continuation.MILOVI_COMMUNITY_ID,
            },
            promotion_journal_path=tmp_path / "nonexistent-journal.json",
            journal=None,
            envelope=None,
        )
