from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from video_channel_manager.platforms.vk.text_writer import VkVideoTextWriter
from video_channel_manager.platforms.vk.writer import VkWriteError


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


class VkVideoDescriptionWriter(VkVideoTextWriter):
    """Exact native-Clip description facade over the single guarded ``video.edit`` boundary."""

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
        if expected_description == new_description:
            raise ValueError("Exact Clip description edit requires a changed target")

        dispatch_started = False

        def exact_pre_dispatch() -> None:
            nonlocal dispatch_started
            if before_dispatch is not None:
                before_dispatch()
            dispatch_started = True

        try:
            result = VkVideoTextWriter.replace_text_if_current(
                self,
                owner_id=owner_id,
                video_id=video_id,
                expected_description=expected_description,
                new_description=new_description,
                verification_attempts=verification_attempts,
                verification_delay_seconds=verification_delay_seconds,
                exact_description=True,
                require_short_video=True,
                before_dispatch=exact_pre_dispatch,
            )
        except VkWriteError as exc:
            if not dispatch_started:
                raise
            raise VkVideoDescriptionRecoveryRequired(
                "video.edit outcome requires exact read reconciliation; blind retry is forbidden",
                method="video.edit",
                retryable=False,
            ) from exc

        return VkVideoDescriptionEditResult(
            remote_id=result.remote_id,
            title=result.title,
            video_type="short_video",
            before_text_sha256=_text_sha256(expected_description),
            after_text_sha256=_text_sha256(new_description),
        )


__all__ = [
    "VkVideoDescriptionEditResult",
    "VkVideoDescriptionRecoveryRequired",
    "VkVideoDescriptionWriter",
]
