from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from video_channel_manager.wave_engine.article_prepare import (
    ARTICLE_POLICY_VERSION,
    load_approved_policy,
)
from video_channel_manager.wave_engine.vk_article_provider import (
    VK_ARTICLE_COMMUNITY_ID,
    VK_ARTICLE_OWNER_ID,
    VK_ARTICLE_PROJECT_KEY,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "data" / "editorial" / "legendary-poet-article-wave-202608.json"


def test_approved_legendary_poet_article_policy_is_digest_locked() -> None:
    policy = load_approved_policy(POLICY)
    assert policy["project_key"] == VK_ARTICLE_PROJECT_KEY
    assert policy["vk_community_id"] == VK_ARTICLE_COMMUNITY_ID
    assert policy["vk_owner_id"] == VK_ARTICLE_OWNER_ID
    assert policy["source_repository_commit"] == "85c4303dc683abc6e201ea707a0b4d6f5f19f82c"
    assert policy["policy_sha256"] == (
        "sha256:af210867d2ea392394e2034cffa9d43c3e1adc632386e9ec4827b033c8fff9a0"
    )
    assert ARTICLE_POLICY_VERSION == "legendary-poet-article-photo-wave-202608-v1"


def test_approved_policy_contains_exact_ten_post_schedule_and_messages() -> None:
    policy = load_approved_policy(POLICY)
    operations = policy["operations"]
    assert len(operations) == 10
    assert [item["ordinal"] for item in operations] == list(range(1, 11))
    assert len({item["operation_id"] for item in operations}) == 10
    assert len({item["guid"] for item in operations}) == 10

    previous: int | None = None
    for operation in operations:
        publish_at = datetime.fromisoformat(operation["publish_at"])
        assert publish_at.hour == 19
        assert publish_at.minute == 0
        assert publish_at.utcoffset() is not None
        assert publish_at.utcoffset().total_seconds() == 3 * 3600
        assert int(publish_at.timestamp()) == operation["publish_date"]
        if previous is not None:
            assert operation["publish_date"] - previous == 2 * 86_400
        previous = operation["publish_date"]

        message = operation["message"]
        expected_message_sha = "sha256:" + hashlib.sha256(message.encode("utf-8")).hexdigest()
        assert operation["message_sha256"] == expected_message_sha
        assert message.count(operation["url"]) == 1
        assert operation["url"].startswith("https://thelegendarypoet.ru/essays/")


def test_policy_json_round_trips_without_ascii_escaping() -> None:
    raw = POLICY.read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert "Лермонтов" in raw
    assert payload["operations"][0]["message"].startswith("🌌")
