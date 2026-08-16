from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import pytest

from video_channel_manager.platforms.vk.wall_safety import VkWallPostFingerprint, VkWallSnapshot, VkWallSurface
from video_channel_manager.platforms.vk.wall_text_writer import VkWallTextWriter


def _sha(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


class _HookBoundaryWriter:
    def __init__(self, *, expected: VkWallPostFingerprint, before_text: str) -> None:
        self.expected = expected
        self.before_text = before_text
        self.snapshot_reads = 0
        self.post_reads = 0
        self.provider_calls = 0

    def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int) -> VkWallSnapshot:
        assert community_id == 68859909
        assert max_posts_per_surface == 10000
        self.snapshot_reads += 1
        return VkWallSnapshot(
            community_id=community_id,
            captured_at="2026-08-16T20:00:00+00:00",
            complete=True,
            published_pages=1,
            postponed_pages=1,
            posts=(self.expected,),
        )

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any]:
        assert community_id == 68859909
        assert post_id == self.expected.post_id
        self.post_reads += 1
        return {
            "owner_id": self.expected.owner_id,
            "id": self.expected.post_id,
            "date": self.expected.publish_date,
            "text": self.before_text,
            "attachments": [
                {
                    "type": "video",
                    "video": {"owner_id": -68859909, "id": 456239232},
                }
            ],
        }

    def _call(self, method: str, *, params: Mapping[str, Any], retry_transient: bool) -> int:
        self.provider_calls += 1
        raise AssertionError(f"provider call must not run: {method} {params} {retry_transient}")


def test_durability_hook_runs_after_exact_preflight_and_before_wall_edit() -> None:
    before_text = "exact reviewed BEFORE"
    expected = VkWallPostFingerprint(
        owner_id=-68859909,
        post_id=700,
        surface=VkWallSurface.PUBLISHED,
        publish_date=1_786_900_000,
        text_sha256=_sha(before_text),
        attachments=("video-68859909_456239232",),
    )
    writer = _HookBoundaryWriter(expected=expected, before_text=before_text)
    hook_observation: list[tuple[int, int, int]] = []

    def fail_durable_start() -> None:
        hook_observation.append((writer.snapshot_reads, writer.post_reads, writer.provider_calls))
        raise OSError("promotion journal unavailable")

    with pytest.raises(OSError, match="promotion journal unavailable"):
        VkWallTextWriter.replace_message_if_current(  # type: ignore[arg-type]
            writer,
            expected=expected,
            before_text=before_text,
            after_text="exact reviewed AFTER",
            before_dispatch=fail_durable_start,
        )

    assert hook_observation == [(1, 1, 0)]
    assert writer.provider_calls == 0
