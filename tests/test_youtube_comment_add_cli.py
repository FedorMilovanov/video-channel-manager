from __future__ import annotations

import hashlib
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


def _replan(
    path: Path, *, text: str, video_id: str = "video-1", expected: dict[str, str] | None = None
) -> dict[str, Any]:
    operation = make_comment_operation(
        action="create",
        channel_id=CHANNEL,
        video_id=video_id,
        video_title="Title",
        comment_text=text,
        source_ids=["source-2"],
        reviewed_at="2026-11-26T01:00:00+00:00",
        expected_owned_comments=expected if expected is not None else {},
    )
    plan = build_comment_plan(
        account_alias=ACCOUNT,
        channel_id=CHANNEL,
        source_snapshot="snapshot-2",
        source_snapshot_generated_at="2026-11-26T00:59:00+00:00",
        inventory_video_ids=[video_id],
        operations=[operation],
        mode="reviewed-additional-comment" if expected else "reviewed-first-comment",
    )
    path.write_text(json.dumps(plan), encoding="utf-8")
    return plan


def test_edited_first_plan_cannot_escape_unresolved_intent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, plan, writer, _ = _setup(tmp_path, monkeypatch)

    def ambiguous(**kwargs: Any) -> None:
        kwargs["before_dispatch"]()
        raise ValueError("Ambiguous provider result")

    writer.create_top_level_comment.side_effect = ambiguous
    with pytest.raises(typer.Exit):
        _run(path, plan, execute=True)
    intent = next((tmp_path / "reports").glob("*-intent.json"))
    before = intent.read_bytes()
    changed = _replan(path, text="Edited first comment")
    with pytest.raises(typer.Exit):
        _run(path, changed, execute=True)
    writer.create_top_level_comment.assert_called_once()
    assert intent.read_bytes() == before
    assert list((tmp_path / "reports").glob("*-intent.json")) == [intent]


def test_legacy_text_keyed_intent_blocks_changed_first_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, plan, writer, _ = _setup(tmp_path, monkeypatch)
    key = hashlib.sha256(
        json.dumps([CHANNEL, "video-1", plan["operations"][0]["comment_sha256"]]).encode("utf-8")
    ).hexdigest()
    reports = tmp_path / "reports"
    reports.mkdir()
    old = reports / f"youtube-comment-add-{key}-intent.json"
    old.write_text(json.dumps({"status": "may_exist", "plan": plan, "effect_key": key}), encoding="utf-8")
    before = old.read_bytes()
    changed = _replan(path, text="Edited first comment")
    with pytest.raises(typer.Exit):
        _run(path, changed, execute=True)
    writer.create_top_level_comment.assert_not_called()
    assert old.read_bytes() == before


def test_unresolved_first_intent_blocks_additional_even_when_first_is_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, plan, writer, inventory = _setup(tmp_path, monkeypatch)

    def ambiguous(**kwargs: Any) -> None:
        kwargs["before_dispatch"]()
        raise ValueError("Ambiguous provider result")

    writer.create_top_level_comment.side_effect = ambiguous
    with pytest.raises(typer.Exit):
        _run(path, plan, execute=True)
    first = _snapshot(plan["operations"][0]["comment_text"])
    inventory.append(first)
    additional = _replan(path, text="Independent second comment", expected={first.comment_id: first.text_sha256})
    with pytest.raises(typer.Exit):
        _run(path, additional, execute=True)
    writer.create_top_level_comment.assert_called_once()


def test_verified_first_intent_allows_additional_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, plan, writer, inventory = _setup(tmp_path, monkeypatch)

    def create(**kwargs: Any) -> SimpleNamespace:
        kwargs["before_dispatch"]()
        item = _snapshot(kwargs["text"])
        inventory.append(item)
        return item

    writer.create_top_level_comment.side_effect = create
    writer.read_comment.side_effect = lambda *_args, **_kwargs: inventory[0]
    _run(path, plan, execute=True)
    reports = tmp_path / "reports"
    saved = {p: p.read_bytes() for p in reports.glob("*.json")}
    first = inventory[0]
    additional = _replan(path, text="Independent second comment", expected={first.comment_id: first.text_sha256})
    _run(path, additional)
    writer.create_top_level_comment.assert_called_once()
    assert {p: p.read_bytes() for p in reports.glob("*.json")} == saved


