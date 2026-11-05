from __future__ import annotations
import hashlib
import json
from pathlib import Path
import pytest
from video_channel_manager.platforms.youtube.copy_plan import validate_copy_plan
from video_channel_manager.platforms.youtube.lord_god_scoped import (
    LORD_GOD_CHANNEL,
    build_one_video_scoped_plan,
)

VID = "e5d1zaJWAoQ"
LINK = "http://www.youtube.com/channel/" + LORD_GOD_CHANNEL + "/playlists?view=50&flow=grid&shelf_id=15&sort=dd"
BEFORE = "Панорама Библии\nПроповеди: " + LINK + "\nДругой текст\n"
AFTER = "Панорама Библии\nДругой текст\n"
MISSES = ["MISS001", "MISS002", "MISS003", "MISS004", "MISS005", "MISS006"]


def sha(x: str) -> str:
    return hashlib.sha256(x.encode("utf-8")).hexdigest()


def fixtures(tmp_path: Path) -> tuple[dict, Path, dict, Path]:
    audit = {
        "schema_name": "video-manager.audit-package",
        "channel": {"ref": {"remote_id": LORD_GOD_CHANNEL}},
        "videos": [
            {
                "ref": {"remote_id": VID, "channel_id": LORD_GOD_CHANNEL},
                "title": "Панорама Библии",
                "description": BEFORE,
                "privacy_status": "public",
                "revision": "sha256:rev",
            }
        ],
        "metadata": {
            "uploads_playlist_inventory": {
                "complete": False,
                "upload_count": 8,
                "unique_upload_count": 7,
                "materialized_video_count": 1,
                "missing_metadata_count": 6,
                "missing_metadata_ids": list(MISSES),
                "pagination_integrity": {"validation_passes": 2, "unique_id_set_reconciled": True},
            }
        },
        "findings": [
            {"severity": "error", "rule_id": "youtube.owner-upload-metadata-gap", "details": {"video_id": miss}}
            for miss in MISSES
        ],
    }
    preview = {
        "schema": "lordgod-preview-not-executable-v1",
        "channel_id": LORD_GOD_CHANNEL,
        "is_executable_plan": False,
        "items": [
            {
                "video_id": VID,
                "privacy": "public",
                "unmodified_manual_holds": [],
                "owner_review_required": True,
                "execution_authority": False,
                "current_description": BEFORE,
                "candidate_description": AFTER,
                "current_sha256": sha(BEFORE),
                "candidate_sha256": sha(AFTER),
            }
        ],
    }
    audit_path = tmp_path / "owner.json"
    preview_path = tmp_path / "review.json"
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    preview_path.write_text(json.dumps(preview), encoding="utf-8")
    return audit, audit_path, preview, preview_path


def build(tmp_path: Path, mutate=None):
    audit, audit_path, preview, preview_path = fixtures(tmp_path)
    if mutate:
        mutate(audit, preview)
    return build_one_video_scoped_plan(audit, audit_path, preview, preview_path, video_id=VID)


def test_scoped_plan_keeps_exact_six_metadata_exceptions_and_signed_copy(tmp_path: Path) -> None:
    plan, report = build(tmp_path)
    validate_copy_plan(plan)
    assert plan["project_key"] == "lord-god-strength"
    assert plan["link_profile"] == "lord-god-strength"
    assert plan["vk_owner_id"] == -60805374
    assert len(plan["operations"]) == 1
    assert len(plan["unresolved"]) == 6
    assert plan["operations"][0]["after_description"] == AFTER
    assert plan["operations"][0]["fixes"][0]["count"] == 1
    assert "Unmaterialized metadata" in report


@pytest.mark.parametrize(
    "mutator, expected",
    [
        (lambda a, p: a["channel"]["ref"].update(remote_id="UC-foreign"), "Wrong authenticated"),
        (
            lambda a, p: a["metadata"]["uploads_playlist_inventory"]["pagination_integrity"].update(
                unique_id_set_reconciled=False
            ),
            "not reconciled",
        ),
        (
            lambda a, p: a["metadata"]["uploads_playlist_inventory"].update(missing_metadata_count=5),
            "gap count mismatch",
        ),
        (lambda a, p: a["findings"].append({"severity": "error", "rule_id": "unrelated"}), "Unexpected error findings"),
        (lambda a, p: a["videos"][0].update(privacy_status="private"), "Nonpublic videos"),
        (lambda a, p: p["items"][0].update(unmodified_manual_holds=[{"line": "check"}]), "Mixed/semantic"),
        (lambda a, p: p["items"][0].update(candidate_description=AFTER + "new content"), "Preview after SHA"),
        (
            lambda a, p: p["items"][0].update(
                candidate_description=BEFORE.replace("Другой текст", "Подмена"),
                candidate_sha256=sha(BEFORE.replace("Другой текст", "Подмена")),
            ),
            "beyond exact",
        ),
        (lambda a, p: p["items"][0].update(current_description="Manual overwrite"), "does not match immutable"),
    ],
)
def test_fail_closed(tmp_path: Path, mutator, expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        build(tmp_path, mutator)


def test_blocks_target_in_missing_ids(tmp_path: Path) -> None:
    def mutate(a, p):
        a["metadata"]["uploads_playlist_inventory"]["missing_metadata_ids"][0] = VID
        a["findings"][0]["details"]["video_id"] = VID

    with pytest.raises(ValueError, match="Cannot edit an unmaterialized"):
        build(tmp_path, mutate)


@pytest.mark.parametrize(
    "appended, error",
    [
        ("Поддержка переводов: https://t.me/fedormilovanov\n", "Legacy personal contact"),
        ("📚 *Проповеди:*\n", "Empty thematic navigation heading"),
        (
            "Другая серия: https://www.youtube.com/playlist?list=PLNotAnOwnerMembership\n",
            "Unproven or unrelated YouTube playlist",
        ),
    ],
)
def test_rejects_bad_project_links_or_empty_headings(tmp_path: Path, appended: str, error: str) -> None:
    def mutate(audit, preview):
        before = BEFORE + appended
        after = AFTER + appended
        audit["videos"][0]["description"] = before
        row = preview["items"][0]
        row["current_description"] = before
        row["current_sha256"] = sha(before)
        row["candidate_description"] = after
        row["candidate_sha256"] = sha(after)

    with pytest.raises(ValueError, match=error):
        build(tmp_path, mutate)
