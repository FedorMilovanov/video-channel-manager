from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import pytest

from video_channel_manager.platforms.vk.wall import VkWallRecoveryRequired
from video_channel_manager.platforms.vk.wall_safety import (
    VkWallPostFingerprint,
    VkWallSnapshot,
    VkWallSurface,
)
from video_channel_manager.platforms.vk.wall_text_writer import VkWallTextWriter
from video_channel_manager.platforms.vk.writer import VkWriteError


def _sha(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _attachment(token: str) -> dict[str, object]:
    kind_and_owner, media_text = token.split("_", maxsplit=1)
    split_at = next(index for index, char in enumerate(kind_and_owner) if char in "-0123456789")
    kind = kind_and_owner[:split_at]
    owner_id = int(kind_and_owner[split_at:])
    return {
        "type": kind,
        kind: {"owner_id": owner_id, "id": int(media_text)},
    }


def _raw_post(
    *,
    post_id: int,
    text: str,
    publish_date: int,
    attachments: tuple[str, ...],
) -> dict[str, object]:
    return {
        "owner_id": -68859909,
        "id": post_id,
        "date": publish_date,
        "text": text,
        "attachments": [_attachment(token) for token in attachments],
    }


def _fingerprint(
    *,
    post_id: int = 500,
    surface: VkWallSurface = VkWallSurface.POSTPONED,
    publish_date: int = 1_786_900_000,
    text: str = "before exact",
    attachments: tuple[str, ...] = ("photo-68859909_900", "video-68859909_456239240"),
) -> VkWallPostFingerprint:
    return VkWallPostFingerprint(
        owner_id=-68859909,
        post_id=post_id,
        surface=surface,
        publish_date=publish_date,
        text_sha256=_sha(text),
        attachments=tuple(sorted(attachments)),
    )


def _snapshot(post: VkWallPostFingerprint) -> VkWallSnapshot:
    return VkWallSnapshot(
        community_id=68859909,
        captured_at="2026-08-16T17:10:00+00:00",
        complete=True,
        published_pages=1,
        postponed_pages=1,
        posts=(post,),
    )


class _FakeWallWriter:
    def __init__(
        self,
        *,
        snapshots: tuple[VkWallSnapshot, ...],
        posts: tuple[dict[str, object] | None, ...],
        call_error: VkWriteError | None = None,
    ) -> None:
        self._snapshots = iter(snapshots)
        self._posts = iter(posts)
        self._call_error = call_error
        self.calls: list[tuple[str, dict[str, Any], bool]] = []

    def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int) -> VkWallSnapshot:
        assert community_id == 68859909
        assert max_posts_per_surface == 10000
        return next(self._snapshots)

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        assert community_id == 68859909
        assert post_id > 0
        value = next(self._posts)
        return dict(value) if value is not None else None

    def _call(self, method: str, *, params: Mapping[str, Any], retry_transient: bool) -> int:
        self.calls.append((method, dict(params), retry_transient))
        if self._call_error is not None:
            raise self._call_error
        return 1


def _run(
    writer: _FakeWallWriter,
    *,
    expected: VkWallPostFingerprint,
    before_text: str,
    after_text: str,
):
    return VkWallTextWriter.replace_message_if_current(  # type: ignore[arg-type]
        writer,
        expected=expected,
        before_text=before_text,
        after_text=after_text,
    )


def test_postponed_exact_edit_preserves_raw_attachment_order_and_publish_date() -> None:
    before_text = "before exact"
    after_text = "after exact"
    raw_order = ("video-68859909_456239240", "photo-68859909_900")
    expected = _fingerprint(text=before_text, attachments=raw_order)
    expected_after = VkWallPostFingerprint(
        owner_id=expected.owner_id,
        post_id=expected.post_id,
        surface=expected.surface,
        publish_date=expected.publish_date,
        text_sha256=_sha(after_text),
        attachments=expected.attachments,
    )
    writer = _FakeWallWriter(
        snapshots=(_snapshot(expected), _snapshot(expected_after)),
        posts=(
            _raw_post(
                post_id=expected.post_id,
                text=before_text,
                publish_date=expected.publish_date or 0,
                attachments=raw_order,
            ),
            _raw_post(
                post_id=expected.post_id,
                text=after_text,
                publish_date=expected.publish_date or 0,
                attachments=raw_order,
            ),
        ),
    )

    result = _run(writer, expected=expected, before_text=before_text, after_text=after_text)

    assert result.remote_id == expected.remote_id
    assert result.provider_writes_executed == 1
    assert result.attachments == raw_order
    assert writer.calls == [
        (
            "wall.edit",
            {
                "owner_id": expected.owner_id,
                "post_id": expected.post_id,
                "message": after_text,
                "attachments": ",".join(raw_order),
                "publish_date": expected.publish_date,
            },
            False,
        )
    ]


