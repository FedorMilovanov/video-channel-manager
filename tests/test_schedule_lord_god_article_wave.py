from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "content" / "policies" / "lord-god-article-wave-202608.json"
CURRENT = ROOT / "scripts" / "schedule_lord_god_article_wave_current.py"
EXPECTED_SHA = "sha256:b3467af4911d5faa2550b2c2f0e53ce051b0365651e82abfc57cae8a68a66f5a"
MOSCOW = timezone(timedelta(hours=3))


def canonical_sha(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def message_sha(value: object) -> str:
    return f"sha256:{hashlib.sha256(str(value).strip().encode()).hexdigest()}"


def test_article_wave_policy_is_exact_and_project_scoped() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    digest = canonical_sha({key: value for key, value in policy.items() if key != "policy_sha256"})

    assert policy["schema_version"] == 2
    assert policy["policy_sha256"] == digest == EXPECTED_SHA
    assert policy["project_key"] == "lord-god-strength"
    assert policy["vk_community_id"] == 60805374
    assert policy["vk_owner_id"] == -60805374
    assert policy["source_repository"] == "FedorMilovanov/gb-is-my-strength"
    assert policy["source_manifest_blob_sha"] == "952cfbd8b276fc7e877a784660fb4481dc8bd83f"
    assert policy["attachment_mode"] == "external-link-card-via-wall.parseAttachedLink"
    assert policy["minimum_gap_minutes"] == 120


def test_article_wave_has_ten_daily_image_cards_at_fourteen() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    operations = policy["operations"]

    assert len(operations) == 10
    assert len({item["url"] for item in operations}) == 10
    assert len({item["publish_date"] for item in operations}) == 10
    assert operations[0]["id"] == "rimlyanam-7"
    assert operations[3]["id"] == "nagornaya-ch1"
    assert operations[-1]["id"] == "enoh-audit"

    for ordinal, operation in enumerate(operations, start=1):
        publish_at = datetime.fromisoformat(operation["publish_at"]).astimezone(MOSCOW)
        assert operation["ordinal"] == ordinal
        assert publish_at.hour == 14 and publish_at.minute == 0
        assert operation["url"].startswith("https://gospod-bog.ru/")
        assert operation["og_image"].startswith("https://gospod-bog.ru/")
        assert operation["og_image"].endswith(".webp")
        assert operation["url"] in operation["message"]
        assert "💬" in operation["message"]
        assert 400 <= len(operation["message"]) <= 1000
        assert operation["message_sha256"] == message_sha(operation["message"])


def test_current_entrypoint_applies_only_reviewed_live_corrections() -> None:
    source = CURRENT.read_text(encoding="utf-8")

    assert "lord-god-article-wave-202608-05-hermenevtika" in source
    assert "og-hermenevtika-hristotsentrichnaya-otsenka.webp" in source
    assert "lord-god-article-wave-202608-06-diotrefy" in source
    assert "lord-god-article-wave-202608-06-krajne-isporcheno" in source
    assert "https://gospod-bog.ru/articles/krajne-li-isporcheno-serdce/" in source
    assert "https://gospod-bog.ru/images/og-krajne-isporcheno.webp" in source
    assert '"ordinal": 6' in source
    assert '"publish_date": 1786186800' in source
    assert "module.EXPECTED_SHA = policy[\"policy_sha256\"]" in source


def test_current_entrypoint_accepts_only_usable_vk_link_parse_shapes() -> None:
    source = CURRENT.read_text(encoding="utf-8")

    assert "install_vk_link_parse_compatibility" in source
    assert "module.parsed_photo_tokens(attachments, link)" in source
    assert 'parse_mode = "photo_tokens_plus_external_url"' in source
    assert '"attachment_type": "link" if link else "photo+external-link"' in source
    assert 'attachment_parts = [*photo_tokens, normalized]' in source
    assert "wall.parseAttachedLink returned no usable image attachment" in source
    assert "module.parse_attached_link = parse_attached_link" in source
