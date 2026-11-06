from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import milovi_school_reading_due as school
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_state import load_ledger

ROOT = Path(__file__).resolve().parents[1]
FEED = Path("content/telegram/milovi-cake/feed")


def _create_legacy_pending_fixture(tmp_path: Path) -> Path:
    school.initialize_all(tmp_path)
    ip = tmp_path / FEED / "index.json"
    idx = json.loads(ip.read_text(encoding="utf-8"))
    for pub, (old_digest, old_candidate, old_payload) in school.RICH_EDITORIAL_PREDECESSORS.items():
        lp = tmp_path / FEED / f"{pub}.json"
        old = json.loads(lp.read_text(encoding="utf-8"))
        old["release_digest"] = old_digest
        old["entries"][pub]["provider_payload_sha256"] = old_payload
        lp.write_text(json.dumps(old, ensure_ascii=False) + "\n", encoding="utf-8")
        idx["entries"][pub]["release_candidate_sha256"] = old_candidate
        idx["entries"][pub]["provider_payload_sha256"] = old_payload
    ip.write_text(json.dumps(idx, ensure_ascii=False) + "\n", encoding="utf-8")
    return ip


def test_two_exact_old_pending_ledgers_migrate_to_rich_photo_without_provider(tmp_path: Path) -> None:
    ip = _create_legacy_pending_fixture(tmp_path)
    # The Nov 17 historical pending entry is not replaced.
    paris_before = json.loads((tmp_path / FEED / "milovi-feed-20261117-002.json").read_text(encoding="utf-8"))
    school.initialize_all(tmp_path)
    idx = json.loads(ip.read_text(encoding="utf-8"))
    for pub in school.RICH_EDITORIAL_PREDECESSORS:
        release = load_release(ROOT / "content/telegram/milovi-cake/releases" / f"{pub}-runtime.json")
        ledger = load_ledger(tmp_path / FEED / f"{pub}.json", release)
        e = ledger.entries[pub]
        assert e.state == "pending" and e.provider_effect == "impossible"
        assert e.message_id is None and e.intent_id is None
        assert idx["entries"][pub]["release_candidate_sha256"] == release.candidate_digest()
        assert idx["entries"][pub]["provider_payload_sha256"] == release.items[0].payload.provider_payload_sha256
    assert json.loads((tmp_path / FEED / "milovi-feed-20261117-002.json").read_text(encoding="utf-8")) == paris_before
    after = {p: (tmp_path / FEED / f"{p}.json").read_bytes() for p in school.RICH_EDITORIAL_PREDECESSORS}
    after_idx = ip.read_bytes()
    school.initialize_all(tmp_path)
    assert ip.read_bytes() == after_idx
    assert all((tmp_path / FEED / f"{p}.json").read_bytes() == content for p, content in after.items())


def test_legacy_pending_revision_refuses_unknown_effect_without_half_migration(tmp_path: Path) -> None:
    ip = _create_legacy_pending_fixture(tmp_path)
    pub = "milovi-feed-20261125-001"
    ledger_path = tmp_path / FEED / f"{pub}.json"
    value = json.loads(ledger_path.read_text(encoding="utf-8"))
    value["entries"][pub]["provider_effect"] = "confirmed_absent"
    ledger_path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")
    before_idx = ip.read_bytes()
    before_21 = (tmp_path / FEED / "milovi-feed-20261121-002.json").read_bytes()
    with pytest.raises(ValueError, match="cannot rewrite"):
        school.initialize_all(tmp_path)
    assert ip.read_bytes() == before_idx
    assert (tmp_path / FEED / "milovi-feed-20261121-002.json").read_bytes() == before_21


def test_legacy_revision_refuses_candidate_identity_drift(tmp_path: Path) -> None:
    ip = _create_legacy_pending_fixture(tmp_path)
    idx = json.loads(ip.read_text(encoding="utf-8"))
    idx["entries"]["milovi-feed-20261121-002"]["release_candidate_sha256"] = "sha256:" + "0" * 64
    ip.write_text(json.dumps(idx, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not pinned"):
        school.initialize_all(tmp_path)
