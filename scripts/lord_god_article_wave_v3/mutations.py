from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from video_channel_manager.platforms.vk import VkApiClient, VkApiError

from .common import (
    BLOCKING_JOURNAL_STAGES,
    COMMUNITY_ID,
    JPEG_HEIGHT,
    JPEG_WIDTH,
    OWNER_ID,
    POST_WAIT_SECONDS,
    RESUMABLE_WITH_PHOTO,
    UPLOAD_TIMEOUT_SECONDS,
    bytes_sha,
    canonical_text,
    normalize_url,
    now_iso,
    write_json,
)
from .wall import (
    exact_reference,
    photo_identity_from_token,
    photo_token,
    post_reference,
    wall_snapshot,
)

_UNEXPECTED_OWNER_RE = re.compile(
    r"^RuntimeError: Saved wall photo has unexpected owner: (-?\d+)$"
)
_RECOVERY_WINDOW_SECONDS = 10 * 60


def upload_photo_bytes(upload_url: str, *, operation_id: str, jpeg: bytes) -> dict[str, Any]:
    with httpx.Client(
        follow_redirects=True,
        timeout=UPLOAD_TIMEOUT_SECONDS,
    ) as http:
        response = http.post(
            upload_url,
            files={
                "photo": (
                    f"{operation_id}.jpg",
                    jpeg,
                    "image/jpeg",
                )
            },
        )
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("VK upload server returned a non-object response")
    photo_value = payload.get("photo")
    hash_value = payload.get("hash")
    server_value = payload.get("server")
    if not isinstance(photo_value, str) or not photo_value.strip():
        raise RuntimeError("VK upload response has no photo value")
    if not isinstance(hash_value, str) or not hash_value.strip():
        raise RuntimeError("VK upload response has no hash value")
    if not isinstance(server_value, int):
        raise RuntimeError("VK upload response server value is not an integer")
    return {
        "photo": photo_value,
        "hash": hash_value,
        "server": server_value,
    }


def set_journal_stage(
    journal: dict[str, Any],
    journal_path: Path,
    operation: dict[str, Any],
    stage: str,
    **values: object,
) -> dict[str, Any]:
    operations = journal["operations"]
    operation_id = str(operation["operation_id"])
    entry = operations.get(operation_id)
    if not isinstance(entry, dict):
        entry = {
            "operation_id": operation_id,
            "article_url": operation["url"],
            "publish_date": operation["publish_date"],
            "message_sha256": operation["message_sha256"],
        }
        operations[operation_id] = entry
    entry.update({"stage": stage, "updated_at": now_iso(), **values})
    journal["updated_at"] = now_iso()
    write_json(journal_path, journal)
    return entry


def unexpected_saved_photo_owner(entry: object) -> int | None:
    if not isinstance(entry, dict):
        return None
    if str(entry.get("stage") or "") != "photo_save_unknown":
        return None
    if not isinstance(entry.get("upload_payload"), dict):
        return None
    if entry.get("post_id") is not None or entry.get("photo_token"):
        return None
    match = _UNEXPECTED_OWNER_RE.fullmatch(str(entry.get("error") or "").strip())
    return int(match.group(1)) if match else None


def _photo_has_expected_dimensions(photo: dict[str, Any]) -> bool:
    if photo.get("width") == JPEG_WIDTH and photo.get("height") == JPEG_HEIGHT:
        return True
    orig = photo.get("orig_photo")
    if isinstance(orig, dict) and orig.get("width") == JPEG_WIDTH and orig.get("height") == JPEG_HEIGHT:
        return True
    sizes = photo.get("sizes")
    if not isinstance(sizes, list):
        return False
    return any(
        isinstance(item, dict)
        and item.get("width") == JPEG_WIDTH
        and item.get("height") == JPEG_HEIGHT
        for item in sizes
    )


