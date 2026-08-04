from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Iterable, Mapping

VK_UPLOAD_WALL_POLICY_SCHEMA = "video-manager.vk-upload-wall-policy"
VK_UPLOAD_WALL_POLICY_VERSION = 1
VK_WALL_SNAPSHOT_SCHEMA = "video-manager.vk-wall-snapshot"
VK_WALL_SNAPSHOT_VERSION = 1


class VkWallSurface(StrEnum):
    PUBLISHED = "published"
    POSTPONED = "postponed"

    @property
    def api_filter(self) -> str:
        return "owner" if self is VkWallSurface.PUBLISHED else "postponed"


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _require_exact_bool(value: object, *, field: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{field} must be an exact boolean")
    return value


@dataclass(frozen=True, slots=True)
class VkUploadWallPolicy:
    """Immutable fail-closed authority for a video upload reservation.

    Upload executors are not wall publishers. The only supported generic upload
    policy explicitly disables all three VK ``video.save`` publication/playback
    switches. A future loop exception needs a different reviewed policy type;
    it must never be inferred from loose dictionaries or truthy values.
    """

    wall_mutation_authorized: bool = False
    wallpost: bool = False
    auto_publish: bool = False
    repeat: bool = False

    def __post_init__(self) -> None:
        wall_mutation_authorized = _require_exact_bool(
            self.wall_mutation_authorized,
            field="wall_mutation_authorized",
        )
        wallpost = _require_exact_bool(self.wallpost, field="wallpost")
        auto_publish = _require_exact_bool(self.auto_publish, field="auto_publish")
        repeat = _require_exact_bool(self.repeat, field="repeat")
        if wall_mutation_authorized:
            raise ValueError("Video upload policy cannot authorize a wall mutation")
        if wallpost or auto_publish:
            raise ValueError("Video upload policy must disable wallpost and auto_publish")
        if repeat:
            raise ValueError("Generic video upload policy must disable repeat; use a separately reviewed loop policy")

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_name": VK_UPLOAD_WALL_POLICY_SCHEMA,
            "schema_version": VK_UPLOAD_WALL_POLICY_VERSION,
            "wall_mutation_authorized": self.wall_mutation_authorized,
            "wallpost": self.wallpost,
            "auto_publish": self.auto_publish,
            "repeat": self.repeat,
        }
        payload["policy_sha256"] = _canonical_sha256(payload)
        return payload

    def video_save_params(self) -> dict[str, bool]:
        return {
            "wallpost": self.wallpost,
            "auto_publish": self.auto_publish,
            "repeat": self.repeat,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> VkUploadWallPolicy:
        if raw.get("schema_name") != VK_UPLOAD_WALL_POLICY_SCHEMA:
            raise ValueError("Unsupported or missing VK upload wall policy schema")
        if raw.get("schema_version") != VK_UPLOAD_WALL_POLICY_VERSION:
            raise ValueError("Unsupported VK upload wall policy version")
        expected_digest = raw.get("policy_sha256")
        digest_payload = {key: value for key, value in raw.items() if key != "policy_sha256"}
        if expected_digest != _canonical_sha256(digest_payload):
            raise ValueError("VK upload wall policy self-digest does not match")
        return cls(
            wall_mutation_authorized=_require_exact_bool(
                raw.get("wall_mutation_authorized"),
                field="wall_mutation_authorized",
            ),
            wallpost=_require_exact_bool(raw.get("wallpost"), field="wallpost"),
            auto_publish=_require_exact_bool(raw.get("auto_publish"), field="auto_publish"),
            repeat=_require_exact_bool(raw.get("repeat"), field="repeat"),
        )


DEFAULT_UPLOAD_WALL_POLICY = VkUploadWallPolicy()


def canonical_wall_attachment(attachment: Mapping[str, Any]) -> str | None:
    kind = str(attachment.get("type") or "").strip()
    payload = attachment.get(kind)
    if not kind or not isinstance(payload, Mapping):
        return None
    owner_id = payload.get("owner_id")
    media_id = payload.get("id")
    if type(owner_id) is not int or type(media_id) is not int or owner_id == 0 or media_id <= 0:
        return None
    return f"{kind}{owner_id}_{media_id}"


@dataclass(frozen=True, slots=True)
class VkWallPostFingerprint:
    owner_id: int
    post_id: int
    surface: VkWallSurface
    publish_date: int | None
    text_sha256: str
    attachments: tuple[str, ...]

    @property
    def remote_id(self) -> str:
        return f"{self.owner_id}_{self.post_id}"

    def as_dict(self) -> dict[str, object]:
        return {
            "owner_id": self.owner_id,
            "post_id": self.post_id,
            "surface": self.surface.value,
            "publish_date": self.publish_date,
            "text_sha256": self.text_sha256,
            "attachments": list(self.attachments),
        }

    @classmethod
    def from_item(cls, item: Mapping[str, Any], *, surface: VkWallSurface) -> VkWallPostFingerprint:
        owner_id = item.get("owner_id")
        post_id = item.get("id")
        if type(owner_id) is not int or type(post_id) is not int or owner_id == 0 or post_id <= 0:
            raise ValueError("Wall item has invalid owner/post identity")
        publish_date_raw = item.get("date") if surface is VkWallSurface.POSTPONED else item.get("date")
        publish_date = publish_date_raw if type(publish_date_raw) is int and publish_date_raw >= 0 else None
        text = str(item.get("text") or "")
        attachments = tuple(
            sorted(
                token
                for token in (
                    canonical_wall_attachment(value)
                    for value in item.get("attachments") or []
                    if isinstance(value, Mapping)
                )
                if token is not None
            )
        )
        return cls(
            owner_id=owner_id,
            post_id=post_id,
            surface=surface,
            publish_date=publish_date,
            text_sha256=f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}",
            attachments=attachments,
        )


