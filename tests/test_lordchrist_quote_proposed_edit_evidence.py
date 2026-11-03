"""Never accept stale editorial patch proposals or mistake them for a publication."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "docs/audits/2026-11-03-lordchrist-quote-exact-editorial-proposals.json"
QUEUE = ROOT / "content/telegram/lordchrist/verified-30-posts.json"


def test_every_exact_proposed_edit_matches_sealed_source_without_authorizing_release() -> None:
    payload = json.loads(PROPOSALS.read_text(encoding="utf-8"))
    queue_raw = QUEUE.read_text(encoding="utf-8")
    queue = json.loads(queue_raw)
    assert payload["schema_name"] == "video-channel-manager.lordchrist-quote-proposed-source-edits"
    assert payload["schema_version"] == 1
    assert payload["approval"] is False
    assert payload["is_new_release"] is False
    assert payload["provider_write_authorization"] is False
    assert payload["bound_queue_text_sha256"] == "sha256:" + hashlib.sha256(queue_raw.encode("utf-8")).hexdigest()

    edits = payload["edits"]
    assert len(edits) == 13
    assert {edit["sequence"] for edit in edits} == {4, 5, 10, 12, 15, 18, 21, 22, 27, 28, 29}
    for edit in edits:
        post = queue["posts"][edit["sequence"] - 1]
        assert edit["publication_id"] == post["publication_id"]
        assert edit["source_url"] == post["source"]["url"]
        value = post
        for segment in edit["field"].split("."):
            value = value[segment]
        assert value.count(edit["exact_before"]) == 1
        assert edit["exact_before"] != edit["proposed_after"]
        assert edit["status"] == "proposed_only_requires_full_source_review"