def test_other_video_intent_does_not_block_first_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, plan, writer, _ = _setup(tmp_path, monkeypatch)

    def ambiguous(**kwargs: Any) -> None:
        kwargs["before_dispatch"]()
        raise ValueError("Ambiguous provider result")

    writer.create_top_level_comment.side_effect = ambiguous
    with pytest.raises(typer.Exit):
        _run(path, plan, execute=True)
    writer.read_video_identity.return_value.video_id = "video-2"
    other = _replan(path, text="First comment for another video", video_id="video-2")
    _run(path, other)
    writer.create_top_level_comment.assert_called_once()


@pytest.mark.parametrize("legacy", [False, True])
def test_positive_readback_reconciles_original_intent_without_post(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, legacy: bool
) -> None:
    path, plan, writer, inventory = _setup(tmp_path, monkeypatch)

    def ambiguous(**kwargs: Any) -> None:
        kwargs["before_dispatch"]()
        raise ValueError("Ambiguous provider result")

    writer.create_top_level_comment.side_effect = ambiguous
    with pytest.raises(typer.Exit):
        _run(path, plan, execute=True)
    reports = tmp_path / "reports"
    intent = next(reports.glob("*-intent.json"))
    if legacy:
        prior = json.loads(intent.read_text(encoding="utf-8"))
        key = hashlib.sha256(
            json.dumps([CHANNEL, "video-1", plan["operations"][0]["comment_sha256"]]).encode("utf-8")
        ).hexdigest()
        prior["effect_key"] = key
        intent.unlink()
        intent = reports / f"youtube-comment-add-{key}-intent.json"
        intent.write_text(json.dumps(prior), encoding="utf-8")
    original = intent.read_bytes()
    first = _snapshot(plan["operations"][0]["comment_text"])
    inventory.append(first)
    writer.read_comment.return_value = first

    _run(path, plan)
    assert not list(reports.glob("*-result.json"))
    _run(path, plan, execute=True)
    writer.create_top_level_comment.assert_called_once()
    assert intent.read_bytes() == original
    result = intent.with_name(intent.name.removesuffix("-intent.json") + "-result.json")
    assert json.loads(result.read_text(encoding="utf-8"))["status"] == "verified"
    additional = _replan(path, text="Independent second comment", expected={first.comment_id: first.text_sha256})
    _run(path, additional)


def test_wrong_direct_readback_does_not_resolve_intent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, plan, writer, inventory = _setup(tmp_path, monkeypatch)

    def ambiguous(**kwargs: Any) -> None:
        kwargs["before_dispatch"]()
        raise ValueError("Ambiguous provider result")

    writer.create_top_level_comment.side_effect = ambiguous
    with pytest.raises(typer.Exit):
        _run(path, plan, execute=True)
    inventory.append(_snapshot(plan["operations"][0]["comment_text"]))
    writer.read_comment.return_value = _snapshot("Different text")
    with pytest.raises(typer.Exit):
        _run(path, plan, execute=True)
    assert not list((tmp_path / "reports").glob("*-result.json"))
    writer.create_top_level_comment.assert_called_once()


def _update_plan(path: Path, *, text: str, inventory: list[Any]) -> dict[str, Any]:
    operation = make_comment_operation(
        action="update",
        channel_id=CHANNEL,
        video_id="video-1",
        video_title="Title",
        comment_text=text,
        source_ids=["source-1"],
        reviewed_at="2026-11-26T01:00:00+00:00",
        expected_comment_id=inventory[0].comment_id,
        expected_comment_text=inventory[0].text,
        expected_owned_comments={item.comment_id: item.text_sha256 for item in inventory},
    )
    plan = build_comment_plan(
        account_alias=ACCOUNT,
        channel_id=CHANNEL,
        source_snapshot="snapshot-2",
        source_snapshot_generated_at="2026-11-26T00:59:00+00:00",
        inventory_video_ids=["video-1"],
        operations=[operation],
        mode="reviewed-comment-update",
    )
    path.write_text(json.dumps(plan), encoding="utf-8")
    return plan


