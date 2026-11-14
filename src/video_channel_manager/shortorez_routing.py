"""Provider-inert platform routing for a source-locked SHORTOREZ clip.

A route is a proposed render, never an accepted MP4 or publishing authority.
Do not use this module as another Telegram/VK/Instagram writer.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from video_channel_manager.editorial._project_profiles import LORD_GOD_STRENGTH, PROJECT_CHANNEL_IDS

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
_PILOT_PROJECT = LORD_GOD_STRENGTH


@dataclass(frozen=True)
class ClipInterval:
    project_key: str
    source_channel_id: str
    source_video_id: str
    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        if self.project_key != _PILOT_PROJECT or self.source_channel_id not in PROJECT_CHANNEL_IDS[_PILOT_PROJECT]:
            raise ValueError("SHORTOREZ pilot requires the exact registered source project and channel")
        if not isinstance(self.source_video_id, str) or not _YOUTUBE_ID.fullmatch(self.source_video_id):
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
                (rate, (clip.duration_ms * 100 + rate - 1) // rate)
                for rate in rates
                if max_ms is None or (clip.duration_ms * 100 + rate - 1) // rate <= max_ms
            ),
            None,
        )
        # VK native Clips and Meta Reels both require at least three seconds.
        # A synthetic one-second route must not look render-ready.
        if selected is None or (surface in ("vk_native_clip", "instagram_reel_api") and selected[1] < 3_000):
            routes.append(VariantRoute(clip, surface, 100, clip.duration_ms, "duration_ineligible"))
        else:
            rate, projected_ms = selected
            state: RouteStatus = "speed_listening_required" if rate != 100 else "render_qc_required"
            routes.append(VariantRoute(clip, surface, rate, projected_ms, state))
    return tuple(routes)


def _source_link_position(caption: str, source_video_id: str) -> int | None:
    """Locate a genuinely exact HTTPS watch URL, not a lookalike substring."""
    for match in re.finditer(r"https://[^\s<>()\[\]]+", caption):
        candidate = match.group().rstrip(".,!?;:")
        try:
            parsed = urlsplit(candidate)
        except ValueError:
            continue
        if (
            parsed.scheme == "https"
            and parsed.hostname in {"www.youtube.com", "youtube.com"}
            and parsed.path == "/watch"
            and parse_qs(parsed.query).get("v") == [source_video_id]
        ):
            return match.start()
    return None


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
        # Reject truncated/recomposed output even when it incidentally fits the
        # provider maximum. This cannot replace listening/semantic QA.
        if abs(actual_duration_ms - route.projected_duration_ms) > 1_500:
            issues.append("actual_duration_differs_from_reviewed_interval")
    if not isinstance(media_sha256, str) or not _SHA256.fullmatch(media_sha256):
        issues.append("invalid_media_fingerprint")
    if not isinstance(caption, str):
        issues.append("missing_exact_full_video_link")
    else:
        link_position = _source_link_position(caption, route.clip.source_video_id)
        if link_position is None:
            issues.append("missing_exact_full_video_link")
        elif not re.search(
            r"полная проповедь|полную проповедь|полное видео|полный выпуск|смотреть полностью",
            caption[max(0, link_position - 120) : link_position],
            flags=re.IGNORECASE,
        ):
            issues.append("missing_full_video_link_label")
        if route.surface == "telegram_native_video" and len(caption) > 1_024:
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


def main(argv: list[str] | None = None) -> int:
    """Produce a read-only JSON preview after exact RU listening set the boundaries."""
    parser = argparse.ArgumentParser(description="SHORTOREZ provider-inert route preview (no uploads)")
    parser.add_argument("--youtube-id", required=True, help="Exact owner-channel video ID")
    parser.add_argument("--start-ms", required=True, type=int, help="Verified Russian-speech cut start")
    parser.add_argument("--end-ms", required=True, type=int, help="Verified Russian-speech cut end")
    parser.add_argument("--allow-speedup", action="store_true", help="Propose up to 1.20x for native VK Clip only")
    args = parser.parse_args(argv)
    try:
        channels = PROJECT_CHANNEL_IDS[_PILOT_PROJECT]
        if len(channels) != 1:
            parser.error("Pilot project must have one unambiguous canonical owner-channel ID")
        clip = ClipInterval(_PILOT_PROJECT, next(iter(channels)), args.youtube_id, args.start_ms, args.end_ms)
    except ValueError as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            {
                "provider_write_performed": False,
                "release_authorized": False,
                "source_project": clip.project_key,
                "source_channel": clip.source_channel_id,
                "full_video_url": clip.full_video_url,
                "source_start_ms": clip.start_ms,
                "source_end_ms": clip.end_ms,
                "routes": [
                    {
                        "key": route.key,
                        "surface": route.surface,
                        "speed_percent": route.speed_percent,
                        "projected_duration_ms": route.projected_duration_ms,
                        "status": route.status,
                        "audio_listening_required": route.audio_listening_required,
                    }
                    for route in plan_routes(clip, allow_speedup=args.allow_speedup)
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
