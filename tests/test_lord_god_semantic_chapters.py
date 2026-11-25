"""Fail-closed tests for exact reviewed Lord God transcript-grounded chapter plans."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from video_channel_manager.platforms.youtube.copy_plan import (
    canonical_sha256,
    finalize_copy_plan,
    sha256_text,
    validate_copy_plan,
)
from video_channel_manager.platforms.youtube.chapter_release import (
    require_chapter_release,
    RETIRED_PLAN_SHA256,
    RETIRED_EFFECTS,
)
from video_channel_manager.platforms.youtube.lord_god_scoped import (
    LORD_GOD_CHANNEL,
    build_one_video_chapter_plan,
    build_panorama_owner_chapter_plan,
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
    events = []
    for i, entry in enumerate(entries):
        start = entry["second"] * 1000
        events.append({"tStartMs": start, "segs": [{"utf8": CHUNKS[i][2]}]})
        entry["semantic_boundary"] = "APPROVED"
        entry["boundary_evidence"] = {
            "start_ms": start,
            "event_index": i,
            "cue": entry["cue"],
            "note": "Synthetic test fixture: verified topic start",
        }
    captions = tmp_path / "synthetic-ru.json3"
    captions.write_text(json.dumps({"events": events}), encoding="utf-8")
    suffix = "\n\nТаймкоды:\n" + "\n".join(x["stamp"] + " " + x["heading"] for x in entries)
    review = {
        "schema": "lordgod-chapter-editorial-review-v2",
        "editorial_approval": "APPROVED",
        "semantic_review": {
            "reviewer": "test-fixture (not real approval)",
            "reviewed_at": "2026-11-24T00:00:00+00:00",
            "basis": "exact_ru_caption_boundaries",
            "recording_video_id": VID,
            "evidence_file": captions.name,
            "evidence_sha256": _sha_bytes(captions),
            "chapters_sha256": canonical_sha256(entries),
            "description_sha256": sha256_text(PUBLISHED_AFTER + suffix),
            "boundary_count": len(entries),
            "all_boundaries_reviewed": True,
        },
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
        review_file.write_text(json.dumps(review), encoding="utf-8")
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
    require_chapter_release(plan, execute=True, confirm_review_sha256=plan["source_chapter_review_sha256"])


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
        (lambda a, p, r: r.update(editorial_approval="HOLD"), "not approved"),
        (lambda a, p, r: r.update(schema="lordgod-chapter-editorial-review-v1"), "non-executable"),
        (lambda a, p, r: r["semantic_review"].update(all_boundaries_reviewed=False), "incomplete"),
        (lambda a, p, r: r["semantic_review"].update(reviewed_at="2026-11-24T00:00:00"), "offset-aware"),
        (lambda a, p, r: r["semantic_review"].update(chapters_sha256="sha256:bad"), "incomplete"),
        (lambda a, p, r: r["semantic_review"].update(evidence_file="missing.json3"), "missing or changed"),
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


def test_execution_needs_exact_independent_review_hash(tmp_path: Path) -> None:
    plan, _ = build(tmp_path)
    with pytest.raises(ValueError, match="confirm-chapter-review-sha256"):
        require_chapter_release(plan, execute=True)
    require_chapter_release(plan, execute=False)
    review = Path(plan["source_chapter_review"])
    review.write_text(review.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="missing or changed"):
        require_chapter_release(plan, execute=True, confirm_review_sha256=plan["source_chapter_review_sha256"])


def test_generic_plan_cannot_bypass_new_chapter_gate(tmp_path: Path) -> None:
    plan, _ = build(tmp_path)
    plan["ruleset"] = plan["operations"][0]["ruleset"] = "generic-copy"
    finalize_copy_plan(plan, checked_video_ids=plan["checked_video_ids"])
    with pytest.raises(ValueError, match="semantic chapter ruleset"):
        require_chapter_release(plan, execute=True)


@pytest.mark.parametrize("digest", sorted(RETIRED_PLAN_SHA256))
def test_retired_plan_digest_is_execution_only_block(digest: str) -> None:
    plan = {"target_channel_id": LORD_GOD_CHANNEL, "plan_sha256": digest, "operations": []}
    require_chapter_release(plan, execute=False)
    with pytest.raises(ValueError, match="SUPERSEDED_DO_NOT_REPLAY"):
        require_chapter_release(plan, execute=True)


def test_retired_effect_registry_contains_all_four_exact_targets() -> None:
    assert set(RETIRED_EFFECTS) == {"FgXzTeSj3ro", "LsaLPgYqBlM", "rkz_7hE4F9E", "tSexgfSCgT8"}


def test_caption_event_cue_and_timestamp_must_match(tmp_path: Path) -> None:
    audit, audit_file, previous, previous_file, review, review_file, db = fixture(tmp_path)
    review["chapters"][1]["boundary_evidence"]["cue"] = "Invented cue"
    review["semantic_review"]["chapters_sha256"] = canonical_sha256(review["chapters"])
    review_file.write_text(json.dumps(review), encoding="utf-8")
    with pytest.raises(ValueError, match="not in the cited original event"):
        build_one_video_chapter_plan(audit, audit_file, previous, previous_file, review, review_file, db, video_id=VID)


def test_caption_boundary_inside_archive_chunk_is_supported(tmp_path: Path) -> None:
    audit, audit_file, previous, previous_file, review, review_file, db = fixture(tmp_path)
    chapter = review["chapters"][1]
    chapter.update(second=125, stamp="02:05")
    chapter["boundary_evidence"]["start_ms"] = 125_500
    captions = tmp_path / review["semantic_review"]["evidence_file"]
    obj = json.loads(captions.read_text(encoding="utf-8"))
    obj["events"][1]["tStartMs"] = 125_500
    captions.write_text(json.dumps(obj), encoding="utf-8")
    after = PUBLISHED_AFTER + "\n\nТаймкоды:\n" + "\n".join(x["stamp"] + " " + x["heading"] for x in review["chapters"])
    review["proposed_description_sha256"] = sha256_text(after)
    review["semantic_review"].update(
        evidence_sha256=_sha_bytes(captions),
        chapters_sha256=canonical_sha256(review["chapters"]),
        description_sha256=sha256_text(after),
    )
    review_file.write_text(json.dumps(review), encoding="utf-8")
    plan, _ = build_one_video_chapter_plan(
        audit, audit_file, previous, previous_file, review, review_file, db, video_id=VID
    )
    assert "02:05 " in plan["operations"][0]["after_description"]


def test_legacy_chapter_plan_refused_before_oauth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import typer
    from types import SimpleNamespace
    from video_channel_manager.cli import youtube

    plan, _ = build(tmp_path)
    plan["ruleset"] = plan["operations"][0]["ruleset"] = "lord-god-one-video-semantic-chapters-v1"
    finalize_copy_plan(plan, checked_video_ids=plan["checked_video_ids"])
    plan_file = tmp_path / "old-plan.json"
    plan_file.write_text(json.dumps(plan), encoding="utf-8")

    def no_oauth(*args, **kwargs):
        pytest.fail("A retired chapter ruleset reached OAuth/provider initialization")

    monkeypatch.setattr(youtube, "prepare_windows_youtube_console", lambda: None)
    monkeypatch.setattr(youtube, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))
    monkeypatch.setattr(youtube, "require_lord_god_youtube_presentation", lambda payload: None)
    monkeypatch.setattr(youtube, "_writer_components", no_oauth)
    with pytest.raises(typer.Exit) as failure:
        youtube.apply_copy_fixes(
            plan_file,
            account="fedor-milovanov",
            confirm_channel=LORD_GOD_CHANNEL,
            execute=True,
            confirm_target=VID,
            confirm_after_sha256=plan["operations"][0]["after_sha256"],
            backup_output=tmp_path / "backup.json",
            result_output=tmp_path / "result.json",
        )
    assert failure.value.exit_code == 2
    assert not (tmp_path / "backup.json").exists()
    assert not (tmp_path / "result.json").exists()


def test_resealed_retired_effect_cannot_execute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan, _ = build(tmp_path)
    monkeypatch.setitem(RETIRED_EFFECTS, VID, plan["operations"][0]["after_sha256"])
    plan["generated_at"] = "resealed"
    finalize_copy_plan(plan, checked_video_ids=plan["checked_video_ids"])
    require_chapter_release(plan, execute=False)
    with pytest.raises(ValueError, match="retired chapter effect"):
        require_chapter_release(plan, execute=True, confirm_review_sha256=plan["source_chapter_review_sha256"])


@pytest.mark.parametrize(
    "variant",
    ["exact", "unreviewed", "wrong_end", "wrong_start", "wrong_previous", "large_gap", "different_cue", "audio_basis"],
)
def test_caption_boundary_in_reviewed_short_archive_gap(tmp_path: Path, variant: str) -> None:
    audit, audit_file, previous, previous_file, review, review_file, db = fixture(tmp_path)
    previous_end = 116_200 if variant != "large_gap" else 110_000
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("UPDATE transcript_chunks SET end_ms=? WHERE video_id=? AND start_ms=0", (previous_end, VID))
    ch = review["chapters"][1]
    ch.update(second=117, stamp="01:57")
    cue = "Грамматический анализ"
    if variant == "different_cue":
        cue = "и контекст текста"
    gap = {
        "reviewed": variant != "unreviewed",
        "previous_chunk_index": 2 if variant == "wrong_previous" else 0,
        "previous_end_ms": previous_end - 1 if variant == "wrong_end" else previous_end,
        "next_start_ms": 120_001 if variant == "wrong_start" else 120_000,
    }
    ch["boundary_evidence"].update(start_ms=117_000, cue=cue, archive_gap=gap)
    captions = tmp_path / review["semantic_review"]["evidence_file"]
    data = json.loads(captions.read_text(encoding="utf-8"))
    data["events"][1]["tStartMs"] = 117_000
    captions.write_text(json.dumps(data), encoding="utf-8")
    after = PUBLISHED_AFTER + "\n\nТаймкоды:\n" + "\n".join(x["stamp"] + " " + x["heading"] for x in review["chapters"])
    review["proposed_description_sha256"] = sha256_text(after)
    review["semantic_review"].update(
        evidence_sha256=_sha_bytes(captions),
        chapters_sha256=canonical_sha256(review["chapters"]),
        description_sha256=sha256_text(after),
    )
    if variant == "audio_basis":
        review["semantic_review"]["basis"] = "exact_ru_audio_boundaries"
    review_file.write_text(json.dumps(review), encoding="utf-8")
    if variant == "exact":
        plan, _ = build_one_video_chapter_plan(
            audit, audit_file, previous, previous_file, review, review_file, db, video_id=VID
        )
        assert plan["chapter_evidence"]["reviewed_archive_gap_chapter_ordinals"] == [1]
        assert "\n01:57 " in plan["operations"][0]["after_description"]
        require_chapter_release(plan, execute=True, confirm_review_sha256=plan["source_chapter_review_sha256"])
    else:
        with pytest.raises(ValueError, match="archival transcript cue"):
            build_one_video_chapter_plan(
                audit, audit_file, previous, previous_file, review, review_file, db, video_id=VID
            )


def panorama_owner_fixture(tmp_path: Path):
    from video_channel_manager.platforms.youtube.chapter_release import PANORAMA_PLAYLIST

    _, _, _, _, review, review_file, db = fixture(tmp_path)
    original = "https://www.slovo.org/resursy/propovedi/panorama-biblii-27-kniga-test/"
    before = (
        "Алексей Коломийцев объясняет содержание книги пророка.\n"
        "Лекция раскрывает основные темы и исторический контекст.\n\n"
        "*Изучение Писания*\n_Учебная лекция._\n"
        f"{original}\nhttps://www.youtube.com/playlist?list={PANORAMA_PLAYLIST}"
    )
    raw = {
        "id": VID,
        "snippet": {
            "channelId": LORD_GOD_CHANNEL,
            "title": "Панорама Библии - 27",
            "description": before,
            "defaultLanguage": "ru",
            "defaultAudioLanguage": "ru",
            "tags": ["Библия"],
            "categoryId": "27",
        },
        "contentDetails": {"duration": "PT1H7M"},
        "status": {"privacyStatus": "public"},
        "localizations": {"ru": {"title": "Панорама Библии - 27", "description": before}},
    }
    owner = {
        "schema": "panorama-exact-owner-one-probe-v1",
        "status": "OWNER_READ_SUCCESS",
        "read_only": True,
        "provider_writes": 0,
        "api_read_operations": 1,
        "video_id": VID,
        "owner_channel_id_expected": LORD_GOD_CHANNEL,
        "owner_channel_id": LORD_GOD_CHANNEL,
        "title": raw["snippet"]["title"],
        "description_sha256": sha256_text(before),
        "revision": canonical_sha256(raw),
        "locale_keys": ["ru"],
        "raw": raw,
    }
    playlist = {
        "schema": "panorama-current-owner-playlist-v1",
        "playlist_id": PANORAMA_PLAYLIST,
        "owner_channel_id": LORD_GOD_CHANNEL,
        "memberships": [
            {
                "position": i,
                "video_id": VID if i == 26 else f"test-{i}",
                "video_owner": LORD_GOD_CHANNEL,
                "video_title": raw["snippet"]["title"] if i == 26 else f"Lecture {i}",
            }
            for i in range(68)
        ],
    }
    sources = {
        "schema": "panorama-68-exact-original-sources-verified-v1",
        "catalogue": "https://www.slovo.org/resursy/serii/panorama-biblii/",
        "items": [
            {
                "number": i,
                "ok": True,
                "url": original if i == 27 else f"https://www.slovo.org/resursy/propovedi/test-{i}/",
            }
            for i in range(1, 69)
        ],
    }
    after = before + "\n\nТаймкоды:\n" + "\n".join(c["stamp"] + " " + c["heading"] for c in review["chapters"])
    review.update(
        episode=27,
        original=original,
        source_description_sha256=sha256_text(before),
        proposed_description_sha256=sha256_text(after),
    )
    review["semantic_review"]["description_sha256"] = sha256_text(after)
    paths = [tmp_path / "owner.json", tmp_path / "playlist.json", tmp_path / "sources.json", review_file]
    for f, payload in zip(paths, (owner, playlist, sources, review), strict=True):
        f.write_text(json.dumps(payload), encoding="utf-8")
    return owner, playlist, sources, review, paths, db


def test_exact_panorama_owner_append_and_execution_gate(tmp_path: Path):
    owner, playlist, sources, review, paths, db = panorama_owner_fixture(tmp_path)
    plan, report = build_panorama_owner_chapter_plan(*paths, db, video_id=VID)
    validate_copy_plan(plan)
    assert plan["checked_video_ids"] == [VID]
    assert plan["unresolved"] == []
    assert plan["source_scope"] == "exact-panorama-owner-v1"
    assert "source_audit_snapshot_id" not in plan
    assert "source_previous_editorial_plan" not in plan
    assert plan["operations"][0]["before_description"] == owner["raw"]["snippet"]["description"]
    assert plan["operations"][0]["expected_revision"] == owner["revision"]
    assert "fresh live preflight" in report
    require_chapter_release(plan, execute=True, confirm_review_sha256=plan["source_chapter_review_sha256"])
    paths[1].write_text(json.dumps(playlist) + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact missing or changed"):
        require_chapter_release(plan, execute=True, confirm_review_sha256=plan["source_chapter_review_sha256"])


@pytest.mark.parametrize(
    "case",
    [
        "foreign",
        "revision",
        "tags",
        "locale",
        "private",
        "audio",
        "source",
        "playlist",
        "position",
        "title",
        "hold",
        "duration",
        "receipt",
        "missing_raw",
        "incomplete_raw",
        "missing_url",
        "episode",
    ],
)
def test_exact_panorama_owner_refuses_invalid_evidence(tmp_path: Path, case: str):
    owner, playlist, sources, review, paths, db = panorama_owner_fixture(tmp_path)
    raw = owner["raw"]
    if case == "foreign":
        raw["snippet"]["channelId"] = "foreign"
    elif case == "revision":
        owner["revision"] = "bad"
    elif case == "tags":
        raw["snippet"].pop("tags")
    elif case == "locale":
        raw["localizations"]["ru"].pop("description")
    elif case == "private":
        raw["status"]["privacyStatus"] = "private"
    elif case == "audio":
        raw["snippet"]["defaultAudioLanguage"] = "en-US"
    elif case == "source":
        sources["items"][26]["url"] += "wrong"
    elif case == "playlist":
        playlist["playlist_id"] = "wrong"
    elif case == "position":
        playlist["memberships"][26]["position"] = 25
    elif case == "title":
        playlist["memberships"][26]["video_title"] = "wrong"
    elif case == "hold":
        review["editorial_approval"] = "HOLD"
    elif case == "duration":
        raw["contentDetails"]["duration"] = "PT1M"
    elif case == "receipt":
        owner["status"] = "READ_FAILED"
    elif case == "missing_raw":
        owner.pop("raw")
    elif case == "incomplete_raw":
        raw.pop("localizations")
    elif case == "missing_url":
        raw["snippet"]["description"] = "Missing primary source"
        owner["description_sha256"] = sha256_text(raw["snippet"]["description"])
    elif case == "episode":
        review["episode"] = 28
    if case != "revision":
        owner["revision"] = canonical_sha256(raw)
    for f, payload in zip(paths, (owner, playlist, sources, review), strict=True):
        f.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        build_panorama_owner_chapter_plan(*paths, db, video_id=VID)


def test_exact_panorama_cli_is_offline_and_refuses_output_overwrite(tmp_path: Path, monkeypatch):
    import sys
    from scripts import autofix_youtube_copy

    owner, playlist, sources, review, paths, db = panorama_owner_fixture(tmp_path)
    plan_path = tmp_path / "plan.json"
    report_path = tmp_path / "report.md"
    args = [
        "autofix_youtube_copy.py",
        str(paths[0]),
        "--panorama-playlist-receipt",
        str(paths[1]),
        "--panorama-source-register",
        str(paths[2]),
        "--lord-god-chapters-review",
        str(paths[3]),
        "--archive-transcript-db",
        str(db),
        "--target-video-id",
        VID,
        "--plan-output",
        str(plan_path),
        "--report-output",
        str(report_path),
    ]
    original_bytes = [f.read_bytes() for f in paths]
    monkeypatch.setattr(sys, "argv", args)
    assert autofix_youtube_copy.main() == 0
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    validate_copy_plan(plan)
    output_before = plan_path.read_bytes()
    with pytest.raises(SystemExit) as err:
        autofix_youtube_copy.main()
    assert err.value.code == 2
    assert plan_path.read_bytes() == output_before
    monkeypatch.setattr(
        sys, "argv", args[:-4] + ["--plan-output", str(paths[0]), "--report-output", str(tmp_path / "new.md")]
    )
    with pytest.raises(SystemExit) as err:
        autofix_youtube_copy.main()
    assert err.value.code == 2
    assert [f.read_bytes() for f in paths] == original_bytes


@pytest.mark.parametrize("scope", [None, "unknown", "legacy-audit-package-v1"])
def test_panorama_scope_cannot_be_removed_or_relabelled(tmp_path: Path, scope):
    _, _, _, _, paths, db = panorama_owner_fixture(tmp_path)
    plan, _ = build_panorama_owner_chapter_plan(*paths, db, video_id=VID)
    if scope is None:
        plan.pop("source_scope")
    else:
        plan["source_scope"] = scope
    finalize_copy_plan(plan, checked_video_ids=[VID])
    with pytest.raises(ValueError, match="scope|bound chapter source"):
        require_chapter_release(plan, execute=True, confirm_review_sha256=plan["source_chapter_review_sha256"])


@pytest.mark.parametrize("legacy", [True, False])
def test_chapter_executor_rederives_and_refuses_changed_transcript(tmp_path: Path, legacy: bool):
    if legacy:
        plan, _ = build(tmp_path)
        db = Path(plan["chapter_evidence"]["transcript_database"])
    else:
        _, _, _, _, paths, db = panorama_owner_fixture(tmp_path)
        plan, _ = build_panorama_owner_chapter_plan(*paths, db, video_id=VID)
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("UPDATE transcript_chunks SET text=text || ' extra' WHERE video_id=? AND start_ms=3900000", (VID,))
    with pytest.raises(ValueError, match="re-derived"):
        require_chapter_release(plan, execute=True, confirm_review_sha256=plan["source_chapter_review_sha256"])


def test_panorama_resealed_operation_drift_refused(tmp_path: Path):
    _, _, _, _, paths, db = panorama_owner_fixture(tmp_path)
    plan, _ = build_panorama_owner_chapter_plan(*paths, db, video_id=VID)
    plan["operations"][0]["expected_revision"] = "sha256:altered"
    finalize_copy_plan(plan, checked_video_ids=[VID])
    with pytest.raises(ValueError, match="re-derived"):
        require_chapter_release(plan, execute=True, confirm_review_sha256=plan["source_chapter_review_sha256"])


@pytest.mark.parametrize("case", ["pass", "owner_drift", "metadata", "duration", "register", "foreign"])
def test_exact_owner_historical_format_candidate_is_never_executable(tmp_path: Path, case: str):
    import hashlib

    from scripts.audit_panorama_chapter_evidence import bind_format_preview_to_owner
    from video_channel_manager.platforms.youtube.chapter_release import normalize_existing_chapter_stamps

    owner, playlist, sources, _, paths, _ = panorama_owner_fixture(tmp_path)
    owner_file, playlist_file, source_file, _ = paths
    raw = owner["raw"]
    inventory = [("00:00", "Opening"), ("15:00", "Source"), ("65:00", "Canon")]
    before = raw["snippet"]["description"] + "\n\n" + "\n".join(f"{stamp} {heading}" for stamp, heading in inventory)
    after = normalize_existing_chapter_stamps(before, inventory, duration_seconds=4020)
    raw["snippet"]["description"] = before
    raw["localizations"]["ru"]["description"] = before
    owner["description_sha256"] = sha256_text(before)
    owner["revision"] = canonical_sha256(raw)

    def write(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return hashlib.sha256(path.read_bytes()).hexdigest()

    old_plan = tmp_path / f"{VID}-plan.json"
    old_sha = write(
        old_plan, {"operations": [{"video_id": VID, "after_description": before, "after_sha256": sha256_text(before)}]}
    )
    chapters = [
        {"stamp": stamp, "heading": heading, "second": second, "canonical_stamp": canonical}
        for (stamp, heading), second, canonical in zip(
            inventory, [0, 900, 3900], ["00:00", "15:00", "1:05:00"], strict=True
        )
    ]
    audit_file = tmp_path / "historical-audit.json"
    audit_sha = write(
        audit_file,
        {
            "schema": "panorama-historical-chapter-evidence-audit-v2",
            "owner_channel_id": LORD_GOD_CHANNEL,
            "is_executable_plan": False,
            "frozen_playlist_sha256": hashlib.sha256(playlist_file.read_bytes()).hexdigest(),
            "source_register_sha256": hashlib.sha256(source_file.read_bytes()).hexdigest(),
            "results": [{"video_id": VID, "episode": 27, "chapters": chapters, "last_tail_ms": 120000}],
        },
    )
    preview_file = tmp_path / "historical-preview.json"
    write(
        preview_file,
        {
            "schema": "panorama-format-only-review-report-v1",
            "project_key": "lord-god-strength",
            "owner_channel_id": LORD_GOD_CHANNEL,
            "source_audit": audit_file.name,
            "source_audit_sha256": audit_sha,
            "is_executable_plan": False,
            "semantic_approval": False,
            "fresh_owner_snapshot": False,
            "provider_reads": 0,
            "provider_writes": 0,
            "items": [
                {
                    "episode": 27,
                    "video_id": VID,
                    "historical_plan": old_plan.name,
                    "historical_plan_sha256": old_sha,
                    "before_description": before,
                    "before_sha256": sha256_text(before).removeprefix("sha256:"),
                    "proposed_description": after,
                    "proposed_sha256": sha256_text(after).removeprefix("sha256:"),
                    "proposed_utf8_bytes": len(after.encode()),
                    "changes": chapters[2:],
                }
            ],
        },
    )
    if case == "owner_drift":
        raw["snippet"]["description"] += " "
        owner["description_sha256"] = sha256_text(raw["snippet"]["description"])
    elif case == "metadata":
        raw["snippet"].pop("tags")
    elif case == "duration":
        raw["contentDetails"]["duration"] = "PT1H"
    elif case == "register":
        sources["items"][0]["url"] += "changed"
        write(source_file, sources)
    elif case == "foreign":
        raw["snippet"]["channelId"] = "foreign"
    owner["revision"] = canonical_sha256(raw)
    write(owner_file, owner)
    args = (audit_file, preview_file, owner_file, playlist_file, source_file)
    if case != "pass":
        with pytest.raises(ValueError):
            bind_format_preview_to_owner(*args, video_id=VID)
    else:
        candidate = bind_format_preview_to_owner(*args, video_id=VID)
        assert candidate["proposed_description"] == after
        assert candidate["owner_revision"] == owner["revision"]
        assert candidate["format_review"] == candidate["execution"] == "HOLD"
        assert candidate["is_executable_plan"] is candidate["semantic_approval"] is False
        with pytest.raises(ValueError):
            validate_copy_plan(candidate)

        from video_channel_manager.platforms.youtube.panorama_format_release import (
            build_format_correction_plan,
            require_format_correction_plan,
        )
        from video_channel_manager.platforms.youtube.copy_plan import finalize_copy_plan
        from video_channel_manager.platforms.youtube.chapter_release import digest_file

        candidate_file = tmp_path / "candidate.json"
        write(candidate_file, candidate)
        review_file = tmp_path / "format-review.json"
        review = {
            "schema": "panorama-existing-chapter-format-review-v1",
            "owner_channel_id": LORD_GOD_CHANNEL,
            "video_id": VID,
            "candidate_sha256": digest_file(candidate_file),
            "before_sha256": sha256_text(before),
            "after_sha256": sha256_text(after),
            "format_review": "APPROVED",
            "semantic_approval": False,
            "reviewer": "synthetic test fixture only",
            "reviewed_at": "2026-11-24T12:00:00+00:00",
        }
        write(review_file, review)
        plan, _ = build_format_correction_plan(
            owner_file, playlist_file, source_file, candidate_file, review_file, video_id=VID
        )
        require_format_correction_plan(plan)
        require_chapter_release(plan, execute=False)
        with pytest.raises(ValueError, match="confirm-chapter-review"):
            require_chapter_release(plan, execute=True)
        require_chapter_release(plan, execute=True, confirm_review_sha256=digest_file(review_file))
        plan["operations"][0]["expected_revision"] = "resealed-wrong-revision"
        finalize_copy_plan(plan, checked_video_ids=[VID])
        with pytest.raises(ValueError, match="re-derived"):
            require_format_correction_plan(plan)
        review["format_review"] = "HOLD"
        write(review_file, review)
        with pytest.raises(ValueError, match="format review"):
            build_format_correction_plan(
                owner_file, playlist_file, source_file, candidate_file, review_file, video_id=VID
            )
