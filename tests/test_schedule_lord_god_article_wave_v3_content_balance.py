from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "content" / "policies" / "lord-god-article-wave-v3-202608.json"


def test_final_article_selection_is_balanced_and_public() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    operations = policy["operations"]

    assert [item["id"] for item in operations[-3:]] == [
        "gill-part1",
        "nagornaya-ch2",
        "nagornaya-ch3",
    ]
    assert [item["url"] for item in operations[-2:]] == [
        "https://gospod-bog.ru/nagornaya/chast-2/",
        "https://gospod-bog.ru/nagornaya/chast-3/",
    ]
    assert [item["image_url"] for item in operations[-2:]] == [
        "https://gospod-bog.ru/images/og-nagornaya-propoved-chast-2.webp",
        "https://gospod-bog.ru/images/og-nagornaya-propoved-chast-3.webp",
    ]
    assert [item["source_path"] for item in operations[-2:]] == [
        "src/components/nagornaya/chast-2/NagornayaChast2MainShell.astro",
        "src/components/nagornaya/chast-3/NagornayaChast3MainShell.astro",
    ]
    assert sum("gill" in item["id"] for item in operations) == 2
    assert sum(item["id"].startswith("nagornaya-") for item in operations) == 3
    assert all("dzhon-gill-chast-2" not in item["url"] for item in operations)
    assert all("dzhon-gill-chast-3" not in item["url"] for item in operations)
