from __future__ import annotations

import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
import typer

from video_channel_manager.cli import youtube as youtube_cli
from video_channel_manager.platforms.youtube.comment_plan import build_comment_plan, make_comment_operation
from video_channel_manager.platforms.youtube.comments import comment_text_sha256

CHANNEL = "UC-78ys2S3cQ3lpqgXfo-SvQ"
ACCOUNT = "legendary-poet"


def _snapshot(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        comment_id="comment-1",
        video_id="video-1",
        author_channel_id=CHANNEL,
        text=text,
        text_sha256=comment_text_sha256(text),
    )


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, dict[str, Any], Mock, list[Any]]:
    operation = make_comment_operation(
        action="create",
        channel_id=CHANNEL,
        video_id="video-1",
        video_title="Title",
        comment_text="Reviewed first comment",
        source_ids=["source-1"],
        reviewed_at="2026-11-26T00:00:00+00:00",
        expected_owned_comments={},
    )
    plan = build_comment_plan(
        account_alias=ACCOUNT,
        channel_id=CHANNEL,
        source_snapshot="snapshot-1",
        source_snapshot_generated_at="2026-11-25T23:59:00+00:00",
        inventory_video_ids=["video-1"],
        operations=[operation],
        mode="reviewed-first-comment",
    )
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    inventory: list[Any] = []
    writer = Mock()
    writer.reserve_guarded_comment_wave.side_effect = lambda **_: nullcontext()
    writer.read_video_identity.return_value = SimpleNamespace(
        video_id="video-1", channel_id=CHANNEL, privacy_status="public", title="Title"
    )
    writer.list_top_level_comments.side_effect = lambda *_args, **_kwargs: list(inventory)
    api = Mock()
    api.list_my_channels.return_value = [SimpleNamespace(ref=SimpleNamespace(channel_id=CHANNEL))]
    monkeypatch.setattr(youtube_cli, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))
    monkeypatch.setattr(youtube_cli, "_components", lambda *_args: (None, None, api))
    monkeypatch.setattr(youtube_cli, "YouTubeCommentWriter", lambda **_kwargs: writer)
    return path, plan, writer, inventory


def _run(path: Path, plan: dict[str, Any], *, execute: bool = False) -> None:
    youtube_cli.apply_comment_add(
        path,
        account=ACCOUNT,
        confirm_channel=CHANNEL,
        confirm_plan_sha256=plan["plan_sha256"] if execute else "",
        execute=execute,
        client_secret=None,
    )


def test_first_comment_dry_run_and_verified_execute_are_single_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, plan, writer, inventory = _setup(tmp_path, monkeypatch)
    _run(path, plan)
    writer.create_top_level_comment.assert_not_called()
    assert not list((tmp_path / "reports").glob("*.json"))

    def create(**kwargs: Any) -> SimpleNamespace:
        assert kwargs["expected_owned_comments"] is None
        assert kwargs["strict_inventory_max_pages"] == 10
        assert kwargs["expected_video_title"] == "Title"
        assert kwargs["expected_privacy_status"] == "public"
        kwargs["before_dispatch"]()
        assert len(list((tmp_path / "reports").glob("*-intent.json"))) == 1
        item = _snapshot(kwargs["text"])
        inventory.append(item)
        return item

    writer.create_top_level_comment.side_effect = create
    writer.read_comment.side_effect = lambda *_args, **_kwargs: inventory[0]
    _run(path, plan, execute=True)
    _run(path, plan, execute=True)
    writer.create_top_level_comment.assert_called_once()
    receipts = list((tmp_path / "reports").glob("*-result.json"))
    assert len(receipts) == 1
    assert json.loads(receipts[0].read_text(encoding="utf-8"))["status"] == "verified"


def test_first_comment_refuses_unreviewed_owner_comment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, plan, writer, inventory = _setup(tmp_path, monkeypatch)
    inventory.append(_snapshot("Unreviewed existing comment"))
    with pytest.raises(typer.Exit):
        _run(path, plan, execute=True)
    writer.create_top_level_comment.assert_not_called()


def test_first_comment_refuses_replay_after_ambiguous_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, plan, writer, _ = _setup(tmp_path, monkeypatch)

    def ambiguous(**kwargs: Any) -> None:
        kwargs["before_dispatch"]()
        raise ValueError("Ambiguous provider result")

    writer.create_top_level_comment.side_effect = ambiguous
    for _ in range(2):
        with pytest.raises(typer.Exit):
            _run(path, plan, execute=True)
    writer.create_top_level_comment.assert_called_once()
    assert len(list((tmp_path / "reports").glob("*-intent.json"))) == 1
    assert not list((tmp_path / "reports").glob("*-result.json"))