def _run_update(path: Path, plan: dict[str, Any], *, execute: bool = False) -> None:
    youtube_cli.apply_comment_update(
        path,
        account=ACCOUNT,
        confirm_channel=CHANNEL,
        confirm_plan_sha256=plan["plan_sha256"] if execute else "",
        execute=execute,
        client_secret=None,
    )


def test_reviewed_update_dry_run_and_verified_execute_preserve_other_comments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, writer, inventory = _setup(tmp_path, monkeypatch)
    other = _snapshot("Unchanged comment")
    other.comment_id = "comment-2"
    inventory.extend([_snapshot("Reviewed before"), other])
    plan = _update_plan(path, text="Reviewed correction", inventory=inventory)
    _run_update(path, plan)
    assert not list((tmp_path / "reports").glob("*.json"))
    writer.update_top_level_comment.assert_not_called()
    with pytest.raises(typer.Exit):
        _run(path, plan, execute=True)

    def update(**kwargs: Any) -> SimpleNamespace:
        assert kwargs["comment_id"] == "comment-1"
        assert kwargs["expected_text"] == "Reviewed before"
        assert kwargs["expected_owned_comments"] == {item.comment_id: item.text_sha256 for item in inventory}
        assert kwargs["strict_inventory_max_pages"] == 10
        assert kwargs["expected_video_title"] == "Title"
        assert kwargs["expected_privacy_status"] == "public"
        kwargs["before_dispatch"]()
        assert len(list((tmp_path / "reports").glob("*-intent.json"))) == 1
        inventory[0] = _snapshot(kwargs["new_text"])
        return inventory[0]

    writer.update_top_level_comment.side_effect = update
    writer.read_comment.side_effect = lambda *_args, **_kwargs: inventory[0]
    _run_update(path, plan, execute=True)
    _run_update(path, plan, execute=True)
    writer.update_top_level_comment.assert_called_once()
    writer.create_top_level_comment.assert_not_called()
    assert inventory[1] is other
    receipt = next((tmp_path / "reports").glob("*-result.json"))
    assert json.loads(receipt.read_text(encoding="utf-8"))["existing_preserved"] == ["comment-2"]


def test_unresolved_update_blocks_edited_update_and_create_then_reconciles_exact_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, writer, inventory = _setup(tmp_path, monkeypatch)
    inventory.append(_snapshot("Reviewed before"))
    plan = _update_plan(path, text="Reviewed correction", inventory=inventory)

    def ambiguous(**kwargs: Any) -> None:
        kwargs["before_dispatch"]()
        raise ValueError("Unknown PUT outcome")

    writer.update_top_level_comment.side_effect = ambiguous
    with pytest.raises(typer.Exit):
        _run_update(path, plan, execute=True)
    edited = _update_plan(path, text="Edited correction", inventory=inventory)
    with pytest.raises(typer.Exit):
        _run_update(path, edited, execute=True)
    extra = _replan(path, text="Additional comment", expected={inventory[0].comment_id: inventory[0].text_sha256})
    with pytest.raises(typer.Exit):
        _run(path, extra, execute=True)
    inventory[0] = _snapshot("Reviewed correction")
    writer.read_comment.return_value = inventory[0]
    path.write_text(json.dumps(plan), encoding="utf-8")
    _run_update(path, plan)
    assert not list((tmp_path / "reports").glob("*-result.json"))
    _run_update(path, plan, execute=True)
    assert len(list((tmp_path / "reports").glob("*-result.json"))) == 1
    writer.update_top_level_comment.assert_called_once()
    writer.create_top_level_comment.assert_not_called()


@pytest.mark.parametrize("drift", ["text", "extra", "title", "other-match"])
def test_reviewed_update_rejects_live_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drift: str) -> None:
    path, _, writer, inventory = _setup(tmp_path, monkeypatch)
    inventory.append(_snapshot("Reviewed before"))
    plan = _update_plan(path, text="Reviewed correction", inventory=inventory)
    if drift == "text":
        inventory[0] = _snapshot("Unreviewed change")
    elif drift == "title":
        writer.read_video_identity.return_value.title = "Changed title"
    else:
        other = _snapshot("Reviewed correction" if drift == "other-match" else "Other comment")
        other.comment_id = "comment-2"
        inventory.append(other)
    with pytest.raises(typer.Exit):
        _run_update(path, plan, execute=True)
    writer.update_top_level_comment.assert_not_called()
    writer.create_top_level_comment.assert_not_called()
    assert not list((tmp_path / "reports").glob("*.json"))