def recover_saved_photo_token(
    read_client: VkApiClient,
    entry: dict[str, Any],
    *,
    current_user_id: int,
) -> str:
    owner_id = unexpected_saved_photo_owner(entry)
    if owner_id != current_user_id:
        raise RuntimeError(
            "Unexpected-owner photo recovery is allowed only for the current token user"
        )
    try:
        reference_time = datetime.fromisoformat(str(entry["updated_at"])).timestamp()
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("Photo recovery journal has no valid updated_at") from exc

    response = read_client._call(
        "photos.get",
        params={
            "owner_id": current_user_id,
            "album_id": "wall",
            "rev": True,
            "extended": False,
            "photo_sizes": True,
            "count": 20,
        },
    )
    items = response.get("items") if isinstance(response, dict) else None
    photos = [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
    candidates: list[dict[str, Any]] = []
    for photo in photos:
        photo_date = photo.get("date")
        if photo.get("owner_id") != current_user_id:
            continue
        if not isinstance(photo.get("id"), int) or int(photo["id"]) <= 0:
            continue
        if not isinstance(photo_date, int):
            continue
        if abs(float(photo_date) - reference_time) > _RECOVERY_WINDOW_SECONDS:
            continue
        if not _photo_has_expected_dimensions(photo):
            continue
        candidates.append(photo)

    if len(candidates) != 1:
        raise RuntimeError(
            "Saved-photo recovery did not find exactly one recent 1200x630 wall photo; "
            f"candidates={len(candidates)}"
        )
    token = photo_token(candidates[0])
    if not token:
        raise RuntimeError("Recovered wall photo has no usable attachment token")
    return token


def saved_photo_token(
    mutation_client: VkApiClient,
    upload_payload: dict[str, Any],
) -> str:
    response = mutation_client._call(
        "photos.saveWallPhoto",
        params={
            "group_id": COMMUNITY_ID,
            "photo": str(upload_payload["photo"]),
            "server": int(upload_payload["server"]),
            "hash": str(upload_payload["hash"]),
        },
    )
    photos = (
        [item for item in response if isinstance(item, dict)]
        if isinstance(response, list)
        else []
    )
    if len(photos) != 1:
        raise RuntimeError(f"photos.saveWallPhoto returned {len(photos)} photos")
    token = photo_token(photos[0])
    if not token:
        raise RuntimeError("photos.saveWallPhoto returned no usable photo token")
    owner_id = photos[0].get("owner_id")
    if owner_id != OWNER_ID:
        get_current_user = getattr(mutation_client, "get_current_user", None)
        current_user_id = (
            get_current_user().user_id if callable(get_current_user) else None
        )
        if owner_id != current_user_id:
            raise RuntimeError(f"Saved wall photo has unexpected owner: {owner_id!r}")
    return token


def prepare_photo_token(
    *,
    operation: dict[str, Any],
    jpeg: bytes,
    read_client: VkApiClient,
    mutation_client: VkApiClient,
    journal: dict[str, Any],
    journal_path: Path,
) -> str:
    operation_id = str(operation["operation_id"])
    entry = journal["operations"].get(operation_id)
    entry = entry if isinstance(entry, dict) else {}
    stage = str(entry.get("stage") or "")
    existing_token = str(entry.get("photo_token") or "").strip()

    if stage in RESUMABLE_WITH_PHOTO and existing_token:
        return existing_token

    recover_owner = unexpected_saved_photo_owner(entry)
    if recover_owner is not None:
        current_user_id = read_client.get_current_user().user_id
        token = recover_saved_photo_token(
            read_client,
            entry,
            current_user_id=current_user_id,
        )
        set_journal_stage(
            journal,
            journal_path,
            operation,
            "photo_saved",
            photo_token=token,
            recovered_from="photo_save_unknown",
            recovered_owner_id=current_user_id,
        )
        return token

    if stage in BLOCKING_JOURNAL_STAGES:
        raise RuntimeError(f"Cannot prepare photo from blocking journal stage: {stage}")
    if stage == "photo_uploaded":
        upload_payload = entry.get("upload_payload")
        if not isinstance(upload_payload, dict):
            raise RuntimeError("photo_uploaded journal entry lacks upload payload")
    else:
        set_journal_stage(
            journal,
            journal_path,
            operation,
            "photo_upload_intent",
            asset_sha256=bytes_sha(jpeg),
        )
        server = read_client._call(
            "photos.getWallUploadServer",
            params={"group_id": COMMUNITY_ID},
        )
        upload_url = (
            str(server.get("upload_url") or "").strip()
            if isinstance(server, dict)
            else ""
        )
        parsed = urlsplit(upload_url)
        if parsed.scheme != "https" or not parsed.netloc:
            set_journal_stage(
                journal,
                journal_path,
                operation,
                "photo_upload_failed",
                error="no usable HTTPS upload URL",
            )
            raise RuntimeError("photos.getWallUploadServer returned no usable HTTPS URL")
        try:
            upload_payload = upload_photo_bytes(
                upload_url,
                operation_id=operation_id,
                jpeg=jpeg,
            )
        except Exception as exc:
            set_journal_stage(
                journal,
                journal_path,
                operation,
                "photo_upload_failed",
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        set_journal_stage(
            journal,
            journal_path,
            operation,
            "photo_uploaded",
            upload_payload=upload_payload,
        )

    set_journal_stage(
        journal,
        journal_path,
        operation,
        "photo_save_intent",
    )
    try:
        token = saved_photo_token(mutation_client, upload_payload)
    except VkApiError as exc:
        stage = (
            "photo_save_rejected"
            if exc.code is not None and not exc.retryable
            else "photo_save_unknown"
        )
        set_journal_stage(
            journal,
            journal_path,
            operation,
            stage,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise RuntimeError(
            f"Photo save outcome is {stage}; do not retry blindly: {operation_id}"
        ) from exc
    except Exception as exc:
        set_journal_stage(
            journal,
            journal_path,
            operation,
            "photo_save_unknown",
            error=f"{type(exc).__name__}: {exc}",
        )
        raise RuntimeError(
            f"Photo save outcome is unknown; do not retry blindly: {operation_id}"
        ) from exc

    set_journal_stage(
        journal,
        journal_path,
        operation,
        "photo_saved",
        photo_token=token,
    )
    return token


def response_post_id(response: object) -> int:
    value = (
        response
        if isinstance(response, int)
        else response.get("post_id")
        if isinstance(response, dict)
        else None
    )
    if isinstance(value, int) and value > 0:
        return value
    raise RuntimeError(f"wall.post returned no positive post ID: {response!r}")


def find_exact_post(
    client: VkApiClient,
    operation: dict[str, Any],
    *,
    expected_photo_token: str | None,
    expected_post_id: int | None = None,
) -> dict[str, Any] | None:
    _, postponed = wall_snapshot(client)
    for raw_post in postponed:
        if expected_post_id is not None and raw_post.get("id") != expected_post_id:
            continue
        reference = post_reference(raw_post, "postponed")
        if exact_reference(
            operation,
            reference,
            expected_photo_token=expected_photo_token,
        ):
            return reference
    return None


def wait_for_exact_post(
    client: VkApiClient,
    operation: dict[str, Any],
    *,
    post_id: int,
    photo_token_value: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + POST_WAIT_SECONDS
    last: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        _, postponed = wall_snapshot(client)
        for raw_post in postponed:
            if raw_post.get("owner_id") != OWNER_ID or raw_post.get("id") != post_id:
                continue
            reference = post_reference(raw_post, "postponed")
            last = reference
            if reference["message"] != canonical_text(operation["message"]):
                raise RuntimeError(f"Accepted post text differs: {operation['operation_id']}")
            if reference["date"] != operation["publish_date"]:
                raise RuntimeError(f"Accepted post time differs: {operation['operation_id']}")
            if normalize_url(operation["url"]) not in reference["text_urls"]:
                raise RuntimeError(
                    f"Accepted post text lacks article URL: {operation['operation_id']}"
                )
            expected_identity = photo_identity_from_token(photo_token_value)
            if (
                expected_identity is None
                or expected_identity not in reference["photo_identities"]
            ):
                raise RuntimeError(
                    f"Accepted post has a different wall photo: {operation['operation_id']}"
                )
            return reference
        time.sleep(3)
    if last is None:
        raise RuntimeError(
            f"Accepted postponed post is not visible after {POST_WAIT_SECONDS}s"
        )
    raise RuntimeError(f"Accepted postponed post is not exact after {POST_WAIT_SECONDS}s")


def submit_wall_post(
    *,
    operation: dict[str, Any],
    photo_token_value: str,
    read_client: VkApiClient,
    mutation_client: VkApiClient,
    journal: dict[str, Any],
    journal_path: Path,
) -> tuple[int, dict[str, Any]]:
    operation_id = str(operation["operation_id"])
    guid = str(operation.get("guid") or operation_id)
    set_journal_stage(
        journal,
        journal_path,
        operation,
        "wall_post_intent",
        photo_token=photo_token_value,
        guid=guid,
    )
    try:
        response = mutation_client._call(
            "wall.post",
            params={
                "owner_id": OWNER_ID,
                "from_group": True,
                "message": str(operation["message"]),
                "attachments": photo_token_value,
                "publish_date": int(operation["publish_date"]),
                "guid": guid,
            },
        )
    except VkApiError as exc:
        explicit = exc.code is not None and not exc.retryable
        stage = "wall_post_rejected" if explicit else "wall_post_unknown"
        set_journal_stage(
            journal,
            journal_path,
            operation,
            stage,
            photo_token=photo_token_value,
            guid=guid,
            error=f"{type(exc).__name__}: {exc}",
        )
        if not explicit:
            reconciled = find_exact_post(
                read_client,
                operation,
                expected_photo_token=photo_token_value,
            )
            if reconciled and isinstance(reconciled.get("post_id"), int):
                post_id = int(reconciled["post_id"])
                set_journal_stage(
                    journal,
                    journal_path,
                    operation,
                    "verified",
                    photo_token=photo_token_value,
                    guid=guid,
                    post_id=post_id,
                    reconciled_from="wall_post_unknown",
                )
                return post_id, reconciled
        raise RuntimeError(
            f"wall.post outcome is {stage}; do not retry blindly: {operation_id}"
        ) from exc
    except Exception as exc:
        set_journal_stage(
            journal,
            journal_path,
            operation,
            "wall_post_unknown",
            photo_token=photo_token_value,
            guid=guid,
            error=f"{type(exc).__name__}: {exc}",
        )
        reconciled = find_exact_post(
            read_client,
            operation,
            expected_photo_token=photo_token_value,
        )
        if reconciled and isinstance(reconciled.get("post_id"), int):
            post_id = int(reconciled["post_id"])
            set_journal_stage(
                journal,
                journal_path,
                operation,
                "verified",
                photo_token=photo_token_value,
                guid=guid,
                post_id=post_id,
                reconciled_from="wall_post_unknown",
            )
            return post_id, reconciled
        raise RuntimeError(
            f"wall.post outcome is unknown; do not retry blindly: {operation_id}"
        ) from exc

    post_id = response_post_id(response)
    set_journal_stage(
        journal,
        journal_path,
        operation,
        "wall_post_accepted",
        photo_token=photo_token_value,
        guid=guid,
        post_id=post_id,
    )
    try:
        reference = wait_for_exact_post(
            read_client,
            operation,
            post_id=post_id,
            photo_token_value=photo_token_value,
        )
    except Exception as exc:
        set_journal_stage(
            journal,
            journal_path,
            operation,
            "wall_post_accepted_unverified",
            photo_token=photo_token_value,
            guid=guid,
            post_id=post_id,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise RuntimeError(f"Accepted post requires inspection: {operation_id}") from exc

    set_journal_stage(
        journal,
        journal_path,
        operation,
        "verified",
        photo_token=photo_token_value,
        guid=guid,
        post_id=post_id,
    )
    return post_id, reference
