from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from video_channel_manager.editorial._project_profiles import MILOVI_CAKE, resolve_project_key
from video_channel_manager.platforms.http import HttpFailureKind
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text
from video_channel_manager.platforms.vk.wall import VkWallWriter
from video_channel_manager.platforms.vk.wall_safety import (
    VkWallDelta,
    VkWallDeltaStatus,
    VkWallPostFingerprint,
    VkWallSnapshot,
    VkWallSurface,
    compare_wall_snapshots,
)
from video_channel_manager.platforms.vk.writer import VkWriteError

MILOVI_ROLLOUT_ISSUE = 323
MILOVI_COMMUNITY_ID = 68859909
MILOVI_OWNER_ID = -MILOVI_COMMUNITY_ID
MILOVI_IMMEDIATE_WALL_POLICY = "milovi-cake-issue-323-immediate-wall-v1"
MILOVI_SOURCE_ALLOWLIST = frozenset(
    {
        "d48QLgOuiTs",
        "Oix9s6l9vNg",
        "uA8SbnXzJJc",
        "u-PuqjWuhKk",
        "L6XG2_zzrPU",
        "pCARxxaVjTw",
        "OWV-KGsLdA8",
        "o1WXIMupuws",
        "1_SuzeQD_1g",
        "5B9OuXbdGKc",
        "BAVKrQQ00XI",
        "R0KjJvbxS8s",
    }
)
MILOVI_EXPLICITLY_BLOCKED = frozenset({"SiluLt5Bz1c"})

_AMBIGUOUS_WALL_FAILURES = frozenset(
    {
        HttpFailureKind.TRANSPORT,
        HttpFailureKind.RATE_LIMIT,
        HttpFailureKind.TRANSIENT_HTTP,
        HttpFailureKind.PROVIDER_TRANSIENT,
        HttpFailureKind.INVALID_JSON,
        HttpFailureKind.INVALID_PAYLOAD,
    }
)


class MiloviImmediateWallRecoveryRequired(VkWriteError):
    """An immediate wall mutation may have been accepted and needs reconciliation."""


@dataclass(frozen=True, slots=True)
class MiloviImmediateWallAuthority:
    source_video_id: str
    community_id: int = MILOVI_COMMUNITY_ID
    owner_id: int = MILOVI_OWNER_ID
    project_key: str = MILOVI_CAKE
    issue_number: int = MILOVI_ROLLOUT_ISSUE
    policy_version: str = MILOVI_IMMEDIATE_WALL_POLICY

    def __post_init__(self) -> None:
        source_id = self.source_video_id.strip()
        if source_id in MILOVI_EXPLICITLY_BLOCKED or source_id not in MILOVI_SOURCE_ALLOWLIST:
            raise ValueError(f"YouTube source {self.source_video_id!r} is not authorized by Issue #323")
        if self.project_key != MILOVI_CAKE:
            raise ValueError("Immediate wall authority is Milovi Cake only")
        if self.community_id != MILOVI_COMMUNITY_ID or self.owner_id != MILOVI_OWNER_ID:
            raise ValueError("Immediate wall authority target differs from canonical Milovi Cake identity")
        if self.issue_number != MILOVI_ROLLOUT_ISSUE or self.policy_version != MILOVI_IMMEDIATE_WALL_POLICY:
            raise ValueError("Immediate wall authority does not match reviewed Issue #323 policy")
        resolved = resolve_project_key(
            {
                "project_key": self.project_key,
                "community_id": self.community_id,
                "owner_id": self.owner_id,
            }
        )
        if resolved != MILOVI_CAKE:
            raise ValueError("Milovi project/community/owner identity is inconsistent")
        object.__setattr__(self, "source_video_id", source_id)

    def as_dict(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "project_key": self.project_key,
                "community_id": self.community_id,
                "owner_id": self.owner_id,
                "source_video_id": self.source_video_id,
                "issue_number": self.issue_number,
                "policy_version": self.policy_version,
                "publication_mode": "immediate",
                "publish_date": None,
            }
        )


