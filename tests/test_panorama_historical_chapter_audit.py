"""Synthetic tests for offline historical schema normalization; no provider calls."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from scripts.audit_panorama_chapter_evidence import audit, parse_stamp
from video_channel_manager.platforms.youtube.lord_god_source_preservation import LORD_GOD_OWNER_CHANNEL


@pytest.mark.parametrize(
    ("stamp", "seconds"),
    [("00:00", 0), ("04:00", 240), ("60:00", 3600), ("1:01:05", 3665), ("100:00", 6000)],
)
def test_legacy_and_native_stamp_parse(stamp: str, seconds: int) -> None:
    assert parse_stamp(stamp) == seconds


@pytest.mark.parametrize("stamp", ["1:60", "1:60:00", "1:00:60", "-1:00", "no time"])
def test_invalid_clock_component_refused(stamp: str) -> None:
    with pytest.raises(ValueError):
        parse_stamp(stamp)


def _json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def test_all_schema_audit_preserves_sources_and_separates_historical_from_approval(tmp_path: Path) -> None:
    ids = [f"video{i:06d}" for i in range(68)]
    src = [f"https://www.slovo.org/example/{i}" for i in range(68)]
    playlist = _json(
        tmp_path / "playlist.json",
        {
            "memberships": [
                {"video_id": v, "position": i, "video_owner": LORD_GOD_OWNER_CHANNEL} for i, v in enumerate(ids)
            ]
        },
    )
    sources = _json(
        tmp_path / "sources.json",
        {"items": [{"number": i + 1, "url": url, "ok": True} for i, url in enumerate(src)]},
    )
    archive = tmp_path / "archive.db"
    with closing(sqlite3.connect(archive)) as db, db:
        db.execute("CREATE TABLE transcript_chunks (video_id TEXT, start_ms INT, end_ms INT)")
        db.executemany(
            "INSERT INTO transcript_chunks VALUES (?, ?, ?)",
            [(video, t, t + 30000) for video in ids[:2] for t in (0, 240000, 3600000)],
        )
    for i, video in enumerate(ids[:2]):
        captions = _json(
            tmp_path / f"{video}.ru-orig.json3",
            {"events": [{"tStartMs": t, "segs": [{"utf8": "synthetic"}]} for t in (0, 240000, 3600000)]},
        )
        digest = hashlib.sha256(captions.read_bytes()).hexdigest()
        if i == 0:
            rows = [
                {"time": s, "title": "heading", "nearest_caption_ms": t, "nearest_archive_ms": t}
                for s, t in [("00:00", 0), ("04:00", 240000), ("60:00", 3600000)]
            ]
            evidence = {"original": src[i], "caption_sha256": digest, "chapters": rows}
        else:
            rows = [
                {"timestamp": s, "label": "heading", "caption_timestamp_ms": t, "nearest_archived_ms": t}
                for s, t in [("00:00", 0), ("04:00", 240000), ("1:00:00", 3600000)]
            ]
            evidence = {"source_original": src[i], "captions_sha256": digest, "chapters": rows}
        _json(tmp_path / f"{video}-evidence.json", {"video_id": video, "duration_ms": 3660000, **evidence})
    result = audit(tmp_path, playlist, sources, archive)
    assert result["videos"] == 2
    assert result["chapter_count"] == 6
    assert result["legacy_stamp_count"] == 1
    assert result["four_minute_grid_count_excluding_zero"] == 4
    assert result["caption_sha256_matches"] == result["source_url_matches"] == 2
    assert result["caption_anchors_missing"] == result["archive_anchors_missing"] == 0
    assert result["provider_reads"] == result["provider_writes"] == 0
    assert result["semantic_approval"] is result["is_executable_plan"] is False
    # Changing actual caption bytes does not get silently treated as evidence proof.
    captions = tmp_path / f"{ids[0]}.ru-orig.json3"
    captions.write_text(captions.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert audit(tmp_path, playlist, sources, archive)["caption_sha256_matches"] == 1
