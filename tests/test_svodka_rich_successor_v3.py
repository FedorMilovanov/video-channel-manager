from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest

from video_channel_manager.svodka_rich_reconciliation import semantic_structure_sha256
from video_channel_manager.svodka_rich_successor_v3 import (
    PREDECESSOR_MESSAGE_ID,
    PREDECESSOR_PUBLICATION_ID,
    PREDECESSOR_RELEASE_ID,
    RELEASE_ID,
    build_document,
    load_release,
    new_ledger,
    release_digest,
    select,
)

RELEASE_PATH = Path("content/telegram/svodka/rich-v1/successor-v3-finalizer-2026-08.json")


def _custom_emoji_ids(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        if value.get("type") == "custom_emoji" and isinstance(value.get("custom_emoji_id"), str):
            found.append(value["custom_emoji_id"])
        for child in value.values():
            found.extend(_custom_emoji_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_custom_emoji_ids(child))
    return found


def test_v3_release_is_fresh_one_item_scheduled_finalizer_bound_to_verified_message_28() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    assert release["release_id"] == RELEASE_ID
    assert release["publication_window_minutes"] == 120
    assert release["max_verified_per_day_moscow"] == 2
    predecessor = cast(dict[str, Any], release["verified_predecessor_canary"])
    assert predecessor == {
        "release_id": PREDECESSOR_RELEASE_ID,
        "publication_id": PREDECESSOR_PUBLICATION_ID,
        "message_id": PREDECESSOR_MESSAGE_ID,
        "required_state": "published",
        "required_provider_effect": "verified",
    }
    items = cast(list[dict[str, Any]], release["items"])
    assert len(items) == 1
    assert items[0]["publication_id"] == "svodka-rich-wombat-cubic-poop"
    assert items[0]["scheduled_at"] == "2026-08-18T20:30:00+03:00"
    assert items[0]["dispatch_mode"] == "scheduled"
    assert release_digest(release).startswith("sha256:")


def test_v3_document_uses_observed_telegram_heading_canonicalization_and_one_ready_photo() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    item = cast(list[dict[str, Any]], release["items"])[0]
    document, render, article = build_document(Path("."), release, item)

    headings = [block for block in document.input_rich_message["blocks"] if block.get("type") == "heading"]
    assert headings[0]["text"] == "🔬 Почему у вомбата получаются кубики"
    assert headings[1]["text"] == "1️⃣ Сначала уберём главную шутку"
    assert headings[2]["text"] == "2️⃣ Как мягкая кишка делает плоские грани"
    assert headings[3]["text"] == "3️⃣ А зачем вообще кубическая форма"
    assert all(isinstance(block["text"], str) for block in headings)
    assert "skip_entity_detection" not in document.input_rich_message
    assert not _custom_emoji_ids(document.input_rich_message)
    assert len(article.media) == 1
    assert len(document.provider_assigned_media_paths) == 1
    assert render.provider_assigned_media == tuple(media.media_id for media in article.media)


def test_message_28_plain_heading_fragment_normalization_is_semantically_exact() -> None:
    fragmented = {"blocks": [{"type": "heading", "size": 2, "text": ["1️⃣", " ", "Заголовок"]}]}
    canonical = {"blocks": [{"type": "heading", "size": 2, "text": "1️⃣ Заголовок"}]}
    assert semantic_structure_sha256(fragmented) == semantic_structure_sha256(canonical)


def test_v3_ledger_starts_provider_impossible_and_never_selects_canary_mode() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    ledger = new_ledger(release)
    entry = cast(dict[str, dict[str, Any]], ledger["entries"])["svodka-rich-wombat-cubic-poop"]
    assert entry["state"] == "pending"
    assert entry["provider_effect"] == "impossible"
    assert entry["dispatch_mode"] is None

    assert select(release, ledger, datetime.fromisoformat("2026-08-18T20:29:59+03:00")) is None
    selected = select(release, ledger, datetime.fromisoformat("2026-08-18T20:30:00+03:00"))
    assert selected is not None
    item, mode = selected
    assert item["publication_id"] == "svodka-rich-wombat-cubic-poop"
    assert mode == "scheduled"


def test_v3_strict_window_expires_without_replay_authority() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    ledger = new_ledger(release)
    with pytest.raises(ValueError, match="strict-next window expired"):
        select(release, ledger, datetime.fromisoformat("2026-08-18T22:30:00+03:00"))


def test_v3_terminal_or_ambiguous_state_cannot_be_reselected() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    ledger = new_ledger(release)
    entry = cast(dict[str, dict[str, Any]], ledger["entries"])["svodka-rich-wombat-cubic-poop"]
    entry["state"] = "may_exist"
    entry["provider_effect"] = "may_exist"
    with pytest.raises(ValueError, match="durable blocker"):
        select(release, ledger, datetime.fromisoformat("2026-08-18T20:31:00+03:00"))

    entry["state"] = "published"
    entry["provider_effect"] = "verified"
    assert select(release, ledger, datetime.fromisoformat("2026-08-18T20:31:00+03:00")) is None
