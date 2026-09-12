from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text
from video_channel_manager.platforms.vk.wall import VkWallWriter
from video_channel_manager.platforms.vk.wall_content_audit import extract_video_ids_from_post
from video_channel_manager.platforms.vk.wall_safety import (
    VkWallDeltaStatus,
    VkWallSnapshot,
    VkWallSurface,
    build_wall_snapshot,
    compare_wall_snapshots,
)
from video_channel_manager.platforms.vk.writer import VkWriteError
from video_channel_manager.wave_engine.engine import (
    KnownProviderRejectionError,
    OperationRejectedError,
    UnknownProviderOutcomeError,
)
from video_channel_manager.wave_engine.models import WaveOperation

VK_VIDEO_WALL_OPERATION_KIND = "vk.postponed_video_wall"
VK_VIDEO_WALL_POLICY_VERSION = "vk-postponed-video-wall-v1"
VK_VIDEO_WALL_PROJECT_KEY = "legendary-poet"
VK_VIDEO_WALL_COMMUNITY_ID = 235216998
VK_VIDEO_WALL_OWNER_ID = -235216998
VK_VIDEO_WALL_ACCOUNT_ALIAS = "legendary-poet"


class VkVideoWallError(RuntimeError):
    """Deterministic postponed-video wall validation or preflight failure."""


@dataclass(frozen=True, slots=True)
class VideoWallOperation:
    source_video_id: str
    account_alias: str
    video_owner_id: int
    video_id: int
    message: str
    message_sha256: str
    publish_date: int
    guid: str
    expected_video_title: str
    expected_video_description_sha256: str

    @property
    def video_remote_id(self) -> str:
        return f"{self.video_owner_id}_{self.video_id}"

    @property
    def attachment(self) -> str:
        return f"video{self.video_remote_id}"


@dataclass(frozen=True, slots=True)
class VideoWallCapture:
    published: tuple[dict[str, Any], ...]
    postponed: tuple[dict[str, Any], ...]
    snapshot: VkWallSnapshot


@dataclass(frozen=True, slots=True)
class ExactVideoWallPost:
    owner_id: int
    post_id: int
    publish_date: int
    surface: str

    @property
    def remote_id(self) -> str:
        return f"{self.owner_id}_{self.post_id}"


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _exact_string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise VkVideoWallError(f"{field} must be an exact non-empty string")
    return value


