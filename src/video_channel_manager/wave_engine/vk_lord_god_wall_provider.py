from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text
from video_channel_manager.platforms.vk.wall import VkWallRecoveryRequired, VkWallWriter
from video_channel_manager.platforms.vk.wall_safety import (
    VkWallDeltaStatus,
    VkWallPostFingerprint,
    VkWallSurface,
    compare_wall_snapshots,
)
from video_channel_manager.platforms.vk.writer import VkWriteError
from video_channel_manager.wave_engine.engine import (
    KnownProviderRejectionError,
    OperationRejectedError,
    UnknownProviderOutcomeError,
)
from video_channel_manager.wave_engine.models import WaveOperation


LORD_GOD_WALL_OPERATION_KIND = "vk.lord_god.postponed_wall"
LORD_GOD_WALL_POLICY_VERSION = "vk-lord-god-postponed-wall-v4"
LORD_GOD_PROJECT_KEY = "lord-god-strength"
LORD_GOD_COMMUNITY_ID = 60805374
LORD_GOD_OWNER_ID = -60805374
# The legacy shared credential (aliases ``legendary-poet`` / ``default``) is
# quarantined by docs/operations/vk-credential-quarantine.md: it must never be
# used for a provider call again. Policy v4 therefore binds every new Lord God
# postponed-wall operation to the community access key of community 60805374
# itself (created in the community's API settings with the ``wall``
# permission, stored in the GitHub Environment ``The_Lord_God_VK`` and
# imported locally under this alias via ``video-manager vk
# community-key-login``). Changing the alias also changes the payload and
# therefore the operation identity, so a v3 plan can never be replayed under
# the new credential.
LORD_GOD_ACCOUNT_ALIAS = "vk-lord-god-community-key"
LORD_GOD_QUARANTINED_ACCOUNT_ALIASES = frozenset({"legendary-poet", "default"})


class LordGodWallError(RuntimeError):
    """Deterministic Lord God postponed-wall validation failure."""


@dataclass(frozen=True, slots=True)
class LordGodWallOperation:
    content_kind: str
    account_alias: str
    message: str
    message_sha256: str
    publish_date: int
    guid: str
    source_id: str
    photo_path: str | None = None
    photo_sha256: str | None = None
    video_owner_id: int | None = None
    video_id: int | None = None
    expected_video_title: str | None = None
    expected_video_description_sha256: str | None = None

    @property
    def video_remote_id(self) -> str | None:
        if self.video_owner_id is None or self.video_id is None:
            return None
        return f"{self.video_owner_id}_{self.video_id}"

    @property
    def attachment(self) -> str | None:
        remote_id = self.video_remote_id
        return f"video{remote_id}" if remote_id else None


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_text_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _exact_string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise LordGodWallError(f"{field} must be an exact non-empty string")
    return value


