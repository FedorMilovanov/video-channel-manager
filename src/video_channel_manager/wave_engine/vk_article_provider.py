from __future__ import annotations

import hashlib
import json
import struct
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text
from video_channel_manager.platforms.vk.wall import VkWallWriter
from video_channel_manager.platforms.vk.wall_safety import (
    VkWallDeltaStatus,
    VkWallSnapshot,
    VkWallSurface,
    build_wall_snapshot,
    compare_wall_snapshots,
)
from video_channel_manager.platforms.vk.writer import VkWriteError
from video_channel_manager.wave_engine.canonical import (
    file_sha256,
    object_sha256,
    resolve_repository_relative_path,
)
from video_channel_manager.wave_engine.engine import (
    OperationRejectedError,
    UnknownProviderOutcomeError,
)
from video_channel_manager.wave_engine.models import WaveOperation

VK_ARTICLE_OPERATION_KIND = "vk_postponed_article_photo"
VK_ARTICLE_PROJECT_KEY = "legendary-poet"
VK_ARTICLE_COMMUNITY_ID = 235216998
VK_ARTICLE_OWNER_ID = -235216998
VK_ARTICLE_ACCOUNT_ALIAS = "legendary-poet"
VK_ARTICLE_SITE_HOST = "thelegendarypoet.ru"
VK_ARTICLE_POLICY_RELATIVE_PATH = "data/editorial/legendary-poet-article-wave-202608.json"
VK_ARTICLE_APPROVED_POLICY_SHA256 = (
    "sha256:af210867d2ea392394e2034cffa9d43c3e1adc632386e9ec4827b033c8fff9a0"
)


class VkArticleWallError(RuntimeError):
    """A deterministic article-wall validation or preflight failure."""


@dataclass(frozen=True, slots=True)
class ArticleOperation:
    editorial_operation_id: str
    account_alias: str
    article_url: str
    image_source_url: str
    message: str
    message_sha256: str
    publish_date: int
    guid: str
    asset_path: str
    asset_sha256: str
    asset_width: int
    asset_height: int
    policy_sha256: str
    required_canary: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class WallCapture:
    published: tuple[dict[str, Any], ...]
    postponed: tuple[dict[str, Any], ...]
    snapshot: VkWallSnapshot


@dataclass(frozen=True, slots=True)
class ExactArticlePost:
    owner_id: int
    post_id: int
    publish_date: int
    photo_tokens: tuple[str, ...]
    surface: str

    @property
    def remote_id(self) -> str:
        return f"{self.owner_id}_{self.post_id}"


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _exact_string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise VkArticleWallError(f"{field} must be an exact non-empty string")
    return value


