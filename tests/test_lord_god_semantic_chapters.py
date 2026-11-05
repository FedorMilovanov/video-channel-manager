"""Fail-closed tests for exact reviewed Lord God transcript-grounded chapter plans."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from video_channel_manager.platforms.youtube.copy_plan import (
    finalize_copy_plan,
    sha256_text,
    validate_copy_plan,
)
from video_channel_manager.platforms.youtube.lord_god_scoped import (
    LORD_GOD_CHANNEL,
    build_one_video_chapter_plan,
)

VID = "npqnKxVt44Q"
MISSING = [f"missing{i:02d}" for i in range(6)]
SOURCE_BEFORE = "Коломийцев — изучение Библии.\nПрежняя навигация.\n"
PUBLISHED_AFTER = (
    "Алексей Коломийцев — грамматический анализ Библии.\n\nПолный курс: https://www.youtube.com/playlist?list=PLowner\n"
)
CHUNKS = [
    (0, 90_000, "Вступительное слово и введение к лекции"),
    (120_000, 200_000, "Грамматический анализ и контекст текста"),
    (3_660_000, 3_760_000, "Пример анализа слов в 1 Коринфянам"),
    (3_900_000, 4_020_000, "Завершение занятия и молитва"),
]


def _sha_bytes(path: Path) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(tmp_path: Path) -> tuple[dict, Path, dict, Path, dict, Path, Path]:
    audit = {
        "schema_name": "video-manager.audit-package",
        "snapshot_id": "owner-snapshot",
        "channel": {"ref": {"remote_id": LORD_GOD_CHANNEL}},
        "videos": [
            {
                "ref": {"remote_id": VID, "channel_id": LORD_GOD_CHANNEL},
                "title": "Коломийцев — грамматический анализ",
                "description": SOURCE_BEFORE,
                "revision": "sha256:original-revision",
                "privacy_status": "public",
            }
        ],
        "metadata": {
            "uploads_playlist_inventory": {
                "complete": False,
                "unique_upload_count": 7,
                "materialized_video_count": 1,
                "missing_metadata_count": 6,
                "missing_metadata_ids": list(MISSING),
                "pagination_integrity": {
                    "validation_passes": 2,
                    "unique_id_set_reconciled": True,
                },
            }
        },
        "findings": [
            {
                "severity": "error",
                "rule_id": "youtube.owner-upload-metadata-gap",
                "details": {"video_id": item},
            }
            for item in MISSING
        ],
    }
    audit_file = tmp_path / "audit.json"
    audit_file.write_text(json.dumps(audit), encoding="utf-8")
    previous = {
        "ruleset": "lord-god-manual-edit-v1",
        "source_audit_sha256": _sha_bytes(audit_file),
        "source_audit_snapshot_id": "owner-snapshot",
        "target_channel_id": LORD_GOD_CHANNEL,
        "project_key": "lord-god-strength",
        "link_profile": "lord-god-strength",
        "videos_checked": 7,
        "operations_count": 1,
        "blocked_operations_count": 6,
        "unresolved_error_videos": 6,
        "operations": [
            {
                "operation": "replace_video_description",
                "platform": "youtube",
                "ruleset": "lord-god-manual-edit-v1",
                "channel_id": LORD_GOD_CHANNEL,
                "video_id": VID,
                "title": "Коломийцев — грамматический анализ",
                "expected_revision": "sha256:original-revision",
                "before_description": SOURCE_BEFORE,
                "after_description": PUBLISHED_AFTER,
                "before_sha256": sha256_text(SOURCE_BEFORE),
                "after_sha256": sha256_text(PUBLISHED_AFTER),
                "fixes": [{"code": "reviewed_edit", "count": 1}],
            }
        ],
        "unresolved": [
            {
                "video_id": item,
                "channel_id": LORD_GOD_CHANNEL,
                "errors": [{"code": "youtube.owner-upload-metadata-gap"}],
            }
            for item in MISSING
        ],
    }
    finalize_copy_plan(previous, checked_video_ids=[VID, *MISSING])
    previous_file = tmp_path / "previous.json"
    previous_file.write_text(json.dumps(previous), encoding="utf-8")
    entries = [
        {
            "index": 0,
            "second": 0,
            "stamp": "00:00",
            "heading": "Введение и начало изучения",
            "cue": "Вступительное",
            "source_excerpt": CHUNKS[0][2][:24],
        },
        {
            "index": 1,
            "second": 120,
            "stamp": "02:00",
            "heading": "Грамматический анализ и контекст",
            "cue": "Грамматический",
            "source_excerpt": CHUNKS[1][2][:24],
        },
        {
            "index": 2,
            "second": 3660,
            "stamp": "1:01:00",
            "heading": "Пример анализа библейского отрывка",
            "cue": "Коринфянам",
            "source_excerpt": CHUNKS[2][2][:24],
        },
    ]
    suffix = "\n\nТаймкоды:\n" + "\n".join(x["stamp"] + " " + x["heading"] for x in entries)
    review = {
        "schema": "lordgod-chapter-editorial-review-v1",
        "video_id": VID,
        "owner_channel_id": LORD_GOD_CHANNEL,
        "source_description_sha256": sha256_text(PUBLISHED_AFTER),
        "proposed_description_sha256": sha256_text(PUBLISHED_AFTER + suffix),
        "source_transcript_chunks": 4,
        "chapters": entries,
        "is_executable_plan": False,
        "requires_fresh_youtube_api_preflight": True,
        "recording_player_review_required": True,
        "provider_writes": 0,
    }
    review_file = tmp_path / "review.json"
    review_file.write_text(json.dumps(review), encoding="utf-8")
    db = tmp_path / "transcripts.db"
    with closing(sqlite3.connect(db)) as c:
        c.execute("CREATE TABLE transcript_chunks (video_id TEXT, start_ms INT, end_ms INT, text TEXT)")
        c.executemany("INSERT INTO transcript_chunks VALUES (?, ?, ?, ?)", [(VID, *row) for row in CHUNKS])
        c.commit()
    return audit, audit_file, previous, previous_file, review, review_file, db


def build(tmp_path: Path, mutate=None):
    audit, audit_file, previous, previous_file, review, review_file, db = fixture(tmp_path)
    if mutate:
        mutate(audit, previous, review)
        previous["plan_sha256"] = "outdated"  # normalized by finalize below
        finalize_copy_plan(previous, checked_video_ids=previous["checked_video_ids"])
        previous_file.write_text(json.dumps(previous), encoding="utf-8")
    return build_one_video_chapter_plan(
        audit, audit_file, previous, previous_file, review, review_file, db, video_id=VID
    )


def test_signed_chapter_plan_is_append_only_and_preserves_missing_ids(tmp_path: Path) -> None:
    plan, report = build(tmp_path)
    validate_copy_plan(plan)
    assert len(plan["operations"]) == 1
    assert len(plan["unresolved"]) == 6
    assert plan["checked_video_ids"] == sorted([VID, *MISSING])
    assert plan["operations"][0]["before_description"] == PUBLISHED_AFTER
    assert plan["operations"][0]["after_description"].startswith(PUBLISHED_AFTER + "\n\nТаймкоды:\n")
    assert plan["operations"][0]["after_description"].count("\n1:01:00 ") == 1
    assert plan["chapter_evidence"]["all_cues_verified"] is True
    assert plan["chapter_evidence"]["player_ui_visual_check_pending"] is True
    assert "fresh live preflight" in report


@pytest.mark.parametrize(
    "mutator, message",
    [
        (lambda a, p, r: a["channel"]["ref"].update(remote_id="wrong"), "Wrong authenticated"),
        (lambda a, p, r: a["videos"][0].update(privacy_status="private"), "public owner"),
        (lambda a, p, r: p.update(project_key="other-site"), "exact owner source"),
        (lambda a, p, r: p.update(source_audit_sha256="sha256:bad"), "exact owner source"),
        (lambda a, p, r: p["unresolved"][0].update(video_id="other"), "absent from checked_video_ids"),
        (lambda a, p, r: r.update(owner_channel_id="not-this-channel"), "exact-owner review"),
        (lambda a, p, r: r.update(is_executable_plan=True), "non-executable"),
        (lambda a, p, r: r.update(requires_fresh_youtube_api_preflight=False), "non-executable"),
        (lambda a, p, r: r.update(source_description_sha256="sha256:outdated"), "previously published"),
        (lambda a, p, r: r.update(source_transcript_chunks=3), "coverage or chunk count"),
        (lambda a, p, r: r["chapters"][1].update(cue="not in this text"), "archival transcript cue"),
        (
            lambda a, p, r: r["chapters"][1].update(source_excerpt="a fake transcript snippet"),
            "archival transcript cue",
        ),
        (lambda a, p, r: r["chapters"][1].update(second=121), "archival transcript cue"),
        (lambda a, p, r: r["chapters"][2].update(stamp="61:00"), "absolute seconds"),
        (lambda a, p, r: r["chapters"][1].update(heading="bad\nnew line"), "chapter metadata"),
        (lambda a, p, r: r["chapters"][2].update(index=50), "chapter metadata"),
        (lambda a, p, r: r["chapters"][2].update(second=125), "archival transcript cue"),
        (lambda a, p, r: r.update(proposed_description_sha256="sha256:bad"), "final description hash"),
        (lambda a, p, r: r.update(chapters=r["chapters"][:2]), "three and forty"),
    ],
)
def test_wrong_source_or_chapter_fails_closed(tmp_path: Path, mutator, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        build(tmp_path, mutator)


def test_missing_transcript_is_blocked(tmp_path: Path) -> None:
    audit, audit_file, previous, previous_file, review, review_file, db = fixture(tmp_path)
    db.unlink()
    with pytest.raises(ValueError, match="database is missing"):
        build_one_video_chapter_plan(audit, audit_file, previous, previous_file, review, review_file, db, video_id=VID)
