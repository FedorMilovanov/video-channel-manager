from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.telegram_quote_content_findings import (
    CONTENT_FINDINGS_FILENAME,
    assert_findings_match_pending_suffix,
    load_pending_content_findings,
)
from video_channel_manager.telegram_quote_depth import build_depth_runtime_queue
from video_channel_manager.telegram_quote_quality_v4 import semantic_blocks
from video_channel_manager.telegram_quote_standalone_review import quotation_sha256

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"


def _queue():
    return build_depth_runtime_queue(
        candidate_path=CONTENT / "successor-quotes-v1.json",
        translation_ledger_path=CONTENT / "successor-translation-ledger-v1.json",
        integrity_amendment_path=CONTENT / "successor-integrity-amendments-v1.json",
        audit_path=CONTENT / "quote-depth-audit-v1.json",
        replacements_path=CONTENT / "quote-depth-replacements-v1.json",
    )


def test_pending_content_findings_are_bound_to_the_sealed_suffix() -> None:
    findings = load_pending_content_findings(CONTENT / CONTENT_FINDINGS_FILENAME)
    queue = _queue()

    summary = assert_findings_match_pending_suffix(findings, queue.posts)

    assert summary == {"verified_findings": len(findings.entries), "pending_suffix": 45}
    assert findings.queue_digest == queue.digest
    for entry in findings.entries:
        assert 16 <= entry.sequence <= 60
        assert "durable-depth-v2-ledger-binding" in entry.requires_reseal_of


def test_pending_content_findings_reject_a_sealed_quotation_that_was_silently_edited() -> None:
    findings = load_pending_content_findings(CONTENT / CONTENT_FINDINGS_FILENAME)
    queue = _queue()
    posts = list(queue.posts)
    entry = findings.entries[0]
    target = next(post for post in posts if post.publication_id == entry.publication_id)
    quote, attribution, context, hashtags = semantic_blocks(target)
    edited = target.model_copy(update={"text": "\n\n".join([quote + " Дописано.", attribution, context, hashtags])})

    with pytest.raises(ValueError, match="sealed pending quotation changed under a recorded finding"):
        assert_findings_match_pending_suffix(
            findings, (*posts[: target.sequence - 1], edited, *posts[target.sequence :])
        )  # type: ignore[arg-type]


def test_pending_content_findings_reject_a_proposed_correction_equal_to_the_sealed_text() -> None:
    payload = json.loads((CONTENT / CONTENT_FINDINGS_FILENAME).read_text(encoding="utf-8"))
    payload["entries"][0]["quotation_sha256"] = quotation_sha256(payload["entries"][0]["proposed_quotation_ru"])
    path = CONTENT / "quote-pending-content-findings-invalid.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="must differ from the sealed reviewed quotation"):
            load_pending_content_findings(path)
    finally:
        path.unlink(missing_ok=True)