def _exact_int(value: object, *, field: str, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        raise VkArticleWallError(f"{field} must be an exact integer >= {minimum}")
    return value


def _https_url(value: object, *, field: str, required_host: str | None = None) -> str:
    url = _exact_string(value, field=field)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise VkArticleWallError(f"{field} must be an absolute HTTPS URL")
    host = (parsed.hostname or "").lower()
    if required_host is not None and host != required_host:
        raise VkArticleWallError(f"{field} must use host {required_host}")
    return url


def _normalized_message(value: object, *, article_url: str) -> str:
    raw = _exact_string(value, field="message")
    normalized = canonical_vk_text(raw)
    if raw != normalized:
        raise VkArticleWallError("message must already be canonical VK plain text")
    if len(raw) > 15_000:
        raise VkArticleWallError("message exceeds the 15,000-character wall policy")
    if raw.count(article_url) != 1:
        raise VkArticleWallError("message must contain the exact article URL once")
    return raw


def _parse_required_canary(value: object) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise VkArticleWallError("required_canary must be an object or null")
    article_url = _https_url(
        value.get("article_url"),
        field="required_canary.article_url",
        required_host=VK_ARTICLE_SITE_HOST,
    )
    message = _normalized_message(value.get("message"), article_url=article_url)
    message_sha256 = _exact_string(
        value.get("message_sha256"),
        field="required_canary.message_sha256",
    )
    if message_sha256 != _sha256_text(message):
        raise VkArticleWallError("required_canary message digest mismatch")
    return {
        "editorial_operation_id": _exact_string(
            value.get("editorial_operation_id"),
            field="required_canary.editorial_operation_id",
        ),
        "article_url": article_url,
        "message": message,
        "message_sha256": message_sha256,
        "publish_date": _exact_int(
            value.get("publish_date"),
            field="required_canary.publish_date",
        ),
    }


def parse_article_operation(operation: WaveOperation) -> ArticleOperation:
    if operation.operation_kind != VK_ARTICLE_OPERATION_KIND:
        raise VkArticleWallError(f"unsupported operation kind: {operation.operation_kind}")
    if (
        operation.project.project_key != VK_ARTICLE_PROJECT_KEY
        or operation.project.community_id != VK_ARTICLE_COMMUNITY_ID
        or operation.project.owner_id != VK_ARTICLE_OWNER_ID
    ):
        raise VkArticleWallError("article operation project/community/owner binding is invalid")
    payload = operation.payload
    article_url = _https_url(
        payload.get("article_url"),
        field="article_url",
        required_host=VK_ARTICLE_SITE_HOST,
    )
    message = _normalized_message(payload.get("message"), article_url=article_url)
    message_sha256 = _exact_string(payload.get("message_sha256"), field="message_sha256")
    if message_sha256 != _sha256_text(message):
        raise VkArticleWallError("message_sha256 mismatch")
    asset_sha256 = _exact_string(payload.get("asset_sha256"), field="asset_sha256")
    if len(asset_sha256) != 64 or any(character not in "0123456789abcdef" for character in asset_sha256):
        raise VkArticleWallError("asset_sha256 must be a lowercase SHA-256 digest")
    policy_sha256 = _exact_string(payload.get("policy_sha256"), field="policy_sha256")
    if policy_sha256 != VK_ARTICLE_APPROVED_POLICY_SHA256:
        raise VkArticleWallError("operation is not bound to the approved article policy")
    guid = _exact_string(payload.get("guid"), field="guid")
    if not guid.startswith("vcm-art-") or len(guid) > 40:
        raise VkArticleWallError("guid must be a deterministic vcm-art- identifier no longer than 40 characters")
    return ArticleOperation(
        editorial_operation_id=_exact_string(
            payload.get("editorial_operation_id"),
            field="editorial_operation_id",
        ),
        account_alias=_exact_string(payload.get("account_alias"), field="account_alias"),
        article_url=article_url,
        image_source_url=_https_url(payload.get("image_source_url"), field="image_source_url"),
        message=message,
        message_sha256=message_sha256,
        publish_date=_exact_int(payload.get("publish_date"), field="publish_date"),
        guid=guid,
        asset_path=_exact_string(payload.get("asset_path"), field="asset_path"),
        asset_sha256=asset_sha256,
        asset_width=_exact_int(payload.get("asset_width"), field="asset_width"),
        asset_height=_exact_int(payload.get("asset_height"), field="asset_height"),
        policy_sha256=policy_sha256,
        required_canary=_parse_required_canary(payload.get("required_canary")),
    )


def _policy_digest(policy: dict[str, Any]) -> str:
    payload = {key: value for key, value in policy.items() if key != "policy_sha256"}
    return "sha256:" + object_sha256(payload)


def _expected_canary(policy: dict[str, Any]) -> dict[str, Any]:
    operations = policy.get("operations")
    if not isinstance(operations, list) or not operations or not isinstance(operations[0], dict):
        raise VkArticleWallError("approved article policy has no canary operation")
    canary = operations[0]
    return {
        "editorial_operation_id": str(canary.get("operation_id") or ""),
        "article_url": str(canary.get("url") or ""),
        "message": str(canary.get("message") or ""),
        "message_sha256": str(canary.get("message_sha256") or ""),
        "publish_date": canary.get("publish_date"),
    }


def assert_approved_article_operation(
    *,
    repository_root: Path,
    article: ArticleOperation,
) -> None:
    policy_path = resolve_repository_relative_path(
        repository_root,
        VK_ARTICLE_POLICY_RELATIVE_PATH,
        require_file=True,
    )
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VkArticleWallError(f"cannot read approved article policy: {exc}") from exc
    if not isinstance(policy, dict):
        raise VkArticleWallError("approved article policy must be a JSON object")
    if (
        policy.get("policy_sha256") != VK_ARTICLE_APPROVED_POLICY_SHA256
        or _policy_digest(policy) != VK_ARTICLE_APPROVED_POLICY_SHA256
        or article.policy_sha256 != VK_ARTICLE_APPROVED_POLICY_SHA256
    ):
        raise VkArticleWallError("approved article policy digest mismatch")
    if (
        policy.get("project_key") != VK_ARTICLE_PROJECT_KEY
        or policy.get("vk_community_id") != VK_ARTICLE_COMMUNITY_ID
        or policy.get("vk_owner_id") != VK_ARTICLE_OWNER_ID
        or policy.get("account_alias") != VK_ARTICLE_ACCOUNT_ALIAS
    ):
        raise VkArticleWallError("approved article policy project binding mismatch")

    operations = policy.get("operations")
    if not isinstance(operations, list) or len(operations) != 10:
        raise VkArticleWallError("approved article policy must contain exactly ten operations")
    matches = [
        row
        for row in operations
        if isinstance(row, dict) and row.get("operation_id") == article.editorial_operation_id
    ]
    if len(matches) != 1:
        raise VkArticleWallError("article operation is absent or duplicated in the approved policy")
    row = matches[0]
    expected = {
        "article_url": row.get("url"),
        "image_source_url": row.get("image_url"),
        "message": row.get("message"),
        "message_sha256": row.get("message_sha256"),
        "publish_date": row.get("publish_date"),
    }
    actual = {
        "article_url": article.article_url,
        "image_source_url": article.image_source_url,
        "message": article.message,
        "message_sha256": article.message_sha256,
        "publish_date": article.publish_date,
    }
    if actual != expected:
        raise VkArticleWallError("article operation differs from its exact approved policy row")

    seed = (
        f"{VK_ARTICLE_APPROVED_POLICY_SHA256}:{article.editorial_operation_id}:"
        f"{article.publish_date}:{article.message_sha256}"
    )
    expected_guid = "vcm-art-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:28]
    if article.guid != expected_guid:
        raise VkArticleWallError("article operation guid differs from approved deterministic identity")

    ordinal = row.get("ordinal")
    if ordinal == 1:
        if article.required_canary is not None:
            raise VkArticleWallError("canary operation cannot require itself")
    elif article.required_canary != _expected_canary(policy):
        raise VkArticleWallError("batch operation lacks the exact approved canary requirement")


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise VkArticleWallError("asset is not a JPEG file")
    index = 2
    while index + 4 <= len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            break
        segment_length = struct.unpack(">H", data[index : index + 2])[0]
        if segment_length < 2 or index + segment_length > len(data):
            raise VkArticleWallError("JPEG has an invalid segment length")
        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            if segment_length < 7:
                raise VkArticleWallError("JPEG SOF segment is too short")
            height = struct.unpack(">H", data[index + 3 : index + 5])[0]
            width = struct.unpack(">H", data[index + 5 : index + 7])[0]
            if width <= 0 or height <= 0:
                raise VkArticleWallError("JPEG has invalid dimensions")
            return width, height
        index += segment_length
    raise VkArticleWallError("JPEG dimensions were not found")


def _photo_tokens(item: Mapping[str, Any]) -> tuple[str, ...]:
    tokens: list[str] = []
    for attachment in item.get("attachments") or []:
        if not isinstance(attachment, Mapping) or attachment.get("type") != "photo":
            continue
        photo = attachment.get("photo")
        if not isinstance(photo, Mapping):
            continue
        owner_id = photo.get("owner_id")
        photo_id = photo.get("id")
        if type(owner_id) is int and owner_id != 0 and type(photo_id) is int and photo_id > 0:
            tokens.append(f"photo{owner_id}_{photo_id}")
    return tuple(sorted(tokens))


def _exact_post(
    item: Mapping[str, Any],
    *,
    surface: VkWallSurface,
    message: str,
    article_url: str,
    publish_date: int,
) -> ExactArticlePost | None:
    owner_id = item.get("owner_id")
    post_id = item.get("id")
    date = item.get("date")
    if type(owner_id) is not int or type(post_id) is not int or type(date) is not int:
        return None
    if owner_id != VK_ARTICLE_OWNER_ID or post_id <= 0:
        return None
    text = canonical_vk_text(str(item.get("text") or ""))
    photos = _photo_tokens(item)
    if text == message and text.count(article_url) == 1 and date == publish_date and len(photos) == 1:
        return ExactArticlePost(
            owner_id=owner_id,
            post_id=post_id,
            publish_date=date,
            photo_tokens=photos,
            surface=surface.value,
        )
    return None


class VkArticleWallWriter(VkWallWriter):
    """Exact postponed article-photo writer for the Legendary Poet project."""

    def capture_complete_wall(self, *, max_posts_per_surface: int = 10_000) -> WallCapture:
        published, published_pages, published_complete = self._read_wall_surface(
            community_id=VK_ARTICLE_COMMUNITY_ID,
            surface=VkWallSurface.PUBLISHED,
            max_posts=max_posts_per_surface,
        )
        postponed, postponed_pages, postponed_complete = self._read_wall_surface(
            community_id=VK_ARTICLE_COMMUNITY_ID,
            surface=VkWallSurface.POSTPONED,
            max_posts=max_posts_per_surface,
        )
        complete = published_complete and postponed_complete
        if not complete:
            raise VkArticleWallError("published/postponed wall preflight is incomplete")
        snapshot = build_wall_snapshot(
            community_id=VK_ARTICLE_COMMUNITY_ID,
            published_items=published,
            postponed_items=postponed,
            published_pages=published_pages,
            postponed_pages=postponed_pages,
            complete=True,
        )
        return WallCapture(
            published=tuple(published),
            postponed=tuple(postponed),
            snapshot=snapshot,
        )

    @staticmethod
    def find_exact(capture: WallCapture, article: ArticleOperation | dict[str, Any]) -> list[ExactArticlePost]:
        if isinstance(article, ArticleOperation):
            message = article.message
            article_url = article.article_url
            publish_date = article.publish_date
        else:
            message = str(article["message"])
            article_url = str(article["article_url"])
            publish_date = int(article["publish_date"])
        matches: list[ExactArticlePost] = []
        for surface, items in (
            (VkWallSurface.PUBLISHED, capture.published),
            (VkWallSurface.POSTPONED, capture.postponed),
        ):
            for item in items:
                match = _exact_post(
                    item,
                    surface=surface,
                    message=message,
                    article_url=article_url,
                    publish_date=publish_date,
                )
                if match is not None:
                    matches.append(match)
        return matches

    @staticmethod
    def _preflight_conflicts(capture: WallCapture, article: ArticleOperation) -> ExactArticlePost | None:
        exact = VkArticleWallWriter.find_exact(capture, article)
        if len(exact) > 1:
            raise VkArticleWallError("more than one exact article post already exists")
        if exact:
            if exact[0].surface != VkWallSurface.POSTPONED.value:
                raise VkArticleWallError("the exact article post is already published, not postponed")
            return exact[0]

        for surface, items in (
            (VkWallSurface.PUBLISHED, capture.published),
            (VkWallSurface.POSTPONED, capture.postponed),
        ):
            for item in items:
                text = canonical_vk_text(str(item.get("text") or ""))
                date = item.get("date")
                remote = f"{item.get('owner_id')}_{item.get('id')}"
                if text == article.message:
                    raise VkArticleWallError(
                        f"article message already occurs in a non-exact {surface.value} post: {remote}"
                    )
                if surface is VkWallSurface.POSTPONED and type(date) is int and date == article.publish_date:
                    raise VkArticleWallError(f"postponed schedule slot is already occupied: {remote}")
        return None

    @staticmethod
    def _assert_canary(capture: WallCapture, required: dict[str, Any] | None) -> None:
        if required is None:
            return
        matches = VkArticleWallWriter.find_exact(capture, required)
        if len(matches) != 1 or matches[0].surface != VkWallSurface.POSTPONED.value:
            raise VkArticleWallError("verified postponed canary is absent or ambiguous")

    def _wall_upload_url(self) -> str:
        server = self._call(
            "photos.getWallUploadServer",
            params={"group_id": VK_ARTICLE_COMMUNITY_ID},
            retry_transient=True,
        )
        upload_url = str(server.get("upload_url") or "").strip() if isinstance(server, dict) else ""
        parsed = urlsplit(upload_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise VkArticleWallError("photos.getWallUploadServer returned no usable HTTPS URL")
        return upload_url

    def _upload_jpeg_once(
        self,
        *,
        upload_url: str,
        article: ArticleOperation,
        jpeg: bytes,
    ) -> dict[str, Any]:
        response = self._http_client.post(
            upload_url,
            files={
                "photo": (
                    f"{article.editorial_operation_id}.jpg",
                    jpeg,
                    "image/jpeg",
                )
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("VK upload server returned a non-object response")
        if not isinstance(payload.get("photo"), str) or not str(payload["photo"]).strip():
            raise RuntimeError("VK upload response has no photo value")
        if not isinstance(payload.get("hash"), str) or not str(payload["hash"]).strip():
            raise RuntimeError("VK upload response has no hash value")
        if type(payload.get("server")) is not int:
            raise RuntimeError("VK upload response server is not an exact integer")
        return payload

    def _save_wall_photo(self, upload: dict[str, Any]) -> tuple[str, int, int]:
        response = self._call(
            "photos.saveWallPhoto",
            params={
                "group_id": VK_ARTICLE_COMMUNITY_ID,
                "photo": str(upload["photo"]),
                "server": int(upload["server"]),
                "hash": str(upload["hash"]),
            },
        )
        photos = [item for item in response if isinstance(item, dict)] if isinstance(response, list) else []
        if len(photos) != 1:
            raise RuntimeError(f"photos.saveWallPhoto returned {len(photos)} photos")
        photo = photos[0]
        owner_id = photo.get("owner_id")
        photo_id = photo.get("id")
        if type(owner_id) is not int or owner_id == 0 or type(photo_id) is not int or photo_id <= 0:
            raise RuntimeError("photos.saveWallPhoto returned an invalid photo identity")
        token = f"photo{owner_id}_{photo_id}"
        access_key = str(photo.get("access_key") or "").strip()
        if access_key:
            token += f"_{access_key}"
        return token, owner_id, photo_id

    def schedule(self, *, article: ArticleOperation, jpeg: bytes) -> dict[str, Any]:
        before = self.capture_complete_wall()
        self._assert_canary(before, article.required_canary)
        existing = self._preflight_conflicts(before, article)
        if existing is not None:
            return {
                "status": "already_scheduled",
                "remote_id": existing.remote_id,
                "publish_date": existing.publish_date,
                "photo_tokens": list(existing.photo_tokens),
                "before_snapshot_sha256": before.snapshot.snapshot_sha256,
                "after_snapshot_sha256": before.snapshot.snapshot_sha256,
            }

        upload_url = self._wall_upload_url()
        mutation_started = False
        try:
            mutation_started = True
            upload = self._upload_jpeg_once(upload_url=upload_url, article=article, jpeg=jpeg)
            photo_token, saved_photo_owner_id, saved_photo_id = self._save_wall_photo(upload)
            response = self._call(
                "wall.post",
                params={
                    "owner_id": VK_ARTICLE_OWNER_ID,
                    "from_group": True,
                    "message": article.message,
                    "attachments": photo_token,
                    "publish_date": article.publish_date,
                    "guid": article.guid,
                },
            )
            post_id = response.get("post_id") if isinstance(response, dict) else response
            if type(post_id) is not int or post_id <= 0:
                raise RuntimeError(f"wall.post returned no positive post ID: {response!r}")

            after: WallCapture | None = None
            exact: list[ExactArticlePost] = []
            for attempt in range(6):
                after = self.capture_complete_wall()
                exact = [
                    item
                    for item in self.find_exact(after, article)
                    if item.post_id == post_id and item.surface == VkWallSurface.POSTPONED.value
                ]
                if len(exact) == 1:
                    break
                if attempt < 5:
                    time.sleep(2)
            if after is None or len(exact) != 1:
                raise RuntimeError("accepted postponed post is not exactly visible after postflight")

            delta = compare_wall_snapshots(before.snapshot, after.snapshot)
            expected_created = (f"postponed:{VK_ARTICLE_OWNER_ID}_{post_id}",)
            if (
                delta.status is not VkWallDeltaStatus.CHANGED
                or delta.created != expected_created
                or delta.removed
                or delta.changed
            ):
                raise RuntimeError("wall postflight observed an unexpected wall delta")
            match = exact[0]
            return {
                "status": "scheduled",
                "remote_id": match.remote_id,
                "publish_date": match.publish_date,
                "photo_tokens": list(match.photo_tokens),
                "saved_photo_owner_id": saved_photo_owner_id,
                "saved_photo_id": saved_photo_id,
                "before_snapshot_sha256": before.snapshot.snapshot_sha256,
                "after_snapshot_sha256": after.snapshot.snapshot_sha256,
                "wall_delta": delta.as_dict(),
            }
        except UnknownProviderOutcomeError:
            raise
        except Exception as exc:
            if mutation_started:
                raise UnknownProviderOutcomeError(f"{type(exc).__name__}: {exc}") from exc
            raise

    def reconcile_exact(self, *, article: ArticleOperation) -> dict[str, Any]:
        capture = self.capture_complete_wall()
        matches = self.find_exact(capture, article)
        if len(matches) != 1:
            raise RuntimeError(f"exact postponed article reconciliation requires one match; found {len(matches)}")
        match = matches[0]
        if match.surface != VkWallSurface.POSTPONED.value:
            raise RuntimeError("reconciled article post is not on the postponed surface")
        return {
            "status": "reconciled_exact_post",
            "remote_id": match.remote_id,
            "publish_date": match.publish_date,
            "photo_tokens": list(match.photo_tokens),
            "snapshot_sha256": capture.snapshot.snapshot_sha256,
        }


class VkPostponedArticlePhotoAdapter:
    def __init__(
        self,
        *,
        repository_root: Path,
        account_alias: str = VK_ARTICLE_ACCOUNT_ALIAS,
    ) -> None:
        if account_alias != VK_ARTICLE_ACCOUNT_ALIAS:
            raise ValueError("Legendary Poet article provider requires the exact local VK alias")
        self.repository_root = repository_root.resolve()
        settings = get_settings()
        self.settings = settings
        self.account_alias = account_alias
        self.writer = VkArticleWallWriter(
            token_store=VkTokenStore(settings.data_dir),
            account_alias=account_alias,
            api_version=settings.vk_api_version,
        )

    def execute(self, operation: WaveOperation) -> Mapping[str, Any]:
        try:
            article = parse_article_operation(operation)
            if article.account_alias != self.account_alias:
                raise VkArticleWallError("operation account alias differs from the provider alias")
            assert_approved_article_operation(
                repository_root=self.repository_root,
                article=article,
            )
            asset_path = resolve_repository_relative_path(
                self.repository_root,
                article.asset_path,
                require_file=True,
            )
            if file_sha256(asset_path) != article.asset_sha256:
                raise VkArticleWallError("materialized JPEG SHA-256 mismatch")
            jpeg = asset_path.read_bytes()
            width, height = jpeg_dimensions(jpeg)
            if (width, height) != (article.asset_width, article.asset_height):
                raise VkArticleWallError(
                    f"materialized JPEG dimensions differ: {(width, height)} != "
                    f"{(article.asset_width, article.asset_height)}"
                )
            if (width, height) != (1200, 630):
                raise VkArticleWallError("article wall JPEG must be exactly 1200x630")
            if article.publish_date <= int(datetime.now(UTC).timestamp()) + 300:
                raise VkArticleWallError("postponed publish_date is not safely in the future")
        except (OSError, ValueError, VkArticleWallError) as exc:
            raise OperationRejectedError(str(exc)) from exc

        lock_path = self.settings.data_dir / "locks" / f"vk-wall-{VK_ARTICLE_COMMUNITY_ID}.lock"
        try:
            with local_vk_write_lock(
                lock_path,
                account=self.account_alias,
                community_id=VK_ARTICLE_COMMUNITY_ID,
                operation=article.editorial_operation_id,
            ):
                return self.writer.schedule(article=article, jpeg=jpeg)
        except UnknownProviderOutcomeError:
            raise
        except (VkArticleWallError, VkWriteError, OSError, ValueError) as exc:
            raise OperationRejectedError(str(exc)) from exc

    def reconcile(self, operation: WaveOperation) -> Mapping[str, Any]:
        article = parse_article_operation(operation)
        if article.account_alias != self.account_alias:
            raise RuntimeError("operation account alias differs from the provider alias")
        assert_approved_article_operation(
            repository_root=self.repository_root,
            article=article,
        )
        return self.writer.reconcile_exact(article=article)


__all__ = [
    "VK_ARTICLE_ACCOUNT_ALIAS",
    "VK_ARTICLE_APPROVED_POLICY_SHA256",
    "VK_ARTICLE_COMMUNITY_ID",
    "VK_ARTICLE_OPERATION_KIND",
    "VK_ARTICLE_OWNER_ID",
    "VK_ARTICLE_POLICY_RELATIVE_PATH",
    "VK_ARTICLE_PROJECT_KEY",
    "VK_ARTICLE_SITE_HOST",
    "ArticleOperation",
    "ExactArticlePost",
    "WallCapture",
    "VkArticleWallError",
    "VkArticleWallWriter",
    "VkPostponedArticlePhotoAdapter",
    "assert_approved_article_operation",
    "jpeg_dimensions",
    "parse_article_operation",
]
