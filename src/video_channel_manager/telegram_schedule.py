from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from video_channel_manager.telegram_models import ScheduledSlot


class PublicationSlotConfig(BaseModel):
    """Version-controlled schedule definition for one logical publication slot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cron: str = Field(min_length=5, max_length=64)
    time: str = Field(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    iso_weekdays: tuple[int, ...]

    @field_validator("iso_weekdays")
    @classmethod
    def valid_iso_weekdays(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if not value:
            raise ValueError("publication slot must contain at least one ISO weekday")
        if any(day < 1 or day > 7 for day in value):
            raise ValueError("ISO weekdays must be in range 1..7")
        if len(value) != len(set(value)):
            raise ValueError("publication slot ISO weekdays must be unique")
        return value


class ProductionSchedule(BaseModel):
    """Release-bound @lordchrist publication cadence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-production-schedule"]
    schema_version: Literal[3]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    chat_id: int = Field(lt=0)
    bot_id: int = Field(gt=0)
    bot_username: str = Field(min_length=2, max_length=64)
    enabled: bool
    not_before_moscow_date: date
    timezone: Literal["Europe/Moscow"]
    slots: dict[ScheduledSlot, PublicationSlotConfig]
    max_verified_per_slot: Literal[1]
    max_verified_per_day: Literal[2]
    backfill_policy: Literal["none"]
    queue_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    presentation_policy_id: str = Field(min_length=2, max_length=120)
    presentation_policy_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    activation_note: str = Field(min_length=20, max_length=1000)

    @model_validator(mode="after")
    def exact_slot_contract(self) -> "ProductionSchedule":
        if set(self.slots) != {"morning", "evening"}:
            raise ValueError("production schedule must define exactly morning and evening slots")
        if self.slots["morning"].iso_weekdays != (1, 2, 3, 4, 5, 6, 7):
            raise ValueError("morning slot must be enabled every day")
        if self.slots["evening"].iso_weekdays != (2, 5, 7):
            raise ValueError("evening slot must be enabled only Tuesday, Friday, and Sunday")
        if self.slots["morning"].time != "09:17":
            raise ValueError("morning slot must remain at 09:17 Europe/Moscow")
        if self.slots["evening"].time != "21:17":
            raise ValueError("evening slot must remain at 21:17 Europe/Moscow")
        if self.slots["morning"].cron != "17 9 * * *":
            raise ValueError("morning slot cron differs from the release contract")
        if self.slots["evening"].cron != "17 21 * * 2,5,0":
            raise ValueError("evening slot cron differs from the release contract")
        return self


@dataclass(frozen=True)
class ScheduleDecision:
    active: bool
    slot: ScheduledSlot | None
    reason: str


def load_production_schedule(path: Path) -> ProductionSchedule:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ProductionSchedule.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid Telegram production schedule {path}: {exc}") from exc


def require_release_binding(
    schedule: ProductionSchedule,
    *,
    queue_digest: str,
    chat_id: int,
    bot_id: int,
    bot_username: str,
    presentation_policy_id: str,
    presentation_policy_sha256: str,
) -> None:
    if schedule.queue_digest != queue_digest:
        raise ValueError("production schedule queue digest does not match approved queue digest")
    if schedule.chat_id != chat_id:
        raise ValueError("production schedule chat id does not match configured Telegram target")
    if schedule.bot_id != bot_id:
        raise ValueError("production schedule bot id does not match configured Telegram bot")
    if schedule.bot_username.casefold() != bot_username.casefold():
        raise ValueError("production schedule bot username does not match configured Telegram bot")
    if schedule.presentation_policy_id != presentation_policy_id:
        raise ValueError("production schedule presentation policy id mismatch")
    if schedule.presentation_policy_sha256 != presentation_policy_sha256:
        raise ValueError("production schedule presentation policy digest mismatch")


def decide_scheduled_slot(
    schedule: ProductionSchedule,
    *,
    event_schedule: str,
    now: datetime | None = None,
) -> ScheduleDecision:
    """Map one GitHub schedule event to one logical slot without catch-up/backfill."""

    current = now or datetime.now(tz=UTC)
    if current.tzinfo is None:
        raise ValueError("schedule decision timestamp must be timezone-aware")
    try:
        zone = ZoneInfo(schedule.timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown publication timezone: {schedule.timezone}") from exc
    local = current.astimezone(zone)

    if not schedule.enabled:
        return ScheduleDecision(False, None, "production schedule disabled")
    if local.date() < schedule.not_before_moscow_date:
        return ScheduleDecision(False, None, "production schedule not active yet")

    matching = [name for name, slot in schedule.slots.items() if slot.cron == event_schedule]
    if len(matching) != 1:
        return ScheduleDecision(False, None, "schedule event does not map to exactly one configured slot")
    slot_name = cast(ScheduledSlot, matching[0])
    slot = schedule.slots[slot_name]
    if local.isoweekday() not in slot.iso_weekdays:
        return ScheduleDecision(False, None, f"{slot_name} slot is not eligible on ISO weekday {local.isoweekday()}")
    return ScheduleDecision(True, slot_name, f"{slot_name} slot active")
