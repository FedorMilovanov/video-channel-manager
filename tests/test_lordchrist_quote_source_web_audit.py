from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import pytest

from video_channel_manager.telegram_quote_source_audit import (
    assert_future_exact_source_coverage,
    load_source_web_audit,
)

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
AUDIT_PATH = CONTENT / "quote-source-web-audit-v2.json"
PROBE_PATH = CONTENT / "quote-source-live-probe-v2.json"
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
    assert audit.research_pages_reviewed >= 99
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
    assert probe["urls_attempted"] == audit.research_pages_reviewed == 99
    assert probe["urls_fetched_successfully"] >= 50
    assert probe["urls_fetched_successfully"] + probe["fetch_failures"] == probe["urls_attempted"]
    assert "not evidence" in probe["failure_semantics"].casefold()

    results = probe["results"]
    assert len(results) == probe["urls_attempted"]
    assert [entry["url"] for entry in results] == list(audit.research_pages)
    outcomes = [entry["outcome"] for entry in results]
    assert set(outcomes).issubset(
        {
            "retrieved",
            "transport_failure",
            "bot_protection",
            "stale_url_relocated",
            "not_found",
            "insufficient_evidence",
        }
    )
    counts = {outcome: outcomes.count(outcome) for outcome in set(outcomes)}
    assert probe["classification_counts"] == counts
    assert counts["retrieved"] == probe["urls_fetched_successfully"]
    assert probe["fetch_failures"] == probe["urls_attempted"] - counts["retrieved"]
    for entry in results:
        if entry["outcome"] != "retrieved":
            assert "not evidence" in entry["note"].casefold() or "layer" in entry["note"].casefold()


def test_live_probe_resolution_for_the_reverified_exact_source_card_is_recorded() -> None:
    """One automated-sweep failure was re-verified live; the class must say so."""

    audit = load_source_web_audit(AUDIT_PATH)
    probe = json.loads(PROBE_PATH.read_text(encoding="utf-8"))
    by_url = {entry["url"]: entry for entry in probe["results"]}

    tgc = "https://www.thegospelcoalition.org/article/the-ground-of-all-human-assurance-before-god/"
    assert tgc in audit.research_pages
    entry = by_url[tgc]
    assert entry["outcome"] == "retrieved"
    assert entry["observed_on"] == "2026-10-04"
    assert "exact reviewed sentence" in entry["note"]


def test_web_audit_records_only_reviewed_canonical_equivalent_forms() -> None:
    audit = load_source_web_audit(AUDIT_PATH)

    assert audit.canonical_equivalents, "the reviewed inventory must document its canonical aliases"
    for equivalent in audit.canonical_equivalents:
        assert equivalent.url in audit.research_pages
        assert equivalent.canonical_url in audit.research_pages
        assert len(equivalent.note) >= 40

    gty = "https://www.gty.org/articles/A326/what-doctrines-are-fundamental-part-1"
    print_form = "https://www.gty.org/articles/print/A326/what-doctrines-are-fundamental-part-1"
    equivalent = next(entry for entry in audit.canonical_equivalents if entry.url == gty)
    assert equivalent.canonical_url == print_form
    assert equivalent.kind == "official_print_or_view_endpoint"


def test_canonical_equivalence_is_required_before_a_non_inventory_form_can_cover_a_card() -> None:
    """Coverage only ever resolves through the explicit reviewed equivalence map."""

    from video_channel_manager.telegram_quote_source_audit import assert_future_exact_source_coverage

    audit = load_source_web_audit(AUDIT_PATH)
    cited = "https://www.gty.org/articles/A326/what-doctrines-are-fundamental-part-1"
    assert cited in audit.research_pages
    pruned = audit.model_copy(update={"research_pages": tuple(page for page in audit.research_pages if page != cited)})
    coverage_args = {
        "candidate_path": CONTENT / "successor-quotes-v1.json",
        "translation_ledger_path": CONTENT / "successor-translation-ledger-v1.json",
        "integrity_amendment_path": CONTENT / "successor-integrity-amendments-v1.json",
        "depth_audit_path": CONTENT / "quote-depth-audit-v1.json",
        "replacements_path": CONTENT / "quote-depth-replacements-v1.json",
    }

    # The explicitly reviewed official print/view endpoint of the same document covers the card.
    covered = assert_future_exact_source_coverage(pruned, **coverage_args)
    assert covered[46] == cited

    # Without that recorded equivalence the same citation is uncovered: a
    # thematically related page on the same host is never verification.
    without_equivalents = pruned.model_copy(update={"canonical_equivalents": ()})
    with pytest.raises(ValueError, match="missing exact source URLs"):
        assert_future_exact_source_coverage(without_equivalents, **coverage_args)


def test_reviewed_source_coverage_maps_every_pending_sequence_to_a_reviewed_form() -> None:
    from video_channel_manager.telegram_quote_source_audit import reviewed_source_coverage

    audit = load_source_web_audit(AUDIT_PATH)
    coverage = reviewed_source_coverage(
        audit,
        candidate_path=CONTENT / "successor-quotes-v1.json",
        translation_ledger_path=CONTENT / "successor-translation-ledger-v1.json",
        integrity_amendment_path=CONTENT / "successor-integrity-amendments-v1.json",
        depth_audit_path=CONTENT / "quote-depth-audit-v1.json",
        replacements_path=CONTENT / "quote-depth-replacements-v1.json",
    )

    assert tuple(coverage) == tuple(range(16, 61))
    for cited, reviewed in coverage.values():
        assert cited in audit.research_pages
        assert reviewed in audit.research_pages
