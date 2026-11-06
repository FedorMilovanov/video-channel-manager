from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts import milovi_school_reading_due as school
from video_channel_manager.milovi_telegram_feed import validate_bundle
from video_channel_manager.telegram_multichannel_release import load_release

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / "content/telegram/milovi-cake/releases"
WORKFLOW = ROOT / ".github/workflows/milovi-telegram-school-reading-due-20261117.yml"


def test_three_exact_school_photo_releases_keep_cake_and_school_distinct() -> None:
    assert len(school.FIRST_TEN) == 10
    assert len(set(school.FIRST_TEN)) == 10
    assert school.FIRST_TEN[0] == "milovi-feed-20261107-002"
    assert school.FIRST_TEN[-1] == "milovi-feed-20261116-001"
    school.validate_exact_releases()
    for day, pid, slug in school.RELEASES:
        release = load_release(RELEASE_ROOT / f"{pid}-runtime.json")
        media = json.loads((RELEASE_ROOT / f"{pid}-media.json").read_text(encoding="utf-8"))
        approval = json.loads((RELEASE_ROOT / f"{pid}-execution-authority.json").read_text(encoding="utf-8"))
        candidate = json.loads(
            (ROOT / "content/telegram/milovi-cake/candidates" / f"{pid}.json").read_text(encoding="utf-8")
        )
        assert validate_bundle(pid, require_execution_authorized=True)["payload_kind"] == "photo"
        assert release.reviewed_publication_id == pid and release.release_authorized
        assert release.items[0].scheduled_at.isoformat() == day + "T12:30:00+03:00"
        assert release.daily_verified_limit == 2
        assert release.chat_id == -1002215328390
        assert release.bot_id == 8716602202
        assert release.candidate_digest() == approval["release_candidate_sha256"]
        assert release.digest == approval["release_digest"]
        assert approval["max_provider_attempts"] == 1
        assert approval["blind_mutation_retries"] == 0
        assert media["source"]["repository"] == school.SCHOOL_REPO
        assert media["source"]["commit"] == school.SOURCE_COMMIT
        assert media["source"]["path"] == f"public/images/articles/{slug}.webp"
        assert media["source"]["pixel_width"] == 1280
        assert media["source"]["pixel_height"] == 800
        assert media["transport"]["format"] == "image/jpeg"
        assert candidate["editorial_guards"]["school_separate_educational_content"] is True
        assert candidate["editorial_guards"]["contains_product_process_claim"] is False
        caption = candidate["caption"]
        assert release.items[0].payload.caption == caption
        assert release.items[0].payload.media_byte_size == media["transport"]["byte_size"]
        assert release.items[0].payload.media_sha256 == media["transport"]["sha256"]
        assert candidate["caption_sha256"] == "sha256:" + hashlib.sha256(caption.encode("utf-8")).hexdigest()
        assert len(caption) < 1024
        assert "Иллюстрация — Milovi School." in caption
        assert f"https://french.milovicake.ru/articles/{slug}/" in caption


def test_only_one_existing_provider_writer_and_no_competing_video_workflow() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'cron: "37 9 17,21,25 11 *"' in text
    assert "group: milovi-cake-telegram-publisher" in text
    assert "Milovi Telegram feed quality" in text
    assert "github.event.workflow_run.head_sha == github.sha" in text
    assert "milovi-telegram-feed-publisher.yml" in text
    assert "-f operation=publish" in text
    assert "ten actual Cake receipts" in text
    assert "sendPhoto" not in text
    assert "curl" not in text
    assert "python -m scripts.milovi_school_reading_due due" in text
    video = (ROOT / ".github/workflows/milovi-telegram-muted15-due-20261108.yml").read_text(encoding="utf-8")
    assert "group: milovi-cake-telegram-publisher" in video
    assert 'cron: "7 16 8-22 11 *"' in video


def test_school_publications_start_pending_and_not_sent(tmp_path: Path) -> None:
    school.initialize_all(tmp_path)
    for _, pid, _ in school.RELEASES:
        release = load_release(RELEASE_ROOT / f"{pid}-runtime.json")
        state = json.loads((tmp_path / "content/telegram/milovi-cake/feed" / f"{pid}.json").read_text(encoding="utf-8"))
        entry = state["entries"][pid]
        assert state["release_digest"] == release.digest
        assert entry["state"] == "pending"
        assert entry["provider_effect"] == "impossible"
        assert entry["message_id"] is None
        assert entry["intent_id"] is None
    school.initialize_all(tmp_path)  # No reset or new intents on a repeated CI event.


def test_fresh_due_blocks_school_before_ten_verified_cake_videos(tmp_path: Path) -> None:
    school.initialize_all(tmp_path)
    now = datetime(2026, 11, 17, 12, 37, tzinfo=ZoneInfo("Europe/Moscow"))
    with pytest.raises(ValueError, match="first-ten Cake video"):
        school.due(tmp_path, now=now)


def test_exact_first_date_and_year_gate_without_provider_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    school.initialize_all(tmp_path)
    monkeypatch.setattr(school, "require_first_ten_real_cake_videos", lambda *_args: None)
    due = school.due(tmp_path, now=datetime(2026, 11, 17, 12, 37, tzinfo=ZoneInfo("Europe/Moscow")))
    assert due == {
        "dispatch": "true",
        "publication_id": "milovi-feed-20261117-002",
        "reason": "exact_owner_approved_school_photo_due",
    }
    assert (
        school.due(tmp_path, now=datetime(2026, 11, 18, 12, 37, tzinfo=ZoneInfo("Europe/Moscow")))["dispatch"]
        == "false"
    )
    assert (
        school.due(tmp_path, now=datetime(2027, 11, 17, 12, 37, tzinfo=ZoneInfo("Europe/Moscow")))["dispatch"]
        == "false"
    )
    assert (
        school.due(tmp_path, now=datetime(2026, 11, 17, 15, 0, tzinfo=ZoneInfo("Europe/Moscow")))["dispatch"] == "false"
    )
    with pytest.raises(ValueError, match="strict predecessor"):
        school.due(tmp_path, now=datetime(2026, 11, 21, 12, 37, tzinfo=ZoneInfo("Europe/Moscow")))


def test_first_ten_criterion_fails_closed_on_unverified_receipts(tmp_path: Path) -> None:
    entries: dict[str, object] = {
        pid: {
            "publication_id": pid,
            "state": "pending",
            "provider_effect": "impossible",
            "message_id": None,
            "message_url": None,
        }
        for pid in school.FIRST_TEN
    }
    with pytest.raises(ValueError, match="first-ten"):
        school.require_first_ten_real_cake_videos(tmp_path, entries)
    entries[school.FIRST_TEN[0]] = {
        "publication_id": school.FIRST_TEN[0],
        "state": "published",
        "provider_effect": "may_exist",
        "message_id": 99,
        "message_url": "https://t.me/MiloviCake/99",
    }
    assert not school._verified(entries[school.FIRST_TEN[0]], school.FIRST_TEN[0])
