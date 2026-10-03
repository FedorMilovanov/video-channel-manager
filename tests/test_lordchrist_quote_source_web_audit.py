from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from video_channel_manager.telegram_quote_source_audit import (
    assert_future_exact_source_coverage,
    load_source_web_audit,
)

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
AUDIT_PATH = CONTENT / "quote-source-web-audit-v2.json"
PROBE_PATH = CONTENT / "quote-source-live-probe-v1.json"
EXPECTED_QUEUE_DIGEST = "sha256:c2ad28bb96e88a9e0633c4b7a55d6033bbf29c5a557e1aa4478cc2e0359e3441"


def _family(host: str | None) -> str | None:
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
    return None


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
    assert audit.research_pages_reviewed >= 98
    assert len(audit.research_pages) == audit.research_pages_reviewed
    assert len(set(audit.research_pages)) == audit.research_pages_reviewed


def test_source_web_audit_retains_all_reviewed_primary_and_official_source_families() -> None:
    audit = load_source_web_audit(AUDIT_PATH)
    families = {family for url in audit.research_pages if (family := _family(urlparse(url).hostname)) is not None}

    assert families == {"ccel.org", "newadvent.org", "spurgeon.org", "ligonier.org", "gty.org"}


def test_every_pending_card_exact_source_url_is_present_in_fresh_web_audit() -> None:
    audit = load_source_web_audit(AUDIT_PATH)
    exact_sources = assert_future_exact_source_coverage(
        audit,
        candidate_path=CONTENT / "successor-quotes-v1.json",
        translation_ledger_path=CONTENT / "successor-translation-ledger-v1.json",
        integrity_amendment_path=CONTENT / "successor-integrity-amendments-v1.json",
        depth_audit_path=CONTENT / "quote-depth-audit-v1.json",
        replacements_path=CONTENT / "quote-depth-replacements-v1.json",
    )

    assert tuple(exact_sources) == tuple(range(16, 61))
    assert set(exact_sources.values()).issubset(set(audit.research_pages))


def test_live_probe_records_real_fetch_results_without_misclassifying_retrieval_failures() -> None:
    audit = load_source_web_audit(AUDIT_PATH)
    probe = json.loads(PROBE_PATH.read_text(encoding="utf-8"))

    assert probe["release_id"] == audit.release_id
    assert probe["queue_digest"] == audit.queue_digest
    assert probe["urls_attempted"] == audit.research_pages_reviewed == 98
    assert probe["urls_fetched_successfully"] == 77
    assert probe["fetch_failures"] == 21
    assert probe["urls_fetched_successfully"] + probe["fetch_failures"] == probe["urls_attempted"]
    assert len(probe["failed_urls"]) == probe["fetch_failures"]
    assert len(set(probe["failed_urls"])) == probe["fetch_failures"]
    assert set(probe["failed_urls"]).issubset(set(audit.research_pages))
    assert "not evidence" in probe["failure_semantics"].casefold()
