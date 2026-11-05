from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.platforms.youtube.copy_plan import validate_copy_plan, sha256_text
from video_channel_manager.platforms.youtube.lord_god_retired_appeal import (
    build_one_video_retired_appeal_plan,
)
from video_channel_manager.platforms.youtube.lord_god_scoped import LORD_GOD_CHANNEL

VID = "e5d1zaJWAoQ"
LINK = f"http://www.youtube.com/channel/{LORD_GOD_CHANNEL}/playlists?view=50&flow=grid&shelf_id=15&sort=dd"
BODY = (
    "Подробное сообщение о Божьем милосердии и верности Священного Писания. "
    "Автор рассматривает историческую обстановку библейского отрывка, "
    "отношение человека к Евангелию, смысл спасения через Иисуса Христа "
    "и практическое применение Божьего Слова в жизни христианской общины. "
    "Слушателям предлагается внимательно изучить контекст и прочитать "
    "соседние главы, чтобы не вырывать отдельный стих из повествования.\n\n"
)
APPEAL = (
    "➡️ Некоторые проповеди получается перевести и озвучить самому, "
    "если есть возможность помочь с переводами, то пишите: "
    "https://t.me/fedormilovanov\n"
)
SHELF = f"Тематические серии проповедей: {LINK}\n"
BEFORE = BODY + SHELF + APPEAL + "\nTelegram проекта: https://t.me/lordchrist\n"
SHELF_REMOVED = BODY + APPEAL + "\nTelegram проекта: https://t.me/lordchrist\n"
AFTER = BODY + "\nTelegram проекта: https://t.me/lordchrist\n"
MISSING = ["missA", "missB", "missC", "missD", "missE", "missF"]


def fixture(tmp_path: Path):
    audit = {
        "schema_name": "video-manager.audit-package",
        "snapshot_id": "snapshot-uuid",
        "channel": {"ref": {"remote_id": LORD_GOD_CHANNEL}},
        "videos": [
            {
                "ref": {"remote_id": VID, "channel_id": LORD_GOD_CHANNEL},
                "title": "Историческая лекция о Евангелии",
                "description": BEFORE,
                "privacy_status": "public",
                "revision": "sha256:revision",
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
                "details": {"video_id": miss},
            }
            for miss in MISSING
        ],
    }
    review = {
        "schema": "lordgod-retired-solicitation-review-v1",
        "video_id": VID,
        "owner_channel_id": LORD_GOD_CHANNEL,
        "original_description": BEFORE,
        "shelf_removed_only": SHELF_REMOVED,
        "final_description": AFTER,
        "original_sha256": sha256_text(BEFORE),
        "shelf_removed_only_sha256": sha256_text(SHELF_REMOVED),
        "final_sha256": sha256_text(AFTER),
        "expected_legacy_shelf_lines_deleted": 1,
        "sole_allowed_retired_solicitation_line": APPEAL,
        "archived_snapshot_only": True,
        "owner_live_preflight_required": True,
        "is_executable_plan": False,
        "publisher_ready": False,
        "provider_writes": 0,
    }
    ap = tmp_path / "owner.json"
    rp = tmp_path / "review.json"
    ap.write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")
    rp.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
    return audit, ap, review, rp


def build(tmp_path: Path, mutate=None):
    audit, ap, review, rp = fixture(tmp_path)
    if mutate:
        mutate(audit, review)
    return build_one_video_retired_appeal_plan(audit, ap, review, rp, video_id=VID)


def test_signed_single_video_plan_preserves_all_substance_and_six_exceptions(tmp_path: Path):
    plan, report = build(tmp_path)
    validate_copy_plan(plan)
    assert plan["target_channel_id"] == LORD_GOD_CHANNEL
    assert plan["project_key"] == "lord-god-strength"
    assert plan["operations_count"] == 1
    assert plan["unresolved_error_videos"] == 6
    assert len(plan["unresolved"]) == 6
    assert len(plan["checked_video_ids"]) == 7
    assert plan["operations"][0]["before_description"] == BEFORE
    assert plan["operations"][0]["after_description"] == AFTER
    assert plan["operations"][0]["after_description"].startswith(BODY)
    assert plan["fix_code_counts"] == {
        "removed_vetted_legacy_shelf_lines": 1,
        "removed_one_retired_translation_appeal": 1,
    }
    assert plan["live_provider_preflight_required"] is True
    assert "Fresh exact-ID" in report


