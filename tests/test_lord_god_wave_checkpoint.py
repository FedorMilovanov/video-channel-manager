"""Regression tests for the Lord God local-only checkpoint."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lord_god_wave_checkpoint.py"
SPEC = importlib.util.spec_from_file_location("lord_god_wave_checkpoint", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

A = "a" * 11
B = "b" * 11
C = "c" * 11


def scan() -> dict:
    return {
        "schema": module.SCAN_SCHEMA,
        "owner": module.OWNER,
        "utc": "2026-11-08T13:26:48+00:00",
        "total": 3,
        "accessible": 3,
        "clean_ids": [A],
        "dirty_ids": [B, C],
        "clean_count": 1,
        "dirty_count": 2,
        "remaining_shelf_links": 8,
        "remaining_old_contacts": 1,
        "missing_ids": 0,
        "regressions": 0,
        "unexpected_clean": 0,
    }


def archive() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute(
        "CREATE TABLE videos (video_id TEXT, title TEXT, description TEXT,"
        " view_count INTEGER, transcript_chunks INTEGER, transcript_sha256 TEXT,"
        " published_at TEXT, duration INTEGER, playlist_count INTEGER)"
    )
    db.execute("CREATE TABLE transcript_chunks (video_id TEXT, chunk_index INTEGER, start_ms INTEGER, text TEXT)")
    for video_id, views in [(B, 500), (C, 100)]:
        db.execute(
            "INSERT INTO videos VALUES (?,?,?,?,?,?,?,?,?)",
            (video_id, "Title", "Archive source URL", views, 3, "abc", "2026", 1500, 2),
        )
        for idx in range(3):
            db.execute(
                "INSERT INTO transcript_chunks VALUES (?,?,?,?)", (video_id, idx, idx * 15000, "archived speech")
            )
    return db


def checkpoint(snapshot: dict, hold_ids: set[str]) -> dict:
    with archive() as db:
        return module.build_checkpoint(snapshot, db, hold_ids, limit=25, scan_digest="scan", archive_digest="archive")


def test_separate_clean_dirty_and_hold_without_provider_authority() -> None:
    result = checkpoint(scan(), {C})
    assert result["candidate_count"] == 1
    assert result["candidates"][0]["video_id"] == B
    assert result["hold_ids_excluded"] == [C]
    assert result["provider_get_calls"] == 0
    assert result["provider_writes"] == 0
    assert result["publication_approved"] is False
    assert result["can_generate_signed_plan"] is False
    assert result["candidates"][0]["archive_speech_samples"][1]["at_seconds"] == 15


def test_fail_closed_on_wrong_owner_and_overlapping_ids() -> None:
    snapshot = scan()
    snapshot["owner"] = "wrong"
    with pytest.raises(ValueError, match="owner"):
        checkpoint(snapshot, {C})
    snapshot = scan()
    snapshot["dirty_ids"] = [A, C]
    with pytest.raises(ValueError, match="inconsistent"):
        checkpoint(snapshot, {C})


def test_fail_closed_on_missing_hold_set_or_unreasonable_limit() -> None:
    with archive() as db:
        with pytest.raises(ValueError, match="HOLD"):
            module.build_checkpoint(scan(), db, set(), limit=25, scan_digest="a", archive_digest="b")
        with pytest.raises(ValueError, match="limit"):
            module.build_checkpoint(scan(), db, {C}, limit=51, scan_digest="a", archive_digest="b")


def test_archive_sha_is_raw_not_signed_plan_sha() -> None:
    assert module.raw_sha("A") == "559aead08264d5795d3909718cdd05abd49572e84fe55590eef31a88a08fdffd"
    assert not module.raw_sha("A").startswith("sha256:")


def test_snapshot_requires_full_complete_owner_inventory() -> None:
    snapshot = scan()
    snapshot["missing_ids"] = 1
    with pytest.raises(ValueError, match="inconsistent"):
        checkpoint(snapshot, {C})


def test_real_owner_zero_anomalies_are_empty_arrays() -> None:
    snapshot = scan()
    snapshot["missing_ids"] = []
    snapshot["regressions"] = []
    snapshot["unexpected_clean"] = []
    assert checkpoint(snapshot, {C})["candidate_count"] == 1
