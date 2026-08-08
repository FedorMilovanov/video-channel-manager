from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_CONSTRUCTORS = Counter(
    {
        "src/video_channel_manager/platforms/http.py": 1,
        "src/video_channel_manager/telegram_transport.py": 2,
        "src/video_channel_manager/telegram_channel_discovery.py": 1,
        "src/video_channel_manager/telegram_multichannel_transport.py": 3,
        "scripts/complete_vk_longform_tail.py": 1,
        "scripts/lord_god_article_wave_v3/mutations.py": 1,
        "scripts/run_vk_wall_wave.py": 1,
        "scripts/schedule_lord_god_article_wave.py": 1,
        "scripts/schedule_lord_god_article_wave_current.py": 3,
        "scripts/sync_youtube_thumbnails_to_vk.py": 1,
        "scripts/vk_shorts_reset.py": 2,
    }
)


def _qualified_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _qualified_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def test_http_client_constructors_match_reviewed_ownership_inventory() -> None:
    observed: Counter[str] = Counter()
    for search_root in (ROOT / "src", ROOT / "scripts"):
        for path in sorted(search_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _qualified_name(node.func) == "httpx.Client":
                    observed[str(path.relative_to(ROOT)).replace("\\", "/")] += 1

    assert observed == EXPECTED_CONSTRUCTORS
