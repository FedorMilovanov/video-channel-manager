"""Provider-free tests for opt-in exact description state guards."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from video_channel_manager.platforms.youtube.copy_execution import preflight_copy_operations
from video_channel_manager.platforms.youtube.writer import (
    YouTubeDescriptionWriter,
    YouTubeRevisionConflictError,
    YouTubeWriteError,
    VideoDescriptionSnapshot,
)


@pytest.mark.parametrize(
    ("description", "revision"),
    [("Before ", "rev"), ("Before", "other"), ("After", "rev")],
)
def test_strict_copy_preflight_refuses_drift_or_unreconciled_after(description, revision):
    writer = Mock()
    writer.read_description.return_value = SimpleNamespace(
        channel_id="owner", title="Title", description=description, revision=revision
    )
    operation = {
        "video_id": "video",
        "channel_id": "owner",
        "title": "Title",
        "expected_revision": "rev",
        "before_description": "Before",
        "after_description": "After",
    }
    with pytest.raises(YouTubeRevisionConflictError):
        preflight_copy_operations([operation], confirm_channel="owner", writer=writer, require_exact_state=True)


@pytest.mark.parametrize(("description", "revision"), [("Before ", "rev"), ("Before", "other")])
def test_strict_writer_refuses_drift_before_put(description, revision):
    writer = Mock()
    writer.read_description.return_value = SimpleNamespace(
        channel_id="owner", description=description, revision=revision
    )
    with pytest.raises(YouTubeRevisionConflictError):
        YouTubeDescriptionWriter.replace_description(
            writer,
            video_id="video",
            expected_channel_id="owner",
            expected_revision="rev",
            expected_description="Before",
            new_description="After",
            require_exact_state=True,
        )
    writer._write_description.assert_not_called()


def test_strict_writer_passes_exact_state_to_existing_dispatch():
    writer = Mock()
    current = SimpleNamespace(channel_id="owner", description="Before", revision="rev")
    writer.read_description.return_value = current
    YouTubeDescriptionWriter.replace_description(
        writer,
        video_id="video",
        expected_channel_id="owner",
        expected_revision="rev",
        expected_description="Before",
        new_description="After",
        require_exact_state=True,
    )
    writer._write_description.assert_called_once_with(
        current=current,
        new_description="After",
        require_exact_state=True,
    )


def _snapshot(raw):
    return VideoDescriptionSnapshot(
        video_id=raw["id"],
        channel_id=raw["snippet"]["channelId"],
        title=raw["snippet"]["title"],
        description=raw["snippet"]["description"],
        revision="rev",
        raw=raw,
    )


def _raw():
    return {
        "id": "video",
        "snippet": {
            "channelId": "owner",
            "title": "Title",
            "categoryId": "27",
            "description": "Before",
            "tags": ["tag"],
            "defaultLanguage": "ru",
            "defaultAudioLanguage": "ru",
        },
        "contentDetails": {"duration": "PT2H"},
        "status": {"privacyStatus": "public", "license": "youtube"},
        "localizations": {
            "ru": {"title": "Title", "description": "Before"},
            "en": {"title": "English", "description": "English unchanged"},
        },
    }


@pytest.mark.parametrize(
    "case",
    [
        "success",
        "locale_drift",
        "description_drift",
        "status_drift",
        "duration_drift",
        "missing_tags",
        "ambiguous_put",
        "postflight_unavailable",
    ],
)
def test_strict_existing_dispatch_is_single_put_with_exact_postflight(case):
    writer = Mock()
    writer._quota_guard = None
    writer.retry_policy.max_attempts = 1
    raw = _raw()
    after = deepcopy(raw)
    after["snippet"]["description"] = "After"
    after["localizations"]["ru"]["description"] = "After"
    if case == "locale_drift":
        after["localizations"]["en"]["description"] += " "
    elif case == "description_drift":
        after["snippet"]["description"] += " "
    elif case == "status_drift":
        after["status"]["license"] = "creativeCommon"
    elif case == "duration_drift":
        after["contentDetails"]["duration"] = "PT1H"
    elif case == "missing_tags":
        after["snippet"].pop("tags")
    elif case == "ambiguous_put":
        writer._request.side_effect = YouTubeWriteError("ambiguous mutation")
    elif case == "postflight_unavailable":
        writer.read_description.side_effect = YouTubeWriteError("read unavailable")
    writer.read_description.return_value = _snapshot(after)
    args = dict(current=_snapshot(raw), new_description="After", require_exact_state=True)
    if case == "success":
        result = YouTubeDescriptionWriter._write_description(writer, **args)
        assert result.raw == after
    else:
        with pytest.raises(YouTubeWriteError):
            YouTubeDescriptionWriter._write_description(writer, **args)
    writer._request.assert_called_once()
    assert writer._request.call_args.args == ("PUT", "videos")
    body = writer._request.call_args.kwargs["json_body"]
    assert body["localizations"] == {
        "ru": {"title": "Title", "description": "After"},
        "en": raw["localizations"]["en"],
    }
    assert body["snippet"]["tags"] == raw["snippet"]["tags"]
    if case == "ambiguous_put":
        writer.read_description.assert_not_called()
    else:
        writer.read_description.assert_called_once_with("video")


@pytest.mark.parametrize("case", ["missing_localizations", "primary_drift", "missing_tags", "missing_duration"])
def test_strict_dispatch_refuses_incomplete_metadata_before_put(case):
    writer = Mock()
    raw = _raw()
    if case == "missing_localizations":
        raw.pop("localizations")
    elif case == "primary_drift":
        raw["localizations"]["ru"]["description"] = "Independent edit"
    elif case == "missing_tags":
        raw["snippet"].pop("tags")
    else:
        raw["contentDetails"].pop("duration")
    with pytest.raises(YouTubeWriteError):
        YouTubeDescriptionWriter._write_description(
            writer, current=_snapshot(raw), new_description="After", require_exact_state=True
        )
    writer._request.assert_not_called()


def test_resilient_writer_strict_mode_never_falls_back_to_relaxed_verifier(monkeypatch):
    from video_channel_manager.platforms.youtube.resilient_writer import YouTubeDescriptionWriter as Resilient

    writer = Mock()
    call = Mock(side_effect=YouTubeWriteError("Verification failed after updating description for video."))
    monkeypatch.setattr(YouTubeDescriptionWriter, "_write_description", call)
    # Use a real subclass instance without constructing provider components.
    actual = object.__new__(Resilient)
    actual.read_description = writer.read_description
    current = _snapshot(_raw())
    with pytest.raises(YouTubeWriteError):
        actual._write_description(current=current, new_description="After", require_exact_state=True)
    call.assert_called_once_with(current=current, new_description="After", require_exact_state=True)
    writer.read_description.assert_not_called()


@pytest.mark.parametrize("case", ["unconfigured", "insufficient", "ready"])
def test_exact_outer_budget_covers_all_four_reads_and_put(tmp_path, case):
    from video_channel_manager.platforms.youtube.store import ProjectQuotaGuard
    import httpx

    guard = ProjectQuotaGuard(tmp_path / "quota.sqlite3", "fedor-milovanov")
    writer = object.__new__(YouTubeDescriptionWriter)
    writer._quota_guard = guard
    writer.retry_policy = Mock(max_attempts=2)
    if case != "unconfigured":
        guard.configure_day(
            day=guard.budget_status()["pacific_day"],
            allowances={"shared": 58 if case == "ready" else 57, "search": 0, "uploads": 0},
            evidence="synthetic console review",
        )
    if case != "ready":
        with pytest.raises(YouTubeWriteError, match="quota headroom"):
            with YouTubeDescriptionWriter.reserve_exact_description_execution(writer):
                pytest.fail("unreviewed or insufficient quota reached dispatch")
        assert guard.budget_status()["buckets"]["shared"]["estimated_units"] == 0
        return
    with YouTubeDescriptionWriter.reserve_exact_description_execution(writer):
        for _ in range(4):
            guard(lambda: httpx.Response(200), "GET", "videos")
        with guard.reserve(52):
            guard(lambda: httpx.Response(200), "PUT", "videos")
            guard(lambda: httpx.Response(200), "GET", "videos")
            guard(lambda: httpx.Response(200), "GET", "videos")
        for _ in range(2):
            guard(lambda: httpx.Response(200), "GET", "videos")
    shared = guard.budget_status()["buckets"]["shared"]
    assert shared == {"estimated_units": 58, "reserved_units": 0, "local_remaining": 0}


@pytest.mark.parametrize("stage", ["success", "put_unknown", "postflight", "quota_block"])
def test_historical_cli_never_rolls_back_or_replays(tmp_path, monkeypatch, stage):
    import json
    from contextlib import contextmanager
    from types import SimpleNamespace

    import typer
    from video_channel_manager.cli import youtube as cli
    from video_channel_manager.platforms.youtube.copy_plan import finalize_copy_plan, sha256_text
    from video_channel_manager.platforms.youtube.panorama_format_release import FORMAT_RULESET, format_intent_path
    from video_channel_manager.platforms.youtube.lord_god_source_preservation import LORD_GOD_OWNER_CHANNEL

    vid = "e5d1zaJWAoQ"
    op = {
        "operation": "replace_video_description",
        "platform": "youtube",
        "ruleset": FORMAT_RULESET,
        "video_id": vid,
        "channel_id": LORD_GOD_OWNER_CHANNEL,
        "title": "Title",
        "expected_revision": "rev",
        "before_description": "Before",
        "after_description": "After",
        "before_sha256": sha256_text("Before"),
        "after_sha256": sha256_text("After"),
    }
    plan = {
        "ruleset": FORMAT_RULESET,
        "target_channel_id": LORD_GOD_OWNER_CHANNEL,
        "project_key": "lord-god-strength",
        "source_audit_sha256": "sha256:test",
        "source_chapter_review_sha256": "sha256:review",
        "videos_checked": 1,
        "operations_count": 1,
        "unresolved_error_videos": 0,
        "operations": [op],
        "unresolved": [],
    }
    finalize_copy_plan(plan, checked_video_ids=[vid])
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    marker = format_intent_path(tmp_path, vid)
    backup, receipt = tmp_path / "backup.json", tmp_path / "receipt.json"
    writer = Mock()
    events = []

    @contextmanager
    def budget():
        events.append("reserve")
        if stage == "quota_block":
            raise YouTubeWriteError("no quota")
        yield
        events.append("release")

    writer.reserve_exact_description_execution.side_effect = budget
    before = _raw()
    before["id"] = vid
    before["snippet"]["channelId"] = LORD_GOD_OWNER_CHANNEL
    after = deepcopy(before)
    after["snippet"]["description"] = "After"
    after["localizations"]["ru"]["description"] = "After"
    if stage == "postflight":
        after["localizations"]["en"]["description"] += " "

    def preflight(operations, **kwargs):
        assert events == ["reserve"] and kwargs["require_exact_state"]
        events.append("preflight")
        return SimpleNamespace(prepared=operations, already_applied=0, revision_drift_tolerated=0)

    def replace(**kwargs):
        assert marker.is_file() and backup.is_file() and receipt.is_file()
        assert json.loads(receipt.read_text(encoding="utf-8"))["attempted"][0]["status"] == "attempting"
        assert kwargs["require_exact_state"]
        events.append("PUT")
        if stage == "put_unknown":
            raise YouTubeWriteError("ambiguous response")
        good = deepcopy(after)
        good["localizations"]["en"]["description"] = "English unchanged"
        return _snapshot(good)

    writer.replace_description.side_effect = replace
    writer.read_description.return_value = _snapshot(after)
    store = SimpleNamespace(load_token=lambda _: SimpleNamespace(scopes=[cli.YOUTUBE_FORCE_SSL_SCOPE]))
    monkeypatch.setattr(cli, "prepare_windows_youtube_console", lambda: None)
    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))
    # Real immutable-plan rederivation is exercised by the semantic chapter tests.
    monkeypatch.setattr(cli, "require_lord_god_youtube_presentation", lambda _: None)
    monkeypatch.setattr(cli, "require_chapter_release", lambda *a, **k: None)
    monkeypatch.setattr(cli, "_writer_components", lambda *_: (store, None, writer))
    monkeypatch.setattr(cli, "preflight_copy_operations", preflight)
    args = dict(
        plan=plan_path,
        account="fedor-milovanov",
        confirm_channel=LORD_GOD_OWNER_CHANNEL,
        execute=True,
        confirm_target=vid,
        confirm_after_sha256=op["after_sha256"],
        confirm_chapter_review_sha256=plan["source_chapter_review_sha256"],
        max_operations=1,
        backup_output=backup,
        result_output=receipt,
    )
    if stage == "success":
        cli.apply_copy_fixes(**args)
        assert json.loads(receipt.read_text(encoding="utf-8"))["status"] == "owner_verified_public_qa_pending"
    else:
        with pytest.raises(typer.Exit):
            cli.apply_copy_fixes(**args)
        if stage == "quota_block":
            assert not marker.exists()
            writer.replace_description.assert_not_called()
            return
        assert json.loads(receipt.read_text(encoding="utf-8"))["status"] == "pending_reconciliation"
    writer.replace_description.assert_called_once()
    writer.restore_description_if_current.assert_not_called()
    assert marker.is_file()
    args.update(backup_output=tmp_path / "new-backup.json", result_output=tmp_path / "new-receipt.json")
    with pytest.raises(typer.Exit):
        cli.apply_copy_fixes(**args)
    writer.replace_description.assert_called_once()
    assert not args["backup_output"].exists()


@pytest.mark.parametrize(
    "description,expected", [("After", "live_after"), ("After ", "live_third_state"), ("Before", "live_before")]
)
def test_exact_reconcile_preserves_byte_identity_and_never_grants_replay(description, expected):
    from video_channel_manager.platforms.youtube.copy_execution import reconcile_copy_operations

    writer = Mock()
    writer.read_description.return_value = SimpleNamespace(channel_id="owner", title="Title", description=description)
    operation = {
        "video_id": "video",
        "channel_id": "owner",
        "before_description": "Before",
        "after_description": "After",
    }
    rows = reconcile_copy_operations([operation], confirm_channel="owner", writer=writer, require_exact_state=True)
    assert rows[0]["state"] == expected
    assert rows[0]["safe_to_replay"] is False
    writer.replace_description.assert_not_called()


@pytest.mark.parametrize("keys", [[], ["ru"], ["ru", "ru-RU"], ["ru-RU"]])
def test_chapter_description_write_preserves_reduced_locale_keys(keys):
    writer = Mock()
    writer._quota_guard = None
    writer.retry_policy.max_attempts = 1
    raw = _raw()
    raw["localizations"] = {key: deepcopy(raw["localizations"]["ru"]) for key in keys}
    after = deepcopy(raw)
    after["snippet"]["description"] = "After"
    for locale in after["localizations"].values():
        locale["description"] = "After"
    writer.read_description.return_value = _snapshot(after)
    observed = YouTubeDescriptionWriter._write_description(
        writer, current=_snapshot(raw), new_description="After", require_exact_state=True
    )
    assert observed.raw == after
    writer._request.assert_called_once()
    assert writer._request.call_args.kwargs["json_body"]["localizations"] == after["localizations"]
    assert writer._request.call_args.kwargs["params"] == {"part": "snippet,localizations"}
