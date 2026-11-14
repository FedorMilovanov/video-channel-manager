from __future__ import annotations

from pathlib import Path

import pytest

from video_channel_manager.youtube_upload_plan import (
    UploadPlanError,
    abandon_planned_journal,
    build_intent,
    intent_digest,
    journal_path,
    planned_journal,
    require_new_plan_allowed,
    stable_upload_key,
    validate_intent,
)


CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"


def _spec(media_sha256: str, *, title: str = "Black Man") -> dict[str, object]:
    return {
        "schema_name": "video-manager.youtube-video-upload-spec",
        "schema_version": "2.0",
        "project_key": "legendary-poet",
        "account_alias": "legendary-poet",
        "target_channel_id": CHANNEL_ID,
        "expected_media_sha256": media_sha256,
        "title": title,
        "description": "Provider-inert planning fixture",
        "tags": ["Есенин", "Чёрный человек"],
        "category_id": "10",
        "default_language": "ru",
        "privacy_status": "private",
        "contains_synthetic_media": True,
    }


def _media(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / "album.mp4"
    path.write_bytes(b"exact-black-man-render-bytes")
    import hashlib

    return path, "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_stable_upload_key_ignores_timestamp_and_metadata(tmp_path: Path) -> None:
    media, media_sha = _media(tmp_path)
    first = build_intent(_spec(media_sha, title="First title"), media, created_at="2026-08-09T00:00:00+00:00")
    second = build_intent(_spec(media_sha, title="Retitled"), media, created_at="2026-08-09T01:00:00+00:00")

    assert first["upload_key_sha256"] == second["upload_key_sha256"]
    assert first["intent_sha256"] != second["intent_sha256"]
    assert first["upload_key_sha256"] == stable_upload_key(
        project_key="legendary-poet",
        target_channel_id=CHANNEL_ID,
        media_sha256=media_sha,
    )


def test_same_media_replan_cannot_escape_planned_stable_journal(tmp_path: Path) -> None:
    media, media_sha = _media(tmp_path)
    first = build_intent(_spec(media_sha), media, created_at="2026-08-09T00:00:00+00:00")
    second = build_intent(_spec(media_sha, title="Changed metadata"), media, created_at="2026-08-09T02:00:00+00:00")
    journal = planned_journal(first, now="2026-08-09T00:01:00+00:00")

    with pytest.raises(UploadPlanError, match="Existing stable upload journal blocks a new plan"):
        require_new_plan_allowed(journal, intent=second)


def test_may_exist_or_verified_journal_blocks_same_media_replan(tmp_path: Path) -> None:
    media, media_sha = _media(tmp_path)
    intent = build_intent(_spec(media_sha), media, created_at="2026-08-09T00:00:00+00:00")
    journal = planned_journal(intent)

    for state, effect in (("session_unknown", "may_exist"), ("verified", "verified")):
        blocked = dict(journal, state=state, provider_effect=effect)
        with pytest.raises(UploadPlanError, match="blocks a new plan"):
            require_new_plan_allowed(blocked, intent=intent)


def test_abandon_is_only_safe_local_replan_release(tmp_path: Path) -> None:
    media, media_sha = _media(tmp_path)
    intent = build_intent(_spec(media_sha), media, created_at="2026-08-09T00:00:00+00:00")
    journal = planned_journal(intent, now="2026-08-09T00:01:00+00:00")

    abandoned = abandon_planned_journal(journal, intent=intent, now="2026-08-09T00:02:00+00:00")

    assert abandoned["state"] == "abandoned"
    assert abandoned["provider_effect"] == "confirmed_absent"
    require_new_plan_allowed(abandoned, intent=intent)


def test_old_intent_schema_fails_closed(tmp_path: Path) -> None:
    media, media_sha = _media(tmp_path)
    intent = build_intent(_spec(media_sha), media)
    intent["schema_version"] = "1.0"
    intent["intent_sha256"] = intent_digest(intent)

    with pytest.raises(UploadPlanError, match="Unsupported upload intent schema"):
        validate_intent(intent)


def test_cross_project_identity_fails_before_media_planning(tmp_path: Path) -> None:
    media, media_sha = _media(tmp_path)
    spec = _spec(media_sha)
    spec["account_alias"] = "fedor-milovanov"

    with pytest.raises(ValueError, match="OAuth alias differs from canonical project identity"):
        build_intent(spec, media)


def test_provider_authorization_cannot_be_smuggled_into_v2_intent(tmp_path: Path) -> None:
    media, media_sha = _media(tmp_path)
    intent = build_intent(_spec(media_sha), media)
    intent["provider_write_authorized"] = True
    intent["intent_sha256"] = intent_digest(intent)

    with pytest.raises(UploadPlanError, match="must remain provider_write_authorized=false"):
        validate_intent(intent)


def test_journal_path_uses_stable_key_not_attempt_digest(tmp_path: Path) -> None:
    media, media_sha = _media(tmp_path)
    first = build_intent(_spec(media_sha), media, created_at="2026-08-09T00:00:00+00:00")
    second = build_intent(_spec(media_sha), media, created_at="2026-08-09T00:00:01+00:00")

    first_path = journal_path(tmp_path, str(first["upload_key_sha256"]))
    second_path = journal_path(tmp_path, str(second["upload_key_sha256"]))

    assert first_path == second_path
    assert str(first["intent_sha256"]).removeprefix("sha256:") not in first_path.name


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("description", "Playlist: https://youtube.com/playlist?list=PASTE-YESENIN-PLAYLIST-ID"),
        ("title", "The poet | YOUR_VIDEO_LINK"),
        ("tags", ["Есенин", "INSERT-PLAYLIST-URL"]),
        ("description", "Link: replace_my_playlist_id"),
        ("description", "REPLACE_ME"),
    ],
)
def test_unresolved_metadata_templates_fail_before_media_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, invalid_value: object
) -> None:
    media, media_sha = _media(tmp_path)
    spec = _spec(media_sha)
    spec[field] = invalid_value

    def forbidden_digest(_path: Path) -> str:
        pytest.fail("Unresolved metadata must fail before any media byte read")

    monkeypatch.setattr("video_channel_manager.youtube_upload_plan.sha256_file", forbidden_digest)
    with pytest.raises(UploadPlanError, match="Unresolved metadata placeholder"):
        build_intent(spec, media)


