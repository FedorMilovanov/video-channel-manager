"""Provider-inert Milovi Cake Shorts source inventory regression tests."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "docs/audits/2026-11-05-milovi-cake-shorts-public-index.json"

PROTECTED_ISSUE_323 = {
    "d48QLgOuiTs",
    "Oix9s6l9vNg",
    "uA8SbnXzJJc",
    "u-PuqjWuhKk",
    "L6XG2_zzrPU",
    "pCARxxaVjTw",
    "OWV-KGsLdA8",
    "o1WXIMupuws",
    "1_SuzeQD_1g",
    "5B9OuXbdGKc",
    "BAVKrQQ00XI",
    "R0KjJvbxS8s",
}


def _read() -> dict:
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def test_public_shorts_index_binds_exact_project_and_source_provenance() -> None:
    index = _read()
    source = index["source_ids_in_public_order"]
    assert index["schema_name"] == "video-manager.milovi-cake-youtube-shorts-public-index"
    assert index["schema_version"] == 1
    assert index["project_key"] == "milovi-cake"
    assert index["youtube_channel_id"] == "UCMDnxfGZiBqcDzgUV1zjFpw"
    assert index["vk_community_id"] == 68859909
    assert index["vk_owner_id"] == -68859909
    assert index["snapshot"]["kind"] == "public_youtube_shorts_playlist_listing"
    assert index["snapshot"]["captured_date"] == "2026-11-05"
    assert re.fullmatch(r"sha256:[a-f0-9]{64}", index["snapshot"]["sha256"])
    assert index["snapshot"]["confirmed_all_ids_in_historical_owner_audit"] is True
    assert len(source) == index["totals"]["public_short_ids"] == 135
    assert len(set(source)) == len(source)
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{11}", value) for value in source)


def test_protected_historical_migration_cannot_become_new_upload_queue() -> None:
    index = _read()
    source = set(index["source_ids_in_public_order"])
    protected = set(index["protected_historical_2026_08_source_ids"])
    assert protected == PROTECTED_ISSUE_323
    assert protected <= source
    assert len(protected) == index["totals"]["protected_historical_ids"] == 12


def test_inventory_cannot_be_misread_as_permission_or_absence_proof() -> None:
    index = _read()
    target = index["target_reconciliation"]
    assert target["current_vk_inventory"] == "unavailable"
    assert target["current_absence_proof"] == "none"
    assert target["source_status_default"] == "vk_presence_unverified"
    assert target["claim_of_vk_missing_sources"] is False
    assert index["totals"]["confirmed_missing_from_vk"] == 0
    assert index["publication"] == {
        "execution_authorized": False,
        "ready_to_publish": False,
        "scheduled_count": 0,
    }
    assert "upload_operations" not in index
    assert "wall_operations" not in index
    assert "execute" not in index
