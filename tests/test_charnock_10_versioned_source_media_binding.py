"""Versioned #10 recovery identity: independent source, cover and ledger guards.

No Telegram credentials, provider requests or writes occur in these tests.
The protected historical manifest is never altered to make a newer page pass.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from video_channel_manager import lordchrist_charnock_reschedule as m

ROOT = Path(__file__).resolve().parents[1]
PUBLICATION = "lordchrist-telegraph-charnock-10"
OLD_SHA = "sha256:b15e2658d1ed040c3bef62a7be226ed75a19fd0136bfd519ce0e89c42c43c7ae"
REVIEWED_SHA = "sha256:1302f2e9dfbc7660b93f4123fed572540677c5e347e2726508ee1a7f3c1e84e8"
COVER_SHA = "sha256:d2fffe4e5c9f04c64eece0dd7d84d2e52d4907c6acf3b76092edd1895e9071d0"
OLD_MEDIA_REV = "6f67b689f3de6ba811134bb4b49eff0e2fd9fee3"
QC_MEDIA_REV = "c1bafa972e91d536fc56d86e53b4ce6f3502f37d"
TREE_SHA = "56b06597af499958efe515cf41ac9284d6c08e18046825ada34de322f7407db0"


def _due() -> dict:
    manifest = json.loads((ROOT / m.MANIFEST).read_text(encoding="utf-8"))
    return next(x for x in manifest["items"] if x["publication_id"] == PUBLICATION)


def _original_ledger() -> dict:
    source = _due()
    return {
        "entries": {
            PUBLICATION: {
                "state": "published",
                "provider_effect": "verified",
                "telegram_message_id": 1600,
                "telegram_chat_id": -1001295216957,
                "telegraph_url": source["verified_telegraph_url"],
                "article_sha256": OLD_SHA,
                "cover_sha256": COVER_SHA,
                "github_sha": OLD_MEDIA_REV,
            }
        }
    }


def _args() -> SimpleNamespace:
    return SimpleNamespace(
        stage="preview",
        repo_root=ROOT,
        publication_id=PUBLICATION,
    )


def test_pinned_legacy_manifest_and_v2_binding_are_distinct() -> None:
    legacy = _due()
    assert legacy["article_git_blob_sha"] == "1173a305bb192c0aec3606485c5b3664c95e8650"
    assert legacy["source_article_sha256"] == OLD_SHA
    assert m._file_git_blob_sha((ROOT / m.MANIFEST).read_bytes()) == m.LEGACY_MANIFEST_GIT_BLOB
    assert m._file_git_blob_sha((ROOT / m.V2_BINDING).read_bytes()) == m.V2_BINDING_GIT_BLOB


def test_v2_source_media_binding_resolves_only_article_10() -> None:
    original = _due()
    approved = m.approved_reissue_entry(ROOT, original)
    assert original["article_git_blob_sha"] != approved["article_git_blob_sha"]
    assert original["source_article_sha256"] == OLD_SHA
    assert approved["historical_source_article_sha256"] == OLD_SHA
    assert approved["source_article_sha256"] == REVIEWED_SHA
    assert approved["media_base_revision"] == QC_MEDIA_REV
    assert approved["original_github_sha"] == OLD_MEDIA_REV
    assert approved["reviewed_cover_git_blob_sha"] == "c64a4582311e408f5734cdb66a35ee0f929ad5ce"
    assert approved["binding_git_blob_sha"] == m.V2_BINDING_GIT_BLOB

    for ordinal in ("06", "07", "08", "09", "11", "12", "13"):
        legacy = {"publication_id": f"lordchrist-telegraph-charnock-{ordinal}", "source_article_sha256": OLD_SHA}
        assert m.approved_reissue_entry(ROOT, legacy) is legacy


def test_current_queue_and_real_article_render_against_pinned_live_media_base() -> None:
    # Actual production source/cover bytes and the real queue (no mocks).
    ledger = _original_ledger()
    before = copy.deepcopy(ledger)
    entry, item, payload, original = m._select_due(
        _args(), ledger, now=datetime(2026, 11, 24, 12, 5, tzinfo=m.MOSCOW)
    )
    assert original is ledger["entries"][PUBLICATION]
    assert ledger == before
    assert entry["source_article_sha256"] == REVIEWED_SHA
    assert payload.article_sha256 == REVIEWED_SHA
    assert payload.cover_sha256 == COVER_SHA
    assert item.article_blob == entry["article_git_blob_sha"]
    assert payload.cover_url.startswith(
        "https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/" + QC_MEDIA_REV + "/"
    )
    assert len(payload.nodes) == 97
    assert m._normalized_telegraph_digest(payload.nodes, retain_heading_ids=True) == TREE_SHA


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("article_sha256", "sha256:" + "f" * 64),
        ("cover_sha256", "sha256:" + "f" * 64),
        ("github_sha", "f" * 40),
        ("telegram_message_id", 1),
        ("telegraph_url", "https://telegra.ph/Wrong-Page"),
    ],
)
def test_original_ledger_identity_drift_fails_before_provider_side_effect(field: str, wrong: object) -> None:
    ledger = _original_ledger()
    ledger["entries"][PUBLICATION][field] = wrong
    before = copy.deepcopy(ledger)
    with pytest.raises(RuntimeError):
        m._select_due(_args(), ledger, now=datetime(2026, 11, 24, 12, 5, tzinfo=m.MOSCOW))
    assert ledger == before
    assert "scheduled_reissue" not in ledger["entries"][PUBLICATION]


def test_unauthorized_binding_bytes_fail_closed(tmp_path: Path) -> None:
    old = tmp_path / m.MANIFEST
    v2 = tmp_path / m.V2_BINDING
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_bytes((ROOT / m.MANIFEST).read_bytes())
    v2.write_bytes((ROOT / m.V2_BINDING).read_bytes() + b" ")
    with pytest.raises(RuntimeError, match="Unapproved Charnock v2"):
        m.approved_reissue_entry(tmp_path, _due())


def test_unmodified_legacy_manifest_sha_is_required(tmp_path: Path) -> None:
    old = tmp_path / m.MANIFEST
    v2 = tmp_path / m.V2_BINDING
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_bytes((ROOT / m.MANIFEST).read_bytes() + b" ")
    v2.write_bytes((ROOT / m.V2_BINDING).read_bytes())
    with pytest.raises(RuntimeError, match="Historical Charnock release authority"):
        m.approved_reissue_entry(tmp_path, _due())


def test_versioned_receipt_must_pin_new_target_and_binding() -> None:
    entry = m.approved_reissue_entry(ROOT, _due())
    ledger = _original_ledger()
    assert m.scheduled_reissue_preflight_status(ledger, entry) == "unclaimed"
    original = ledger["entries"][PUBLICATION]
    original["scheduled_reissue"] = {
        "state": "verified",
        "provider_effect": "verified",
        "new_message_id": 1800,
        "scheduled_on_moscow": entry["scheduled_on_moscow"],
        "original_deleted_message_id": 1600,
        "source_article_sha256": REVIEWED_SHA,
        "telegraph_url": entry["verified_telegraph_url"],
        "binding_git_blob_sha": m.V2_BINDING_GIT_BLOB,
    }
    assert m.scheduled_reissue_preflight_status(ledger, entry) == "verified"
    original["scheduled_reissue"]["binding_git_blob_sha"] = "f" * 40
    with pytest.raises(RuntimeError, match="reconcile without resend"):
        m.scheduled_reissue_preflight_status(ledger, entry)


def test_workflow_checks_v2_binding_before_redundant_schedule() -> None:
    flow = (
        ROOT / ".github/workflows/lordchrist-charnock-scheduled-reissue.yml"
    ).read_text(encoding="utf-8")
    assert "approved=approved_reissue_entry(Path(\".\"),matches[0])" in flow
    assert "scheduled_reissue_preflight_status(state,approved)" in flow
    assert "APPROVED_MANIFEST_SHA256" in flow
    assert "github.event_name == 'schedule'" in flow
