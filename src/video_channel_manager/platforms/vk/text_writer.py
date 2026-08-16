from __future__ import annotations

import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from video_channel_manager.platforms.vk.writer import VkVideoWriter, VkWriteError

_ZERO_WIDTH = {"\ufeff", "\u200b", "\u2060"}


@dataclass(frozen=True, slots=True)
class VkVideoTextSnapshot:
    owner_id: int
    video_id: int
    title: str
    description: str

    @property
    def remote_id(self) -> str:
        return f"{self.owner_id}_{self.video_id}"


def canonical_vk_text(value: str) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    text = "".join(character for character in text if character not in _ZERO_WIDTH)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).strip()


def vk_texts_equivalent(left: str, right: str) -> bool:
    return canonical_vk_text(left) == canonical_vk_text(right)


def vk_edit_response_succeeded(response: object) -> bool:
    """Return whether VK acknowledged an edit mutation.

    ``video.edit`` and ``video.editAlbum`` may return either the legacy scalar
    ``1`` or an object such as ``{"success": 1, "access_key": "..."}``.
    The caller must still verify the resulting live state after this
    acknowledgement; this helper deliberately does not treat an access key by
    itself as success.
    """

    if response in (1, True):
        return True
    if not isinstance(response, dict):
        return False
    return response.get("success") in (1, True)


class VkVideoTextWriter(VkVideoWriter):
    """Guarded editor for VK video titles and plain-text descriptions."""

    def read_text(self, *, owner_id: int, video_id: int) -> VkVideoTextSnapshot | None:
        item = self.read_video(owner_id=owner_id, video_id=video_id)
        if item is None:
            return None
        return VkVideoTextSnapshot(
            owner_id=int(item.get("owner_id") or owner_id),
            video_id=int(item.get("id") or video_id),
            title=str(item.get("title") or ""),
            description=str(item.get("description") or ""),
        )

    def replace_text_if_current(
        self,
        *,
        owner_id: int,
        video_id: int,
        expected_description: str,
        new_description: str,
        expected_title: str | None = None,
        new_title: str | None = None,
        verification_attempts: int = 5,
        verification_delay_seconds: float = 0.5,
        exact_description: bool = False,
        require_short_video: bool = False,
        before_dispatch: Callable[[], None] | None = None,
    ) -> VkVideoTextSnapshot:
        raw_current = self.read_video(owner_id=owner_id, video_id=video_id)
        if raw_current is None:
            raise VkWriteError(
                f"VK video {owner_id}_{video_id} is not visible.",
                method="video.get",
            )
        if raw_current.get("owner_id") != owner_id or raw_current.get("id") != video_id:
            raise VkWriteError(
                f"VK returned unexpected identity {raw_current.get('owner_id')}_{raw_current.get('id')} "
                f"for {owner_id}_{video_id}.",
                method="video.get",
            )
        if require_short_video and raw_current.get("type") != "short_video":
            raise VkWriteError(
                f"VK video {owner_id}_{video_id} is not an exact native short_video Clip.",
                method="video.get",
            )
        raw_title = raw_current.get("title")
        raw_description = raw_current.get("description")
        if exact_description and (not isinstance(raw_title, str) or not raw_title):
            raise VkWriteError(f"VK video {owner_id}_{video_id} has no exact non-empty title.", method="video.get")
        if exact_description and not isinstance(raw_description, str):
            raise VkWriteError(f"VK video {owner_id}_{video_id} has no exact description string.", method="video.get")

        current = VkVideoTextSnapshot(
            owner_id=owner_id,
            video_id=video_id,
            title=str(raw_title or ""),
            description=str(raw_description or ""),
        )
        description_matches = (
            current.description == expected_description
            if exact_description
            else vk_texts_equivalent(current.description, expected_description)
        )
        if not description_matches:
            detail = (
                "does not equal the exact reviewed BEFORE state"
                if exact_description
                else "no longer matches the reviewed before-state"
            )
            raise VkWriteError(
                f"VK video {current.remote_id} description {detail}.",
                method="video.edit",
            )
        if expected_title is not None:
            title_matches = current.title == expected_title if exact_description else vk_texts_equivalent(current.title, expected_title)
            if not title_matches:
                raise VkWriteError(
                    f"VK video {current.remote_id} title no longer matches the reviewed before-state.",
                    method="video.edit",
                )

        target_title = current.title if new_title is None else (new_title if exact_description else new_title.strip())
        target_description = new_description if exact_description else canonical_vk_text(new_description)
        if not target_title:
            raise ValueError("VK video title cannot be blank")

        title_changed = current.title != target_title if exact_description else not vk_texts_equivalent(current.title, target_title)
        description_changed = (
            current.description != target_description
            if exact_description
            else not vk_texts_equivalent(current.description, target_description)
        )
        if not title_changed and not description_changed:
            return current

        params: dict[str, str | int] = {
            "owner_id": owner_id,
            "video_id": video_id,
        }
        if title_changed:
            params["name"] = target_title
        if description_changed:
            params["desc"] = target_description

        if before_dispatch is not None:
            before_dispatch()
        response = self._call("video.edit", params=params, retry_transient=False)
        if not vk_edit_response_succeeded(response):
            raise VkWriteError(
                f"video.edit returned an unexpected response: {response!r}",
                method="video.edit",
            )

        attempts = max(1, verification_attempts)
        delay = max(0.0, verification_delay_seconds)
        last: VkVideoTextSnapshot | None = None
        last_raw_type: object = None
        for attempt in range(attempts):
            raw_last = self.read_video(owner_id=owner_id, video_id=video_id)
            if raw_last is not None:
                last_raw_type = raw_last.get("type")
                raw_last_title = raw_last.get("title")
                raw_last_description = raw_last.get("description")
                if isinstance(raw_last_title, str) and isinstance(raw_last_description, str):
                    last = VkVideoTextSnapshot(
                        owner_id=int(raw_last.get("owner_id") or owner_id),
                        video_id=int(raw_last.get("id") or video_id),
                        title=raw_last_title,
                        description=raw_last_description,
                    )
            if last is not None:
                identity_matches = last.owner_id == owner_id and last.video_id == video_id
                type_matches = not require_short_video or last_raw_type == "short_video"
                if exact_description:
                    title_matches = last.title == target_title
                    description_matches = last.description == target_description
                else:
                    title_matches = vk_texts_equivalent(last.title, target_title)
                    description_matches = vk_texts_equivalent(last.description, target_description)
                if identity_matches and type_matches and title_matches and description_matches:
                    return last
            if attempt + 1 < attempts and delay:
                time.sleep(delay)
                delay *= 2

        observed: dict[str, Any] = {
            "title": None if last is None else last.title,
            "description": None if last is None else last.description,
            "type": last_raw_type,
        }
        raise VkWriteError(
            f"video.edit was not visible after {attempts} verification attempts: {observed!r}",
            method="video.edit",
        )


__all__ = [
    "VkVideoTextSnapshot",
    "VkVideoTextWriter",
    "canonical_vk_text",
    "vk_edit_response_succeeded",
    "vk_texts_equivalent",
]
