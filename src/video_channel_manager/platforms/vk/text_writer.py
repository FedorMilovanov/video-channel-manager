from __future__ import annotations

import time
import unicodedata
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
    ) -> VkVideoTextSnapshot:
        current = self.read_text(owner_id=owner_id, video_id=video_id)
        if current is None:
            raise VkWriteError(
                f"VK video {owner_id}_{video_id} is not visible.",
                method="video.get",
            )
        if current.owner_id != owner_id or current.video_id != video_id:
            raise VkWriteError(
                f"VK returned unexpected identity {current.remote_id} for {owner_id}_{video_id}.",
                method="video.get",
            )
        if not vk_texts_equivalent(current.description, expected_description):
            raise VkWriteError(
                f"VK video {current.remote_id} description no longer matches the reviewed before-state.",
                method="video.edit",
            )
        if expected_title is not None and not vk_texts_equivalent(current.title, expected_title):
            raise VkWriteError(
                f"VK video {current.remote_id} title no longer matches the reviewed before-state.",
                method="video.edit",
            )

        target_title = current.title if new_title is None else new_title.strip()
        target_description = canonical_vk_text(new_description)
        if not target_title:
            raise ValueError("VK video title cannot be blank")

        title_changed = not vk_texts_equivalent(current.title, target_title)
        description_changed = not vk_texts_equivalent(current.description, target_description)
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

        response = self._call("video.edit", params=params)
        if not vk_edit_response_succeeded(response):
            raise VkWriteError(
                f"video.edit returned an unexpected response: {response!r}",
                method="video.edit",
            )

        attempts = max(1, verification_attempts)
        delay = max(0.0, verification_delay_seconds)
        last: VkVideoTextSnapshot | None = None
        for attempt in range(attempts):
            last = self.read_text(owner_id=owner_id, video_id=video_id)
            if (
                last is not None
                and vk_texts_equivalent(last.title, target_title)
                and vk_texts_equivalent(last.description, target_description)
            ):
                return last
            if attempt + 1 < attempts and delay:
                time.sleep(delay)
                delay *= 2

        observed: dict[str, Any] = {
            "title": None if last is None else last.title,
            "description": None if last is None else last.description,
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