@dataclass(frozen=True, slots=True)
class MiloviImmediateWallPostResult:
    owner_id: int
    post_id: int
    video_remote_id: str
    source_video_id: str
    guid: str
    before_snapshot_sha256: str
    after_snapshot_sha256: str

    @property
    def remote_id(self) -> str:
        return f"{self.owner_id}_{self.post_id}"


def _message_sha256(message: str) -> str:
    return "sha256:" + hashlib.sha256(message.encode("utf-8")).hexdigest()


def _post_has_video(post: VkWallPostFingerprint, *, owner_id: int, video_id: int) -> bool:
    return f"video{owner_id}_{video_id}" in post.attachments


def _expected_published_post(
    snapshot: VkWallSnapshot,
    *,
    owner_id: int,
    video_id: int,
    message: str,
    post_id: int | None,
) -> list[VkWallPostFingerprint]:
    digest = _message_sha256(canonical_vk_text(message))
    return [
        post
        for post in snapshot.posts
        if post.surface is VkWallSurface.PUBLISHED
        and post.text_sha256 == digest
        and _post_has_video(post, owner_id=owner_id, video_id=video_id)
        and (post_id is None or post.post_id == post_id)
    ]


def _validate_exact_delta(
    *,
    before: VkWallSnapshot,
    after: VkWallSnapshot,
    delta: VkWallDelta,
    matches: list[VkWallPostFingerprint],
) -> VkWallPostFingerprint:
    if not before.complete or not after.complete:
        raise MiloviImmediateWallRecoveryRequired(
            "Immediate wall pre/post snapshot is incomplete",
            method="wall.get",
            retryable=False,
        )
    if delta.status is VkWallDeltaStatus.UNKNOWN_REQUIRES_RECONCILIATION:
        raise MiloviImmediateWallRecoveryRequired(
            f"Immediate wall outcome is unknown: {delta.reasons}",
            method="wall.get",
            retryable=False,
        )
    if len(matches) != 1:
        raise MiloviImmediateWallRecoveryRequired(
            "Immediate wall outcome cannot be reconciled to exactly one published post",
            method="wall.get",
            retryable=False,
        )
    match = matches[0]
    expected_created = (f"published:{match.remote_id}",)
    if delta.created != expected_created or delta.removed or delta.changed:
        raise MiloviImmediateWallRecoveryRequired(
            "VK wall changed outside the one approved immediate published post",
            method="wall.get",
            retryable=False,
        )
    return match