def _reply_plan(path: Path, *, text: str = "Спасибо! ❤️", parent: str = "parent-1") -> dict[str, Any]:
    operation = make_comment_operation(
        action="reply",
        channel_id=CHANNEL,
        video_id="video-1",
        video_title="Title",
        comment_text=text,
        source_ids=["owner-request"],
        reviewed_at="2026-11-27T00:00:00+00:00",
        expected_comment_id=parent,
        expected_comment_text="Viewer text",
        expected_parent_author_channel_id="viewer",
        expected_owned_comments={},
    )
    plan = build_comment_plan(
        account_alias=ACCOUNT,
        channel_id=CHANNEL,
        source_snapshot="strict-reply-inventory",
        source_snapshot_generated_at="2026-11-27T00:00:00+00:00",
        inventory_video_ids=["video-1"],
        operations=[operation],
        mode="reviewed-comment-reply",
    )
    path.write_text(json.dumps(plan), encoding="utf-8")
    return plan


def _run_reply(path: Path, plan: dict[str, Any], *, execute: bool = False) -> None:
    youtube_cli.apply_comment_reply(
        path,
        account=ACCOUNT,
        confirm_channel=CHANNEL,
        execute=execute,
        confirm_plan_sha256=plan["plan_sha256"] if execute else "",
        client_secret=None,
    )


@pytest.mark.parametrize("case", ["ok", "unknown", "wrong-parent"])
def test_reply_cli_uses_same_lock_intent_and_recovery_without_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    path, _, writer, top_level = _setup(tmp_path, monkeypatch)
    top_level.append(_snapshot("Preserved author comment"))
    inventory: list[Any] = []
    writer.reserve_guarded_reply_wave.side_effect = lambda **_: nullcontext()
    writer.read_reply_context.side_effect = lambda **_: list(inventory)
    plan = _reply_plan(path)
    _run_reply(path, plan)
    assert not list((tmp_path / "reports").glob("*.json"))
    with pytest.raises(typer.Exit):
        _run(path, plan, execute=True)
    item = _snapshot("Спасибо! ❤️")
    item.comment_id = "reply-1"
    item.raw = {"snippet": {"parentId": "parent-1", "textOriginal": item.text}}

    def create(**kwargs: Any) -> Any:
        assert kwargs["parent_id"] == "parent-1"
        assert kwargs["expected_parent_author"] == "viewer"
        assert kwargs["expected_parent_text"] == "Viewer text"
        assert kwargs["expected_owned_replies"] == {}
        kwargs["before_dispatch"]()
        assert len(list((tmp_path / "reports").glob("*-intent.json"))) == 1
        if case == "unknown":
            raise ValueError("Unknown POST outcome")
        inventory.append(item)
        return item

    writer.create_reply.side_effect = create
    writer.read_comment.return_value = item
    if case == "wrong-parent":
        wrong = _snapshot("Спасибо! ❤️")
        wrong.comment_id = "reply-1"
        wrong.raw = {"snippet": {"parentId": "other-parent", "textOriginal": wrong.text}}
        writer.read_comment.return_value = wrong
    if case == "ok":
        _run_reply(path, plan, execute=True)
    else:
        with pytest.raises(typer.Exit):
            _run_reply(path, plan, execute=True)
        assert not list((tmp_path / "reports").glob("*-result.json"))
        if case == "unknown":
            changed = _reply_plan(path, text="Different reply")
            with pytest.raises(typer.Exit):
                _run_reply(path, changed, execute=True)
            inventory.append(item)
            path.write_text(json.dumps(plan), encoding="utf-8")
        writer.read_comment.return_value = item
    _run_reply(path, plan, execute=True)
    writer.create_reply.assert_called_once()
    writer.create_top_level_comment.assert_not_called()
    writer.update_top_level_comment.assert_not_called()
    assert len(top_level) == 1
    receipt = next((tmp_path / "reports").glob("*-result.json"))
    result = json.loads(receipt.read_text(encoding="utf-8"))
    assert result["comment_id"] == "reply-1"
    assert result["parent_comment_id"] == "parent-1"
    assert result["status"] == "verified"


