from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "schedule_lord_god_wall_tail.py"


def load_module():
    spec = importlib.util.spec_from_file_location("schedule_lord_god_wall_tail", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lord_god_wall_tail_policy_is_exact() -> None:
    module = load_module()
    policy = module.load_policy(ROOT)
    module.validate_policy(policy)
    operations = policy["operations"]
    assert len(operations) == 26
    assert len({item["video_id"] for item in operations}) == 26
    assert policy["policy_sha256"] == module.EXPECTED_POLICY_SHA256
    assert operations[0]["publish_at"] == "2026-08-03T09:00:00+03:00"
    assert operations[-1]["publish_at"] == "2026-08-15T19:00:00+03:00"
    assert all(item["mode"] == "postponed" for item in operations)
    for item in operations:
        text = item["message"]
        assert "https://gospod-bog.ru/" in text
        assert "https://t.me/lordchrist" in text
        assert "https://vkvideo.ru/@the_lord_god_is_my_strength" in text
        assert "https://rutube.ru/channel/1876662/" in text
        assert f"https://www.youtube.com/watch?v={item['youtube_id']}" in text
