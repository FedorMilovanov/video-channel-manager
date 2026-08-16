from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, Mapping

from video_channel_manager.platforms.vk.wall import VkWallRecoveryRequired, VkWallWriter
from video_channel_manager.platforms.vk.wall_safety import (
    VkWallDeltaStatus,
    VkWallPostFingerprint,
    VkWallSnapshot,
    VkWallSurface,
    canonical_wall_attachment,
    compare_wall_snapshots,
)
from video_channel_manager.platforms.vk.writer import VkWriteError


def _text_sha256(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _ordered_attachment_tokens(raw_post: Mapping[str, Any]) -> tuple[str, ...]:
    raw_attachments = raw_post.get("attachments") or []
    if not isinstance(raw_attachments, list):
        raise VkWriteError("wall.getById returned malformed attachments", method="wall.getById")
    tokens: list[str] = []
    for attachment in raw_attachments:
        if not isinstance(attachment, Mapping):
            raise VkWriteError("wall.getById returned a non-object attachment", method="wall.getById")
        token = canonical_wall_attachment(attachment)
        if token is None:
            raise VkWriteError("wall.getById returned an attachment without stable VK identity", method="wall.getById")
        tokens.append(token)
    return tuple(tokens)


def _exact_snapshot_post(snapshot: VkWallSnapshot, expected: VkWallPostFingerprint) -> VkWallPostFingerprint:
    if not snapshot.complete:
        raise VkWriteError("VK wall snapshot is incomplete", method="wall.get")
    matches = tuple(
        post for post in snapshot.posts if post.remote_id == expected.remote_id and post.surface is expected.surface
    )
    if len(matches) != 1:
        raise VkWriteError(
            f"Expected wall incarnation is not unique: {expected.surface.value}:{expected.remote_id}",
            method="wall.get",
        )
    if matches[0] != expected:
        raise VkWriteError(
            f"Wall incarnation changed before edit: {expected.surface.value}:{expected.remote_id}",
            method="wall.get",
        )
    return matches[0]


@dataclass(frozen=True, slots=True)
class VkWallTextEditResult:
    remote_id: str
    surface: VkWallSurface
    publish_date: int | None
    attachments: tuple[str, ...]
    before_text_sha256: str
    after_text_sha256: str
    before_snapshot_sha256: str
    after_snapshot_sha256: str
    provider_writes_executed: int = 1


class VkWallTextWriter(VkWallWriter):
    """Perform one exact wall-message replacement without create/delete fallback."""

    def replace_message_if_current(
        self,
        *,
        expected: VkWallPostFingerprint,
        before_text: str,
        after_text: str,
        max_posts_per_surface: int = 10000,
        before_dispatch: Callable[[], None] | None = None,
    ) -> VkWallTextEditResult:
        if expected.owner_id >= 0:
            raise ValueError("Exact wall text edit requires a community-owned post")
        community_id = -expected.owner_id
        if max_posts_per_surface <= 0:
            raise ValueError("max_posts_per_surface must be positive")
        if _text_sha256(before_text) != expected.text_sha256:
            raise ValueError("before_text does not match the reviewed wall fingerprint")
        if before_text == after_text:
            raise ValueError("Exact wall text edit requires a changed after_text")
        if len(after_text) > 15000:
            raise ValueError("after_text exceeds the 15,000-character project policy")

        before_snapshot = self.capture_wall_snapshot(
            community_id=community_id,
            max_posts_per_surface=max_posts_per_surface,
        )
        _exact_snapshot_post(before_snapshot, expected)

        raw_before = self.read_post(community_id=community_id, post_id=expected.post_id)
        if raw_before is None:
            raise VkWriteError("Exact wall post disappeared before edit", method="wall.getById")
        raw_before_fingerprint = VkWallPostFingerprint.from_item(raw_before, surface=expected.surface)
        if raw_before_fingerprint != expected:
            raise VkWriteError("wall.getById differs from the reviewed wall fingerprint", method="wall.getById")
        ordered_attachments = _ordered_attachment_tokens(raw_before)
        if tuple(sorted(ordered_attachments)) != expected.attachments:
            raise VkWriteError("Raw wall attachment identities differ from reviewed fingerprint", method="wall.getById")

        params: dict[str, Any] = {
            "owner_id": expected.owner_id,
            "post_id": expected.post_id,
            "message": after_text,
            "attachments": ",".join(ordered_attachments),
        }
        if expected.surface is VkWallSurface.POSTPONED:
            if expected.publish_date is None or expected.publish_date <= 0:
                raise ValueError("Postponed wall edit requires the exact positive publish_date")
            params["publish_date"] = expected.publish_date

        if before_dispatch is not None:
            before_dispatch()

        try:
            self._call("wall.edit", params=params, retry_transient=False)
        except VkWriteError as exc:
            raise VkWallRecoveryRequired(
                "wall.edit outcome requires exact read reconciliation; blind retry is forbidden",
                method="wall.edit",
                retryable=False,
            ) from exc

        after_snapshot = self.capture_wall_snapshot(
            community_id=community_id,
            max_posts_per_surface=max_posts_per_surface,
        )
        expected_after = replace(expected, text_sha256=_text_sha256(after_text))
        try:
            _exact_snapshot_post(after_snapshot, expected_after)
        except VkWriteError as exc:
            raise VkWallRecoveryRequired(
                "wall.edit postflight does not match the exact reviewed incarnation",
                method="wall.get",
                retryable=False,
            ) from exc

        delta = compare_wall_snapshots(before_snapshot, after_snapshot)
        expected_changed = (f"{expected.surface.value}:{expected.remote_id}",)
        if (
            delta.status is not VkWallDeltaStatus.CHANGED
            or delta.created
            or delta.removed
            or delta.changed != expected_changed
        ):
            raise VkWallRecoveryRequired(
                "wall.edit changed state outside the one exact reviewed wall message",
                method="wall.get",
                retryable=False,
            )

        raw_after = self.read_post(community_id=community_id, post_id=expected.post_id)
        if raw_after is None:
            raise VkWallRecoveryRequired(
                "Exact wall post disappeared during postflight",
                method="wall.getById",
                retryable=False,
            )
        if VkWallPostFingerprint.from_item(raw_after, surface=expected.surface) != expected_after:
            raise VkWallRecoveryRequired(
                "wall.getById postflight differs from the expected exact wall incarnation",
                method="wall.getById",
                retryable=False,
            )
        if _ordered_attachment_tokens(raw_after) != ordered_attachments:
            raise VkWallRecoveryRequired(
                "wall.edit changed attachment ordering",
                method="wall.getById",
                retryable=False,
            )

        return VkWallTextEditResult(
            remote_id=expected.remote_id,
            surface=expected.surface,
            publish_date=expected.publish_date,
            attachments=ordered_attachments,
            before_text_sha256=expected.text_sha256,
            after_text_sha256=expected_after.text_sha256,
            before_snapshot_sha256=before_snapshot.snapshot_sha256,
            after_snapshot_sha256=after_snapshot.snapshot_sha256,
        )


__all__ = ["VkWallTextEditResult", "VkWallTextWriter"]
