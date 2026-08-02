from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "content" / "policies" / "lord-god-article-wave-202608.json"
EXPECTED_SHA = "sha256:458b716dad898f7a692da7204259b43c42b1803387e9ea5ca855d456f044b85b"
MOSCOW = timezone(timedelta(hours=3))


def canonical_sha(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def test_article_wave_policy_is_exact_and_project_scoped() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    digest = canonical_sha({key: value for key, value in policy.items() if key != "policy_sha256"})

    assert policy["policy_sha256"] == digest == EXPECTED_SHA
    assert policy["project_key"] == "lord-god-strength"
    assert policy["vk_community_id"] == 60805374
    assert policy["vk_owner_id"] == -60805374
    assert policy["source_repository"] == "FedorMilovanov/gb-is-my-strength"
    assert policy["attachment_mode"] == "external-link-card"


def test_article_wave_has_ten_daily_image_cards_at_fourteen() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    operations = policy["operations"]

    assert len(operations) == 10
    assert len({item["url"] for item in operations}) == 10
    assert len({item["publish_date"] for item in operations}) == 10

    for ordinal, operation in enumerate(operations, start=1):
        publish_at = datetime.fromisoformat(operation["publish_at"]).astimezone(MOSCOW)
        assert operation["ordinal"] == ordinal
        assert publish_at.hour == 14 and publish_at.minute == 0
        assert operation["url"].startswith("https://gospod-bog.ru/")
        assert operation["og_image"].startswith("https://gospod-bog.ru/")
        assert operation["og_image"].endswith(".webp")
        assert operation["url"] in operation["message"]
        assert 300 <= len(operation["message"]) <= 1200
