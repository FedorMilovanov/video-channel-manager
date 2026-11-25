"""Provider-inert format-only chapter correction regressions."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.audit_panorama_chapter_evidence import verify_format_preview
from video_channel_manager.platforms.youtube.copy_plan import canonical_sha256, sha256_text
from video_channel_manager.platforms.youtube.lord_god_source_preservation import LORD_GOD_OWNER_CHANNEL

from video_channel_manager.platforms.youtube.chapter_release import normalize_existing_chapter_stamps

CHAPTERS = [("00:00", "Opening"), ("58:00", "Source"), ("65:00", "Canon"), ("84:00", "Closing")]
BEFORE = (
    "Intro 65:00 stays\r\nhttps://example.com/65:00\r\n"
    + "\r\n".join(f"{stamp} {heading}" for stamp, heading in CHAPTERS)
    + "\r\nEnd."
)
AFTER = BEFORE.replace("\r\n65:00 Canon", "\r\n1:05:00 Canon").replace("\r\n84:00 Closing", "\r\n1:24:00 Closing")


def test_exact_format_only_preserves_every_other_character() -> None:
    assert normalize_existing_chapter_stamps(BEFORE, CHAPTERS, duration_seconds=5500) == AFTER


@pytest.mark.parametrize(
    "before, chapters, duration",
    [
        (BEFORE + "\n90:00 Extra", CHAPTERS, 6000),
        (BEFORE, CHAPTERS[:-1], 5500),
        (BEFORE, list(reversed(CHAPTERS)), 5500),
        (BEFORE.replace("65:00 Canon", "65:00 Other"), CHAPTERS, 5500),
        (BEFORE.replace("65:00 Canon", " 65:00 Canon"), CHAPTERS, 5500),
        (BEFORE.replace("65:00 Canon", "65:60 Canon"), [*CHAPTERS[:2], ("65:60", "Canon"), CHAPTERS[3]], 5500),
        (BEFORE, CHAPTERS, 5045),
        (BEFORE, CHAPTERS, True),
        (AFTER, [*CHAPTERS[:2], ("1:05:00", "Canon"), ("1:24:00", "Closing")], 5500),
        ("x" * 5000 + "\n" + BEFORE, CHAPTERS, 5500),
    ],
)
def test_invalid_or_unbound_inventory_refused(before: str, chapters: list[tuple[str, str]], duration: int) -> None:
    with pytest.raises(ValueError):
        normalize_existing_chapter_stamps(before, chapters, duration_seconds=duration)


def _save(path: Path, obj: object) -> str:
    path.write_text(json.dumps(obj), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("defect", ["none", "after", "source", "duplicate", "authority", "missing_chapter"])
def test_archived_preview_rederivation(tmp_path: Path, defect: str) -> None:
    video = "example0001"
    source = tmp_path / f"{video}-plan.json"
    src_hash = _save(
        source, {"operations": [{"video_id": video, "after_description": BEFORE, "after_sha256": sha256_text(BEFORE)}]}
    )
    chapters = [
        {"stamp": stamp, "heading": heading, "second": second, "canonical_stamp": canonical}
        for (stamp, heading), second, canonical in zip(
            CHAPTERS, [0, 3480, 3900, 5040], ["00:00", "58:00", "1:05:00", "1:24:00"], strict=True
        )
    ]
    audit_file = tmp_path / "audit.json"
    audit_sha = _save(
        audit_file,
        {
            "schema": "panorama-historical-chapter-evidence-audit-v2",
            "owner_channel_id": LORD_GOD_OWNER_CHANNEL,
            "is_executable_plan": False,
            "results": [{"video_id": video, "episode": 1, "chapters": chapters, "last_tail_ms": 460000}],
        },
    )
    item = {
        "episode": 1,
        "video_id": video,
        "historical_plan": source.name,
        "historical_plan_sha256": src_hash,
        "before_description": BEFORE,
        "before_sha256": sha256_text(BEFORE).removeprefix("sha256:"),
        "proposed_description": AFTER,
        "proposed_sha256": sha256_text(AFTER).removeprefix("sha256:"),
        "proposed_utf8_bytes": len(AFTER.encode()),
        "changes": chapters[2:],
    }
    items = [item, item] if defect == "duplicate" else [item]
    preview = {
        "schema": "panorama-format-only-review-report-v1",
        "owner_channel_id": LORD_GOD_OWNER_CHANNEL,
        "project_key": "lord-god-strength",
        "source_audit": audit_file.name,
        "source_audit_sha256": audit_sha,
        "is_executable_plan": defect == "authority",
        "semantic_approval": False,
        "fresh_owner_snapshot": False,
        "provider_reads": 0,
        "provider_writes": 0,
        "items": items,
    }
    if defect == "after":
        item["proposed_description"] = AFTER + " edited"
    if defect == "source":
        source.write_text("{}", encoding="utf-8")
    if defect == "missing_chapter":
        item["changes"] = chapters[2:3]
    preview_file = tmp_path / "preview.json"
    _save(preview_file, preview)
    if defect != "none":
        with pytest.raises(ValueError):
            verify_format_preview(audit_file, preview_file)
    else:
        report = verify_format_preview(audit_file, preview_file)
        assert report["videos_checked"] == 1
        assert report["stamps_verified"] == 2
        assert report["is_executable_plan"] is False


def _russian_metadata_evidence() -> tuple[dict, dict]:
    from video_channel_manager.platforms.youtube.chapter_release import PANORAMA_PLAYLIST

    title = "Панорама Библии — Бытие"
    description = "Русский текст.\n00:00 Введение\n12:00 Бытие"
    video_id = "video000000"
    raw = {
        "id": video_id,
        "snippet": {
            "channelId": LORD_GOD_OWNER_CHANNEL,
            "title": title,
            "description": description,
            "defaultLanguage": "ru",
            "defaultAudioLanguage": "ru",
            "categoryId": "22",
            "tags": ["Библия"],
        },
        "status": {"privacyStatus": "public"},
        "contentDetails": {"duration": "PT1H"},
        "localizations": {
            "ru": {"title": title, "description": description},
            "ru-RU": {"title": title, "description": description},
            "en-US": {"title": "Genesis", "description": "English text"},
            "de": {"title": "Genesis", "description": "German text"},
        },
    }
    owner = {
        "schema": "panorama-exact-owner-one-probe-v1",
        "status": "OWNER_READ_SUCCESS",
        "read_only": True,
        "provider_writes": 0,
        "api_read_operations": 1,
        "video_id": video_id,
        "owner_channel_id_expected": LORD_GOD_OWNER_CHANNEL,
        "owner_channel_id": LORD_GOD_OWNER_CHANNEL,
        "title": title,
        "description_sha256": sha256_text(description),
        "revision": canonical_sha256(raw),
        "locale_keys": sorted(raw["localizations"]),
        "raw": raw,
    }
    playlist = {
        "schema": "panorama-current-owner-playlist-v1",
        "playlist_id": PANORAMA_PLAYLIST,
        "owner_channel_id": LORD_GOD_OWNER_CHANNEL,
        "memberships": [
            {
                "video_id": f"video{i:06d}",
                "video_title": title,
                "video_owner": LORD_GOD_OWNER_CHANNEL,
                "position": i,
            }
            for i in range(68)
        ],
    }
    return owner, playlist


def test_panorama_russian_metadata_reduction_is_exact_and_inert() -> None:
    from video_channel_manager.platforms.youtube.lord_god_presentation import plan_panorama_russian_metadata

    owner, playlist = _russian_metadata_evidence()
    baseline = copy.deepcopy(owner)
    result = plan_panorama_russian_metadata(owner, playlist, video_id=owner["video_id"])
    assert result["removed_locale_keys"] == ["de", "en-US"]
    assert result["after_localizations"] == {key: owner["raw"]["localizations"][key] for key in ("ru", "ru-RU")}
    assert result["before_localizations"] == baseline["raw"]["localizations"]
    assert result["before_sha256"] == canonical_sha256(baseline["raw"]["localizations"])
    assert result["after_sha256"] == canonical_sha256(result["after_localizations"])
    assert result["captions_action"] == "PRESERVE"
    assert result["disposition"] == "REVIEW_REQUIRED"
    assert result["is_executable_plan"] is False
    assert result["execution_authorized"] is False
    assert result["provider_reads"] == result["provider_writes"] == 0
    result["after_localizations"]["ru"]["title"] = "changed"
    assert owner == baseline


@pytest.mark.parametrize("keys", [[], ["ru"], ["en-US"]])
def test_panorama_russian_metadata_explicit_empty_or_reduced_map(keys: list[str]) -> None:
    from video_channel_manager.platforms.youtube.lord_god_presentation import plan_panorama_russian_metadata

    owner, playlist = _russian_metadata_evidence()
    raw = owner["raw"]
    raw["localizations"] = {key: raw["localizations"][key] for key in keys}
    owner["locale_keys"] = sorted(keys)
    owner["revision"] = canonical_sha256(raw)
    result = plan_panorama_russian_metadata(owner, playlist, video_id=owner["video_id"])
    assert result["disposition"] == ("REVIEW_REQUIRED" if keys == ["en-US"] else "NO_CHANGE")
    assert set(result["after_localizations"]) == ({"ru"} if keys == ["ru"] else set())
    assert result["is_executable_plan"] is False


@pytest.mark.parametrize(
    "defect",
    [
        "missing_map",
        "foreign_owner",
        "bad_revision",
        "unknown_id",
        "partial_playlist",
        "duplicate_member",
        "foreign_member",
        "wrong_title",
        "non_russian_default",
        "non_russian_audio",
        "missing_tags",
        "malformed_locale",
        "russian_drift",
        "duplicate_locale_case",
        "wrong_locale_keys",
        "write_receipt",
        "boolean_reads",
        "boolean_writes",
        "missing_snippet",
        "missing_status",
        "missing_details",
    ],
)
def test_panorama_russian_metadata_fails_closed(defect: str) -> None:
    from video_channel_manager.platforms.youtube.lord_god_presentation import plan_panorama_russian_metadata

    owner, playlist = _russian_metadata_evidence()
    raw = owner["raw"]
    target = owner["video_id"]
    if defect == "missing_map":
        raw.pop("localizations")
    elif defect == "foreign_owner":
        raw["snippet"]["channelId"] = "other"
    elif defect == "unknown_id":
        target = "other000000"
    elif defect == "partial_playlist":
        playlist["memberships"].pop()
    elif defect == "duplicate_member":
        playlist["memberships"][1]["video_id"] = target
    elif defect == "foreign_member":
        playlist["memberships"][1]["video_owner"] = "other"
    elif defect == "wrong_title":
        playlist["memberships"][0]["video_title"] = "other"
    elif defect == "non_russian_default":
        raw["snippet"]["defaultLanguage"] = "en"
    elif defect == "non_russian_audio":
        raw["snippet"]["defaultAudioLanguage"] = "en"
    elif defect == "missing_tags":
        raw["snippet"].pop("tags")
    elif defect == "malformed_locale":
        raw["localizations"]["de"].pop("title")
    elif defect == "russian_drift":
        raw["localizations"]["ru-RU"]["title"] = "different"
    elif defect == "duplicate_locale_case":
        raw["localizations"]["RU"] = raw["localizations"]["ru"]
    elif defect == "write_receipt":
        owner["read_only"] = False
    elif defect == "boolean_reads":
        owner["api_read_operations"] = True
    elif defect == "boolean_writes":
        owner["provider_writes"] = False
    elif defect == "missing_snippet":
        raw.pop("snippet")
    elif defect == "missing_status":
        raw.pop("status")
    elif defect == "missing_details":
        raw.pop("contentDetails")
    owner["locale_keys"] = sorted(raw.get("localizations", {}))
    if defect == "wrong_locale_keys":
        owner["locale_keys"] = []
    owner["revision"] = "invalid" if defect == "bad_revision" else canonical_sha256(raw)
    with pytest.raises(ValueError):
        plan_panorama_russian_metadata(owner, playlist, video_id=target)


@pytest.mark.parametrize(
    "defect",
    [
        "none",
        "missing_map",
        "old_map",
        "changed_russian",
        "changed_audio",
        "changed_tags",
        "changed_status",
        "changed_details",
        "changed_thumbnail",
        "wrong_id",
        "wrong_owner",
        "localized_view_only",
    ],
)
def test_panorama_russian_metadata_readback(defect: str) -> None:
    from video_channel_manager.platforms.youtube.lord_god_presentation import (
        plan_panorama_russian_metadata,
        verify_panorama_russian_metadata_readback,
    )

    owner, playlist = _russian_metadata_evidence()
    candidate = plan_panorama_russian_metadata(owner, playlist, video_id=owner["video_id"])
    after = copy.deepcopy(owner["raw"])
    after["localizations"] = copy.deepcopy(candidate["after_localizations"])
    if defect == "missing_map":
        after.pop("localizations")
    elif defect == "old_map":
        after["localizations"] = copy.deepcopy(owner["raw"]["localizations"])
    elif defect == "changed_russian":
        after["snippet"]["description"] += " drift"
    elif defect == "changed_audio":
        after["snippet"]["defaultAudioLanguage"] = "en"
    elif defect == "changed_tags":
        after["snippet"].pop("tags")
    elif defect == "changed_status":
        after["status"]["embeddable"] = False
    elif defect == "changed_details":
        after["contentDetails"]["caption"] = "false"
    elif defect == "changed_thumbnail":
        after["snippet"]["thumbnails"] = {"default": {"url": "other"}}
    elif defect == "wrong_id":
        after["id"] = "other000000"
    elif defect == "wrong_owner":
        after["snippet"]["channelId"] = "other"
    elif defect == "localized_view_only":
        after["snippet"]["localized"] = {"title": "Панорама", "description": "Русский"}
    report = verify_panorama_russian_metadata_readback(candidate, owner, playlist, after)
    assert report["metadata_matches"] is (defect in {"none", "localized_view_only"})
    assert not report["captions_verified"] and not report["public_display_verified"]
    assert report["execution_authorized"] is False
    assert report["provider_reads"] == report["provider_writes"] == 0


def test_panorama_empty_map_readback_must_be_explicit_and_candidate_rederived() -> None:
    from video_channel_manager.platforms.youtube.lord_god_presentation import (
        plan_panorama_russian_metadata,
        verify_panorama_russian_metadata_readback,
    )

    owner, playlist = _russian_metadata_evidence()
    raw = owner["raw"]
    raw["localizations"] = {"en-US": raw["localizations"]["en-US"]}
    owner["revision"] = canonical_sha256(raw)
    owner["locale_keys"] = ["en-US"]
    candidate = plan_panorama_russian_metadata(owner, playlist, video_id=owner["video_id"])
    after = copy.deepcopy(raw)
    after["localizations"] = {}
    assert verify_panorama_russian_metadata_readback(candidate, owner, playlist, after)["metadata_matches"]
    after.pop("localizations")
    assert not verify_panorama_russian_metadata_readback(candidate, owner, playlist, after)["metadata_matches"]
    with pytest.raises(ValueError, match="differs from bound"):
        verify_panorama_russian_metadata_readback({**candidate, "execution_authorized": True}, owner, playlist, after)
    with pytest.raises(ValueError, match="Missing exact candidate video ID"):
        verify_panorama_russian_metadata_readback({}, owner, playlist, after)
    after.pop("snippet")
    with pytest.raises(ValueError, match="Incomplete readback snippet"):
        verify_panorama_russian_metadata_readback(candidate, owner, playlist, after)


def test_panorama_inventory_counts_all_members_without_false_clean() -> None:
    from video_channel_manager.platforms.youtube.lord_god_presentation import inventory_panorama_russian_metadata

    owner, playlist = _russian_metadata_evidence()
    clean = copy.deepcopy(owner)
    clean["video_id"] = clean["raw"]["id"] = "video000001"
    clean["raw"]["localizations"] = {"ru": clean["raw"]["localizations"]["ru"]}
    clean["locale_keys"] = ["ru"]
    clean["revision"] = canonical_sha256(clean["raw"])
    malformed = copy.deepcopy(owner)
    malformed["video_id"] = malformed["raw"]["id"] = "video000002"
    malformed["raw"].pop("localizations")
    duplicate = copy.deepcopy(owner)
    duplicate["video_id"] = duplicate["raw"]["id"] = "video000003"
    duplicate["revision"] = canonical_sha256(duplicate["raw"])
    report = inventory_panorama_russian_metadata(playlist, [duplicate, clean, owner, malformed, duplicate])
    assert report["counts"] == {"REVIEW_REQUIRED": 1, "NO_CHANGE": 1, "MISSING": 64, "HOLD": 2}
    assert [row["episode"] for row in report["episodes"]] == list(range(1, 69))
    assert report["episodes"][3]["reason"] == "duplicate_owner_receipts"
    assert not report["all_receipts_reviewable"]
    assert not report["live_verified"] and not report["execution_authorized"]
    assert report["provider_reads"] == report["provider_writes"] == 0


def test_panorama_inventory_complete_and_foreign_receipt_rejected() -> None:
    from video_channel_manager.platforms.youtube.lord_god_presentation import inventory_panorama_russian_metadata

    owner, playlist = _russian_metadata_evidence()
    owners = []
    for member in playlist["memberships"]:
        receipt = copy.deepcopy(owner)
        receipt["video_id"] = receipt["raw"]["id"] = member["video_id"]
        receipt["revision"] = canonical_sha256(receipt["raw"])
        owners.append(receipt)
    report = inventory_panorama_russian_metadata(playlist, owners)
    assert report["counts"]["REVIEW_REQUIRED"] == 68
    assert report["all_receipts_reviewable"] and not report["live_verified"]
    with pytest.raises(ValueError, match="outside exact Panorama"):
        inventory_panorama_russian_metadata(playlist, [{**owner, "video_id": "other000000"}])


@pytest.mark.parametrize("mode", ["dry_run", "wrong_target", "wrong_review_sha", "wrong_after", "approved", "tampered"])
def test_panorama_cli_offline_review_and_exact_authority(tmp_path, monkeypatch, mode):
    from unittest.mock import Mock

    from typer.testing import CliRunner

    from video_channel_manager.cli import youtube as cli
    from video_channel_manager.platforms.youtube.lord_god_presentation import plan_panorama_russian_metadata

    owner, playlist = _russian_metadata_evidence()
    candidate = plan_panorama_russian_metadata(owner, playlist, video_id=owner["video_id"])
    review = {
        "schema": "panorama-russian-metadata-approval-v1",
        "candidate_sha256": canonical_sha256(candidate),
        "approved": True,
        "reviewer": "independent",
        "reviewed_at": "2026-11-25T12:00:00+00:00",
    }
    bundle = tmp_path / "bundle.json"
    review_file = tmp_path / "review.json"
    review_file.write_text(json.dumps(review), encoding="utf-8")
    if mode == "tampered":
        candidate["removed_locale_keys"] = []
    bundle.write_text(json.dumps({"owner": owner, "playlist": playlist, "candidate": candidate}), encoding="utf-8")
    writer = Mock()
    writer.reduce_panorama_localizations.return_value = {"status": "owner_verified_public_qa_pending"}
    components = Mock(return_value=(None, None, writer))
    monkeypatch.setattr(cli, "_writer_components", components)
    monkeypatch.setattr(cli, "prepare_windows_youtube_console", lambda: None)
    args = ["apply-panorama-russian-metadata", str(bundle), "--confirm-channel", LORD_GOD_OWNER_CHANNEL]
    if mode not in {"dry_run", "tampered"}:
        args.extend(
            [
                "--execute",
                "--confirm-target",
                "other000000" if mode == "wrong_target" else owner["video_id"],
                "--confirm-after-sha256",
                "wrong" if mode == "wrong_after" else candidate["after_sha256"],
                "--review",
                str(review_file),
                "--confirm-review-sha256",
                "wrong" if mode == "wrong_review_sha" else canonical_sha256(review),
            ]
        )
    result = CliRunner().invoke(cli.youtube_app, args)
    assert result.exit_code == (0 if mode in {"dry_run", "approved"} else 2), result.output
    if mode == "approved":
        components.assert_called_once()
        writer.reduce_panorama_localizations.assert_called_once()
        writer.close.assert_called_once()
    else:
        components.assert_not_called()
    if mode == "dry_run":
        assert '"provider_writes": 0' in result.output