@pytest.mark.parametrize(
    "mutator,expected",
    [
        (lambda a, r: a["channel"]["ref"].update(remote_id="foreign"), "Wrong authenticated"),
        (lambda a, r: a["videos"][0].update(privacy_status="private"), "Nonpublic"),
        (lambda a, r: a["metadata"]["uploads_playlist_inventory"].update(missing_metadata_count=5), "gap count"),
        (lambda a, r: r.update(owner_channel_id="foreign"), "exact-owner"),
        (lambda a, r: r.update(publisher_ready=True), "non-executable"),
        (lambda a, r: r.update(provider_writes=1), "non-executable"),
        (lambda a, r: r.update(original_sha256="sha256:bogus"), "SHA or archived"),
        (lambda a, r: r.update(final_sha256="sha256:bogus"), "SHA or archived"),
        (lambda a, r: r.update(expected_legacy_shelf_lines_deleted=2), "deletion count"),
        (lambda a, r: r.update(sole_allowed_retired_solicitation_line="not the source"), "exact retired"),
        (lambda a, r: r.update(final_description=AFTER.replace("Иисуса Христа", "другую цель")), "SHA or archived"),
        (lambda a, r: r.update(shelf_removed_only=SHELF_REMOVED + "новый абзац"), "SHA or archived"),
        (lambda a, r: r.update(original_description=BEFORE.replace("Иисуса Христа", "самого себя")), "SHA or archived"),
        (lambda a, r: r.update(owner_live_preflight_required=False), "non-executable"),
        (lambda a, r: r.update(is_executable_plan=True), "non-executable"),
    ],
)
def test_source_or_scope_mutation_rejected(tmp_path: Path, mutator, expected: str):
    with pytest.raises(ValueError, match=expected):
        build(tmp_path, mutator)


def test_refuses_to_delete_a_source_link_from_appeal_line(tmp_path: Path):
    audit, ap, review, rp = fixture(tmp_path)
    dangerous = APPEAL.rstrip("\n") + " https://gty.org/sermons/source123\n"
    audit["videos"][0]["description"] = BEFORE.replace(APPEAL, dangerous)
    review["original_description"] = BEFORE.replace(APPEAL, dangerous)
    review["shelf_removed_only"] = SHELF_REMOVED.replace(APPEAL, dangerous)
    review["sole_allowed_retired_solicitation_line"] = dangerous
    review["original_sha256"] = sha256_text(review["original_description"])
    review["shelf_removed_only_sha256"] = sha256_text(review["shelf_removed_only"])
    with pytest.raises(ValueError, match="Exactly one narrowly recognized"):
        build_one_video_retired_appeal_plan(audit, ap, review, rp, video_id=VID)


def test_refuses_to_edit_if_not_a_single_appeal(tmp_path: Path):
    audit, ap, review, rp = fixture(tmp_path)
    extra = APPEAL
    for key in ["original_description", "shelf_removed_only"]:
        review[key] += extra
    review["final_description"] = AFTER
    review["original_sha256"] = sha256_text(review["original_description"])
    review["shelf_removed_only_sha256"] = sha256_text(review["shelf_removed_only"])
    audit["videos"][0]["description"] = review["original_description"]
    with pytest.raises(ValueError, match="Exactly one narrowly recognized"):
        build_one_video_retired_appeal_plan(audit, ap, review, rp, video_id=VID)


def test_short_only_link_description_refused(tmp_path: Path):
    audit, ap, review, rp = fixture(tmp_path)
    short = "Видео без пояснений.\n"
    for key in ["original_description", "shelf_removed_only", "final_description"]:
        review[key] = review[key].replace(BODY, short)
    review["original_sha256"] = sha256_text(review["original_description"])
    review["shelf_removed_only_sha256"] = sha256_text(review["shelf_removed_only"])
    review["final_sha256"] = sha256_text(review["final_description"])
    audit["videos"][0]["description"] = review["original_description"]
    with pytest.raises(ValueError, match="substantial editorial content"):
        build_one_video_retired_appeal_plan(audit, ap, review, rp, video_id=VID)
