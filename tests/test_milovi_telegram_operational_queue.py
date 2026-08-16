from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "content/telegram/milovi-cake/queues/bootstrap-first-screen-queue-2026-08.json"
FROZEN_ROLLOUT = ROOT / "content/telegram/milovi-cake/bootstrap-rollout-candidate-2026-08.json"
CANDIDATES = ROOT / "content/telegram/milovi-cake/bootstrap-first-screen-candidates-2026-08.json"
PROOF = ROOT / "content/telegram/milovi-cake/bootstrap-photo-transport-proof-2026-08.json"
PROFILE = ROOT / "content/telegram/channels/milovi-cake.json"
ZONE = ZoneInfo("Europe/Moscow")


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _caption_sha(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_queue_is_exactly_ten_future_daylight_items_and_remains_provider_inert() -> None:
    queue = _load(QUEUE)
    profile = _load(PROFILE)
    assert queue["schema_name"] == "video-channel-manager.milovi-telegram-operational-queue"
    assert queue["project_key"] == "milovi-cake"
    assert queue["chat_id"] == -1002215328390
    assert queue["chat_username"] == "MiloviCake"
    assert queue["bot_id"] == 8716602202
    assert queue["bot_username"] == "preaching_mp3_bot"
    assert queue["execution_authorized"] is False
    assert queue["provider_mutation_allowed"] is False
    assert profile["provider_writes_authorized"] is False

    items = queue["items"]
    assert isinstance(items, list)
    assert len(items) == 10
    assert [item["sequence"] for item in items] == list(range(1, 11))
    assert [item["publication_id"] for item in items] == [f"milovi-bootstrap-{index:03d}" for index in range(1, 11)]
    assert "milovi-cake-canary-001" not in {item["publication_id"] for item in items}

    parsed = [datetime.fromisoformat(item["planned_local"]) for item in items]
    assert all(value.tzinfo is not None for value in parsed)
    assert parsed == sorted(parsed)
    assert parsed[0].isoformat() == "2026-08-17T10:30:00+03:00"
    assert parsed[-1].isoformat() == "2026-08-21T20:00:00+03:00"
    assert all(value.astimezone(ZONE).date().isoformat() >= "2026-08-17" for value in parsed)
    assert not any(value.astimezone(ZONE).date().isoformat() == "2026-08-16" for value in parsed)
    assert [value.astimezone(ZONE).time().replace(tzinfo=None) for value in parsed] == [
        time(10, 30),
        time(20, 0),
    ] * 5
    counts = Counter(value.astimezone(ZONE).date().isoformat() for value in parsed)
    assert sorted(counts.values()) == [2, 2, 2, 2, 2]
    assert all(time(9, 0) <= value.astimezone(ZONE).time().replace(tzinfo=None) <= time(21, 0) for value in parsed)


def test_queue_preserves_every_frozen_caption_operation_and_media_identity() -> None:
    queue = _load(QUEUE)
    rollout = _load(FROZEN_ROLLOUT)
    candidates = _load(CANDIDATES)
    proof = _load(PROOF)
    queue_items = queue["items"]
    rollout_items = rollout["items"]
    candidate_items = candidates["candidates"]
    photo_items = proof["photos"]
    assert isinstance(queue_items, list)
    assert isinstance(rollout_items, list)
    assert isinstance(candidate_items, list)
    assert isinstance(photo_items, list)

    rollout_by_id = {item["publication_id"]: item for item in rollout_items}
    candidate_by_id = {item["publication_id"]: item for item in candidate_items}
    proof_by_media = {item["media_id"]: item for item in photo_items}

    for item in queue_items:
        publication_id = item["publication_id"]
        frozen = rollout_by_id[publication_id]
        candidate = candidate_by_id[publication_id]
        caption = item["caption"]
        assert item["operation"] == frozen["operation"] == candidate["operation"]
        assert caption == candidate["caption"]
        assert item["caption_sha256"] == frozen["caption_sha256"] == _caption_sha(caption)
        assert item["media_id"] == frozen["media_id"] == candidate["media_id"]
        assert item["transport_sha256"] == frozen["transport_sha256"]
        assert item["transport_byte_size"] == frozen["transport_byte_size"]
        if item["operation"] == "sendPhoto":
            media = proof_by_media[item["media_id"]]
            assert media["transport_ready"] is True
            assert item["transport_sha256"] == media["transport_sha256"]
            assert item["transport_byte_size"] == media["transport_byte_size"]
        else:
            assert item["operation"] == "sendMessage"
            assert item["media_id"] is None
            assert item["transport_sha256"] is None
            assert item["transport_byte_size"] is None


def test_queue_rebases_schedule_only_and_never_turns_missed_slots_into_night_catchup() -> None:
    queue = _load(QUEUE)
    rollout = _load(FROZEN_ROLLOUT)
    queue_items = queue["items"]
    frozen_items = rollout["items"]
    assert isinstance(queue_items, list)
    assert isinstance(frozen_items, list)
    assert frozen_items[0]["planned_local"] == "2026-08-16T10:30:00+03:00"
    assert frozen_items[1]["planned_local"] == "2026-08-16T20:00:00+03:00"
    assert queue_items[0]["planned_local"] == "2026-08-17T10:30:00+03:00"
    assert queue_items[1]["planned_local"] == "2026-08-17T20:00:00+03:00"
    assert queue["schedule_rebase"]["content_identity_changed"] is False
    assert queue["rollout_policy"]["missed_slot_catchup_during_quiet_hours"] is False
    assert queue["rollout_policy"]["blind_mutation_retries"] == 0
    assert queue["rollout_policy"]["strict_next_only"] is True
    assert queue["rollout_policy"]["unknown_outcome_blocks_successor"] is True


def test_queue_requires_fresh_release_canary_and_starts_with_no_provider_receipts() -> None:
    queue = _load(QUEUE)
    items = queue["items"]
    assert isinstance(items, list)
    gate = queue["canary_gate"]
    assert gate["fresh_release_canary_required"] is True
    assert gate["required_publication_id"] == "milovi-bootstrap-001"
    assert gate["historical_canary_publication_id"] == "milovi-cake-canary-001"
    assert gate["historical_canary_satisfies_gate"] is False
    assert gate["successor_dispatch_allowed_only_after_verified_receipt"] is True
    assert items[0]["queue_status"] == "awaiting_manual_release_canary"
    assert all(item["queue_status"] == "queued_waiting_for_release_canary" for item in items[1:])
    assert all(item["message_id"] is None for item in items)
    assert all(item["sent_at"] is None for item in items)
    assert all(item["provider_outcome"] is None for item in items)


def test_queue_first_screen_preserves_cake_school_editorial_boundary() -> None:
    queue = _load(QUEUE)
    items = queue["items"]
    assert isinstance(items, list)
    joined = "\n".join(str(item["caption"]) for item in items).casefold()
    assert "milovi school" not in joined
    assert "french.milovicake.ru" not in joined
    assert "француз" not in joined
