from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from video_channel_manager.lordchrist_rich_live_canary import (
    ATTACHMENT_NAMES,
    OWNING_ISSUE,
    PUBLICATION_ID,
    RELEASE_ID,
    _LordChristMultipartProvider,
    build_document,
    load_release,
    new_ledger,
    require_live_window,
)
from video_channel_manager.telegram_rich_provider import TelegramRichRequestTimeout

RELEASE_PATH = Path("content/telegram/lordchrist/rich-v1/live-canary-release-2026-08-18.json")
MODULE_PATH = Path("src/video_channel_manager/lordchrist_rich_live_canary.py")
WORKFLOW_PATH = Path(".github/workflows/lordchrist-rich-live-canary.yml")


def _input_media_identities(value: object) -> list[str]:
    identities: list[str] = []

    def walk(candidate: object) -> None:
        if isinstance(candidate, dict):
            identity = candidate.get("media")
            if isinstance(identity, str) and (identity.startswith("attach://") or identity.startswith("https://")):
                identities.append(identity)
            for child in candidate.values():
                walk(child)
        elif isinstance(candidate, list):
            for child in candidate:
                walk(child)

    walk(value)
    return identities


def test_live_canary_release_is_one_exact_issue_bound_publication() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    assert release["release_id"] == RELEASE_ID
    assert release["owning_issue"] == OWNING_ISSUE == 473
    assert release["publication_id"] == PUBLICATION_ID == "lordchrist-rich-sermons-survive-century"
    assert release["approved"] is True
    assert release["max_combined_verified_per_day_moscow"] == 2
    assert release["max_rich_verified_per_day_moscow"] == 1
    assert "three-expository-patterns" not in RELEASE_PATH.read_text(encoding="utf-8")


def test_live_canary_renders_exact_three_photo_multipart_document_without_fallback() -> None:
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
    assert [media.uri for media in article.media] == [
        "attach://lc_calvin",
        "attach://lc_spurgeon",
        "attach://lc_tape",
    ]
    assert len(document.provider_assigned_media_paths) == 3
    assert render.provider_assigned_media == ("media-calvin", "media-spurgeon", "media-tape")
    assert sum(block.get("type") == "photo" for block in document.input_rich_message["blocks"]) == 3
    assert sorted(_input_media_identities(document.input_rich_message)) == sorted(
        f"attach://{name}" for name in ATTACHMENT_NAMES.values()
    )
    assert not any(identity.startswith("https://") for identity in _input_media_identities(document.input_rich_message))


def test_multipart_provider_sends_exact_three_attachments_in_one_request() -> None:
    observed: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        body = request.content
        content_type = request.headers["content-type"]
        assert "multipart/form-data" in content_type
        assert b'"chat_id"' not in body
        assert b"-1001295216957" in body
        for name in ATTACHMENT_NAMES.values():
            assert f'attach://{name}'.encode() in body
            assert f'name="{name}"'.encode() in body
        assert b"CALVIN_BYTES" in body
        assert b"SPURGEON_BYTES" in body
        assert b"TAPE_BYTES" in body
        return httpx.Response(400, json={"ok": False, "error_code": 400, "description": "test rejection"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = _LordChristMultipartProvider(
        token="test-token",
        http_client=client,
        attachments={
            "lc_calvin": ("john-calvin.jpg", b"\xff\xd8\xffCALVIN_BYTES", "image/jpeg"),
            "lc_spurgeon": ("charles-spurgeon.jpg", b"\xff\xd8\xffSPURGEON_BYTES", "image/jpeg"),
            "lc_tape": ("reel-to-reel.jpg", b"\xff\xd8\xffTAPE_BYTES", "image/jpeg"),
        },
    )
    rich_message = {
        "blocks": [
            {"type": "photo", "photo": {"type": "photo", "media": "attach://lc_calvin"}},
            {"type": "photo", "photo": {"type": "photo", "media": "attach://lc_spurgeon"}},
            {"type": "photo", "photo": {"type": "photo", "media": "attach://lc_tape"}},
        ]
    }
    try:
        response = provider.send_rich_message(
            chat_id=-1001295216957,
            rich_message=rich_message,
            timeout=TelegramRichRequestTimeout(),
        )
    finally:
        provider.close()
    assert response.status_code == 400
    assert response.body == {"ok": False, "error_code": 400, "description": "test rejection"}
    assert len(observed) == 1


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
    assert '"delivery_mode": "multipart-attach"' in source
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
