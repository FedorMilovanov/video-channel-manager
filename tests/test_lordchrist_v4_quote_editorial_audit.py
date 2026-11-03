"""Track every live quote against the exact editorial audit identity.

This is NOT a release gate, review approval, or provider authorization. A changed
source payload must invalidate the old findings instead of silently inheriting them.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs/audits/2026-11-03-lordchrist-v4-quote-editorial-register.json"


def _read() -> tuple[dict[str, object], dict[str, object]]:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    queue = json.loads((ROOT / str(audit["queue_path"])).read_text(encoding="utf-8"))
    return audit, queue


def test_audit_covers_every_exact_live_quote_and_text_hash() -> None:
    audit, queue = _read()
    path = ROOT / str(audit["queue_path"])
    expected_sha = "sha256:" + hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    assert audit["schema_name"] == "video-channel-manager.lordchrist-v4-quote-editorial-review"
    assert audit["schema_version"] == 1
    assert audit["queue_text_sha256"] == expected_sha

    posts = queue["posts"]
    entries = audit["entries"]
    assert len(posts) == len(entries) == 30
    for post, entry in zip(posts, entries, strict=True):
        assert post["sequence"] == entry["sequence"]
        assert post["publication_id"] == entry["publication_id"]
        assert post["source"]["author"] == entry["author"]
        assert post["source"]["work"] == entry["source_work"]
        assert post["source"]["url"] == entry["source_url"]
        assert entry["source_text_sha256"] == "sha256:" + hashlib.sha256(post["text"].encode("utf-8")).hexdigest()
        assert entry["source_collation"] == "pending_full_source_collation"


def test_audit_static_findings_match_bytes_and_are_not_approvals() -> None:
    audit, queue = _read()
    assert audit["full_text_verification_complete"] is False
    assert audit["provider_write_authorization"] is False
    assert audit["editorial_review_status"] == "blocked_pending_full_collation"

    flags = Counter()
    risk = Counter()
    for post, entry in zip(queue["posts"], audit["entries"], strict=True):
        text = post["text"]
        current = []
        if "\u2026" in text:
            current.append("quoted_ellipsis")
        if text.startswith("\u00ab\u00ab"):
            current.append("double_guillemet")
        if text.count("\u00ab") != text.count("\u00bb"):
            current.append("guillemet_mismatch")
        assert entry["static_flags"] == current
        flags.update(current)
        risk.update([entry["preliminary_risk"]])
        assert entry["finding"]
    assert flags == {"quoted_ellipsis": 8, "double_guillemet": 2, "guillemet_mismatch": 1}
    assert risk == {"critical": 10, "major": 8, "review": 2, "screened": 10}


def test_source_selection_policy_was_not_silently_waived() -> None:
    audit, queue = _read()
    assert (
        audit["queue_digest"]
        == json.loads(
            (ROOT / "content/telegram/lordchrist/quote-v4-runtime-activation.json").read_text(encoding="utf-8")
        )["queue_digest"]
    )
    assert {post["source"]["selection_policy"] for post in queue["posts"]} == {"contiguous_complete_no_omissions"}
    # Deliberately leave the source-text inconsistency visible for editorial
    # release review; this register does not edit any sealed publication.
    flagged = [entry["sequence"] for entry in audit["entries"] if "quoted_ellipsis" in entry["static_flags"]]
    assert flagged == [5, 7, 8, 11, 12, 13, 14, 27]
