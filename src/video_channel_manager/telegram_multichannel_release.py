from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.telegram_multichannel_transport import (
    GenericMessagePayload,
    GenericPhotoPayload,
    GenericPollPayload,
)

GenericProviderPayload = GenericMessagePayload | GenericPollPayload | GenericPhotoPayload


class GenericReleaseItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1)
    publication_id: str = Field(min_length=5, max_length=96)
    scheduled_at: datetime
    source_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    payload: GenericProviderPayload

    @model_validator(mode="after")
    def validate_item(self) -> "GenericReleaseItem":
        if self.scheduled_at.tzinfo is None:
            raise ValueError("release item scheduled_at must be timezone-aware")
        if self.payload.publication_id != self.publication_id:
            raise ValueError("release item publication_id differs from provider payload")
        return self


class GenericReleaseQueue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-release-queue"]
    schema_version: Literal[1]
    release_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{4,95}$")
    project_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    channel_username: str = Field(pattern=r"^@[A-Za-z0-9_]{5,32}$")
    profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    timezone: str = Field(min_length=3, max_length=80)
    daily_verified_limit: int = Field(ge=1, le=20)
    target_binding_sha256: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    chat_id: int | None = Field(default=None, lt=0)
    bot_id: int | None = Field(default=None, gt=0)
    bot_username: str | None = Field(
        default=None,
        min_length=2,
        max_length=64,
        pattern=r"^[A-Za-z0-9_]+$",
    )
    release_authorized: bool = False
    reviewed_candidate_sha256: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    reviewed_by: str | None = Field(default=None, max_length=200)
    reviewed_at: datetime | None = None
    items: tuple[GenericReleaseItem, ...] = Field(min_length=1, max_length=500)

    def candidate_digest(self) -> str:
        payload = self.model_dump(mode="json")
        payload["release_authorized"] = False
        payload["reviewed_candidate_sha256"] = None
        payload["reviewed_by"] = None
        payload["reviewed_at"] = None
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @model_validator(mode="after")
    def validate_release(self) -> "GenericReleaseQueue":
        try:
            zone = ZoneInfo(self.timezone)
        except Exception as exc:
            raise ValueError(f"unknown release timezone: {self.timezone}") from exc

        sequences = [item.sequence for item in self.items]
        if sequences != list(range(1, len(self.items) + 1)):
            raise ValueError("release item sequences must be consecutive starting at 1")
        publication_ids = [item.publication_id for item in self.items]
        if len(publication_ids) != len(set(publication_ids)):
            raise ValueError("release publication_id values must be unique")
        if any(
            self.items[index].scheduled_at >= self.items[index + 1].scheduled_at for index in range(len(self.items) - 1)
        ):
            raise ValueError("release items must be strictly ordered by scheduled_at")

        per_day: dict[str, int] = {}
        for item in self.items:
            if item.payload.project_key != self.project_key:
                raise ValueError(f"provider payload project mismatch: {item.publication_id}")
            if item.payload.channel_username.casefold() != self.channel_username.casefold():
                raise ValueError(f"provider payload channel mismatch: {item.publication_id}")
            if item.payload.profile_sha256 != self.profile_sha256:
                raise ValueError(f"provider payload profile digest mismatch: {item.publication_id}")
            local_day = item.scheduled_at.astimezone(zone).date().isoformat()
            per_day[local_day] = per_day.get(local_day, 0) + 1
        if any(count > self.daily_verified_limit for count in per_day.values()):
            raise ValueError("release exceeds the configured daily publication limit")

        target_values = (
            self.target_binding_sha256,
            self.chat_id,
            self.bot_id,
            self.bot_username,
        )
        target_is_unset = all(value is None for value in target_values)
        target_is_complete = all(value is not None for value in target_values)
        if not target_is_unset and not target_is_complete:
            raise ValueError("Telegram release target binding must be either complete or entirely unset")

        if self.release_authorized:
            if not target_is_complete:
                raise ValueError("authorized release requires exact target binding and bot/channel identity")
            if self.reviewed_candidate_sha256 is None:
                raise ValueError("authorized release requires exact reviewed candidate provenance")
            if self.reviewed_candidate_sha256 != self.candidate_digest():
                raise ValueError("authorized release reviewed candidate digest does not match its immutable candidate")
            if not self.reviewed_by or self.reviewed_at is None:
                raise ValueError("authorized release requires reviewed_by and reviewed_at")
            if self.reviewed_at.tzinfo is None:
                raise ValueError("authorized release reviewed_at must be timezone-aware")
        elif self.reviewed_candidate_sha256 is not None or self.reviewed_by is not None or self.reviewed_at is not None:
            raise ValueError("unauthorized release must not claim completed review metadata")
        return self

    @property
    def digest(self) -> str:
        canonical = json.dumps(self.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_release(path: Path) -> GenericReleaseQueue:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return GenericReleaseQueue.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid Telegram release queue {path}: {exc}") from exc


def save_release(path: Path, release: GenericReleaseQueue) -> None:
    validated = GenericReleaseQueue.model_validate(release.model_dump(mode="json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(validated.model_dump_json(indent=2) + "\n", encoding="utf-8")
