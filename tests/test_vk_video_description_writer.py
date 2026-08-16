from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from video_channel_manager.platforms.vk.video_description_writer import (
    VkVideoDescriptionRecoveryRequired,
    VkVideoDescriptionWriter,
)
from video_channel_manager.platforms.vk.writer import VkWriteError


OWNER_ID = -68859909
VIDEO_ID = 456239232
TITLE = "Exact Clip title"


def _clip(
    description: str,
    *,
    title: str = TITLE,
    video_type: str = "short_video",
    owner_id: int = OWNER_ID,
    video_id: int = VIDEO_ID,
) -> dict[str, Any]:
    return {
        "owner_id": owner_id,
        "id": video_id,
        "type": video_type,
        "title": title,
        "description": description,
    }


class _FakeVideoDescriptionWriter:
    def __init__(
        self,
        *,
        reads: tuple[dict[str, Any] | None | VkWriteError, ...],
        call_error: VkWriteError | None = None,
    ) -> None:
        self._reads = iter(reads)
        self._call_error = call_error
        self.calls: list[tuple[str, dict[str, Any], bool]] = []

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        assert owner_id == OWNER_ID
        assert video_id == VIDEO_ID
        value = next(self._reads)
        if isinstance(value, VkWriteError):
            raise value
        return dict(value) if value is not None else None

    def _call(self, method: str, *, params: Mapping[str, Any], retry_transient: bool) -> int:
        self.calls.append((method, dict(params), retry_transient))
        if self._call_error is not None:
            raise self._call_error
        return 1


def _run(
    writer: _FakeVideoDescriptionWriter,
    *,
    before: str,
    after: str,
    verification_attempts: int = 1,
):
    return VkVideoDescriptionWriter.replace_description_if_current(  # type: ignore[arg-type]
        writer,
        owner_id=OWNER_ID,
        video_id=VIDEO_ID,
        expected_description=before,
        new_description=after,
        verification_attempts=verification_attempts,
        verification_delay_seconds=0,
    )


def test_exact_clip_description_edit_preserves_target_text_without_normalization() -> None:
    before = "  reviewed BEFORE\nline two\u200b  "
    after = "  reviewed AFTER\r\nline two\u200b  \n"
    writer = _FakeVideoDescriptionWriter(reads=(_clip(before), _clip(after)))

    result = _run(writer, before=before, after=after)

    assert result.remote_id == f"{OWNER_ID}_{VIDEO_ID}"
    assert result.title == TITLE
    assert result.video_type == "short_video"
    assert result.provider_writes_executed == 1
    assert writer.calls == [
        (
            "video.edit",
            {
                "owner_id": OWNER_ID,
                "video_id": VIDEO_ID,
                "desc": after,
            },
            False,
        )
    ]


def test_whitespace_drift_in_before_description_blocks_before_write() -> None:
    reviewed_before = "reviewed BEFORE\n"
    writer = _FakeVideoDescriptionWriter(reads=(_clip("reviewed BEFORE"),))

    with pytest.raises(VkWriteError, match="exact reviewed BEFORE"):
        _run(writer, before=reviewed_before, after="reviewed AFTER")

    assert writer.calls == []


def test_non_short_video_blocks_before_write() -> None:
    before = "reviewed BEFORE"
    writer = _FakeVideoDescriptionWriter(reads=(_clip(before, video_type="video"),))

    with pytest.raises(VkWriteError, match="short_video"):
        _run(writer, before=before, after="reviewed AFTER")

    assert writer.calls == []


def test_ambiguous_video_edit_response_requires_reconciliation_without_replay() -> None:
    before = "reviewed BEFORE"
    writer = _FakeVideoDescriptionWriter(
        reads=(_clip(before),),
        call_error=VkWriteError("lost video.edit response", method="video.edit"),
    )

    with pytest.raises(VkVideoDescriptionRecoveryRequired, match="blind retry is forbidden"):
        _run(writer, before=before, after="reviewed AFTER")

    assert len(writer.calls) == 1
    assert writer.calls[0][0] == "video.edit"
    assert writer.calls[0][2] is False


def test_postflight_title_drift_requires_reconciliation_after_one_write() -> None:
    before = "reviewed BEFORE"
    after = "reviewed AFTER"
    writer = _FakeVideoDescriptionWriter(
        reads=(
            _clip(before),
            _clip(after, title="Provider changed title"),
        )
    )

    with pytest.raises(VkVideoDescriptionRecoveryRequired, match="postflight"):
        _run(writer, before=before, after=after)

    assert len(writer.calls) == 1


def test_postflight_read_failure_never_replays_video_edit() -> None:
    before = "reviewed BEFORE"
    writer = _FakeVideoDescriptionWriter(
        reads=(
            _clip(before),
            VkWriteError("transient video.get failed", method="video.get", retryable=True),
        )
    )

    with pytest.raises(VkVideoDescriptionRecoveryRequired, match="blind retry is forbidden"):
        _run(writer, before=before, after="reviewed AFTER")

    assert len(writer.calls) == 1


def test_exact_postflight_is_required_before_final_success() -> None:
    before = "reviewed BEFORE"
    after = "reviewed AFTER"
    writer = _FakeVideoDescriptionWriter(
        reads=(
            _clip(before),
            _clip("stale provider projection"),
            _clip(after),
        )
    )

    result = _run(writer, before=before, after=after, verification_attempts=2)

    assert result.remote_id == f"{OWNER_ID}_{VIDEO_ID}"
    assert result.title == TITLE
    assert len(writer.calls) == 1
