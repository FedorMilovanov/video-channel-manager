"""Provider-free branch coverage for repository safety control planes.

The real token store, network clients and provider write methods must never
be constructed by these tests. Failures are tested before any provider access.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import typer
from pydantic import ValidationError

from video_channel_manager.cli import vk
from video_channel_manager.platforms.vk import client as vk_client
from video_channel_manager.telegram_rich_models import (
    RichTextBold,
    RichTextMath,
    iter_text_fragments,
    rich_text_is_empty,
)
from video_channel_manager.telegram_schedule import PublicationSlotConfig


def _local_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(vk, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path, vk_access_token=None))


def test_vk_accounts_is_local_and_does_not_call_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _local_settings(monkeypatch, tmp_path)
    store = SimpleNamespace(list_accounts=lambda: [], token_exists=lambda _alias: True)
    monkeypatch.setattr(vk, "VkTokenStore", lambda _path: store)
    vk.accounts()
    assert "No VK accounts are registered" in capsys.readouterr().out

    item = SimpleNamespace(
        alias="safe-fixture",
        user=SimpleNamespace(display_name="Test owner"),
        communities=[SimpleNamespace(title="Testing community")],
        updated_at=datetime(2026, 11, 4, 10, 0, tzinfo=UTC),
    )
    store.list_accounts = lambda: [item]
    vk.accounts()
    output = capsys.readouterr().out
    assert "safe-fixture" in output and "Test owner" in output and "Testing community" in output

    store.token_exists = lambda _alias: False
    vk.accounts()
    assert "missing" in capsys.readouterr().out


def test_vk_accounts_read_errors_fail_closed_without_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _local_settings(monkeypatch, tmp_path)

    def fail() -> None:
        raise ValueError("local registry corrupt")

    monkeypatch.setattr(vk, "VkTokenStore", lambda _path: SimpleNamespace(list_accounts=fail))
    with pytest.raises(typer.Exit) as e:
        vk.accounts()
    assert e.value.exit_code == 2


def test_vk_local_flood_control_probes_have_explicit_required_gates() -> None:
    for func, kwargs in (
        (vk.community_key_login, {"community": 0}),
        (vk.community_key_capabilities, {"community": -1}),
        (vk.community_probe, {"community": 0}),
        (vk.wall_probe, {"community": -1}),
    ):
        with pytest.raises(typer.BadParameter, match="community must be positive"):
            func(**kwargs)
    with pytest.raises(typer.BadParameter, match="required"):
        vk.flood_reset(method="wall.get", confirm_code=None)
    with pytest.raises(typer.BadParameter, match="required"):
        vk.flood_reset(method="wall.get", confirm_code=0)


def test_vk_flood_status_read_only_local_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _local_settings(monkeypatch, tmp_path)
    store = SimpleNamespace(validate_alias=lambda x: x)
    monkeypatch.setattr(vk, "VkTokenStore", lambda _path: store)
    gate = SimpleNamespace(list_open=lambda: [])
    monkeypatch.setattr(vk, "VkCredentialFloodControl", lambda _store, _alias: gate)
    vk.flood_status("fixture")
    assert "Provider calls: 0" in capsys.readouterr().out

    gate.list_open = lambda: [
        SimpleNamespace(method="wall.get", first_observed_at="start", last_observed_at="end", occurrences=2)
    ]
    vk.flood_status("fixture")
    out = capsys.readouterr().out
    assert "wall.get" in out and "No automatic TTL" in out

    def broken():
        raise OSError("fixture read error")

    gate.list_open = broken
    with pytest.raises(typer.Exit) as e:
        vk.flood_status("fixture")
    assert e.value.exit_code == 2


def test_vk_login_already_authorized_never_reads_token_or_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _local_settings(monkeypatch, tmp_path)
    store = SimpleNamespace(validate_alias=lambda x: x, token_exists=lambda _alias: True)
    monkeypatch.setattr(vk, "VkTokenStore", lambda _path: store)
    monkeypatch.setattr(
        vk, "_read_token_input", lambda _path: pytest.fail("login must stop before reading any credentials")
    )
    with pytest.raises(typer.Exit) as exc:
        vk.login("fixture", force=False)
    assert exc.value.exit_code == 2


def test_vk_safe_client_parsers_handle_malformed_and_flood_responses_without_io() -> None:
    assert vk_client._provider_response_kind(httpx.Response(429)) is None
    assert vk_client._provider_response_kind(httpx.Response(200, content=b"not-json")) is None
    assert vk_client._provider_response_kind(httpx.Response(200, json=[])) is None
    assert vk_client._provider_response_kind(httpx.Response(200, json={"error": "not-object"})) is None
    assert vk_client._provider_response_kind(httpx.Response(200, json={"error": {"error_code": 9}}))
    assert vk_client._dict_items([]) == []
    assert vk_client._dict_items({"items": None}) == []
    assert vk_client._dict_items({"items": [2, {"a": 3}]}) == [{"a": 3}]
    assert vk_client._unix_datetime("not-integer") is None
    assert vk_client._unix_datetime(-1) is None
    assert vk_client._best_image([None, {"url": "https://img.invalid/a.jpg", "width": 2, "height": 3}])
    assert vk_client._video_remote_id({"owner_id": "1", "id": 42}) is None
    assert vk_client._community_url({}, 123).endswith("club123")


def test_rich_text_validation_enforces_visible_content_for_nested_entities() -> None:
    assert list(iter_text_fragments(("alpha", ("beta", "gamma")))) == ["alpha", "beta", "gamma"]
    assert rich_text_is_empty(("", ("  ", "")))
    assert not rich_text_is_empty((" ", "visible"))
    assert list(iter_text_fragments(RichTextBold(text="meaning"))) == ["meaning"]
    with pytest.raises(ValidationError, match="visible text"):
        RichTextBold(text="   ")
    # An inline mathematical expression contributes its source to visible text.
    assert list(iter_text_fragments(RichTextMath(expression="x^2"))) == ["x^2"]


@pytest.mark.parametrize(
    ("weekdays", "diagnostic"),
    [
        ((), "at least one ISO weekday"),
        ((0,), "range 1..7"),
        ((1, 1), "unique"),
        ((8,), "range 1..7"),
    ],
)
def test_publication_slot_iso_weekdays_fail_closed(weekdays: tuple[int, ...], diagnostic: str) -> None:
    with pytest.raises(ValidationError, match=diagnostic):
        PublicationSlotConfig.model_validate(
            {"cron": "0 7 * * *", "time": "10:00", "iso_weekdays": weekdays, "max_lateness_minutes": 60}
        )
