from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from video_channel_manager.platforms.vk.writer import VkVideoWriter, VkWriteError


def _text_sha256(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


class VkVideoDescriptionRecoveryRequired(VkWriteError):
    """A Clip description edit may have crossed the provider boundary and must not replay."""


@dataclass(frozen=True, slots=True)
class VkVideoDescriptionEditResult:
    remote_id: str
    title: str
    video_type: str
    before_text_sha256: str
    after_text_sha256: str
    provider_writes_executed: int = 1


def _exact_clip_item(
    item: dict[str, Any] | None,
    *,
    owner_id: int,
    video_id: int,
) -> tuple[str, str]:
    if item is None:
        raise VkWriteError(f"VK Clip {owner_id}_{video_id} is not visible", method="video.get")
    if item.get("owner_id") != owner_id or item.get("id") != video_id:
        raise VkWriteError(
            f"VK returned unexpected identity {item.get('owner_id')}_{item.get('id')} for {owner_id}_{video_id}",
            method="video.get",
        )
    if item.get("type") != "short_video":
        raise VkWriteError(
            f"VK video {owner_id}_{video_id} is not an exact native short_video Clip",
            method="video.get",
        )
    title = item.get("title")
    description = item.get("description")
    if not isinstance(title, str) or not title:
        raise VkWriteError(f"VK Clip {owner_id}_{video_id} has no exact non-empty title", method="video.get")
    if not isinstance(description, str):
        raise VkWriteError(f"VK Clip {owner_id}_{video_id} has no exact description string", method="video.get")
    return title, description


class VkVideoDescriptionWriter(VkVideoWriter):
    """Replace one native Clip description using exact, non-normalized provider text evidence."""

    def replace_description_if_current(
        self,
        *,
        owner_id: int,
        video_id: int,
        expected_description: str,
        new_description: str,
        verification_attempts: int = 5,
        verification_delay_seconds: float = 0.5,
        before_dispatch: Callable[[], None] | None = None,
    ) -> VkVideoDescriptionEditResult:
        if owner_id == 0 or video_id <= 0:
            raise ValueError("owner_id cannot be zero and video_id must be positive")
        if expected_description == new_description:
            raise ValueError("Exact Clip description edit requires a changed target")
        if verification_attempts <= 0:
            raise ValueError("verification_attempts must be positive")
        if verification_delay_seconds < 0:
            raise ValueError("verification_delay_seconds cannot be negative")

        before_item = self.read_video(owner_id=owner_id, video_id=video_id)
        before_title, before_description = _exact_clip_item(
            before_item,
            owner_id=owner_id,
            video_id=video_id,
        )
        if before_description != expected_description:
            raise VkWriteError(
                f"VK Clip {owner_id}_{video_id} description no longer equals the exact reviewed BEFORE state",
                method="video.get",
            )

        if before_dispatch is not None:
            before_dispatch()

        try:
            self._call(
                "video.edit",
                params={
                    "owner_id": owner_id,
                    "video_id": video_id,
                    "desc": new_description,
                },
                retry_transient=False,
            )
        except VkWriteError as exc:
            raise VkVideoDescriptionRecoveryRequired(
                "video.edit outcome requires exact read reconciliation; blind retry is forbidden",
                method="video.edit",
                retryable=False,
            ) from exc

        delay = verification_delay_seconds
        last_error: str | None = None
        for attempt in range(verification_attempts):
            try:
                after_item = self.read_video(owner_id=owner_id, video_id=video_id)
                after_title, after_description = _exact_clip_item(
                    after_item,
                    owner_id=owner_id,
                    video_id=video_id,
                )
            except VkWriteError as exc:
                last_error = str(exc)
            else:
                if after_title != before_title:
                    last_error = "Clip title changed during description edit"
                elif after_description != new_description:
                    last_error = "Exact target description is not visible"
                else:
                    return VkVideoDescriptionEditResult(
                        remote_id=f"{owner_id}_{video_id}",
                        title=before_title,
                        video_type="short_video",
                        before_text_sha256=_text_sha256(expected_description),
                        after_text_sha256=_text_sha256(new_description),
                    )
            if attempt + 1 < verification_attempts and delay:
                time.sleep(delay)
                delay *= 2

        raise VkVideoDescriptionRecoveryRequired(
            "video.edit postflight does not prove the exact reviewed Clip description transition; "
            f"last_error={last_error!r}; blind retry is forbidden",
            method="video.get",
            retryable=False,
        )


__all__ = [
    "VkVideoDescriptionEditResult",
    "VkVideoDescriptionRecoveryRequired",
    "VkVideoDescriptionWriter",
]
