from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from video_channel_manager.telegram_quote_source_audit import load_source_web_audit

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
AUDIT_PATH = CONTENT / "quote-source-web-audit-v2.json"
EXPECTED_QUEUE_DIGEST = "sha256:c2ad28bb96e88a9e0633c4b7a55d6033bbf29c5a557e1aa4478cc2e0359e3441"


def _family(host: str | None) -> str:
    if host in {"ccel.org", "www.ccel.org"}:
        return "ccel.org"
    if host in {"newadvent.org", "www.newadvent.org"}:
        return "newadvent.org"
    if host in {"spurgeon.org", "www.spurgeon.org"}:
        return "spurgeon.org"
    if host in {"ligonier.org", "www.ligonier.org", "learn.ligonier.org"}:
        return "ligonier.org"
    if host in {"gty.org", "www.gty.org"}:
        return "gty.org"
    raise AssertionError(f"unexpected audit host: {host}")


def test_source_web_audit_is_exactly_bound_to_pending_depth_v2_suffix() -> None:
    audit = load_source_web_audit(AUDIT_PATH)

    assert audit.release_id == "lordchrist-successor-depth-v2"
    assert audit.queue_digest == EXPECTED_QUEUE_DIGEST
    assert audit.published_boundary == 15
    assert audit.future_sequences_reviewed == tuple(range(16, 61))
    assert len(audit.future_sequences_reviewed) == 45


def test_source_web_audit_exceeds_requested_50_page_floor_with_unique_pages() -> None:
    audit = load_source_web_audit(AUDIT_PATH)

    assert audit.minimum_research_pages == 50
    assert audit.research_pages_reviewed == 70
    assert len(audit.research_pages) == 70
    assert len(set(audit.research_pages)) == 70


def test_source_web_audit_retains_all_reviewed_primary_and_official_source_families() -> None:
    audit = load_source_web_audit(AUDIT_PATH)
    families = {_family(urlparse(url).hostname) for url in audit.research_pages}

    assert families == {"ccel.org", "newadvent.org", "spurgeon.org", "ligonier.org", "gty.org"}
