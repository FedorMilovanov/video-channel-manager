from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.svodka_queue import SvodkaDraftQueue, load_svodka_draft

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"
OVERLAY_PATH = REPOSITORY_ROOT / "content/telegram/svodka/rollout-schedule-2026-08.json"


def test_rollout_overlay_preserves_all_14_items_and_reviewed_content() -> None:
    raw = SvodkaDraftQueue.model_validate(json.loads(QUEUE_PATH.read_text(encoding="utf-8")))
    effective = load_svodka_draft(QUEUE_PATH)

    assert OVERLAY_PATH.exists()
    assert len(raw.posts) == 14
    assert len(effective.posts) == 14
    assert raw.pilot.start_date.isoformat() == "2026-08-09"
    assert raw.pilot.end_date.isoformat() == "2026-08-15"
    assert effective.pilot.start_date.isoformat() == "2026-08-10"
    assert effective.pilot.end_date.isoformat() == "2026-08-16"

    raw_by_id = {post.publication_id: post for post in raw.posts}
    effective_by_id = {post.publication_id: post for post in effective.posts}
    assert set(effective_by_id) == set(raw_by_id)
    for publication_id, raw_post in raw_by_id.items():
        effective_post = effective_by_id[publication_id]
        assert raw_post.html_text == effective_post.html_text
        assert raw_post.sources == effective_post.sources
        assert raw_post.title == effective_post.title
        assert raw_post.format == effective_post.format


def test_time_sensitive_eclipse_moves_ahead_of_evergreen_octopus_item() -> None:
    effective = load_svodka_draft(QUEUE_PATH)
    ids = [post.publication_id for post in effective.posts]

    assert ids[4:6] == [
        "svodka-2026-august-total-solar-eclipse",
        "svodka-octopus-three-hearts-blue-blood",
    ]
    assert effective.posts[4].scheduled_at.isoformat() == "2026-08-12T10:30:00+03:00"
    assert effective.posts[5].scheduled_at.isoformat() == "2026-08-12T19:30:00+03:00"
    assert [post.sequence for post in effective.posts] == list(range(1, 15))


def test_rollout_overlay_is_bound_to_expected_base_window(tmp_path: Path) -> None:
    queue_path = tmp_path / QUEUE_PATH.name
    queue_payload = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    queue_payload["pilot"]["start_date"] = "2026-08-08"
    queue_path.write_text(json.dumps(queue_payload, ensure_ascii=False), encoding="utf-8")
    (tmp_path / OVERLAY_PATH.name).write_text(OVERLAY_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ValueError, match="base window differs"):
        load_svodka_draft(queue_path)


def test_rollout_overlay_rejects_missing_or_duplicate_publication_ids(tmp_path: Path) -> None:
    queue_path = tmp_path / QUEUE_PATH.name
    queue_path.write_text(QUEUE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    overlay = json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))
    overlay["effective_publication_order"][-1] = overlay["effective_publication_order"][0]
    (tmp_path / OVERLAY_PATH.name).write_text(json.dumps(overlay, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="must not contain duplicates"):
        load_svodka_draft(queue_path)


def test_effective_rollout_keeps_two_exact_moscow_slots_per_day() -> None:
    effective = load_svodka_draft(QUEUE_PATH)
    slots_by_day: dict[str, list[str]] = {}
    for post in effective.posts:
        local = post.scheduled_at
        day = local.date().isoformat()
        slots_by_day.setdefault(day, []).append(local.strftime("%H:%M"))

    assert list(slots_by_day) == [
        "2026-08-10",
        "2026-08-11",
        "2026-08-12",
        "2026-08-13",
        "2026-08-14",
        "2026-08-15",
        "2026-08-16",
    ]
    assert all(slots == ["10:30", "19:30"] for slots in slots_by_day.values())
