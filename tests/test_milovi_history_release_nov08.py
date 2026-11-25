from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts import milovi_history_release_20261108 as scheduled
from video_channel_manager.milovi_telegram_feed import state_init
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_state import load_ledger

BASE = Path("content/telegram/milovi-cake/feed")
ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "content/telegram/milovi-cake/releases" / f"{scheduled.PUB}-runtime.json"


def legacy_fixture(tmp_path: Path) -> tuple[Path, Path]:
    state_init(scheduled.PUB, state_checkout=tmp_path)
    index = tmp_path / BASE / "index.json"
    ledger = tmp_path / BASE / f"{scheduled.PUB}.json"
    i = json.loads(index.read_text(encoding="utf-8"))
    ledger_record = json.loads(ledger.read_text(encoding="utf-8"))
    row = i["entries"][scheduled.PUB]
    row["release_candidate_sha256"] = scheduled.OLD_CANDIDATE_DIGEST
    row["provider_payload_sha256"] = scheduled.OLD_PROVIDER_PAYLOAD
    ledger_record["release_digest"] = scheduled.OLD_RELEASE_DIGEST
    ledger_record["entries"][scheduled.PUB]["provider_payload_sha256"] = scheduled.OLD_PROVIDER_PAYLOAD
    assert ledger_record["entries"][scheduled.PUB]["provider_payload_sha256"] == scheduled.OLD_PROVIDER_PAYLOAD
    index.write_text(json.dumps(i, ensure_ascii=False) + "\n", encoding="utf-8")
    ledger.write_text(json.dumps(ledger_record, ensure_ascii=False) + "\n", encoding="utf-8")
    return index, ledger


def test_protected_old_pending_exact_digest_migrates_without_provider_attempt(tmp_path: Path):
    index, ledger = legacy_fixture(tmp_path)
    orig_i = json.loads(index.read_text(encoding="utf-8"))
    # Extra unrelated published/verified row must not be removed/rewritten.
    other = {
        "publication_id": "milovi-feed-20261106-001",
        "release_id": "milovi-feed-20261106-001",
        "release_candidate_sha256": "sha256:" + "1" * 64,
        "provider_payload_sha256": "sha256:" + "2" * 64,
        "ledger_relative_path": "content/telegram/milovi-cake/feed/milovi-feed-20261106-001.json",
        "state": "published",
        "provider_effect": "verified",
        "intent_id": "verified-intent",
        "message_id": 27,
        "message_url": "https://t.me/MiloviCake/27",
        "updated_at_utc": None,
    }
    orig_i["entries"]["milovi-feed-20261106-001"] = other
    index.write_text(json.dumps(orig_i, ensure_ascii=False) + "\n", encoding="utf-8")
    assert scheduled.migrate_pending(tmp_path) == {
        "migrated": "true",
        "reason": "owner_exact_immediate_date_revision_only",
    }
    migrated = json.loads(index.read_text(encoding="utf-8"))
    assert migrated["entries"]["milovi-feed-20261106-001"] == other
    release = load_release(RELEASE)
    assert migrated["entries"][scheduled.PUB]["release_candidate_sha256"] == release.candidate_digest()
    assert migrated["entries"][scheduled.PUB]["provider_payload_sha256"] == scheduled.NEW_PROVIDER_PAYLOAD
    ledger_record = load_ledger(ledger, release).entries[scheduled.PUB]
    assert ledger_record.state == "pending" and ledger_record.provider_effect == "impossible"
    assert ledger_record.message_id is None and ledger_record.intent_id is None
    assert ledger_record.attempted_at_utc is None
    before_index = index.read_bytes()
    before_ledger = ledger.read_bytes()
    assert scheduled.migrate_pending(tmp_path)["migrated"] == "false"
    assert index.read_bytes() == before_index and ledger.read_bytes() == before_ledger


@pytest.mark.parametrize("broken", ["unknown", "published", "dispatching"])
def test_migration_rejects_provider_history_no_mutation(tmp_path: Path, broken: str):
    i, ledger_record = legacy_fixture(tmp_path)
    obj = json.loads(ledger_record.read_text(encoding="utf-8"))
    obj["entries"][scheduled.PUB]["state"] = broken
    obj["entries"][scheduled.PUB]["provider_effect"] = "may_exist"
    ledger_record.write_text(json.dumps(obj, ensure_ascii=False) + "\n", encoding="utf-8")
    old_i = i.read_bytes()
    old_l = ledger_record.read_bytes()
    with pytest.raises(ValueError):
        scheduled.migrate_pending(tmp_path)
    assert i.read_bytes() == old_i and ledger_record.read_bytes() == old_l


def test_future_owner_date_and_hard_freshness_window(tmp_path: Path):
    legacy_fixture(tmp_path)
    scheduled.migrate_pending(tmp_path)
    zone = ZoneInfo("Europe/Moscow")
    assert scheduled.due(tmp_path, now=datetime(2026, 11, 6, 15, 10, tzinfo=zone))["dispatch"] == "false"
    assert scheduled.due(tmp_path, now=datetime(2026, 11, 7, 16, 48, tzinfo=zone))["dispatch"] == "false"
    assert scheduled.due(tmp_path, now=datetime(2026, 11, 7, 16, 55, tzinfo=zone))["dispatch"] == "true"
    assert scheduled.due(tmp_path, now=datetime(2026, 11, 7, 18, 51, tzinfo=zone))["dispatch"] == "false"


def test_publication_provider_photo_bytes_and_target_unchanged():
    release = scheduled.reviewed_release()
    assert release.items[0].payload.provider_payload_sha256 == scheduled.NEW_PROVIDER_PAYLOAD
    assert release.items[0].scheduled_at == scheduled.EXPECTED_TIME
    assert release.chat_id == -1002215328390 and release.bot_id == 8716602202
