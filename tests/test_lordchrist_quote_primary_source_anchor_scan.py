"""Reconcile one dated, read-only 29-source HTTP scan with the sealed v4 queue."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "docs/audits/2026-11-04-lordchrist-30-source-url-and-anchor-scan.json"
QUEUE = ROOT / "content/telegram/lordchrist/verified-30-posts.json"


def test_30_card_scan_is_identity_bound_and_does_not_approve_sources() -> None:
    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    text = QUEUE.read_text(encoding="utf-8")
    posts = json.loads(text)["posts"]
    assert probe["schema_name"] == "video-channel-manager.lordchrist-primary-source-anchor-scan"
    assert probe["schema_version"] == 1
    assert probe["queue_text_sha256"] == "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert probe["full_translation_verified"] is False
    assert probe["rights_verified"] is False
    assert probe["provider_write_authorization"] is False
    assert len(probe["entries"]) == len(posts) == 30
    for post, row in zip(posts, probe["entries"], strict=True):
        assert post["sequence"] == row["sequence"]
        assert post["publication_id"] == row["id"]
        assert post["source"]["url"] == row["url"]
        assert row["source_payload_sha256"] == ("sha256:" + hashlib.sha256(post["text"].encode("utf-8")).hexdigest())


def test_historical_source_observations_are_recorded_not_certified() -> None:
    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    observations = probe["entries"]
    summary = probe["summary"]
    assert summary["attempted_unique_urls"] == 29
    assert summary["http_200"] == 29
    assert len({row["url"] for row in observations}) == 29
    assert sum(row["start_found"] and row["end_found"] for row in observations) == 26
    assert sum(row["anchor_order"] for row in observations) == 26
    unresolved = [row["sequence"] for row in observations if row["first_pass_flag"] == "unresolved_anchor_locator"]
    suspect = [
        row["sequence"]
        for row in observations
        if row["first_pass_flag"] == "substantial_intervening_source_material_possible"
    ]
    assert unresolved == [22, 27, 28, 29]
    assert suspect == [1, 7, 8, 11, 12, 14, 15, 16, 17, 18, 19, 25, 26]
    assert summary["unresolved"] == unresolved
    assert summary["possible_large_gaps"] == suspect
    assert Counter(row["http_status"] for row in observations) == {200: 30}


def test_four_corrected_source_page_proposals_are_not_editorial_approvals() -> None:
    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    rows = probe["corrected_exact_page_proposals"]
    assert [row["sequence"] for row in rows] == [22, 27, 28, 29]
    assert all(row["editorially_approved"] is False for row in rows)
    assert all(row["http_status"] == 200 for row in rows)
    assert all(not row["start_anchor_found_on_proposed_url"] for row in rows if row["sequence"] == 22)
    assert all(row["start_anchor_found_on_proposed_url"] for row in rows if row["sequence"] in (27, 28, 29))
    assert all(row["end_anchor_found_on_proposed_url"] for row in rows if row["sequence"] in (27, 28, 29))
