from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_CONSTRUCTORS = Counter(
    {
        "src/video_channel_manager/cli/instagram_production.py": 1,
        "src/video_channel_manager/instagram/production.py": 2,
        "src/video_channel_manager/platforms/http.py": 1,
        "src/video_channel_manager/platforms/vk/milovi_gap_thumbnail_evidence.py": 1,
        "src/video_channel_manager/telegram_transport.py": 2,
        "src/video_channel_manager/telegram_channel_discovery.py": 1,
        "src/video_channel_manager/telegram_custom_emoji_harvest.py": 1,
        "src/video_channel_manager/telegram_historical_media.py": 1,
        "src/video_channel_manager/telegram_multichannel_transport.py": 4,
        "src/video_channel_manager/telegram_multichannel_video.py": 1,
        "src/video_channel_manager/telegram_research_public_permalink_probe.py": 1,
        "src/video_channel_manager/telegram_research_update_probe.py": 1,
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


OWNERSHIP_DOC = ROOT / "docs" / "operations" / "http-client-ownership.md"
DOC_ROW = re.compile(r"^\|\s*`(?P<path>[^`]+\.py)`\s*\|\s*(?P<count>\d+)\s*\|(?P<reason>.*)\|\s*$", re.MULTILINE)


def _observed_constructors() -> Counter[str]:
    observed: Counter[str] = Counter()
    for search_root in (ROOT / "src", ROOT / "scripts"):
        for path in sorted(search_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _qualified_name(node.func) == "httpx.Client":
                    observed[str(path.relative_to(ROOT)).replace("\\", "/")] += 1
    return observed


def test_documented_constructor_inventory_matches_the_enforced_allowlist() -> None:
    """The document and the allowlist must describe the same constructors.

    Before this test, `http-client-ownership.md` claimed `src/` had no constructor outside
    `platforms/http.py` while the allowlist silently permitted 16 more in 11 modules. A rule
    that the enforcement does not implement, and that the code contradicts, is not a rule.
    """

    documented: dict[str, int] = {}
    reasons: dict[str, str] = {}
    for match in DOC_ROW.finditer(OWNERSHIP_DOC.read_text(encoding="utf-8")):
        path = match.group("path")
        assert path not in documented, f"{path} is documented twice"
        documented[path] = int(match.group("count"))
        reasons[path] = match.group("reason").strip()

    assert documented, "the ownership document must record the constructors"
    assert documented == dict(EXPECTED_CONSTRUCTORS), {
        "documented_only": sorted(set(documented) - set(EXPECTED_CONSTRUCTORS)),
        "allowed_only": sorted(set(EXPECTED_CONSTRUCTORS) - set(documented)),
        "count_mismatch": {
            path: (documented.get(path), EXPECTED_CONSTRUCTORS.get(path))
            for path in set(documented) & set(EXPECTED_CONSTRUCTORS)
            if documented[path] != EXPECTED_CONSTRUCTORS[path]
        },
    }
    assert documented == dict(_observed_constructors())

    for path, reason in reasons.items():
        assert reason, f"{path} has no reviewed lifecycle note"

    total = sum(documented.values())
    text = OWNERSHIP_DOC.read_text(encoding="utf-8")
    assert f"{total} reviewed constructors" in text, total


def test_ownership_document_does_not_claim_an_unenforced_rule() -> None:
    text = OWNERSHIP_DOC.read_text(encoding="utf-8")

    assert "No direct `httpx.Client()` constructor may appear in reusable `src/` code outside" not in text
    assert (
        "A direct `httpx.Client()` constructor may appear only in a file listed in one of the inventory tables" in text
    )


def test_http_client_constructors_match_reviewed_ownership_inventory() -> None:
    observed: Counter[str] = Counter()
    for search_root in (ROOT / "src", ROOT / "scripts"):
        for path in sorted(search_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _qualified_name(node.func) == "httpx.Client":
                    observed[str(path.relative_to(ROOT)).replace("\\", "/")] += 1

    assert observed == EXPECTED_CONSTRUCTORS