def _exact_int(value: object, *, field: str, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        raise VkVideoWallError(f"{field} must be an exact integer >= {minimum}")
    return value


def _exact_signed_int(value: object, *, field: str) -> int:
    if type(value) is not int or value == 0:
        raise VkVideoWallError(f"{field} must be an exact non-zero integer")
    return value


def _sha256_value(value: object, *, field: str) -> str:
    digest = _exact_string(value, field=field)
    if not digest.startswith("sha256:") or len(digest) != 71:
        raise VkVideoWallError(f"{field} must be a sha256: digest")
    if any(ch not in "0123456789abcdef" for ch in digest[7:]):
        raise VkVideoWallError(f"{field} must use lowercase hexadecimal")
    return digest


def _canonical_message(value: object) -> str:
    message = _exact_string(value, field="message")
    normalized = canonical_vk_text(message)
    if message != normalized:
        raise VkVideoWallError("message must already be canonical VK plain text")
    if len(message) > 15_000:
        raise VkVideoWallError("message exceeds the 15,000-character wall policy")
    return message


def parse_video_wall_operation(operation: WaveOperation) -> VideoWallOperation:
    if operation.operation_kind != VK_VIDEO_WALL_OPERATION_KIND:
        raise VkVideoWallError(f"unsupported operation kind: {operation.operation_kind}")
    if (
        operation.project.project_key != VK_VIDEO_WALL_PROJECT_KEY
        or operation.project.community_id != VK_VIDEO_WALL_COMMUNITY_ID
        or operation.project.owner_id != VK_VIDEO_WALL_OWNER_ID
    ):
        raise VkVideoWallError("video wall operation project/community/owner binding is invalid")

    payload = operation.payload
    source_video_id = _exact_string(payload.get("source_video_id"), field="source_video_id")
    account_alias = _exact_string(payload.get("account_alias"), field="account_alias")
    video_owner_id = _exact_signed_int(payload.get("video_owner_id"), field="video_owner_id")
    if video_owner_id != VK_VIDEO_WALL_OWNER_ID:
        raise VkVideoWallError("video_owner_id differs from the Legendary Poet VK owner")
    video_id = _exact_int(payload.get("video_id"), field="video_id")
    expected_remote_id = f"{video_owner_id}_{video_id}"
    if _exact_string(payload.get("video_remote_id"), field="video_remote_id") != expected_remote_id:
        raise VkVideoWallError("video_remote_id does not match owner/video identity")

    message = _canonical_message(payload.get("message"))
    message_sha256 = _sha256_value(payload.get("message_sha256"), field="message_sha256")
    if message_sha256 != _sha256_text(message):
        raise VkVideoWallError("message_sha256 mismatch")

    publish_date = _exact_int(payload.get("publish_date"), field="publish_date")
    guid = _exact_string(payload.get("guid"), field="guid")
    guid_seed = f"{source_video_id}:{expected_remote_id}:{publish_date}:{message_sha256}"
    expected_guid = "vcm-vwall-" + hashlib.sha256(guid_seed.encode("utf-8")).hexdigest()[:28]
    if guid != expected_guid:
        raise VkVideoWallError("guid differs from the deterministic video wall identity")
    expected_title = _exact_string(payload.get("expected_video_title"), field="expected_video_title")
    description_sha = _sha256_value(
        payload.get("expected_video_description_sha256"),
        field="expected_video_description_sha256",
    )

    return VideoWallOperation(
        source_video_id=source_video_id,
        account_alias=account_alias,
        video_owner_id=video_owner_id,
        video_id=video_id,
        message=message,
        message_sha256=message_sha256,
        publish_date=publish_date,
        guid=guid,
        expected_video_title=expected_title,
        expected_video_description_sha256=description_sha,
    )


def _attached_video_ids(item: Mapping[str, Any]) -> tuple[str, ...]:
    result: list[str] = []
    for attachment in item.get("attachments") or []:
        if not isinstance(attachment, Mapping):
            continue
        kind = str(attachment.get("type") or "")
        if kind not in {"video", "clip"}:
            continue
        payload = attachment.get(kind)
        if not isinstance(payload, Mapping) and kind == "clip":
            payload = attachment.get("video")
        if not isinstance(payload, Mapping):
            continue
        owner_id = payload.get("owner_id")
        video_id = payload.get("id")
        if type(owner_id) is int and owner_id != 0 and type(video_id) is int and video_id > 0:
            result.append(f"{owner_id}_{video_id}")
    return tuple(sorted(set(result)))


def _exact_post(
    item: Mapping[str, Any],
    *,
    surface: VkWallSurface,
    wall: VideoWallOperation,
) -> ExactVideoWallPost | None:

    owner_id = item.get("owner_id")
    post_id = item.get("id")
    date = item.get("date")
    if type(owner_id) is not int or type(post_id) is not int or type(date) is not int:
        return None
    if owner_id != VK_VIDEO_WALL_OWNER_ID or post_id <= 0:
        return None
    if canonical_vk_text(str(item.get("text") or "")) != wall.message:
        return None
    if date != wall.publish_date:
        return None
    video_ids = _attached_video_ids(item)
    if video_ids != (wall.video_remote_id,):
        return None
    return ExactVideoWallPost(
        owner_id=owner_id,
        post_id=post_id,
        publish_date=date,
        surface=surface.value,
    )


class VkVideoWallWriter(VkWallWriter):
    """Exact postponed-video wall writer for Legendary Poet."""

    def capture_complete_wall(self, *, max_posts_per_surface: int = 10_000) -> VideoWallCapture:
        published, published_pages, published_complete = self._read_wall_surface(
            community_id=VK_VIDEO_WALL_COMMUNITY_ID,
            surface=VkWallSurface.PUBLISHED,
            max_posts=max_posts_per_surface,
        )
        postponed, postponed_pages, postponed_complete = self._read_wall_surface(
            community_id=VK_VIDEO_WALL_COMMUNITY_ID,
            surface=VkWallSurface.POSTPONED,
            max_posts=max_posts_per_surface,
        )
        if not (published_complete and postponed_complete):
            raise VkVideoWallError("published/postponed wall preflight is incomplete")
        snapshot = build_wall_snapshot(
            community_id=VK_VIDEO_WALL_COMMUNITY_ID,
            published_items=published,
            postponed_items=postponed,
            published_pages=published_pages,
            postponed_pages=postponed_pages,
            complete=True,
        )

        return VideoWallCapture(
            published=tuple(published),
            postponed=tuple(postponed),
            snapshot=snapshot,
        )

    @staticmethod
    def find_exact(capture: VideoWallCapture, wall: VideoWallOperation) -> list[ExactVideoWallPost]:
        matches: list[ExactVideoWallPost] = []
        for surface, items in (
            (VkWallSurface.PUBLISHED, capture.published),
            (VkWallSurface.POSTPONED, capture.postponed),
        ):
            for item in items:
                match = _exact_post(item, surface=surface, wall=wall)
                if match is not None:
                    matches.append(match)
        return matches

    @staticmethod
    def _preflight_conflicts(
        capture: VideoWallCapture,
        wall: VideoWallOperation,
    ) -> ExactVideoWallPost | None:
        exact = VkVideoWallWriter.find_exact(capture, wall)
        references: list[tuple[VkWallSurface, Mapping[str, Any]]] = []
        for surface, items in (
            (VkWallSurface.PUBLISHED, capture.published),
            (VkWallSurface.POSTPONED, capture.postponed),
        ):
            for item in items:
                if wall.video_remote_id in extract_video_ids_from_post(dict(item)):
                    references.append((surface, item))

        if len(exact) > 1:
            raise VkVideoWallError("more than one exact wall post already exists for the video")
        if exact:
            if len(references) != 1:
                raise VkVideoWallError("the video has additional published/postponed wall references")
            return exact[0]
        if references:
            raise VkVideoWallError("the video already has a different published/postponed wall reference")

        for item in capture.postponed:
            date = item.get("date")
            if type(date) is int and date == wall.publish_date:
                raise VkVideoWallError("postponed schedule slot is already occupied")
        return None

    def verify_video(self, wall: VideoWallOperation) -> dict[str, Any]:
        item = self.read_video(owner_id=wall.video_owner_id, video_id=wall.video_id)
        if item is None:
            raise VkVideoWallError(f"VK video {wall.video_remote_id} is not visible")
        title = canonical_vk_text(str(item.get("title") or ""))
        description = canonical_vk_text(str(item.get("description") or ""))
        if title != wall.expected_video_title:
            raise VkVideoWallError("live VK video title differs from the reviewed wall operation")
        if _sha256_text(description) != wall.expected_video_description_sha256:
            raise VkVideoWallError("live VK video description differs from the reviewed wall operation")
        source_marker = f"youtube.com/watch?v={wall.source_video_id}"
        if source_marker not in description:
            raise VkVideoWallError("live VK video description lacks the exact YouTube source marker")
        player = str(item.get("player") or "").strip()
        files = item.get("files")
        if not player and not (isinstance(files, Mapping) and any(str(v or "").strip() for v in files.values())):
            raise VkVideoWallError("live VK video is not playable")
        return item

    def schedule(self, *, wall: VideoWallOperation) -> dict[str, Any]:
        self.verify_video(wall)
        before = self.capture_complete_wall()
        existing = self._preflight_conflicts(before, wall)
        if existing is not None:
            return {
                "status": "already_applied",
                "remote_id": existing.remote_id,
                "publish_date": existing.publish_date,
                "surface": existing.surface,
                "before_snapshot_sha256": before.snapshot.snapshot_sha256,
                "after_snapshot_sha256": before.snapshot.snapshot_sha256,
            }

        mutation_started = False
        try:
            mutation_started = True
            response = self._call(
                "wall.post",
                params={
                    "owner_id": VK_VIDEO_WALL_OWNER_ID,
                    "from_group": True,
                    "message": wall.message,
                    "attachments": wall.attachment,
                    "publish_date": wall.publish_date,
                    "guid": wall.guid,
                },
            )

            post_id = response.get("post_id") if isinstance(response, dict) else response
            if type(post_id) is not int or post_id <= 0:
                raise RuntimeError(f"wall.post returned no positive post ID: {response!r}")

            after: VideoWallCapture | None = None
            exact: list[ExactVideoWallPost] = []
            for attempt in range(6):
                after = self.capture_complete_wall()
                exact = [
                    item
                    for item in self.find_exact(after, wall)
                    if item.post_id == post_id and item.surface == VkWallSurface.POSTPONED.value
                ]
                if len(exact) == 1:
                    break
                if attempt < 5:
                    time.sleep(2)
            if after is None or len(exact) != 1:
                raise RuntimeError("accepted postponed video post is not exactly visible after postflight")

            delta = compare_wall_snapshots(before.snapshot, after.snapshot)
            expected_created = (f"postponed:{VK_VIDEO_WALL_OWNER_ID}_{post_id}",)
            if (
                delta.status is not VkWallDeltaStatus.CHANGED
                or delta.created != expected_created
                or delta.removed
                or delta.changed
            ):
                raise RuntimeError("video wall postflight observed an unexpected wall delta")
            return {
                "status": "scheduled",
                "remote_id": exact[0].remote_id,
                "publish_date": exact[0].publish_date,
                "surface": exact[0].surface,
                "before_snapshot_sha256": before.snapshot.snapshot_sha256,
                "after_snapshot_sha256": after.snapshot.snapshot_sha256,
                "wall_delta": delta.as_dict(),
                "video_remote_id": wall.video_remote_id,
                "source_video_id": wall.source_video_id,
            }
        except UnknownProviderOutcomeError:
            raise
        except VkWriteError:
            raise
        except Exception as exc:
            if mutation_started:
                raise UnknownProviderOutcomeError(f"{type(exc).__name__}: {exc}") from exc
            raise

    def reconcile_exact(self, *, wall: VideoWallOperation) -> dict[str, Any]:
        self.verify_video(wall)
        capture = self.capture_complete_wall()
        matches = self.find_exact(capture, wall)

        if len(matches) != 1:
            raise RuntimeError(f"exact video wall reconciliation requires one match; found {len(matches)}")
        match = matches[0]
        return {
            "status": "reconciled_exact_post",
            "remote_id": match.remote_id,
            "publish_date": match.publish_date,
            "surface": match.surface,
            "video_remote_id": wall.video_remote_id,
            "source_video_id": wall.source_video_id,
            "snapshot_sha256": capture.snapshot.snapshot_sha256,
        }


class VkPostponedVideoWallAdapter:
    reconciliation_replay_safe = True

    def __init__(
        self,
        *,
        account_alias: str = VK_VIDEO_WALL_ACCOUNT_ALIAS,
    ) -> None:
        if account_alias != VK_VIDEO_WALL_ACCOUNT_ALIAS:
            raise ValueError("Legendary Poet video wall provider requires the exact local VK alias")
        settings = get_settings()
        self.settings = settings
        self.account_alias = account_alias
        self.writer = VkVideoWallWriter(
            token_store=VkTokenStore(settings.data_dir),
            account_alias=account_alias,
            api_version=settings.vk_api_version,
        )

    def execute(self, operation: WaveOperation) -> Mapping[str, Any]:
        try:
            wall = parse_video_wall_operation(operation)
            if wall.account_alias != self.account_alias:
                raise VkVideoWallError("operation account alias differs from the provider alias")
            if wall.publish_date <= int(datetime.now(UTC).timestamp()) + 300:
                raise VkVideoWallError("postponed publish_date is not safely in the future")
        except (ValueError, VkVideoWallError) as exc:
            raise OperationRejectedError(str(exc)) from exc

        lock_path = self.settings.data_dir / "locks" / f"vk-wall-{VK_VIDEO_WALL_COMMUNITY_ID}.lock"
        try:
            with local_vk_write_lock(
                lock_path,
                account=self.account_alias,
                community_id=VK_VIDEO_WALL_COMMUNITY_ID,
                operation=f"postponed-video-wall:{wall.source_video_id}",
            ):
                return self.writer.schedule(wall=wall)
        except UnknownProviderOutcomeError:
            raise
        except VkWriteError as exc:
            if exc.attempts == 0:
                raise OperationRejectedError(str(exc)) from exc
            if exc.code is not None:
                raise KnownProviderRejectionError(str(exc)) from exc
            raise UnknownProviderOutcomeError(str(exc)) from exc
        except (VkVideoWallError, OSError, ValueError) as exc:
            raise OperationRejectedError(str(exc)) from exc

    def reconcile(self, operation: WaveOperation) -> Mapping[str, Any]:
        wall = parse_video_wall_operation(operation)
        if wall.account_alias != self.account_alias:
            raise RuntimeError("operation account alias differs from the provider alias")
        return self.writer.reconcile_exact(wall=wall)

    def close(self) -> None:
        close = getattr(self.writer, "close", None)
        if callable(close):
            close()


__all__ = [
    "VK_VIDEO_WALL_ACCOUNT_ALIAS",
    "VK_VIDEO_WALL_COMMUNITY_ID",
    "VK_VIDEO_WALL_OPERATION_KIND",
    "VK_VIDEO_WALL_OWNER_ID",
    "VK_VIDEO_WALL_POLICY_VERSION",
    "ExactVideoWallPost",
    "VideoWallCapture",
    "VideoWallOperation",
    "VkPostponedVideoWallAdapter",
    "VkVideoWallError",
    "VkVideoWallWriter",
    "parse_video_wall_operation",
]
