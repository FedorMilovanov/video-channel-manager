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


def test_active_successor_workflow_is_fresh_v3_one_mutation_path_without_self_dispatch() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "successor-v3-finalizer-2026-08.json" in workflow
    assert "video_channel_manager.svodka_rich_successor_v3 send" in workflow
    assert "video_channel_manager.svodka_rich_successor send" not in workflow
    assert "telegram_multichannel_cli send-once" not in workflow
    assert "/sendMessage" not in workflow
    assert "Require verified predecessor canary message 28" in workflow
    assert "Persist intent before Telegram mutation" in workflow
    assert "Send exactly one successor Rich Message" in workflow
    assert "Trigger second successor item after verified canary" not in workflow
    assert "gh workflow run svodka-rich-successor.yml" not in workflow
    assert "Close successor rollout after verified second item" not in workflow


def test_active_successor_persists_v3_preintent_diagnostics_before_any_provider_boundary() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert workflow.count("continue-on-error: true") == 3
    assert "'provider_write_performed': False" in workflow
    assert "rich-successor-v3-preintent/$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT/diagnostic.json" in workflow
    assert "Stop before provider boundary if v3 pre-intent proof failed" in workflow

    diagnostic = workflow.index("Persist v3 pre-intent diagnostics before provider boundary")
    diagnostic_commit = workflow.index("Commit durable v3 pre-intent diagnostic")
    stop = workflow.index("Stop before provider boundary if v3 pre-intent proof failed")
    intent = workflow.index("Persist intent before Telegram mutation")
    send = workflow.index("Send exactly one successor Rich Message")
    assert diagnostic < diagnostic_commit < stop < intent < send
