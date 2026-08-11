from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest

from video_channel_manager.svodka_rich_production import (
    build_document,
    load_ledger,
    load_release,
    release_digest,
    select,
)

RELEASE_PATH = Path("content/telegram/svodka/rich-v1/production-release-2026-08.json")
WORKFLOW_PATH = Path(".github/workflows/svodka-rich-production.yml")
EXPECTED_RELEASE_SHA256 = "sha256:ca7a4047c4808c5800022aebd2a9e8334ad0751197a121aa1c54d707d36b7b9c"


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


def test_release_binds_all_14_exact_sources_and_renders_one_production_path() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    assert release_digest(release) == EXPECTED_RELEASE_SHA256
    items = cast(list[dict[str, Any]], release["items"])
    assert len(items) == 14
    assert items[0]["publication_id"] == "svodka-rich-venus-day-longer-than-year"
    assert items[0]["scheduled_at"] == "2026-08-11T19:30:00+03:00"
    assert items[1]["publication_id"] == "svodka-rich-2026-august-total-solar-eclipse"
    assert items[1]["scheduled_at"] == "2026-08-12T10:30:00+03:00"

    for item in items:
        document, render, article = build_document(Path("."), release, item)
        assert document.publication_id == item["publication_id"]
        assert document.legacy_fallback is None
        assert document.input_rich_message["skip_entity_detection"] is True
        assert _custom_emoji_ids(document.input_rich_message)
        assert render.media_placeholders == ()
        assert len(document.provider_assigned_media_paths) == len(article.media)
        assert render.provider_assigned_media == tuple(media.media_id for media in article.media)


def test_release_uses_verified_primary_premium_numbers_in_section_headings() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    item = cast(list[dict[str, Any]], release["items"])[0]
    document, _render, _article = build_document(Path("."), release, item)
    custom_ids = _custom_emoji_ids(document.input_rich_message)
    assert "5426972640587853090" in custom_ids  # primary premium digit 1


def test_first_due_item_is_canary_then_next_due_item_is_scheduled(tmp_path: Path) -> None:
    release = load_release(RELEASE_PATH, Path("."))
    ledger_path = tmp_path / "ledger.json"
    ledger = load_ledger(ledger_path, release, create=True)

    assert select(release, ledger, datetime.fromisoformat("2026-08-11T19:29:59+03:00")) is None
    first = select(release, ledger, datetime.fromisoformat("2026-08-11T19:30:00+03:00"))
    assert first is not None
    first_item, first_mode = first
    assert first_item["publication_id"] == "svodka-rich-venus-day-longer-than-year"
    assert first_mode == "canary"

    entry = cast(dict[str, dict[str, Any]], ledger["entries"])[first_item["publication_id"]]
    entry.update({"state": "published", "provider_effect": "verified", "dispatch_mode": "canary"})
    second = select(release, ledger, datetime.fromisoformat("2026-08-12T10:30:00+03:00"))
    assert second is not None
    second_item, second_mode = second
    assert second_item["publication_id"] == "svodka-rich-2026-august-total-solar-eclipse"
    assert second_mode == "scheduled"


def test_expired_strict_next_fails_closed() -> None:
    release = load_release(RELEASE_PATH, Path("."))
    ledger = load_ledger(Path("/definitely/missing/svodka-rich-ledger.json"), release, create=True)
    with pytest.raises(ValueError, match="strict-next window expired"):
        select(release, ledger, datetime.fromisoformat("2026-08-11T21:30:00+03:00"))


def test_workflow_has_real_evening_canary_and_no_fallback_sendmessage() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert 'cron: "30 16 11 8 *"' in workflow
    assert 'cron: "30 7 12-18 8 *"' in workflow
    assert 'cron: "30 16 12-17 8 *"' in workflow
    assert "svodka_rich_production send" in workflow
    assert "sendMessage" not in workflow
    assert "group: svodka-telegram-publisher" in workflow
    assert "Archive exact provider outcome before ledger mutation" in workflow
    assert "Persist intent and evidence before Telegram mutation" in workflow
