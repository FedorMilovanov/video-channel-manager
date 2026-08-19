from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

FactoryCoverageStatus = Literal[
    "covered_by_factory",
    "reviewed_unexpanded",
    "editorial_review_required",
]


class FactoryCoverageFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InstagramFactoryCoverageRecord(FactoryCoverageFrozenModel):
    youtube_video_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    youtube_format_status: Literal["short", "longform", "unknown"]
    youtube_short_candidate: bool
    reviewed_editorial_record: str | None = None
    coverage_status: FactoryCoverageStatus
    reel_ids: tuple[str, ...] = ()
    provider_writes_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_coverage_state(self) -> InstagramFactoryCoverageRecord:
        if self.coverage_status == "covered_by_factory" and not self.reel_ids:
            raise ValueError("covered_by_factory requires at least one Reel ID")
        if self.coverage_status != "covered_by_factory" and self.reel_ids:
            raise ValueError("only covered_by_factory records may contain Reel IDs")
        if self.coverage_status == "reviewed_unexpanded" and self.reviewed_editorial_record is None:
            raise ValueError("reviewed_unexpanded requires a reviewed editorial record")
        if self.coverage_status == "editorial_review_required" and self.reviewed_editorial_record is not None:
            raise ValueError("editorial_review_required cannot already have a reviewed editorial record")
        return self


class InstagramFactoryCoverageCounts(FactoryCoverageFrozenModel):
    total_current_videos: int = Field(ge=0)
    covered_by_factory: int = Field(ge=0)
    reviewed_unexpanded: int = Field(ge=0)
    editorial_review_required: int = Field(ge=0)
    factory_reel_jobs: int = Field(ge=0)
    factory_youtube_sources: int = Field(ge=0)
    current_factory_sources: int = Field(ge=0)
    factory_sources_missing_from_current_snapshot: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_partition(self) -> InstagramFactoryCoverageCounts:
        if (
            self.covered_by_factory
            + self.reviewed_unexpanded
            + self.editorial_review_required
            != self.total_current_videos
        ):
            raise ValueError("factory coverage states do not partition current videos")
        if self.current_factory_sources + self.factory_sources_missing_from_current_snapshot != self.factory_youtube_sources:
            raise ValueError("factory source presence counts do not partition factory YouTube sources")
        return self


class InstagramFactoryCoverageArtifact(FactoryCoverageFrozenModel):
    schema_name: Literal["video-manager.instagram-reel-factory-coverage"] = (
        "video-manager.instagram-reel-factory-coverage"
    )
    schema_version: Literal[1] = 1
    status: Literal["provider-inert"] = "provider-inert"
    provider_effect: Literal["impossible"] = "impossible"
    provider_writes_authorized: Literal[False] = False
    project_key: str = Field(min_length=1)
    channel_id: str = Field(min_length=1)
    source_intake_sha256: str
    source_registry_sha256: str
    factory_sources_missing_from_current_snapshot: tuple[str, ...] = ()
    counts: InstagramFactoryCoverageCounts
    records: tuple[InstagramFactoryCoverageRecord, ...]

    @field_validator("source_intake_sha256", "source_registry_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if _SHA256_RE.fullmatch(value) is None:
            raise ValueError("digest must use sha256:<64 lowercase hex>")
        return value

    @model_validator(mode="after")
    def validate_records(self) -> InstagramFactoryCoverageArtifact:
        ids = tuple(record.youtube_video_id for record in self.records)
        if len(ids) != len(set(ids)):
            raise ValueError("factory coverage records must contain unique YouTube video IDs")
        if len(ids) != self.counts.total_current_videos:
            raise ValueError("factory coverage record count differs from total_current_videos")
        missing = self.factory_sources_missing_from_current_snapshot
        if len(missing) != len(set(missing)) or tuple(sorted(missing)) != missing:
            raise ValueError("missing factory source IDs must be unique and sorted")
        if len(missing) != self.counts.factory_sources_missing_from_current_snapshot:
            raise ValueError("missing factory source count differs from exact missing ID list")
        return self
