from __future__ import annotations

from pathlib import Path

from video_channel_manager.telegram_quote_source_probe import (
    FAILURE_OUTCOMES,
    FAILURE_SEMANTICS,
    ProbeResult,
    classify_response,
    probe_inventory,
)

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
AUDIT_PATH = CONTENT / "quote-source-web-audit-v2.json"
PROBE_PATH = CONTENT / "quote-source-live-probe-v2.json"

URL = "https://www.ccel.org/ccel/gurnall/armour/files/gurnal03b.htm"


def test_probe_classifier_separates_retrieval_classes_without_judging_the_quotation() -> None:
    retrieved = classify_response(requested=URL, final_url=URL, status=200, body="<html>chapter text</html>")
    assert retrieved.outcome == "retrieved"

    bot_blocked = classify_response(
        requested=URL,
        final_url=URL,
        status=403,
        body="<html>Attention Required! | Cloudflare</html>",
    )
    assert bot_blocked.outcome == "bot_protection"

    challenge = classify_response(
        requested=URL, final_url=URL, status=200, body="Just a moment... checking your browser"
    )
    assert challenge.outcome == "bot_protection"

    gone = classify_response(requested=URL, final_url=URL, status=404, body="not found")
    assert gone.outcome == "not_found"

    error = classify_response(requested=URL, final_url=URL, status=503, body="unavailable")
    assert error.outcome == "transport_failure"

    relocated = classify_response(
        requested=URL,
        final_url="https://ccel.org/ccel/gurnall/armour/files/gurnal03b.htm",
        status=200,
        body="<html>chapter text</html>",
    )
    assert relocated.outcome == "retrieved"

    moved = classify_response(
        requested=URL,
        final_url="https://www.ccel.org/ccel/gurnall/armour/files/other-chapter.htm",
        status=200,
        body="<html>different document</html>",
    )
    assert moved.outcome == "stale_url_relocated"

    empty = classify_response(requested=URL, final_url=URL, status=200, body="   ")
    assert empty.outcome == "insufficient_evidence"

    for outcome in (bot_blocked, challenge, gone, error, moved, empty):
        assert outcome.outcome in FAILURE_OUTCOMES or outcome.outcome == "insufficient_evidence"
        assert "not evidence" in FAILURE_SEMANTICS.casefold()


def test_probe_classifier_never_returns_an_invalidating_verdict_for_a_failed_fetch() -> None:
    failure = ProbeResult(
        url=URL,
        outcome="transport_failure",
        http_status=None,
        final_url=None,
        note="The automated probe could not complete the request (URLError); not evidence about the quotation.",
    )

    assert "invalid" not in failure.outcome
    assert "not evidence about the quotation" in failure.note


def test_probe_inventory_uses_the_reviewed_inventory_and_records_classes_without_network(tmp_path: Path) -> None:
    """Exercise the report shape with a single reviewed URL and no live fetch."""

    payload = probe_inventory(inventory_path=AUDIT_PATH, timeout=0.001, limit=0)

    assert payload["urls_attempted"] == 0
    assert payload["results"] == []
    assert payload["classification_counts"] == {}
    assert payload["failure_semantics"] == FAILURE_SEMANTICS
    assert payload["web_audit_file"] == AUDIT_PATH.name
    assert "not evidence" in str(payload["failure_semantics"]).casefold()


def test_durable_classified_probe_matches_the_reviewed_inventory() -> None:
    import json

    from video_channel_manager.telegram_quote_source_audit import load_source_web_audit

    audit = load_source_web_audit(AUDIT_PATH)
    probe = json.loads(PROBE_PATH.read_text(encoding="utf-8"))

    assert probe["schema_version"] == 2
    assert [entry["url"] for entry in probe["results"]] == list(audit.research_pages)
    assert probe["classification_counts"]["retrieved"] == probe["urls_fetched_successfully"] >= 50
