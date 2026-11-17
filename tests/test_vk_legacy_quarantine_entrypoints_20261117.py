"""Issue #662: every legacy VK entry point must stop before credential access.

These are synthetic, provider-inert tests: no credentials and no VK requests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

import video_channel_manager.cli.vk as vk_cli
import video_channel_manager.cli.vk_postponed_text as postponed_cli
import video_channel_manager.wave_engine.vk_article_provider as article_module
import video_channel_manager.wave_engine.vk_video_wall_provider as wall_module
from video_channel_manager.platforms.vk.quarantine import (
    QUARANTINED_LEGACY_VK_ALIASES,
    reject_quarantined_legacy_alias,
)


def _no_settings():
    pytest.fail("Quarantined alias reached settings / credential store")


@pytest.mark.parametrize("alias", ["legendary-poet", "default", " legendary-poet "])
def test_legacy_alias_is_rejected_without_any_credential_access(alias: str) -> None:
    with pytest.raises(ValueError, match="quarantined"):
        reject_quarantined_legacy_alias(alias)




@pytest.mark.parametrize("invalid_alias", ["", "  ", None])
def test_blank_or_nonstring_alias_fails_closed(invalid_alias: str) -> None:
    with pytest.raises(ValueError, match="nonempty"):
        reject_quarantined_legacy_alias(invalid_alias)

def test_new_reviewed_alias_is_not_mistaken_for_quarantined_credential() -> None:
    assert QUARANTINED_LEGACY_VK_ALIASES == {"default", "legendary-poet"}
    reject_quarantined_legacy_alias("vk-lord-god-community-key")


def test_article_adapter_rejects_legacy_alias_before_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(article_module, "get_settings", _no_settings)
    with pytest.raises(ValueError, match="quarantined"):
        article_module.VkPostponedArticlePhotoAdapter(repository_root=tmp_path)


def test_video_wall_adapter_rejects_legacy_alias_before_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(wall_module, "get_settings", _no_settings)
    with pytest.raises(ValueError, match="quarantined"):
        wall_module.VkPostponedVideoWallAdapter()


@pytest.mark.parametrize("alias", ["legendary-poet", "default"])
def test_postponed_text_cli_rejects_legacy_alias_before_settings(monkeypatch: pytest.MonkeyPatch, alias: str) -> None:
    monkeypatch.setattr(postponed_cli, "get_settings", _no_settings)
    with pytest.raises(ValueError, match="quarantined"):
        postponed_cli._writer(alias)


@pytest.mark.parametrize("alias", ["legendary-poet", "default"])
def test_vk_login_cannot_force_refresh_legacy_alias_before_settings(
    monkeypatch: pytest.MonkeyPatch, alias: str
) -> None:
    monkeypatch.setattr(vk_cli, "get_settings", _no_settings)
    with pytest.raises(typer.Exit) as exc:
        vk_cli.login(account=alias, token_file=None, force=True)
    assert exc.value.exit_code == 2
