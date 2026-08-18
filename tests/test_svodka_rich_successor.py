from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, cast

from video_channel_manager.svodka_rich_successor import (
    MEDIA_USER_AGENT,
    build_document,
    load_ledger,
    load_release,
    select,
)

RELEASE_PATH = Path("content/telegram/svodka/rich-v1/successor-release-2026-08.json")
WORKFLOW_PATH = Path(".github/workflows/svodka-rich-successor.yml")


def test_historical_v2_successor_remains_two_item_reproducible_with_entity_detection_enabled() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    items = cast(list[dict[str, Any]], release["items"])
    assert len(items) == 2
    assert items[0]["publication_id"] == "svodka-rich-goldfish-three-second-memory-myth"
    assert items[1]["publication_id"] == "svodka-rich-wombat-cubic-poop"

    for item in items:
        document, rendered, article = build_document(Path("."), release, item)
        assert "skip_entity_detection" not in document.input_rich_message
        assert document.legacy_fallback is None
        assert len(document.provider_assigned_media_paths) == len(article.media)
        assert rendered.provider_assigned_media == tuple(media.media_id for media in article.media)


def test_successor_media_reader_identifies_bot_and_operator() -> None:
    assert "bot" in MEDIA_USER_AGENT.casefold()
    assert "video-channel-manager" in MEDIA_USER_AGENT
    assert "https://github.com/FedorMilovanov/video-channel-manager" in MEDIA_USER_AGENT


def test_historical_v2_selection_remains_reproducible_but_is_not_the_active_writer() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    ledger = load_ledger(Path("/definitely/missing/svodka-v2-ledger.json"), release, create=True)

    first = select(release, ledger, datetime.fromisoformat("2026-08-18T15:30:00+03:00"))
    assert first is not None
    first_item, first_mode = first
    assert first_mode == "canary"

    entry = cast(dict[str, dict[str, Any]], ledger["entries"])[first_item["publication_id"]]
    entry.update({"state": "published", "provider_effect": "verified", "dispatch_mode": "canary"})
    second = select(release, ledger, datetime.fromisoformat("2026-08-18T15:31:00+03:00"))
    assert second is not None
    second_item, second_mode = second
    assert second_item["publication_id"] == "svodka-rich-wombat-cubic-poop"
    assert second_mode == "scheduled"


def test_verified_v4_successor_workflow_is_retired_after_terminal_publication() -> None:
    assert not WORKFLOW_PATH.exists()