class MiloviImmediateWallWriter(VkWallWriter):
    """Issue #323 authority: attach one verified Milovi native Clip to the wall now.

    This class does not upload media. It refuses ordinary VK videos and posts only
    an already-existing exact Milovi object whose provider readback says
    ``type=short_video``. ``wall.post`` is sent without ``publish_date``.
    """

    def _require_native_clip(self, *, video_id: int) -> dict[str, Any]:
        item = self.read_video(owner_id=MILOVI_OWNER_ID, video_id=video_id)
        if item is None:
            raise VkWriteError("Milovi Clip is absent from provider readback", method="video.get")
        if item.get("owner_id") != MILOVI_OWNER_ID or item.get("id") != video_id:
            raise VkWriteError("Milovi Clip readback identity mismatch", method="video.get")
        if str(item.get("type") or "").strip() != "short_video":
            raise VkWriteError("Issue #323 wall publication requires provider type=short_video", method="video.get")
        if bool(item.get("processing")) or bool(item.get("converting")):
            raise VkWriteError("Milovi native Clip is still processing", method="video.get")
        return item

    def post_verified_clip_now(
        self,
        *,
        authority: MiloviImmediateWallAuthority,
        video_id: int,
        message: str,
        guid: str,
        max_posts_per_surface: int = 10000,
    ) -> MiloviImmediateWallPostResult:
        if authority.community_id != MILOVI_COMMUNITY_ID or authority.owner_id != MILOVI_OWNER_ID:
            raise ValueError("Issue #323 authority target mismatch")
        if video_id <= 0:
            raise ValueError("video_id must be positive")
        normalized_message = canonical_vk_text(message)
        if not normalized_message:
            raise ValueError("VK wall message cannot be blank")
        if not guid.startswith("vcm-milovi-323-"):
            raise ValueError("guid must be an Issue #323 deterministic vcm-milovi-323 identifier")

        self._require_native_clip(video_id=video_id)
        before = self.capture_wall_snapshot(
            community_id=MILOVI_COMMUNITY_ID,
            max_posts_per_surface=max_posts_per_surface,
        )
        if not before.complete:
            raise VkWriteError("VK wall preflight snapshot is incomplete", method="wall.get")
        duplicates = [
            post for post in before.posts if _post_has_video(post, owner_id=MILOVI_OWNER_ID, video_id=video_id)
        ]
        if duplicates:
            locations = sorted(f"{post.surface.value}:{post.remote_id}" for post in duplicates)
            raise VkWriteError(
                f"Clip already appears in published/postponed wall posts: {locations}",
                method="wall.get",
            )

        params: dict[str, str | int | bool] = {
            "owner_id": MILOVI_OWNER_ID,
            "from_group": True,
            "message": normalized_message,
            "attachments": f"video{MILOVI_OWNER_ID}_{video_id}",
            "guid": guid,
        }
        if "publish_date" in params:
            raise AssertionError("Issue #323 immediate wall request must not contain publish_date")

        try:
            response = self._call("wall.post", params=params)
        except VkWriteError as exc:
            if exc.kind not in _AMBIGUOUS_WALL_FAILURES:
                raise
            after = self.capture_wall_snapshot(
                community_id=MILOVI_COMMUNITY_ID,
                max_posts_per_surface=max_posts_per_surface,
            )
            delta = compare_wall_snapshots(before, after)
            matches = _expected_published_post(
                after,
                owner_id=MILOVI_OWNER_ID,
                video_id=video_id,
                message=normalized_message,
                post_id=None,
            )
            match = _validate_exact_delta(before=before, after=after, delta=delta, matches=matches)
            return MiloviImmediateWallPostResult(
                owner_id=match.owner_id,
                post_id=match.post_id,
                video_remote_id=f"{MILOVI_OWNER_ID}_{video_id}",
                source_video_id=authority.source_video_id,
                guid=guid,
                before_snapshot_sha256=before.snapshot_sha256,
                after_snapshot_sha256=after.snapshot_sha256,
            )

        post_id = response.get("post_id") if isinstance(response, dict) else response
        if not isinstance(post_id, int) or post_id <= 0:
            raise MiloviImmediateWallRecoveryRequired(
                f"wall.post returned no usable immediate post identity: {response!r}",
                method="wall.post",
                retryable=False,
            )
        after = self.capture_wall_snapshot(
            community_id=MILOVI_COMMUNITY_ID,
            max_posts_per_surface=max_posts_per_surface,
        )
        delta = compare_wall_snapshots(before, after)
        matches = _expected_published_post(
            after,
            owner_id=MILOVI_OWNER_ID,
            video_id=video_id,
            message=normalized_message,
            post_id=post_id,
        )
        match = _validate_exact_delta(before=before, after=after, delta=delta, matches=matches)
        return MiloviImmediateWallPostResult(
            owner_id=match.owner_id,
            post_id=match.post_id,
            video_remote_id=f"{MILOVI_OWNER_ID}_{video_id}",
            source_video_id=authority.source_video_id,
            guid=guid,
            before_snapshot_sha256=before.snapshot_sha256,
            after_snapshot_sha256=after.snapshot_sha256,
        )


__all__ = [
    "MILOVI_COMMUNITY_ID",
    "MILOVI_EXPLICITLY_BLOCKED",
    "MILOVI_IMMEDIATE_WALL_POLICY",
    "MILOVI_OWNER_ID",
    "MILOVI_ROLLOUT_ISSUE",
    "MILOVI_SOURCE_ALLOWLIST",
    "MiloviImmediateWallAuthority",
    "MiloviImmediateWallPostResult",
    "MiloviImmediateWallRecoveryRequired",
    "MiloviImmediateWallWriter",
]
