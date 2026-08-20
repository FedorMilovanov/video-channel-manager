from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

HistoricalBacklogAction = Literal[
    "already_covered",
    "design_reel_jobs",
    "build_editorial_record",
]


class HistoricalBacklogFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InstagramHistoricalBacklogRecord(HistoricalBacklogFrozenModel):
    youtube_video_id: str = Field(min_length=1)
    exact_vk_video_id: str = Field(min_length=1)
    reviewed_editorial_record: str | None = None
    factory_reel_ids: tuple[str, ...] = ()
    action: HistoricalBacklogAction
    provider_writes_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_action(self) -> InstagramHistoricalBacklogRecord:
        if self.action == "already_covered":
            if not self.factory_reel_ids:
                raise ValueError("already_covered requires at least one factory Reel ID")
            if self.reviewed_editorial_record is None:
                raise ValueError("already_covered historical sources require reviewed editorial authority")
        elif self.action == "design_reel_jobs":
            if self.factory_reel_ids:
                raise ValueError("design_reel_jobs cannot already contain factory Reel IDs")
            if self.reviewed_editorial_record is None:
                raise ValueError("design_reel_jobs requires reviewed editorial authority")
        else:
            if self.factory_reel_ids:
                raise ValueError("build_editorial_record cannot already contain factory Reel IDs")
            if self.reviewed_editorial_record is not None:
                raise ValueError("build_editorial_record cannot already have reviewed editorial authority")
        return self


class InstagramHistoricalBacklogCounts(HistoricalBacklogFrozenModel):
    total_historical_floor_ids: int = Field(ge=0)
    already_covered: int = Field(ge=0)
    design_reel_jobs: int = Field(ge=0)
    build_editorial_record: int = Field(ge=0)
    reviewed_ids_outside_historical_floor: int = Field(ge=0)
    factory_youtube_sources_outside_historical_floor: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_partition(self) -> InstagramHistoricalBacklogCounts:
        if self.already_covered + self.design_reel_jobs + self.build_editorial_record != self.total_historical_floor_ids:
            raise ValueError("historical backlog actions do not partition the historical floor")
        return self


class InstagramHistoricalBacklogArtifact(HistoricalBacklogFrozenModel):
    schema_name: Literal["video-manager.instagram-historical-factory-backlog"] = (
        "video-manager.instagram-historical-factory-backlog"
    )
    schema_version: Literal[1] = 1
    status: Literal["provider-inert"] = "provider-inert"
    evidence_scope: Literal["historical_floor_not_current_provider_state"] = (
        "historical_floor_not_current_provider_state"
    )
    provider_effect: Literal["impossible"] = "impossible"
    provider_writes_authorized: Literal[False] = False
    project_key: str = Field(min_length=1)
    youtube_channel_id: str = Field(min_length=1)
    source_mapping_sha256: str
    source_reviewed_corpus_sha256: str
    source_registry_sha256: str
    reviewed_ids_outside_historical_floor: tuple[str, ...] = ()
    factory_youtube_sources_outside_historical_floor: tuple[str, ...] = ()
    counts: InstagramHistoricalBacklogCounts
    records: tuple[InstagramHistoricalBacklogRecord, ...]

    @field_validator("source_mapping_sha256", "source_reviewed_corpus_sha256", "source_registry_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if _SHA256_RE.fullmatch(value) is None:
            raise ValueError("digest must use sha256:<64 lowercase hex>")
        return value

    @model_validator(mode="after")
    def validate_records(self) -> InstagramHistoricalBacklogArtifact:
        ids = tuple(record.youtube_video_id for record in self.records)
        if len(ids) != len(set(ids)):
            raise ValueError("historical backlog records must contain unique YouTube IDs")
        if tuple(sorted(ids)) != ids:
            raise ValueError("historical backlog records must be sorted by YouTube ID")
        if len(ids) != self.counts.total_historical_floor_ids:
            raise ValueError("historical backlog record count differs from total_historical_floor_ids")

        reviewed_outside = self.reviewed_ids_outside_historical_floor
        if len(reviewed_outside) != len(set(reviewed_outside)) or tuple(sorted(reviewed_outside)) != reviewed_outside:
            raise ValueError("reviewed IDs outside historical floor must be unique and sorted")
        if len(reviewed_outside) != self.counts.reviewed_ids_outside_historical_floor:
            raise ValueError("reviewed outside-floor count differs from exact ID list")

        factory_outside = self.factory_youtube_sources_outside_historical_floor
        if len(factory_outside) != len(set(factory_outside)) or tuple(sorted(factory_outside)) != factory_outside:
            raise ValueError("factory YouTube IDs outside historical floor must be unique and sorted")
        if len(factory_outside) != self.counts.factory_youtube_sources_outside_historical_floor:
            raise ValueError("factory outside-floor count differs from exact ID list")
        return self
