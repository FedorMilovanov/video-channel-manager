"""Provider-inert platform routing for a source-locked SHORTOREZ clip.

A route is a proposed render, never an accepted MP4 or publishing authority.
Do not use this module as another Telegram/VK/Instagram writer.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

Surface = Literal["vk_native_clip", "telegram_native_video", "instagram_reel_api"]
RouteStatus = Literal["render_qc_required", "speed_listening_required", "duration_ineligible"]

# Provider *surface* limits, not limits on the source clip or the Telegram API.
# The official VK Clips flow allows up to three minutes; Meta's Reels API
# currently accepts up to fifteen minutes. Both can change: recheck before send.
_MAX_MS: dict[Surface, int | None] = {
    "vk_native_clip": 180_000,
    "telegram_native_video": None,
    "instagram_reel_api": 900_000,
}
# Express speed as a percent to avoid float error at the exact 180 s boundary.
_SPEED_PERCENTS = (100, 105, 110, 115, 120)
_YOUTUBE_ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")
_SHA256 = re.compile(r"sha256:[a-f0-9]{64}\Z")
_PILOT_PROJECT = "lord-god-strength"
_PILOT_CHANNEL = "UCeSJsC6go2c9pdJCuUI1BYA"


@dataclass(frozen=True)
class ClipInterval:
    project_key: str
    source_channel_id: str
    source_video_id: str
    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        if (self.project_key, self.source_channel_id) != (_PILOT_PROJECT, _PILOT_CHANNEL):
            raise ValueError("SHORTOREZ pilot requires the exact registered source project and channel")
        if not _YOUTUBE_ID.fullmatch(self.source_video_id):
            raise ValueError("An exact eleven-character YouTube video ID is required")
        if type(self.start_ms) is not int or type(self.end_ms) is not int:
            raise ValueError("Cut boundaries must be integer milliseconds")
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError("Cut interval must have positive duration and nonnegative start")

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    @property
    def full_video_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.source_video_id}"


@dataclass(frozen=True)
class VariantRoute:
    clip: ClipInterval
    surface: Surface
    speed_percent: int
    projected_duration_ms: int
    status: RouteStatus

    @property
    def key(self) -> str:
        return (
            f"{self.clip.project_key}:{self.clip.source_video_id}:"
            f"{self.clip.start_ms}-{self.clip.end_ms}:{self.surface}:{self.speed_percent}"
        )

    @property
    def audio_listening_required(self) -> bool:
        return self.speed_percent != 100


def plan_routes(clip: ClipInterval, *, allow_speedup: bool = False) -> tuple[VariantRoute, ...]:
    """Propose one variant per surface without modifying bytes or dispatching writes.

    Only native VK Clips may use up to 1.20x, and only when this helps a
    complete clip fit 180 seconds. TG and Instagram keep the normal-speed
    longer version. All routes require actual render/rights/editorial QA.
    """
    routes: list[VariantRoute] = []
    for surface, max_ms in _MAX_MS.items():
        rates = _SPEED_PERCENTS if surface == "vk_native_clip" and allow_speedup else (100,)
        selected = next(
            (
                (rate, math.ceil(clip.duration_ms * 100 / rate))
                for rate in rates
                if max_ms is None or math.ceil(clip.duration_ms * 100 / rate) <= max_ms
            ),
            None,
        )
        if selected is None:
            routes.append(VariantRoute(clip, surface, 100, clip.duration_ms, "duration_ineligible"))
        else:
            rate, projected_ms = selected
            state: RouteStatus = "speed_listening_required" if rate != 100 else "render_qc_required"
            routes.append(VariantRoute(clip, surface, rate, projected_ms, state))
    return tuple(routes)


def validate_render_handoff(
    route: VariantRoute,
    *,
    actual_duration_ms: int,
    media_sha256: str,
    caption: str,
    source_rights_reviewed: bool,
    editorial_reviewed: bool,
    audible_result_reviewed: bool,
) -> tuple[str, ...]:
    """Check an external render handoff; success NEVER authorizes a provider write.

    These flags are explicit human/editorial assertions; they cannot prove
    rights or audio correctness by themselves. Canonical VCM writers still
    require their separate exact-media, account and no-replay preflight.
    """
    issues: list[str] = []
    if route.status == "duration_ineligible":
        issues.append("duration_ineligible")
    if type(actual_duration_ms) is not int or actual_duration_ms <= 0:
        issues.append("invalid_actual_duration")
    else:
        max_ms = _MAX_MS[route.surface]
        if max_ms is not None and actual_duration_ms > max_ms:
            issues.append("actual_duration_exceeds_surface")
        if route.surface in ("vk_native_clip", "instagram_reel_api") and actual_duration_ms < 3_000:
            issues.append("actual_duration_below_surface_minimum")
    if not isinstance(media_sha256, str) or not _SHA256.fullmatch(media_sha256):
        issues.append("invalid_media_fingerprint")
    if not isinstance(caption, str) or route.clip.full_video_url not in caption:
        issues.append("missing_exact_full_video_link")
    elif route.surface == "telegram_native_video" and len(caption) > 1_024:
        issues.append("telegram_video_caption_over_limit")
    elif route.surface == "instagram_reel_api" and len(caption) > 2_200:
        issues.append("instagram_caption_over_limit")
    if source_rights_reviewed is not True:
        issues.append("source_rights_not_reviewed")
    if editorial_reviewed is not True:
        issues.append("editorial_not_reviewed")
    if audible_result_reviewed is not True:
        issues.append("encoded_audio_not_listened")
    return tuple(issues)
