"""Proof of historical Charnock release authority: never auto-approve drift.

This is a read-only check of committed, immutable incident evidence. A later
approved, versioned release MUST have separate authority; do not rewrite the
historical manifest or make current QC content masquerade as 2026-11-05 bytes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "content/telegram/lordchrist/telegraph-v1/charnock/charnock-reschedule-2026.json"
QUEUE = ROOT / "content/telegram/lordchrist/telegraph-v1/article-queue.json"
ARTICLE_DIR = ROOT / "content/telegram/lordchrist/telegraph-v1/charnock"
HISTORICAL_MANIFEST_GIT_BLOB = "9bbacf42933da605ca8f47a4708d23dd18971a8b"
HISTORICAL = {
    "10": ("2026-11-24", "1173a305bb192c0aec3606485c5b3664c95e8650"),
    "11": ("2026-11-27", "cd64ba6071f08591e5959949cc73b877d4401e70"),
    "12": ("2026-12-01", "095de9e09ccfcb99e389ea92fc40e350fa374f02"),
    "13": ("2026-12-04", "cc9b20e98cb88c14b7c3ec739a4c07c4f738cae9"),
}


def _blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _by_publication(items: list[dict], publication_id: str) -> dict:
    hits = [x for x in items if x.get("publication_id") == publication_id]
    assert len(hits) == 1
    return hits[0]


def test_old_approved_incident_manifest_is_unchanged() -> None:
    raw = MANIFEST.read_bytes()
    assert _blob(raw) == HISTORICAL_MANIFEST_GIT_BLOB
    data = json.loads(raw)
    assert data["timezone"] == "Europe/Moscow"
    assert data["release_time"] == "12:00"
    assert len(data["items"]) == 8


@pytest.mark.parametrize("ordinal", sorted(HISTORICAL))
def test_historical_authority_does_not_silently_bind_current_qc_article(ordinal: str) -> None:
    """A fixed old approval + revised source MUST fail closed pending new authority."""
    historical = json.loads(MANIFEST.read_text(encoding="utf-8"))
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    pub = f"lordchrist-telegraph-charnock-{ordinal}"
    reviewed_date, approved_old_sha = HISTORICAL[ordinal]
    original = _by_publication(historical["items"], pub)
    current = _by_publication(queue["items"], pub)
    assert original["scheduled_on_moscow"] == reviewed_date
    assert current["scheduled_on_moscow"] == reviewed_date
    assert original["article_git_blob_sha"] == approved_old_sha
    assert current["article"]["git_blob_sha"] != approved_old_sha

    article_path = ROOT / current["article"]["path"]
    assert article_path.parent == ARTICLE_DIR
    actual_current_blob = _blob(article_path.read_bytes())
    assert current["article"]["git_blob_sha"] == actual_current_blob
    assert original["verified_telegraph_url"].startswith("https://telegra.ph/")
    # This discrepancy is NOT a license to mutate the old manifest to the QC hash.
    # A new versioned approval must bind source, media, provider identity and ledger.


def test_charnock_13_is_explicitly_held_by_the_current_sender() -> None:
    script = (ROOT / "src/video_channel_manager/lordchrist_charnock_reschedule.py").read_text(encoding="utf-8")
    assert 'CHARNOCK_EDITORIAL_HOLDS = frozenset({"lordchrist-telegraph-charnock-13"})' in script
    assert 'args.stage in ("prepare", "send")' in script
    assert "TELEGRAM SEND HOLD" in script
