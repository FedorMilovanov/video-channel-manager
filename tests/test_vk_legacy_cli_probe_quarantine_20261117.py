"""Retired VK aliases may not reach live CLI readers or token refreshes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import typer

import video_channel_manager.cli.vk as cli
import video_channel_manager.platforms.vk.clips_evidence_pipeline as clips


def _fail_settings():
    pytest.fail("A quarantined VK alias reached settings or credentials")


@pytest.mark.parametrize(
    ("fn_name", "kwargs"),
    [
        ("_components", {"account": "default"}),
        ("token_capabilities", {"account": "default", "sync_local": False}),
        ("community_key_login", {"community": 60805374, "account": "default", "token_file": None, "force": True}),
        ("community_key_capabilities", {"community": 60805374, "account": "default"}),
        ("flood_reset", {"method": "wall.get", "account": "default", "confirm_code": 9}),
        ("community_probe", {"community": 60805374, "account": "default"}),
        ("wall_probe", {"community": 60805374, "account": "default"}),
        ("community_probe", {"community": 60805374, "account": "legendary-poet"}),
        ("wall_probe", {"community": 60805374, "account": "legendary-poet"}),
    ],
)
def test_legacy_cli_entry_points_fail_before_settings(
    monkeypatch: pytest.MonkeyPatch, fn_name: str, kwargs: dict[str, object]
) -> None:
    monkeypatch.setattr(cli, "get_settings", _fail_settings)
    fn = getattr(cli, fn_name)
    with pytest.raises(typer.BadParameter, match="quarantined"):
        fn(**kwargs)


def test_owner_clips_evidence_rejects_default_before_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clips, "get_settings", _fail_settings)
    monkeypatch.setattr(clips, "parser", lambda: SimpleNamespace(parse_args=lambda: SimpleNamespace(account="default")))
    with pytest.raises(ValueError, match="quarantined"):
        clips.main()


def test_user_login_never_silently_reuses_global_vk_access_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "get_settings", _fail_settings)
    prompted: list[bool] = []

    def fake_prompt(*args: object, **kwargs: object) -> str:
        prompted.append(True)
        return "explicit-new-test-token"

    monkeypatch.setattr(cli.typer, "prompt", fake_prompt)
    token = cli._read_token_input(None)
    assert token is not None
    assert prompted == [True]
