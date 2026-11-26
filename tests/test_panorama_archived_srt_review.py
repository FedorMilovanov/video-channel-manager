"""Provider-inert regression coverage for explicitly reviewed original SRT evidence."""

import copy
import json
import sqlite3

import pytest

from video_channel_manager.platforms.youtube.chapter_release import (
    digest_file,
    render_chapter_appendix,
    require_review,
)
from video_channel_manager.platforms.youtube.copy_plan import canonical_sha256, sha256_text
from video_channel_manager.platforms.youtube.lord_god_scoped import _validated_chapter_appendix
from video_channel_manager.platforms.youtube.lord_god_source_preservation import LORD_GOD_OWNER_CHANNEL


VIDEO = "test-video"
BEFORE = "Русское описание.\nПервоначальный источник."
CUES = [
    ("00:00:00,000", "00:00:04,000", 0, "Введение в послание"),
    ("00:00:10,010", "00:00:14,000", 10010, "Оправдание верою"),
    ("00:00:20,020", "00:00:24,000", 20020, "Свобода во Христе"),
]


def _fixture(tmp_path):
    srt = tmp_path / "source.srt"
    srt.write_bytes(
        ("\ufeff" + "\r\n\r\n".join(
            f"{i}\r\n{start} --> {end}\r\n{text}"
            for i, (start, end, _, text) in enumerate(CUES, 1)
        ) + "\r\n").encode("utf-8")
    )
    chapters = [
        {
            "index": i,
            "second": ms // 1000,
            "stamp": f"00:{ms // 1000:02d}",
            "heading": text,
            "semantic_boundary": "APPROVED",
            "source_cue": text,
            "source_excerpt": text,
            "boundary_evidence": {
                "cue_index": i,
                "start_ms": ms,
                "cue": text,
                "note": "Fixture: exact source boundary",
            },
        }
        for i, (_, _, ms, text) in enumerate(CUES)
    ]
    after = BEFORE + render_chapter_appendix(chapters)
    review = {
        "schema": "lordgod-chapter-editorial-review-v2",
        "owner_channel_id": LORD_GOD_OWNER_CHANNEL,
        "video_id": VIDEO,
        "editorial_approval": "APPROVED",
        "is_executable_plan": False,
        "provider_writes": 0,
        "requires_fresh_youtube_api_preflight": True,
        "recording_player_review_required": True,
        "source_description_sha256": sha256_text(BEFORE),
        "proposed_description_sha256": sha256_text(after),
        "source_transcript_chunks": 3,
        "chapters": chapters,
        "semantic_review": {
            "reviewer": "Synthetic fixture",
            "reviewed_at": "2026-11-26T12:00:00+00:00",
            "basis": "exact_ru_archived_srt_boundaries",
            "recording_video_id": VIDEO,
            "chapters_sha256": canonical_sha256(chapters),
            "description_sha256": sha256_text(after),
            "boundary_count": 3,
            "all_boundaries_reviewed": True,
            "evidence_file": str(srt),
            "evidence_sha256": digest_file(srt),
        },
    }
    db = tmp_path / "source.db"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE transcript_chunks(video_id TEXT, start_ms INTEGER, end_ms INTEGER, text TEXT)")
        connection.executemany(
            "INSERT INTO transcript_chunks VALUES (?, ?, ?, ?)",
            [(VIDEO, 0, 9000, CUES[0][3]), (VIDEO, 10000, 19000, CUES[1][3]), (VIDEO, 20000, 40000, CUES[2][3])],
        )
    return review, after, srt, db


def _save(tmp_path, review):
    path = tmp_path / "review.json"
    path.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
    return path


def test_archived_srt_exact_review_and_archive_agree(tmp_path):
    review, after, _, db = _fixture(tmp_path)
    path = _save(tmp_path, review)
    actual, evidence = _validated_chapter_appendix(
        review, path, db, video_id=VIDEO, before=BEFORE, allow_archived_srt=True
    )
    assert actual == after
    assert evidence["all_cues_verified"]
    assert evidence["reviewed_archive_gap_chapter_ordinals"] == []
    with pytest.raises(ValueError, match="Semantic approval"):
        require_review(review, path, video_id=VIDEO, before=BEFORE, after=after)


@pytest.mark.parametrize("defect", ["index", "timestamp", "text", "partial_text", "json3_locator", "approval", "digest"])
def test_srt_rejects_mismatched_review_even_with_resealed_chapter_digest(tmp_path, defect):
    review, after, srt, _ = _fixture(tmp_path)
    boundary = review["chapters"][1]["boundary_evidence"]
    if defect == "index":
        boundary["cue_index"] = 0
    elif defect == "timestamp":
        boundary["start_ms"] += 1
    elif defect == "text":
        boundary["cue"] = "Другой текст"
    elif defect == "partial_text":
        boundary["cue"] = "Оправдание"
    elif defect == "json3_locator":
        boundary["event_index"] = 1
    elif defect == "approval":
        review["editorial_approval"] = "HOLD"
    elif defect == "digest":
        srt.write_bytes(srt.read_bytes() + b"\n")
    review["semantic_review"]["chapters_sha256"] = canonical_sha256(review["chapters"])
    path = _save(tmp_path, review)
    with pytest.raises(ValueError):
        require_review(review, path, video_id=VIDEO, before=BEFORE, after=after, allow_archived_srt=True)


@pytest.mark.parametrize("defect", ["sequence", "clock", "negative_duration", "fake_json3"])
def test_srt_rejects_malformed_source_even_with_matching_file_digest(tmp_path, defect):
    review, after, srt, _ = _fixture(tmp_path)
    raw = srt.read_bytes()
    if defect == "sequence":
        raw = raw.replace(b"\r\n2\r\n", b"\r\n4\r\n")
    elif defect == "clock":
        raw = raw.replace(b"00:00:10,010", b"00:60:10,010")
    elif defect == "negative_duration":
        raw = raw.replace(b"00:00:14,000", b"00:00:09,000")
    elif defect == "fake_json3":
        raw = b'{"events":[]}'
    srt.write_bytes(raw)
    review["semantic_review"]["evidence_sha256"] = digest_file(srt)
    with pytest.raises(ValueError):
        require_review(
            review, _save(tmp_path, review), video_id=VIDEO, before=BEFORE,
            after=after, allow_archived_srt=True
        )


def test_srt_does_not_authorize_archive_gap_or_different_fragment(tmp_path):
    review, _, _, db = _fixture(tmp_path)
    path = _save(tmp_path, review)
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE transcript_chunks SET start_ms=10011 WHERE start_ms=10000")
    with pytest.raises(ValueError, match="archival transcript cue"):
        _validated_chapter_appendix(
            review, path, db, video_id=VIDEO, before=BEFORE, allow_archived_srt=True
        )
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE transcript_chunks SET start_ms=10000, text='Другой текст' WHERE start_ms=10011")
    with pytest.raises(ValueError, match="archival transcript cue"):
        _validated_chapter_appendix(
            copy.deepcopy(review), path, db, video_id=VIDEO, before=BEFORE, allow_archived_srt=True
        )