@dataclass(frozen=True, slots=True)
class VkWallSnapshot:
    community_id: int
    captured_at: str
    complete: bool
    published_pages: int
    postponed_pages: int
    posts: tuple[VkWallPostFingerprint, ...]

    def __post_init__(self) -> None:
        if self.community_id <= 0:
            raise ValueError("community_id must be positive")
        if type(self.complete) is not bool:
            raise ValueError("complete must be an exact boolean")
        if self.published_pages < 0 or self.postponed_pages < 0:
            raise ValueError("snapshot page counts cannot be negative")
        identities = [(post.surface.value, post.remote_id) for post in self.posts]
        if len(identities) != len(set(identities)):
            raise ValueError("Wall snapshot contains duplicate surface/post identities")
        expected_owner = -self.community_id
        if any(post.owner_id != expected_owner for post in self.posts):
            raise ValueError("Wall snapshot contains a post from another owner")

    @property
    def snapshot_sha256(self) -> str:
        return _canonical_sha256(self._payload())

    def _payload(self) -> dict[str, object]:
        return {
            "schema_name": VK_WALL_SNAPSHOT_SCHEMA,
            "schema_version": VK_WALL_SNAPSHOT_VERSION,
            "community_id": self.community_id,
            "captured_at": self.captured_at,
            "complete": self.complete,
            "published_pages": self.published_pages,
            "postponed_pages": self.postponed_pages,
            "posts": [post.as_dict() for post in sorted(self.posts, key=lambda item: (item.surface.value, item.post_id))],
        }

    def as_dict(self) -> dict[str, object]:
        payload = self._payload()
        payload["snapshot_sha256"] = self.snapshot_sha256
        return payload


class VkWallDeltaStatus(StrEnum):
    CLEAN = "clean"
    CHANGED = "changed"
    UNKNOWN_REQUIRES_RECONCILIATION = "unknown_requires_reconciliation"


@dataclass(frozen=True, slots=True)
class VkWallDelta:
    status: VkWallDeltaStatus
    created: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]
    before_sha256: str
    after_sha256: str
    reasons: tuple[str, ...] = ()

    @property
    def clean(self) -> bool:
        return self.status is VkWallDeltaStatus.CLEAN

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "created": list(self.created),
            "removed": list(self.removed),
            "changed": list(self.changed),
            "before_sha256": self.before_sha256,
            "after_sha256": self.after_sha256,
            "reasons": list(self.reasons),
        }


def compare_wall_snapshots(before: VkWallSnapshot, after: VkWallSnapshot) -> VkWallDelta:
    if before.community_id != after.community_id:
        raise ValueError("Wall snapshots belong to different communities")
    reasons: list[str] = []
    if not before.complete:
        reasons.append("before_snapshot_incomplete")
    if not after.complete:
        reasons.append("after_snapshot_incomplete")

    def keyed(snapshot: VkWallSnapshot) -> dict[tuple[str, str], VkWallPostFingerprint]:
        return {(post.surface.value, post.remote_id): post for post in snapshot.posts}

    before_posts = keyed(before)
    after_posts = keyed(after)
    created_keys = sorted(set(after_posts) - set(before_posts))
    removed_keys = sorted(set(before_posts) - set(after_posts))
    changed_keys = sorted(
        key
        for key in set(before_posts) & set(after_posts)
        if before_posts[key].as_dict() != after_posts[key].as_dict()
    )

    created = tuple(f"{surface}:{remote_id}" for surface, remote_id in created_keys)
    removed = tuple(f"{surface}:{remote_id}" for surface, remote_id in removed_keys)
    changed = tuple(f"{surface}:{remote_id}" for surface, remote_id in changed_keys)
    if reasons:
        status = VkWallDeltaStatus.UNKNOWN_REQUIRES_RECONCILIATION
    elif created or removed or changed:
        status = VkWallDeltaStatus.CHANGED
    else:
        status = VkWallDeltaStatus.CLEAN
    return VkWallDelta(
        status=status,
        created=created,
        removed=removed,
        changed=changed,
        before_sha256=before.snapshot_sha256,
        after_sha256=after.snapshot_sha256,
        reasons=tuple(reasons),
    )


def build_wall_snapshot(
    *,
    community_id: int,
    published_items: Iterable[Mapping[str, Any]],
    postponed_items: Iterable[Mapping[str, Any]],
    published_pages: int,
    postponed_pages: int,
    complete: bool,
    captured_at: datetime | None = None,
) -> VkWallSnapshot:
    observed_at = (captured_at or datetime.now(UTC)).astimezone(UTC).isoformat()
    posts = tuple(
        [VkWallPostFingerprint.from_item(item, surface=VkWallSurface.PUBLISHED) for item in published_items]
        + [VkWallPostFingerprint.from_item(item, surface=VkWallSurface.POSTPONED) for item in postponed_items]
    )
    return VkWallSnapshot(
        community_id=community_id,
        captured_at=observed_at,
        complete=complete,
        published_pages=published_pages,
        postponed_pages=postponed_pages,
        posts=posts,
    )


__all__ = [
    "DEFAULT_UPLOAD_WALL_POLICY",
    "VK_UPLOAD_WALL_POLICY_SCHEMA",
    "VK_UPLOAD_WALL_POLICY_VERSION",
    "VK_WALL_SNAPSHOT_SCHEMA",
    "VK_WALL_SNAPSHOT_VERSION",
    "VkUploadWallPolicy",
    "VkWallDelta",
    "VkWallDeltaStatus",
    "VkWallPostFingerprint",
    "VkWallSnapshot",
    "VkWallSurface",
    "build_wall_snapshot",
    "canonical_wall_attachment",
    "compare_wall_snapshots",
]
