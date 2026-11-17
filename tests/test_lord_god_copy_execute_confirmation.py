"""Lord God YouTube one-video write confirmation independent from a plan's own flags."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from video_channel_manager.cli import youtube
from video_channel_manager.platforms.youtube.lord_god_source_preservation import LORD_GOD_OWNER_CHANNEL


VIDEO_ID = "ExampleOne0"
NEW_TEXT = "Точная редакционная версия описания без публикации."
NEW_SHA = "sha256:" + hashlib.sha256(NEW_TEXT.encode("utf-8")).hexdigest()


def _payload() -> dict[str, Any]:
    return {
        "schema_name": "video-manager.youtube-copy-fix-plan",
        "project_key": "lord-god-strength",
        "target_channel_id": LORD_GOD_OWNER_CHANNEL,
        "provider_mutation_authorized": True,
    }


def _operations() -> list[dict[str, Any]]:
    return [{"video_id": VIDEO_ID, "channel_id": LORD_GOD_OWNER_CHANNEL, "after_description": NEW_TEXT}]


def _check(
    payload: dict[str, Any],
    operations: list[dict[str, Any]],
    *,
    execute: bool = True,
    channel: str = LORD_GOD_OWNER_CHANNEL,
    target: str = VIDEO_ID,
    digest: str = NEW_SHA,
) -> None:
    youtube._require_lord_god_copy_execute_confirmation(
        payload,
        operations,
        execute=execute,
        confirm_channel=channel,
        confirm_target=target,
        confirm_after_sha256=digest,
    )


def test_explicit_target_and_new_text_sha_accept_exactly_one_lord_god_plan() -> None:
    _check(_payload(), _operations())


@pytest.mark.parametrize(
    ("target", "digest"),
    [
        ("", ""),
        ("OtherOne000", NEW_SHA),
        (VIDEO_ID, ""),
        (VIDEO_ID, "sha256:" + "0" * 64),
        (VIDEO_ID, NEW_SHA.removeprefix("sha256:")),
    ],
)
def test_wrong_or_missing_operator_confirmation_fails_closed(target: str, digest: str) -> None:
    with pytest.raises(ValueError, match="independent --confirm-target"):
        _check(_payload(), _operations(), target=target, digest=digest)


def test_frozen_plan_self_authorization_does_not_override_missing_confirmation() -> None:
    payload = _payload()
    assert payload["provider_mutation_authorized"] is True
    with pytest.raises(ValueError, match="independent --confirm-target"):
        _check(payload, _operations(), target="", digest="")


def test_read_only_dry_run_works_without_new_operator_flags() -> None:
    _check(_payload(), _operations(), execute=False, target="", digest="")


def test_other_project_does_not_inherit_lord_god_specific_flags() -> None:
    _check(
        {"project_key": "legendary-poet", "target_channel_id": "UCother"},
        [{"video_id": "OtherOne000", "channel_id": "UCother", "after_description": NEW_TEXT}],
        channel="UCother",
        target="",
        digest="",
    )


@pytest.mark.parametrize("kind", ["channel", "project", "batch", "operation_owner"])
def test_cross_channel_mislabel_and_multi_video_writes_refused(kind: str) -> None:
    payload = _payload()
    operations = _operations()
    channel = LORD_GOD_OWNER_CHANNEL
    if kind == "channel":
        channel = "UCother"
    elif kind == "project":
        payload["project_key"] = "legendary-poet"
    elif kind == "batch":
        operations.append({"video_id": "Another0000", "channel_id": channel, "after_description": NEW_TEXT})
    elif kind == "operation_owner":
        operations[0]["channel_id"] = "UCother"
    with pytest.raises(ValueError, match="one exact owner-bound|independent"):
        _check(payload, operations, channel=channel)


def test_lord_god_write_rejects_missing_confirmation_before_loading_account(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def never_authenticate(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("YouTube account was accessed before independent exact-target confirmation")

    monkeypatch.setattr(youtube, "prepare_windows_youtube_console", lambda: None)
    monkeypatch.setattr(youtube, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))
    monkeypatch.setattr(youtube, "_load_copy_fix_plan", lambda _path: {**_payload(), "operations": _operations()})
    monkeypatch.setattr(youtube, "require_lord_god_youtube_presentation", lambda _payload: None)
    monkeypatch.setattr(youtube, "_writer_components", never_authenticate)
    with pytest.raises(typer.Exit) as failure:
        youtube.apply_copy_fixes(
            tmp_path / "not-a-real-plan.json",
            account="fedor-milovanov",
            confirm_channel=LORD_GOD_OWNER_CHANNEL,
            execute=True,
            confirm_target="",
            confirm_after_sha256="",
            max_operations=1,
            backup_output=tmp_path / "backup.json",
            result_output=tmp_path / "result.json",
            client_secret=None,
        )
    assert failure.value.exit_code == 2
    assert not (tmp_path / "backup.json").exists()
    assert not (tmp_path / "result.json").exists()