def _exact_int(value: object, *, field: str, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        raise LordGodWallError(f"{field} must be an exact integer >= {minimum}")
    return value


def _sha256_value(value: object, *, field: str) -> str:
    digest = _exact_string(value, field=field)
    if not digest.startswith("sha256:") or len(digest) != 71:
        raise LordGodWallError(f"{field} must be a sha256: digest")
    if any(ch not in "0123456789abcdef" for ch in digest[7:]):
        raise LordGodWallError(f"{field} must use lowercase hexadecimal")
    return digest


def _canonical_message(value: object) -> str:
    message = _exact_string(value, field="message")
    normalized = canonical_vk_text(message)
    if message != normalized:
        raise LordGodWallError("message must already be canonical VK plain text")
    if len(message) > 15_000:
        raise LordGodWallError("message exceeds the 15,000-character wall policy")
    return message


def parse_lord_god_wall_operation(operation: WaveOperation) -> LordGodWallOperation:
    if operation.operation_kind != LORD_GOD_WALL_OPERATION_KIND:
        raise LordGodWallError(f"unsupported operation kind: {operation.operation_kind}")
    if operation.policy_version != LORD_GOD_WALL_POLICY_VERSION:
        raise LordGodWallError("Lord God wall policy version mismatch")
    if (
        operation.project.project_key != LORD_GOD_PROJECT_KEY
        or operation.project.community_id != LORD_GOD_COMMUNITY_ID
        or operation.project.owner_id != LORD_GOD_OWNER_ID
    ):
        raise LordGodWallError("Lord God project/community/owner binding is invalid")

    payload = operation.payload
    content_kind = _exact_string(payload.get("content_kind"), field="content_kind")
    if content_kind not in {"video", "text"}:
        raise LordGodWallError("content_kind must be video or text")
    account_alias = _exact_string(payload.get("account_alias"), field="account_alias")
    if account_alias in LORD_GOD_QUARANTINED_ACCOUNT_ALIASES:
        raise LordGodWallError(
            "account_alias is the quarantined legacy VK credential; "
            f"use the separately imported alias {LORD_GOD_ACCOUNT_ALIAS} (Lord God community access key)"
        )
    if account_alias != LORD_GOD_ACCOUNT_ALIAS:
        raise LordGodWallError("account_alias differs from the reviewed Lord God credential alias")
    message = _canonical_message(payload.get("message"))
    message_sha256 = _sha256_value(payload.get("message_sha256"), field="message_sha256")
    if message_sha256 != _sha256_text(message):
        raise LordGodWallError("message_sha256 mismatch")
    publish_date = _exact_int(payload.get("publish_date"), field="publish_date")
    guid = _exact_string(payload.get("guid"), field="guid")
    if not guid.startswith("vcm-lgw-") or len(guid) > 40:
        raise LordGodWallError("guid must be a deterministic vcm-lgw- identifier")
    source_id = _exact_string(payload.get("source_id"), field="source_id")

    if content_kind == "text":
        photo_path = payload.get("photo_path")
        photo_sha256 = payload.get("photo_sha256")
        if (photo_path is None) != (photo_sha256 is None):
            raise LordGodWallError("photo_path and photo_sha256 must be supplied together")
        if photo_path is not None:
            photo_path = _exact_string(photo_path, field="photo_path")
            if photo_path.startswith(("/", ".")) or ".." in Path(photo_path).parts or not photo_path.endswith(".jpg"):
                raise LordGodWallError("photo_path must be a repository-relative .jpg path")
            photo_sha256 = _sha256_value(photo_sha256, field="photo_sha256")
        return LordGodWallOperation(
            content_kind=content_kind,
            account_alias=account_alias,
            message=message,
            message_sha256=message_sha256,
            publish_date=publish_date,
            guid=guid,
            source_id=source_id,
            photo_path=photo_path,
            photo_sha256=photo_sha256,
        )

    video_owner_id = payload.get("video_owner_id")
    if type(video_owner_id) is not int or video_owner_id != LORD_GOD_OWNER_ID:
        raise LordGodWallError("video_owner_id differs from the Lord God VK owner")
    video_id = _exact_int(payload.get("video_id"), field="video_id")
    remote_id = _exact_string(payload.get("video_remote_id"), field="video_remote_id")
    if remote_id != f"{video_owner_id}_{video_id}":
        raise LordGodWallError("video_remote_id does not match owner/video identity")
    expected_title = _exact_string(payload.get("expected_video_title"), field="expected_video_title")
    description_sha = _sha256_value(
        payload.get("expected_video_description_sha256"),
        field="expected_video_description_sha256",
    )
    return LordGodWallOperation(
        content_kind=content_kind,
        account_alias=account_alias,
        message=message,
        message_sha256=message_sha256,
        publish_date=publish_date,
        guid=guid,
        source_id=source_id,
        video_owner_id=video_owner_id,
        video_id=video_id,
        expected_video_title=expected_title,
        expected_video_description_sha256=description_sha,
    )


class LordGodWallWriter(VkWallWriter):
    """Wall writer bound to the Lord God community access key.

    The credential is a community key (``token_type == "community"``), not a
    user token: it carries community permissions (``wall`` …) and can never
    hold the user ``video`` scope the base writer demands before every call.
    For community tokens the verified community permission set is therefore
    authoritative — ``wall`` gates wall reads/writes, while video operations
    still fail deterministically because ``video`` is not in that set.
    """

    def assert_token_scopes(self, *required_scopes: str) -> VkAccessToken:
        token = self.token_store.load_token(self.account_alias)
        if token.token_type != "community":
            return super().assert_token_scopes(*required_scopes)
        if token.is_expired():
            raise VkWriteError(
                "VK community access key is expired. Import a fresh community key with verified permissions.",
                method="token",
                code=5,
                attempts=0,
            )
        missing = [scope for scope in required_scopes if scope not in token.scopes]
        if missing:
            raise VkWriteError(
                "Stored VK community key does not verify required permission(s): " + ", ".join(missing),
                method="token",
                code=7,
                attempts=0,
            )
        return token

    def _token_value(self) -> str:
        token = self.token_store.load_token(self.account_alias)
        if token.token_type != "community":
            return super()._token_value()
        self.assert_token_scopes()
        return token.access_token

    def credential_token_type(self) -> str:
        return self.token_store.load_token(self.account_alias).token_type

    def is_community_key(self) -> bool:
        try:
            return self.credential_token_type() == "community"
        except (AttributeError, OSError, ValueError):
            return False

    def _wall_upload_url(self) -> str:
        server = self._call(
            "photos.getWallUploadServer",
            params={"group_id": LORD_GOD_COMMUNITY_ID},
            retry_transient=True,
        )
        upload_url = str(server.get("upload_url") or "").strip() if isinstance(server, dict) else ""
        parsed = urlsplit(upload_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise LordGodWallError("photos.getWallUploadServer returned no usable HTTPS URL")
        return upload_url

    def _upload_wall_photo(self, *, upload_url: str, jpeg: bytes, file_name: str) -> dict[str, Any]:
        try:
            response = self._http_client.post(
                upload_url,
                files={"photo": (file_name, jpeg, "image/jpeg")},
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise LordGodWallError(f"wall photo upload failed before save: {type(exc).__name__}: {exc}") from exc
        if not isinstance(payload, dict):
            raise LordGodWallError("VK upload server returned a non-object response")
        if not isinstance(payload.get("photo"), str) or not str(payload["photo"]).strip():
            raise LordGodWallError("VK upload response has no photo value")
        if not isinstance(payload.get("hash"), str) or not str(payload["hash"]).strip():
            raise LordGodWallError("VK upload response has no hash value")
        if type(payload.get("server")) is not int:
            raise LordGodWallError("VK upload response server is not an exact integer")
        return payload

    def _save_wall_photo(self, upload: dict[str, Any]) -> str:
        response = self._call(
            "photos.saveWallPhoto",
            params={
                "group_id": LORD_GOD_COMMUNITY_ID,
                "photo": str(upload["photo"]),
                "server": int(upload["server"]),
                "hash": str(upload["hash"]),
            },
        )
        photos = [item for item in response if isinstance(item, dict)] if isinstance(response, list) else []
        if len(photos) != 1:
            raise LordGodWallError(f"photos.saveWallPhoto returned {len(photos)} photos")
        photo = photos[0]
        owner_id = photo.get("owner_id")
        photo_id = photo.get("id")
        if type(owner_id) is not int or owner_id != LORD_GOD_OWNER_ID or type(photo_id) is not int or photo_id <= 0:
            raise LordGodWallError("photos.saveWallPhoto returned an invalid photo identity")
        token = f"photo{owner_id}_{photo_id}"
        access_key = str(photo.get("access_key") or "").strip()
        if access_key:
            token += f"_{access_key}"
        return token

    def _upload_text_photo(self, wall: LordGodWallOperation, jpeg: bytes) -> str:
        if wall.photo_sha256 != _sha256_text_bytes(jpeg):
            raise LordGodWallError("cover photo bytes differ from the reviewed photo_sha256")
        self.assert_token_scopes("wall", "photos")
        upload = self._upload_wall_photo(
            upload_url=self._wall_upload_url(),
            jpeg=jpeg,
            file_name=Path(wall.photo_path or "cover.jpg").name,
        )
        return self._save_wall_photo(upload)

    def schedule_text_with_community_key(
        self, wall: LordGodWallOperation, *, photo_jpeg: bytes | None = None
    ) -> dict[str, Any]:
        """Schedule one text post with the community access key.

        VK rejects ``wall.get`` under group authorization (error 27), so the
        snapshot-based preflight/postflight of the user-token path is
        impossible with this credential. This mode therefore performs exactly
        one ``wall.post`` (idempotency rests on the deterministic ``guid``
        plus the wave journal) and then attempts a non-gating readback via
        ``wall.getById``; the readback outcome is reported, never hidden.
        """

        if self.credential_token_type() != "community":
            raise LordGodWallError("community-key scheduling requires a community access key token")
        self.assert_token_scopes("wall")
        self.assert_method_circuit_closed("wall.post")
        photo_token: str | None = None
        if wall.photo_path is not None:
            if photo_jpeg is None:
                raise LordGodWallError("photo operation requires the reviewed cover bytes")
            # Photo upload/save happens strictly before wall.post dispatch:
            # any failure here is a pre-dispatch rejection, never an unknown
            # wall outcome.
            photo_token = self._upload_text_photo(wall, photo_jpeg)
        post_params: dict[str, Any] = {
            "owner_id": LORD_GOD_OWNER_ID,
            "from_group": True,
            "message": wall.message,
            "publish_date": wall.publish_date,
            "guid": wall.guid,
        }
        if photo_token is not None:
            post_params["attachments"] = photo_token
        try:
            response = self._call(
                "wall.post",
                params=post_params,
            )
        except VkWriteError:
            raise
        except Exception as exc:
            raise UnknownProviderOutcomeError(f"{type(exc).__name__}: {exc}") from exc
        post_id = response.get("post_id") if isinstance(response, dict) else response
        if type(post_id) is not int or post_id <= 0:
            raise RuntimeError(f"wall.post returned no positive post ID: {response!r}")

        readback: dict[str, Any]
        try:
            item = self.read_post(community_id=LORD_GOD_COMMUNITY_ID, post_id=post_id)
        except VkWriteError as exc:
            readback = {"status": "unavailable", "code": exc.code, "method": exc.method or "wall.getById"}
        else:
            if item is None:
                readback = {"status": "not_visible"}
            else:
                fingerprint = VkWallPostFingerprint.from_item(item, surface=VkWallSurface.POSTPONED)
                if photo_token is not None:
                    # Wall readbacks canonicalize attachments without the
                    # access key, so compare against the bare photo token.
                    bare_token = "_".join(photo_token.split("_")[:2])
                    attachment_matches = fingerprint.attachments == (bare_token,)
                else:
                    attachment_matches = not fingerprint.attachments
                matches = (
                    fingerprint.publish_date == wall.publish_date
                    and fingerprint.text_sha256 == wall.message_sha256
                    and attachment_matches
                )
                readback = {"status": "verified" if matches else "mismatch"}
        result: dict[str, Any] = {
            "status": "scheduled_community_key",
            "remote_id": f"{LORD_GOD_OWNER_ID}_{post_id}",
            "publish_date": wall.publish_date,
            "surface": VkWallSurface.POSTPONED.value,
            "readback": readback,
            "source_id": wall.source_id,
        }
        if photo_token is not None:
            result["photo_attachment"] = photo_token
        return result

    def verify_video(self, wall: LordGodWallOperation) -> dict[str, Any]:
        if wall.content_kind != "video" or wall.video_owner_id is None or wall.video_id is None:
            raise LordGodWallError("verify_video requires a video operation")
        item = self.read_video(owner_id=wall.video_owner_id, video_id=wall.video_id)
        if item is None:
            raise LordGodWallError(f"VK video {wall.video_remote_id} is not visible")
        title = canonical_vk_text(str(item.get("title") or ""))
        description = canonical_vk_text(str(item.get("description") or ""))
        if title != wall.expected_video_title:
            raise LordGodWallError("live VK video title differs from the reviewed operation")
        if _sha256_text(description) != wall.expected_video_description_sha256:
            raise LordGodWallError("live VK video description differs from the reviewed operation")
        player = str(item.get("player") or "").strip()
        files = item.get("files")
        if not player and not (isinstance(files, Mapping) and any(str(v or "").strip() for v in files.values())):
            raise LordGodWallError("live VK video is not playable")
        return item

    @staticmethod
    def _matches(snapshot: Any, wall: LordGodWallOperation) -> list[Any]:
        expected_attachment = wall.attachment
        matches = []
        for post in snapshot.posts:
            if post.publish_date != wall.publish_date or post.text_sha256 != wall.message_sha256:
                continue
            if wall.content_kind == "video":
                if post.attachments != (expected_attachment,):
                    continue
            elif wall.photo_path is not None:
                # The saved photo identity is minted during apply, so the
                # operation cannot name an exact token in advance. A photo
                # text post matches when it carries exactly one photo
                # attachment; the token itself is bound by the journal.
                if len(post.attachments) != 1 or not post.attachments[0].startswith("photo"):
                    continue
            elif post.attachments:
                continue
            matches.append(post)
        return matches

    @staticmethod
    def _assert_text_preflight(snapshot: Any, wall: LordGodWallOperation) -> Any | None:
        exact = LordGodWallWriter._matches(snapshot, wall)
        if len(exact) > 1:
            raise LordGodWallError("more than one exact text wall post already exists")
        if exact:
            return exact[0]
        duplicate_text = [post for post in snapshot.posts if post.text_sha256 == wall.message_sha256]
        if duplicate_text:
            raise LordGodWallError("the exact text already exists on the published/postponed wall")
        collisions = [
            post
            for post in snapshot.posts
            if post.surface is VkWallSurface.POSTPONED and post.publish_date == wall.publish_date
        ]
        if collisions:
            raise LordGodWallError("postponed schedule slot is already occupied")
        return None

    def schedule_text(self, wall: LordGodWallOperation, *, photo_jpeg: bytes | None = None) -> dict[str, Any]:
        if self.is_community_key():
            return self.schedule_text_with_community_key(wall, photo_jpeg=photo_jpeg)
        if wall.photo_path is not None:
            raise LordGodWallError("photo attachments are supported only on the community-key path")
        self.assert_method_circuit_closed("wall.get")
        self.assert_method_circuit_closed("wall.post")
        before = self.capture_wall_snapshot(
            community_id=LORD_GOD_COMMUNITY_ID,
            max_posts_per_surface=10_000,
        )
        if not before.complete:
            raise LordGodWallError("published/postponed wall preflight is incomplete")
        existing = self._assert_text_preflight(before, wall)
        if existing is not None:
            return {
                "status": "already_applied",
                "remote_id": existing.remote_id,
                "publish_date": existing.publish_date,
                "surface": existing.surface.value,
                "before_snapshot_sha256": before.snapshot_sha256,
                "after_snapshot_sha256": before.snapshot_sha256,
            }

        mutation_started = False
        try:
            mutation_started = True
            response = self._call(
                "wall.post",
                params={
                    "owner_id": LORD_GOD_OWNER_ID,
                    "from_group": True,
                    "message": wall.message,
                    "publish_date": wall.publish_date,
                    "guid": wall.guid,
                },
            )
            post_id = response.get("post_id") if isinstance(response, dict) else response
            if type(post_id) is not int or post_id <= 0:
                raise RuntimeError(f"wall.post returned no positive post ID: {response!r}")

            after = self.capture_wall_snapshot(
                community_id=LORD_GOD_COMMUNITY_ID,
                max_posts_per_surface=10_000,
            )
            exact = [
                post
                for post in self._matches(after, wall)
                if post.post_id == post_id and post.surface is VkWallSurface.POSTPONED
            ]
            if len(exact) != 1:
                raise RuntimeError("accepted postponed text post is not exactly visible after postflight")
            delta = compare_wall_snapshots(before, after)
            expected_created = (f"postponed:{LORD_GOD_OWNER_ID}_{post_id}",)
            if (
                delta.status is not VkWallDeltaStatus.CHANGED
                or delta.created != expected_created
                or delta.removed
                or delta.changed
            ):
                raise RuntimeError("text wall postflight observed an unexpected wall delta")
            return {
                "status": "scheduled",
                "remote_id": exact[0].remote_id,
                "publish_date": exact[0].publish_date,
                "surface": exact[0].surface.value,
                "before_snapshot_sha256": before.snapshot_sha256,
                "after_snapshot_sha256": after.snapshot_sha256,
                "wall_delta": delta.as_dict(),
                "source_id": wall.source_id,
            }
        except (VkWriteError, VkWallRecoveryRequired):
            raise
        except Exception as exc:
            if mutation_started:
                raise UnknownProviderOutcomeError(f"{type(exc).__name__}: {exc}") from exc
            raise

    def schedule_video(self, wall: LordGodWallOperation) -> dict[str, Any]:
        self.assert_method_circuit_closed("wall.get")
        self.assert_method_circuit_closed("wall.post")
        self.verify_video(wall)
        assert wall.video_owner_id is not None and wall.video_id is not None
        result = self.post_video(
            community_id=LORD_GOD_COMMUNITY_ID,
            video_owner_id=wall.video_owner_id,
            video_id=wall.video_id,
            message=wall.message,
            guid=wall.guid,
            publish_at=datetime.fromtimestamp(wall.publish_date, tz=UTC),
            minimum_future_seconds=300,
            max_posts_per_surface=10_000,
        )
        return {
            "status": "scheduled",
            "remote_id": result.remote_id,
            "publish_date": result.publish_date,
            "surface": VkWallSurface.POSTPONED.value,
            "before_snapshot_sha256": result.before_snapshot_sha256,
            "after_snapshot_sha256": result.after_snapshot_sha256,
            "video_remote_id": result.video_remote_id,
            "source_id": wall.source_id,
        }

    def reconcile_exact(self, wall: LordGodWallOperation) -> dict[str, Any]:
        self.assert_method_circuit_closed("wall.get")
        if wall.content_kind == "video":
            self.verify_video(wall)
        snapshot = self.capture_wall_snapshot(
            community_id=LORD_GOD_COMMUNITY_ID,
            max_posts_per_surface=10_000,
        )
        if not snapshot.complete:
            raise RuntimeError("Lord God wall reconciliation snapshot is incomplete")
        matches = self._matches(snapshot, wall)
        if len(matches) != 1:
            raise RuntimeError(f"exact Lord God wall reconciliation requires one match; found {len(matches)}")
        match = matches[0]
        return {
            "status": "reconciled_exact_post",
            "remote_id": match.remote_id,
            "publish_date": match.publish_date,
            "surface": match.surface.value,
            "source_id": wall.source_id,
            "video_remote_id": wall.video_remote_id,
            "snapshot_sha256": snapshot.snapshot_sha256,
        }


class LordGodPostponedWallAdapter:
    reconciliation_replay_safe = True

    def __init__(self, *, account_alias: str = LORD_GOD_ACCOUNT_ALIAS, repository_root: Path | None = None) -> None:
        if account_alias in LORD_GOD_QUARANTINED_ACCOUNT_ALIASES:
            raise ValueError(
                "Lord God wall provider refuses the quarantined legacy VK credential; "
                f"use the separately imported alias {LORD_GOD_ACCOUNT_ALIAS} (Lord God community access key)"
            )
        if account_alias != LORD_GOD_ACCOUNT_ALIAS:
            raise ValueError("Lord God wall provider requires the exact local VK alias")
        settings = get_settings()
        self.settings = settings
        self.repository_root = (repository_root or Path(".")).resolve()
        self.account_alias = account_alias
        self.writer = LordGodWallWriter(
            token_store=VkTokenStore(settings.data_dir),
            account_alias=account_alias,
            api_version=settings.vk_api_version,
        )

    def execute(self, operation: WaveOperation) -> Mapping[str, Any]:
        try:
            wall = parse_lord_god_wall_operation(operation)
            if wall.publish_date <= int(datetime.now(UTC).timestamp()) + 300:
                raise LordGodWallError("postponed publish_date is not safely in the future")
        except (ValueError, LordGodWallError) as exc:
            raise OperationRejectedError(str(exc)) from exc

        lock_path = self.settings.data_dir / "locks" / f"vk-wall-{LORD_GOD_COMMUNITY_ID}.lock"
        try:
            with local_vk_write_lock(
                lock_path,
                account=self.account_alias,
                community_id=LORD_GOD_COMMUNITY_ID,
                operation=f"lord-god-postponed-wall:{wall.source_id}",
            ):
                if self.writer.is_community_key() and wall.content_kind == "video":
                    raise OperationRejectedError(
                        "the community access key cannot verify or schedule video operations; "
                        "video slots require a user-token credential"
                    )
                if wall.content_kind == "video":
                    return self.writer.schedule_video(wall)
                photo_jpeg: bytes | None = None
                if wall.photo_path is not None:
                    photo_file = (self.repository_root / wall.photo_path).resolve()
                    try:
                        photo_file.relative_to(self.repository_root)
                    except ValueError as exc:
                        raise OperationRejectedError("cover photo path escapes the repository root") from exc
                    try:
                        photo_jpeg = photo_file.read_bytes()
                    except OSError as exc:
                        raise OperationRejectedError(f"cover photo is unreadable: {wall.photo_path}") from exc
                    if _sha256_text_bytes(photo_jpeg) != wall.photo_sha256:
                        raise OperationRejectedError("cover photo bytes differ from the reviewed photo_sha256")
                return self.writer.schedule_text(wall, photo_jpeg=photo_jpeg)
        except UnknownProviderOutcomeError:
            raise
        except VkWallRecoveryRequired as exc:
            raise UnknownProviderOutcomeError(str(exc)) from exc
        except VkWriteError as exc:
            if exc.attempts == 0:
                raise OperationRejectedError(str(exc)) from exc
            if exc.code is not None:
                raise KnownProviderRejectionError(str(exc)) from exc
            raise UnknownProviderOutcomeError(str(exc)) from exc
        except (LordGodWallError, OSError, ValueError) as exc:
            raise OperationRejectedError(str(exc)) from exc

    def reconcile(self, operation: WaveOperation) -> Mapping[str, Any]:
        wall = parse_lord_god_wall_operation(operation)
        if wall.account_alias != self.account_alias:
            raise RuntimeError("operation account alias differs from the provider alias")
        return self.writer.reconcile_exact(wall)

    def close(self) -> None:
        close = getattr(self.writer, "close", None)
        if callable(close):
            close()


__all__ = [
    "LORD_GOD_ACCOUNT_ALIAS",
    "LORD_GOD_QUARANTINED_ACCOUNT_ALIASES",
    "LORD_GOD_COMMUNITY_ID",
    "LORD_GOD_OWNER_ID",
    "LORD_GOD_PROJECT_KEY",
    "LORD_GOD_WALL_OPERATION_KIND",
    "LORD_GOD_WALL_POLICY_VERSION",
    "LordGodPostponedWallAdapter",
    "LordGodWallError",
    "LordGodWallOperation",
    "LordGodWallWriter",
    "parse_lord_god_wall_operation",
]
