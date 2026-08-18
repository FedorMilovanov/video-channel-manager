from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest

from video_channel_manager.svodka_rich_successor_v4 import (
    FAILED_PREDECESSOR_ERROR,
    FAILED_PREDECESSOR_RELEASE_ID,
    PREDECESSOR_MESSAGE_ID,
    PREDECESSOR_PUBLICATION_ID,
    PREDECESSOR_RELEASE_ID,
    RELEASE_ID,
    build_document,
    load_release,
    new_ledger,
    select,
)

RELEASE_PATH = Path("content/telegram/svodka/rich-v1/successor-v4-cdn-finalizer-2026-08.json")


def test_v4_release_is_fresh_cdn_identity_after_verified_canary_and_confirmed_absent_v3() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    assert release["release_id"] == RELEASE_ID
    assert release["publication_window_minutes"] == 120
    assert release["max_verified_per_day_moscow"] == 2
    assert release["verified_predecessor_canary"] == {
        "release_id": PREDECESSOR_RELEASE_ID,
        "publication_id": PREDECESSOR_PUBLICATION_ID,
        "message_id": PREDECESSOR_MESSAGE_ID,
        "required_state": "published",
        "required_provider_effect": "verified",
    }
    assert release["confirmed_absent_predecessor"] == {
        "release_id": FAILED_PREDECESSOR_RELEASE_ID,
        "publication_id": "svodka-rich-wombat-cubic-poop",
        "required_state": "failed_no_effect",
        "required_provider_effect": "confirmed_absent",
        "required_error": FAILED_PREDECESSOR_ERROR,
    }


def test_v4_uses_exact_reviewed_unsplash_cdn_photo_and_telegram_heading_canonicalization() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    override = cast(dict[str, Any], release["media_override"])
    assert override["canonical_source_page_url"] == (
        "https://unsplash.com/photos/a-wombat-stares-directly-at-the-camera-QvgZkCAfJdc"
    )
    assert str(override["direct_media_url"]).startswith("https://images.unsplash.com/photo-1743938153060-7f6c4b1b9ba0?")
    assert override["licence"] == "Unsplash License"
    assert override["expected_mime"] == "image/jpeg"
    assert override["provider_upload_status"] == "not_uploaded"

    item = cast(list[dict[str, Any]], release["items"])[0]
    document, rendered, article = build_document(Path("."), release, item)
    headings = [block for block in document.input_rich_message["blocks"] if block.get("type") == "heading"]
    assert headings[0]["text"] == "🔬 Почему у вомбата получаются кубики"
    assert headings[1]["text"] == "1️⃣ Сначала уберём главную шутку"
    assert all(isinstance(block["text"], str) for block in headings)
    assert len(article.media) == 1
    assert article.media[0].media_id == "asset-wombat-cubic-poop-media-01-v4"
    assert article.media[0].uri == override["direct_media_url"]
    assert len(document.provider_assigned_media_paths) == 1
    assert rendered.provider_assigned_media == (article.media[0].media_id,)
    assert "skip_entity_detection" not in document.input_rich_message


def test_v4_is_scheduled_only_and_strictly_expires() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    ledger = new_ledger(release)
    entry = cast(dict[str, dict[str, Any]], ledger["entries"])["svodka-rich-wombat-cubic-poop"]
    assert entry["state"] == "pending"
    assert entry["provider_effect"] == "impossible"

    assert select(release, ledger, datetime.fromisoformat("2026-08-18T21:09:59+03:00")) is None
    selected = select(release, ledger, datetime.fromisoformat("2026-08-18T21:10:00+03:00"))
    assert selected is not None
    item, mode = selected
    assert item["publication_id"] == "svodka-rich-wombat-cubic-poop"
    assert mode == "scheduled"

    with pytest.raises(ValueError, match="strict-next window expired"):
        select(release, new_ledger(release), datetime.fromisoformat("2026-08-18T23:10:00+03:00"))


def test_v4_never_reselects_ambiguous_no_effect_or_published_state() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    for state, effect in (("may_exist", "may_exist"), ("failed_no_effect", "confirmed_absent")):
        ledger = new_ledger(release)
        entry = cast(dict[str, dict[str, Any]], ledger["entries"])["svodka-rich-wombat-cubic-poop"]
        entry["state"] = state
        entry["provider_effect"] = effect
        with pytest.raises(ValueError, match="durable blocker"):
            select(release, ledger, datetime.fromisoformat("2026-08-18T21:11:00+03:00"))

    ledger = new_ledger(release)
    entry = cast(dict[str, dict[str, Any]], ledger["entries"])["svodka-rich-wombat-cubic-poop"]
    entry["state"] = "published"
    entry["provider_effect"] = "verified"
    assert select(release, ledger, datetime.fromisoformat("2026-08-18T21:11:00+03:00")) is None
