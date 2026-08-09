from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError, field_validator, model_validator

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile

SvodkaFormat = Literal["quick_fact", "myth_fact", "mini_digest", "fresh_science", "quiz", "poll"]
SCHEDULE_OVERLAY_FILENAME = "rollout-schedule-2026-08.json"


def _normalized_options(options: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(option.strip().casefold() for option in options)


class SvodkaSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    url: HttpUrl
    label: str = Field(min_length=3, max_length=240)
    verified_on: date
    evidence: str = Field(min_length=20, max_length=1000)


class SvodkaQuiz(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question: str = Field(min_length=3, max_length=300)
    options: tuple[str, ...] = Field(min_length=2, max_length=10)
    correct_option_index: int = Field(ge=0, le=9)
    explanation: str = Field(min_length=10, max_length=200)

    @model_validator(mode="after")
    def answer_is_in_range(self) -> "SvodkaQuiz":
        if self.correct_option_index >= len(self.options):
            raise ValueError("quiz correct_option_index is outside the options list")
        if any(not option.strip() or len(option) > 100 for option in self.options):
            raise ValueError("quiz options must contain 1..100 visible characters")
        if len(_normalized_options(self.options)) != len(set(_normalized_options(self.options))):
            raise ValueError("quiz options must be unique after whitespace/case normalization")
        return self


class SvodkaPoll(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question: str = Field(min_length=3, max_length=300)
    options: tuple[str, ...] = Field(min_length=2, max_length=10)

    @model_validator(mode="after")
    def options_are_valid(self) -> "SvodkaPoll":
        if any(not option.strip() or len(option) > 100 for option in self.options):
            raise ValueError("poll options must contain 1..100 visible characters")
        if len(_normalized_options(self.options)) != len(set(_normalized_options(self.options))):
            raise ValueError("poll options must be unique after whitespace/case normalization")
        return self


class SvodkaPilot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start_date: date
    end_date: date
    daily_slots: tuple[str, ...] = Field(min_length=1, max_length=8)
    max_posts_per_day: int = Field(ge=1, le=20)
    notes: str = Field(min_length=20, max_length=1000)

    @field_validator("daily_slots")
    @classmethod
    def slots_are_canonical_and_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("Svodka pilot daily_slots must be unique")
        for slot in value:
            if re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", slot) is None:
                raise ValueError("Svodka pilot daily_slots must use canonical HH:MM 24-hour time")
        return value

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "SvodkaPilot":
        if self.end_date < self.start_date:
            raise ValueError("pilot end_date cannot precede start_date")
        if self.max_posts_per_day > len(self.daily_slots):
            raise ValueError("pilot max_posts_per_day cannot exceed the number of configured daily slots")
        return self


class SvodkaEditorialPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tagline: str = Field(min_length=5, max_length=200)
    source_priority: tuple[str, ...] = Field(min_length=1, max_length=12)
    fact_interpretation_boundary: str = Field(min_length=20, max_length=1000)
    dynamic_web_autopublish: Literal[False]


class SvodkaDraftPost(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1)
    publication_id: str = Field(pattern=r"^svodka-[a-z0-9][a-z0-9-]{4,90}$")
    scheduled_at: datetime
    format: SvodkaFormat
    title: str = Field(min_length=3, max_length=180)
    quiz: SvodkaQuiz | None = None
    poll: SvodkaPoll | None = None
    html_text: str = Field(min_length=100, max_length=8192)
    sources: tuple[SvodkaSource, ...] = Field(min_length=1, max_length=12)

    @field_validator("scheduled_at")
    @classmethod
    def scheduled_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("scheduled_at must be timezone-aware")
        return value

    @field_validator("html_text")
    @classmethod
    def style_contract(cls, value: str) -> str:
        if not value.startswith("- Сводка -\n\n"):
            raise ValueError("Svodka post must start with the canonical '- Сводка -' header")
        if "#Сводка" not in value:
            raise ValueError("Svodka post must include #Сводка")
        if "📎" not in value:
            raise ValueError("Svodka factual post must expose at least one visible source line")
        return value

    @model_validator(mode="after")
    def interactive_and_source_contract(self) -> "SvodkaDraftPost":
        if self.format == "quiz":
            if self.quiz is None or self.poll is not None:
                raise ValueError("quiz posts require quiz metadata and no regular poll metadata")
        elif self.format == "poll":
            if self.poll is None or self.quiz is not None:
                raise ValueError("poll posts require poll metadata and no quiz metadata")
        elif self.quiz is not None or self.poll is not None:
            raise ValueError("non-interactive posts must not contain quiz or poll metadata")

        if self.html_text.count("📎") < len(self.sources):
            raise ValueError("Svodka post must expose every structured source as a visible source line")
        for source in self.sources:
            if str(source.url) not in self.html_text:
                raise ValueError(f"visible source URL differs from structured source: {source.url}")
        return self


class SvodkaDraftQueue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-editorial-draft-queue"]
    schema_version: Literal[1]
    project_key: Literal["svodka"]
    channel_username: Literal["@deep_info_life"]
    channel_title: Literal["СВОДКА"]
    timezone: Literal["Europe/Moscow"]
    review_state: Literal["draft_review_required"]
    provider_writes_authorized: Literal[False]
    pilot: SvodkaPilot
    editorial_policy: SvodkaEditorialPolicy
    posts: tuple[SvodkaDraftPost, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def queue_contract(self) -> "SvodkaDraftQueue":
        sequences = [post.sequence for post in self.posts]
        if sequences != list(range(1, len(self.posts) + 1)):
            raise ValueError("Svodka draft sequences must be consecutive starting at 1")
        publication_ids = [post.publication_id for post in self.posts]
        if len(publication_ids) != len(set(publication_ids)):
            raise ValueError("Svodka publication_id values must be unique")
        if self.pilot.max_posts_per_day > 2:
            raise ValueError("current Svodka pilot is capped at two posts per day")

        scheduled = [post.scheduled_at for post in self.posts]
        if any(scheduled[index] >= scheduled[index + 1] for index in range(len(scheduled) - 1)):
            raise ValueError("Svodka draft posts must be strictly ordered by scheduled_at")

        zone = ZoneInfo(self.timezone)
        per_day: dict[date, int] = {}
        used_slots: set[tuple[date, str]] = set()
        for post in self.posts:
            local = post.scheduled_at.astimezone(zone)
            local_date = local.date()
            if not self.pilot.start_date <= local_date <= self.pilot.end_date:
                raise ValueError(f"post {post.publication_id} falls outside the pilot date range")
            if local.second != 0 or local.microsecond != 0:
                raise ValueError(f"post {post.publication_id} must use an exact minute boundary")
            local_slot = local.strftime("%H:%M")
            if local_slot not in self.pilot.daily_slots:
                raise ValueError(f"post {post.publication_id} uses {local_slot}, outside configured pilot daily_slots")
            slot_key = (local_date, local_slot)
            if slot_key in used_slots:
                raise ValueError(f"post {post.publication_id} duplicates configured slot {local_date} {local_slot}")
            used_slots.add(slot_key)
            per_day[local_date] = per_day.get(local_date, 0) + 1
        if any(count > self.pilot.max_posts_per_day for count in per_day.values()):
            raise ValueError("Svodka draft exceeds the configured daily post limit")
        return self

    @property
    def digest(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SvodkaScheduleOverlay(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.svodka-schedule-overlay"]
    schema_version: Literal[1]
    project_key: Literal["svodka"]
    channel_username: Literal["@deep_info_life"]
    base_start_date: date
    base_end_date: date
    shift_days: int = Field(ge=1, le=31)
    effective_start_date: date
    effective_end_date: date
    owning_issue: int = Field(ge=1)
    reason: str = Field(min_length=20, max_length=1000)

    @model_validator(mode="after")
    def shift_is_exact(self) -> "SvodkaScheduleOverlay":
        delta = timedelta(days=self.shift_days)
        if self.effective_start_date != self.base_start_date + delta:
            raise ValueError("Svodka schedule overlay effective_start_date differs from exact shift")
        if self.effective_end_date != self.base_end_date + delta:
            raise ValueError("Svodka schedule overlay effective_end_date differs from exact shift")
        return self


def _load_schedule_overlay(path: Path) -> SvodkaScheduleOverlay | None:
    overlay_path = path.with_name(SCHEDULE_OVERLAY_FILENAME)
    if not overlay_path.exists():
        return None
    try:
        payload = json.loads(overlay_path.read_text(encoding="utf-8"))
        return SvodkaScheduleOverlay.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid Svodka schedule overlay {overlay_path}: {exc}") from exc


def _apply_schedule_overlay(queue: SvodkaDraftQueue, overlay: SvodkaScheduleOverlay | None) -> SvodkaDraftQueue:
    if overlay is None:
        return queue
    if overlay.project_key != queue.project_key or overlay.channel_username != queue.channel_username:
        raise ValueError("Svodka schedule overlay identity differs from draft queue")
    if overlay.base_start_date != queue.pilot.start_date or overlay.base_end_date != queue.pilot.end_date:
        raise ValueError("Svodka schedule overlay base window differs from draft queue")

    delta = timedelta(days=overlay.shift_days)
    effective_pilot = queue.pilot.model_copy(
        update={
            "start_date": overlay.effective_start_date,
            "end_date": overlay.effective_end_date,
            "notes": f"{queue.pilot.notes} Effective rollout schedule shifted by {overlay.shift_days} day(s) under issue #{overlay.owning_issue}.",
        }
    )
    effective_posts = tuple(
        post.model_copy(update={"scheduled_at": post.scheduled_at + delta}) for post in queue.posts
    )
    return SvodkaDraftQueue.model_validate(
        queue.model_copy(update={"pilot": effective_pilot, "posts": effective_posts}).model_dump(mode="python")
    )


def load_svodka_draft(path: Path, profile: TelegramChannelProfile | None = None) -> SvodkaDraftQueue:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        queue = SvodkaDraftQueue.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid Svodka draft queue {path}: {exc}") from exc

    queue = _apply_schedule_overlay(queue, _load_schedule_overlay(path))

    if profile is not None:
        if profile.project_key != queue.project_key or profile.channel_username != queue.channel_username:
            raise ValueError("Svodka queue identity differs from selected Telegram channel profile")
        if profile.timezone != queue.timezone or profile.daily_verified_limit != queue.pilot.max_posts_per_day:
            raise ValueError("Svodka queue schedule contract differs from selected Telegram channel profile")
        if any(not post.publication_id.startswith(profile.publication_id_prefix) for post in queue.posts):
            raise ValueError("Svodka publication IDs do not match the selected profile prefix")
    return queue