def test_published_exact_edit_omits_publish_date_but_preserves_attachments() -> None:
    before_text = "published before"
    after_text = "published after"
    raw_order = ("video-68859909_456239240",)
    expected = _fingerprint(
        surface=VkWallSurface.PUBLISHED,
        text=before_text,
        attachments=raw_order,
    )
    expected_after = VkWallPostFingerprint(
        owner_id=expected.owner_id,
        post_id=expected.post_id,
        surface=expected.surface,
        publish_date=expected.publish_date,
        text_sha256=_sha(after_text),
        attachments=expected.attachments,
    )
    writer = _FakeWallWriter(
        snapshots=(_snapshot(expected), _snapshot(expected_after)),
        posts=(
            _raw_post(
                post_id=expected.post_id,
                text=before_text,
                publish_date=expected.publish_date or 0,
                attachments=raw_order,
            ),
            _raw_post(
                post_id=expected.post_id,
                text=after_text,
                publish_date=expected.publish_date or 0,
                attachments=raw_order,
            ),
        ),
    )

    _run(writer, expected=expected, before_text=before_text, after_text=after_text)

    assert "publish_date" not in writer.calls[0][1]
    assert writer.calls[0][1]["attachments"] == raw_order[0]
    assert writer.calls[0][2] is False


def test_preflight_wall_incarnation_drift_blocks_before_provider_write() -> None:
    expected = _fingerprint(text="reviewed before")
    drifted = VkWallPostFingerprint(
        owner_id=expected.owner_id,
        post_id=expected.post_id,
        surface=expected.surface,
        publish_date=expected.publish_date,
        text_sha256=_sha("manual drift"),
        attachments=expected.attachments,
    )
    writer = _FakeWallWriter(snapshots=(_snapshot(drifted),), posts=())

    with pytest.raises(VkWriteError, match="changed before edit"):
        _run(writer, expected=expected, before_text="reviewed before", after_text="reviewed after")

    assert writer.calls == []


def test_unstable_raw_attachment_identity_blocks_before_provider_write() -> None:
    before_text = "before exact"
    expected = _fingerprint(text=before_text, attachments=("video-68859909_456239240",))
    malformed = _raw_post(
        post_id=expected.post_id,
        text=before_text,
        publish_date=expected.publish_date or 0,
        attachments=(),
    )
    malformed["attachments"] = [{"type": "link", "link": {"url": "https://example.invalid"}}]
    writer = _FakeWallWriter(
        snapshots=(_snapshot(expected),),
        posts=(malformed,),
    )

    with pytest.raises((ValueError, VkWriteError)):
        _run(writer, expected=expected, before_text=before_text, after_text="after exact")

    assert writer.calls == []


def test_ambiguous_wall_edit_response_requires_reconciliation_without_replay() -> None:
    before_text = "before exact"
    after_text = "after exact"
    raw_order = ("video-68859909_456239240",)
    expected = _fingerprint(text=before_text, attachments=raw_order)
    writer = _FakeWallWriter(
        snapshots=(_snapshot(expected),),
        posts=(
            _raw_post(
                post_id=expected.post_id,
                text=before_text,
                publish_date=expected.publish_date or 0,
                attachments=raw_order,
            ),
        ),
        call_error=VkWriteError("lost wall.edit response", method="wall.edit"),
    )

    with pytest.raises(VkWallRecoveryRequired, match="blind retry is forbidden"):
        _run(writer, expected=expected, before_text=before_text, after_text=after_text)

    assert len(writer.calls) == 1
    assert writer.calls[0][0] == "wall.edit"
    assert writer.calls[0][2] is False


def test_postflight_surface_drift_requires_reconciliation_without_retry() -> None:
    before_text = "before exact"
    after_text = "after exact"
    raw_order = ("video-68859909_456239240",)
    expected = _fingerprint(text=before_text, attachments=raw_order)
    moved_after = VkWallPostFingerprint(
        owner_id=expected.owner_id,
        post_id=expected.post_id,
        surface=VkWallSurface.PUBLISHED,
        publish_date=expected.publish_date,
        text_sha256=_sha(after_text),
        attachments=expected.attachments,
    )
    writer = _FakeWallWriter(
        snapshots=(_snapshot(expected), _snapshot(moved_after)),
        posts=(
            _raw_post(
                post_id=expected.post_id,
                text=before_text,
                publish_date=expected.publish_date or 0,
                attachments=raw_order,
            ),
        ),
    )

    with pytest.raises(VkWallRecoveryRequired, match="postflight"):
        _run(writer, expected=expected, before_text=before_text, after_text=after_text)

    assert len(writer.calls) == 1
    assert writer.calls[0][0] == "wall.edit"
    assert writer.calls[0][2] is False


def test_postflight_attachment_order_change_requires_reconciliation() -> None:
    before_text = "before exact"
    after_text = "after exact"
    raw_order = ("video-68859909_456239240", "photo-68859909_900")
    expected = _fingerprint(text=before_text, attachments=raw_order)
    expected_after = VkWallPostFingerprint(
        owner_id=expected.owner_id,
        post_id=expected.post_id,
        surface=expected.surface,
        publish_date=expected.publish_date,
        text_sha256=_sha(after_text),
        attachments=expected.attachments,
    )
    writer = _FakeWallWriter(
        snapshots=(_snapshot(expected), _snapshot(expected_after)),
        posts=(
            _raw_post(
                post_id=expected.post_id,
                text=before_text,
                publish_date=expected.publish_date or 0,
                attachments=raw_order,
            ),
            _raw_post(
                post_id=expected.post_id,
                text=after_text,
                publish_date=expected.publish_date or 0,
                attachments=tuple(reversed(raw_order)),
            ),
        ),
    )

    with pytest.raises(VkWallRecoveryRequired, match="ordering"):
        _run(writer, expected=expected, before_text=before_text, after_text=after_text)

    assert len(writer.calls) == 1
