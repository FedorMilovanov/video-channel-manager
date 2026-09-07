from __future__ import annotations

import json
from pathlib import Path

from video_channel_manager.telegram_research import sha256_json

ROOT = Path(__file__).resolve().parents[1]
POST_DIR = ROOT / "content/telegram/lordchrist/historical-editorial/v1/cycles/2026-09-cycle-02/posts"
POST_FILES = (
    "01-spurgeon-down-grade-1887.json",
    "02-bunyan-bedford-prison.json",
    "03-judson-burmese-bible.json",
    "04-spurgeon-cholera.json",
    "05-carey-enquiry-missions.json",
    "06-fuller-gospel-worthy.json",
    "07-tyndale-new-testament-1526.json",
    "08-stam-china-december-1934.json",
    "09-sattler-schleitheim-1527.json",
)


def test_emit_exact_historical_v2_post_digests() -> None:
    values = {}
    for filename in POST_FILES:
        payload = json.loads((POST_DIR / filename).read_text(encoding="utf-8"))
        values[payload["publication_id"]] = sha256_json(payload)
    raise AssertionError("HISTORICAL_V2_DIGESTS=" + json.dumps(values, sort_keys=True))
