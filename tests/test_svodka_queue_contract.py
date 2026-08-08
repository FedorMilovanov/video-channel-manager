from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from video_channel_manager.svodka_queue import SvodkaDraftQueue

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"


def _payload() -> dict[str, Any]:
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))


def test_equivalent_utc_timestamp_is_validated_in_moscow_schedule() -> None:
    payload = _payload()
    first = payload["posts"][0]
    first["scheduled_at"] = "2026-08-09T07:30:00+00:00"

    queue = SvodkaDraftQueue.model_validate(payload)

    assert queue.posts[0].scheduled_at.isoformat() == "2026-08-09T07:30:00+00:00"


def test_post_outside_configured_daily_slots_is_rejected() -> None:
    payload = _payload()
    first = payload["posts"][0]
    first["scheduled_at"] = "2026-08-09T11:00:00+03:00"

    with pytest.raises(ValueError, match="outside configured pilot daily_slots"):
        SvodkaDraftQueue.model_validate(payload)


def test_duplicate_daily_slots_are_rejected() -> None:
    payload = _payload()
    pilot = payload["pilot"]
    pilot["daily_slots"] = ["10:30", "10:30"]

    with pytest.raises(ValueError, match="daily_slots must be unique"):
        SvodkaDraftQueue.model_validate(payload)


def test_two_posts_cannot_share_the_same_publication_timestamp() -> None:
    payload = _payload()
    posts = payload["posts"]
    posts[1]["scheduled_at"] = posts[0]["scheduled_at"]

    with pytest.raises(ValueError, match="strictly ordered by scheduled_at"):
        SvodkaDraftQueue.model_validate(payload)


def test_publication_timestamp_must_use_exact_minute_boundary() -> None:
    payload = _payload()
    first = payload["posts"][0]
    first["scheduled_at"] = "2026-08-09T10:30:01+03:00"

    with pytest.raises(ValueError, match="exact minute boundary"):
        SvodkaDraftQueue.model_validate(payload)


def test_quiz_options_are_unique_after_case_and_whitespace_normalization() -> None:
    payload = _payload()
    quiz_post = payload["posts"][6]
    quiz_post["quiz"]["options"] = [
        "Канал молнии",
        " канал МОЛНИИ ",
        "Кипящая вода",
    ]

    with pytest.raises(ValueError, match="quiz options must be unique"):
        SvodkaDraftQueue.model_validate(payload)


def test_structured_source_must_match_visible_source_url() -> None:
    payload = deepcopy(_payload())
    first = payload["posts"][0]
    first["sources"][0]["url"] = "https://science.nasa.gov/jupiter/jupiter-facts/"

    with pytest.raises(ValueError, match="visible source URL differs from structured source"):
        SvodkaDraftQueue.model_validate(payload)


def test_posts_must_remain_in_schedule_order() -> None:
    payload = _payload()
    posts = payload["posts"]
    first_time = posts[0]["scheduled_at"]
    second_time = posts[1]["scheduled_at"]
    posts[0]["scheduled_at"] = second_time
    posts[1]["scheduled_at"] = first_time

    with pytest.raises(ValueError, match="strictly ordered by scheduled_at"):
        SvodkaDraftQueue.model_validate(payload)