def test_reply_quota_refusal_blocks_before_intent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from video_channel_manager.platforms.youtube.comments import YouTubeCommentError

    path, _, writer, _ = _setup(tmp_path, monkeypatch)
    plan = _reply_plan(path)
    writer.reserve_guarded_reply_wave.side_effect = YouTubeCommentError("Quota unavailable")
    with pytest.raises(typer.Exit):
        _run_reply(path, plan, execute=True)
    writer.create_reply.assert_not_called()
    assert not list((tmp_path / "reports").glob("*.json"))


@pytest.mark.parametrize("drift", ["none", "wrong-map", "wrong-id", "missing-old", "wrong-readback", "new-extra"])
def test_concurrent_owner_edit_positive_reconciliation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    from video_channel_manager.platforms.youtube.copy_plan import canonical_sha256

    path, _, writer, inventory = _setup(tmp_path, monkeypatch)
    first = _snapshot("Earlier comment")
    inventory.append(first)
    plan = _replan(path, text="Second comment", expected={first.comment_id: first.text_sha256})

    def ambiguous(**kwargs: Any) -> None:
        kwargs["before_dispatch"]()
        raise ValueError("Postflight not completed")

    writer.create_top_level_comment.side_effect = ambiguous
    with pytest.raises(typer.Exit):
        _run(path, plan, execute=True)
    intent = next((tmp_path / "reports").glob("*-intent.json"))
    frozen = intent.read_bytes()
    inventory[0] = _snapshot("Manually revised earlier comment")
    second = _snapshot("Second comment")
    second.comment_id = "comment-2"
    inventory.append(second)
    writer.read_video_identity.return_value.title = "Renamed title"
    writer.read_comment.return_value = second
    if drift == "missing-old":
        inventory.pop(0)
    if drift == "new-extra":
        extra = _snapshot("Unexpected extra comment")
        extra.comment_id = "comment-3"
        inventory.append(extra)
    if drift == "wrong-readback":
        writer.read_comment.return_value = _snapshot("Wrong direct text")
    owner_map = {item.comment_id: item.text_sha256 for item in inventory}
    args = {
        "account": ACCOUNT,
        "confirm_channel": CHANNEL,
        "confirm_plan_sha256": plan["plan_sha256"],
        "comment_id": "wrong-id" if drift == "wrong-id" else second.comment_id,
        "current_title": "Renamed title",
        "confirm_owner_map_sha256": "wrong-digest" if drift == "wrong-map" else canonical_sha256(owner_map),
        "client_secret": None,
    }
    receipt = intent.with_name(intent.name.removesuffix("-intent.json") + "-result.json")
    if drift != "none":
        with pytest.raises(typer.Exit):
            youtube_cli.reconcile_comment_add(path, record=True, **args)
        assert not receipt.exists()
    else:
        youtube_cli.reconcile_comment_add(path, record=False, **args)
        assert not receipt.exists()
        youtube_cli.reconcile_comment_add(path, record=True, **args)
        result = json.loads(receipt.read_text(encoding="utf-8"))
        assert result["status"] == "verified"
        assert result["provider_writes"] == 0
        assert result["existing_preserved"] == []
        assert result["existing_changed"] == {
            first.comment_id: {"before_sha256": first.text_sha256, "observed_sha256": inventory[0].text_sha256}
        }
        youtube_cli._require_safe_comment_history(
            tmp_path / "reports", channel_id=CHANNEL, video_id="video-1", first=False
        )
        with pytest.raises(typer.Exit):
            youtube_cli.reconcile_comment_add(path, record=True, **args)
    assert intent.read_bytes() == frozen
    writer.create_top_level_comment.assert_called_once()
    writer.update_top_level_comment.assert_not_called()
    writer.create_reply.assert_not_called()
