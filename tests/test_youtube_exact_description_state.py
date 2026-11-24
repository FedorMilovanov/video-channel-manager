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
