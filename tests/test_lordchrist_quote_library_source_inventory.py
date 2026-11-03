"""Full research-library coverage without claiming publication rights or approvals."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs/audits/2026-11-03-lordchrist-160-library-source-inventory.json"


def test_all_160_research_cards_have_exact_consistent_evidence() -> None:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    assert index["schema_name"] == "video-channel-manager.lordchrist-quote-library-research-audit"
    assert index["schema_version"] == 1
    assert index["eligible_for_auto_release"] is False
    assert index["primary_source_collation_complete"] is False

    recorded = index["cards"]
    assert len(recorded) == 160
    assert [row["number"] for row in recorded] == list(range(1, 161))
    rebuilt = []
    for file in index["library_files"]:
        contents = (ROOT / "content/telegram/lordchrist" / file).read_text(encoding="utf-8")
        for block in re.split(r"(?=^## \d+\.)", contents, flags=re.MULTILINE)[1:]:
            head = re.match(r"## (\d+)\.\s+([^\r\n]+)", block)
            assert head is not None
            quote = "\n".join(line[2:] for line in block.splitlines() if line.startswith("> "))
            urls = re.findall(r"https?://[^\s)]+", block)
            assert quote and urls
            hostname = (urlparse(urls[0]).hostname or "").lower().removeprefix("www.")
            flags = []
            if hostname.endswith("goodreads.com"):
                flags.append("aggregated_quote_not_primary_source")
            if hostname in {"gty.org", "desiringgod.org"}:
                flags.append("modern_publisher_text_rights_review")
            if len(quote) < 250:
                flags.append("below_250_character_editorial_quality_minimum")
            rebuilt.append(
                {
                    "number": int(head.group(1)),
                    "heading": head.group(2),
                    "library_file": file,
                    "quote_sha256": "sha256:" + hashlib.sha256(quote.encode("utf-8")).hexdigest(),
                    "quote_characters": len(quote),
                    "source_url": urls[0],
                    "source_domain": hostname,
                    "flags": flags,
                    "source_verification": "pending_primary_source_collation",
                    "eligible_for_auto_release": False,
                }
            )

    rebuilt.sort(key=lambda item: item["number"])
    assert recorded == rebuilt
    counts = Counter(flag for row in rebuilt for flag in row["flags"])
    assert counts == {
        "aggregated_quote_not_primary_source": 28,
        "modern_publisher_text_rights_review": 12,
        "below_250_character_editorial_quality_minimum": 1,
    }