def test_resigned_upload_intent_cannot_smuggle_unresolved_template(tmp_path: Path) -> None:
    media, media_sha = _media(tmp_path)
    intent = build_intent(_spec(media_sha), media)
    intent["snippet"]["description"] = "Playlist: https://youtube.com/playlist?list=PASTE-YESENIN-PLAYLIST-ID"
    intent["intent_sha256"] = intent_digest(intent)

    with pytest.raises(UploadPlanError, match="Unresolved metadata placeholder in description"):
        validate_intent(intent)


def test_natural_description_words_do_not_trigger_template_guard(tmp_path: Path) -> None:
    media, media_sha = _media(tmp_path)
    spec = _spec(media_sha)
    spec["description"] = "Your link to the poet is here; paste the text into the discussion."
    spec["tags"] = ["Есенин", "Ссылка на литературный архив"]
    intent = build_intent(spec, media)
    validate_intent(intent)


@pytest.mark.parametrize(
    ("invalid_field", "invalid_value", "expected_message"),
    [
        ("snippet", None, "snippet must be a metadata object"),
        ("title", None, "title or description is invalid"),
        ("title", "   ", "title or description is invalid"),
        ("description", 17, "title or description is invalid"),
        ("tags", "Есенин", "tags must contain non-empty strings"),
        ("tags", ["Есенин", ""], "tags must contain non-empty strings"),
    ],
)
def test_resigned_upload_intent_rejects_invalid_metadata_structure(
    tmp_path: Path, invalid_field: str, invalid_value: object, expected_message: str
) -> None:
    media, media_sha = _media(tmp_path)
    intent = build_intent(_spec(media_sha), media)
    if invalid_field == "snippet":
        intent["snippet"] = invalid_value
    else:
        intent["snippet"][invalid_field] = invalid_value
    intent["intent_sha256"] = intent_digest(intent)

    with pytest.raises(UploadPlanError, match=expected_message):
        validate_intent(intent)


@pytest.mark.parametrize(
    "blocked_copy",
    [
        "This is REVIEW_ONLY_NO_UPLOAD; not a YouTube description.",
        "SOURCE_DATE_CORRECTED_REVIEW_ONLY_NO_UPLOAD",
        "NOT_FOR_PUBLICATION: awaiting owner approval.",
        "PUBLICATION_BLOCKED: legal review.",
        "Письменное разрешение пока не подтверждено.",
    ],
)
def test_internal_publication_hold_never_becomes_public_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, blocked_copy: str
) -> None:
    media, media_sha = _media(tmp_path)
    spec = _spec(media_sha)
    spec["description"] = blocked_copy

    def forbidden_digest(_path: Path) -> str:
        pytest.fail("An internal release hold must be rejected before reading media bytes.")

    monkeypatch.setattr("video_channel_manager.youtube_upload_plan.sha256_file", forbidden_digest)
    with pytest.raises(UploadPlanError, match="Publication hold marker in public metadata description"):
        build_intent(spec, media)


def test_public_source_attribution_not_confused_with_internal_hold(tmp_path: Path) -> None:
    media, media_sha = _media(tmp_path)
    spec = _spec(media_sha)
    spec["description"] = "Paul Washer preaching; original source and credit appear below."
    validate_intent(build_intent(spec, media))
