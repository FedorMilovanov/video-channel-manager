from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from video_channel_manager.lordchrist_rich_live_canary import (
    OWNING_ISSUE,
    PUBLICATION_ID,
    RELEASE_ID,
    build_document,
    load_release,
    new_ledger,
    require_live_window,
)

RELEASE_PATH = Path("content/telegram/lordchrist/rich-v1/live-canary-release-2026-08-18.json")
MODULE_PATH = Path("src/video_channel_manager/lordchrist_rich_live_canary.py")
WORKFLOW_PATH = Path(".github/workflows/lordchrist-rich-live-canary.yml")


def test_live_canary_release_is_one_exact_issue_bound_publication() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    assert release["release_id"] == RELEASE_ID
    assert release["owning_issue"] == OWNING_ISSUE == 473
    assert release["publication_id"] == PUBLICATION_ID == "lordchrist-rich-sermons-survive-century"
    assert release["approved"] is True
    assert release["max_combined_verified_per_day_moscow"] == 2
    assert release["max_rich_verified_per_day_moscow"] == 1
    assert "three-expository-patterns" not in RELEASE_PATH.read_text(encoding="utf-8")


def test_live_canary_renders_exact_three_photo_document_without_fallback() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    document, render, article = build_document(Path("."), release)
    assert document.publication_id == PUBLICATION_ID
    assert document.target.channel_username == "@lordchrist"
    assert document.target.chat_id == -1001295216957
    assert document.target.bot_id == 8716602202
    assert document.target.bot_username == "preaching_mp3_bot"
    assert document.legacy_fallback is None
    assert "skip_entity_detection" not in document.input_rich_message
    assert [media.media_id for media in article.media] == ["media-calvin", "media-spurgeon", "media-tape"]
    assert len(document.provider_assigned_media_paths) == 3
    assert render.provider_assigned_media == ("media-calvin", "media-spurgeon", "media-tape")
    assert sum(block.get("type") == "photo" for block in document.input_rich_message["blocks"]) == 3


def test_live_canary_window_is_exact_and_expires_fail_closed() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    require_live_window(release, datetime.fromisoformat("2026-08-18T22:15:00+03:00"))
    require_live_window(release, datetime.fromisoformat("2026-08-18T23:59:59+03:00"))
    with pytest.raises(ValueError, match="authorization window"):
        require_live_window(release, datetime.fromisoformat("2026-08-18T22:14:59+03:00"))
    with pytest.raises(ValueError, match="authorization window"):
        require_live_window(release, datetime.fromisoformat("2026-08-19T00:00:00+03:00"))


def test_new_live_canary_ledger_is_pending_and_non_retryable_states_are_named() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    ledger = new_ledger(release)
    entry = ledger["entries"][PUBLICATION_ID]
    assert entry["state"] == "pending"
    assert entry["provider_effect"] == "impossible"
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert 'entry["state"] in {"intent", "may_exist", "failed_no_effect"}' in source
    assert '"automatic_retry_allowed": False' in source
    assert '"blind_retry_allowed": False' in source
    assert '"fallback_allowed": False' in source
    assert "publish_rich_once(" in source
    assert "sendMessage" not in source


def test_live_workflow_is_manual_single_writer_when_present() -> None:
    if not WORKFLOW_PATH.exists():
        pytest.skip("workflow is added in the same live-canary branch after runtime tests")
    source = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in source
    assert "schedule:" not in source
    assert "group: lordchrist-telegram-publisher" in source
    assert "cancel-in-progress: false" in source
    assert "PUBLISH:lordchrist-rich-sermons-survive-century" in source
    assert "telegram_github_quality_gate" in source
    assert source.count("lordchrist_rich_live_canary send") == 1
    assert "three-expository-patterns" not in source
