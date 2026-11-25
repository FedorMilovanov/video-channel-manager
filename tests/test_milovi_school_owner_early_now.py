from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts import milovi_school_reading_due as school
from video_channel_manager.milovi_telegram_feed import state_init, validate_bundle
from video_channel_manager.telegram_multichannel_release import load_release

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "content/telegram/milovi-cake"
EARLY = school.OWNER_EARLY_PARIS_BREST
ORIGINAL = school.ORIGINAL_PARIS_BREST
LOCAL = ZoneInfo("Europe/Moscow")


def test_owner_explicit_early_release_binds_exact_original_story() -> None:
    validate_bundle(EARLY, require_execution_authorized=True)
    early = load_release(BASE / "releases" / f"{EARLY}-runtime.json")
    original = load_release(BASE / "releases" / f"{ORIGINAL}-runtime.json")
    assert EARLY == "milovi-feed-20261106-001"
    assert early.release_id == EARLY
    assert early.items[0].scheduled_at == datetime(2026, 11, 6, 22, 20, tzinfo=LOCAL)
    assert early.chat_id == original.chat_id == -1002215328390
    assert early.bot_id == original.bot_id == 8716602202
    assert early.items[0].source_sha256 == original.items[0].source_sha256
    assert early.items[0].payload.caption == original.items[0].payload.caption
    assert early.items[0].payload.media_sha256 == original.items[0].payload.media_sha256
    assert early.items[0].payload.media_byte_size == original.items[0].payload.media_byte_size
    media = json.loads((BASE / "releases" / f"{EARLY}-media.json").read_text(encoding="utf-8"))
    assert media["source"]["repository"] == "FedorMilovanov/Milovi_School"
    assert media["source"]["path"] == "public/images/articles/paris-brest-race-dessert.webp"
    approval = json.loads((BASE / "releases" / f"{EARLY}-execution-authority.json").read_text(encoding="utf-8"))
    assert approval["execution_authorized"] is True
    assert approval["provider_mutation_allowed"] is True
    assert approval["release_digest"] == early.digest
    assert approval["authorized_publication_id"] == EARLY
    candidate = json.loads((BASE / "candidates" / f"{EARLY}.json").read_text(encoding="utf-8"))
    override = candidate["owner_early_override"]
    assert override["override_only_this_publication"] is True
    assert override["original_publication_id"] == ORIGINAL
    assert override["do_not_republish_on_original_date"] is True


def test_early_release_pending_is_not_falsely_reported_published(tmp_path: Path) -> None:
    school.initialize_all(tmp_path)
    state_init(EARLY, state_checkout=tmp_path)
    index = school._load_state_index(tmp_path)
    assert school._early_paris_brest_verified(tmp_path, index) is False


def test_original_nov17_suppressed_when_owner_early_receipt_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    school.initialize_all(tmp_path)
    monkeypatch.setattr(school, "_early_paris_brest_verified", lambda *_args: True)
    result = school.due(tmp_path, now=datetime(2026, 11, 17, 12, 37, tzinfo=LOCAL))
    assert result == {
        "dispatch": "false",
        "reason": "original_story_already_sent_20261106",
    }


def test_nov21_accepts_early_verified_receipt_but_still_requires_first_ten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    school.initialize_all(tmp_path)
    monkeypatch.setattr(school, "_early_paris_brest_verified", lambda *_args: True)
    with pytest.raises(ValueError, match="first-ten"):
        school.due(tmp_path, now=datetime(2026, 11, 21, 12, 37, tzinfo=LOCAL))
    monkeypatch.setattr(school, "require_first_ten_real_cake_videos", lambda *_args: None)
    assert school.due(tmp_path, now=datetime(2026, 11, 21, 12, 37, tzinfo=LOCAL)) == {
        "dispatch": "true",
        "publication_id": "milovi-feed-20261121-002",
        "reason": "exact_owner_approved_school_photo_due",
    }
