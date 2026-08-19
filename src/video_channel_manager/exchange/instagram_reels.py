from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REEL_ID_RE = re.compile(r"^[A-Z]+-R\d{2}$")

ReelEditorialJob = Literal[
    "performance",
    "formal_device",
    "manuscript_publication",
    "source_vs_myth",
    "motif_structure",
    "textual_variant",
    "interpretive_question",
    "interpretive_reading",
    "provenance_disclosure",
    "chronology",
    "source_transformation",
    "media_history",
    "relationship_network",
    "source_card",
]
ReelProductionMode = Literal["source_led", "master_timed", "hybrid"]
ReelSourceKind = Literal["youtube_video", "site_audio", "site_editorial"]
ReelQueueStatus = Literal[
    "source_led_ready",
    "exact_text_binding_required",
    "source_binding_required",
    "materialization_required",
    "timing_selection_required",
    "media_edit_ready",
    "editorial_rebuild_required",
    "hold",
]
ReelSourceState = Literal[
    "editorial_authority",
    "site_audio_pinned",
    "youtube_route_missing",
    "youtube_source_binding_required",
    "youtube_direct_remaster",
    "youtube_editorial_extract",
    "youtube_editorial_rebuild",
    "youtube_hold",
]


class ReelFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _validate_git_sha(value: str, *, field: str) -> str:
    if _GIT_SHA_RE.fullmatch(value) is None:
        raise ValueError(f"{field} must be an exact 40-character lowercase Git SHA")
    return value


def _validate_sha256(value: str, *, field: str) -> str:
    if _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{field} must use sha256:<64 lowercase hex>")
    return value


class YouTubeReelSource(ReelFrozenModel):
    kind: Literal["youtube_video"] = "youtube_video"
    source_id: str = Field(min_length=1)
    youtube_channel_id: str = Field(min_length=1)
    youtube_video_id: str = Field(min_length=1)
    reviewed_editorial_record: str | None = None

    @model_validator(mode="after")
    def validate_identity(self) -> YouTubeReelSource:
        if self.source_id != f"youtube:{self.youtube_video_id}":
            raise ValueError("YouTube Reel source_id must be youtube:<video_id>")
        return self


class SiteAudioReelSource(ReelFrozenModel):
    kind: Literal["site_audio"] = "site_audio"
    source_id: str = Field(min_length=1)
    repository: str = Field(min_length=1)
    commit_sha: str
    record_path: str = Field(min_length=1)
    record_blob_sha: str
    record_symbol: str = Field(min_length=1)
    record_id: str = Field(min_length=1)
    asset_path: str = Field(min_length=1)
    asset_sha256: str
    duration_seconds: float = Field(gt=0)

    @field_validator("commit_sha")
    @classmethod
    def validate_commit_sha(cls, value: str) -> str:
        return _validate_git_sha(value, field="commit_sha")

    @field_validator("record_blob_sha")
    @classmethod
    def validate_record_blob_sha(cls, value: str) -> str:
        return _validate_git_sha(value, field="record_blob_sha")

    @field_validator("asset_sha256")
    @classmethod
    def validate_asset_sha256(cls, value: str) -> str:
        return _validate_sha256(value, field="asset_sha256")


class SiteEditorialReelSource(ReelFrozenModel):
    kind: Literal["site_editorial"] = "site_editorial"
    source_id: str = Field(min_length=1)
    repository: str = Field(min_length=1)
    commit_sha: str
    path: str = Field(min_length=1)
    blob_sha: str
    symbol: str = Field(min_length=1)
    record_id: str | None = None

    @field_validator("commit_sha")
    @classmethod
    def validate_commit_sha(cls, value: str) -> str:
        return _validate_git_sha(value, field="commit_sha")

    @field_validator("blob_sha")
    @classmethod
    def validate_blob_sha(cls, value: str) -> str:
        return _validate_git_sha(value, field="blob_sha")


ReelSource = Annotated[
    YouTubeReelSource | SiteAudioReelSource | SiteEditorialReelSource,
    Field(discriminator="kind"),
]


class InstagramReelJob(ReelFrozenModel):
    reel_id: str
    family_id: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    source_ids: tuple[str, ...] = Field(min_length=1)
    editorial_job: ReelEditorialJob
    production_mode: ReelProductionMode
    brief: str = Field(min_length=1)
    hook: str | None = None
    requires_clean_master: bool = False
    requires_exact_text_span: bool = False
    requires_exact_timing: bool = False
    provider_writes_authorized: Literal[False] = False

    @field_validator("reel_id")
    @classmethod
    def validate_reel_id(cls, value: str) -> str:
        if _REEL_ID_RE.fullmatch(value) is None:
            raise ValueError("reel_id must match FAMILY-RNN")
        return value

    @model_validator(mode="after")
    def validate_production_requirements(self) -> InstagramReelJob:
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("source_ids must be unique within one Reel job")
        if self.requires_exact_timing and not self.requires_clean_master:
            raise ValueError("exact timing requires an exact clean master")
        if self.production_mode == "master_timed" and not self.requires_clean_master:
            raise ValueError("master_timed jobs must require a clean master")
        return self


class InstagramReelFactoryRegistry(ReelFrozenModel):
    schema_name: Literal["video-manager.instagram-reel-factory"] = "video-manager.instagram-reel-factory"
    schema_version: Literal[1] = 1
    status: Literal["provider-inert"] = "provider-inert"
    provider_effect: Literal["impossible"] = "impossible"
    provider_writes_authorized: Literal[False] = False
    project_key: str = Field(min_length=1)
    source_site_repository: str = Field(min_length=1)
    source_site_commit_sha: str
    declared_job_count: int = Field(ge=1)
    sources: tuple[ReelSource, ...]
    jobs: tuple[InstagramReelJob, ...]

    @field_validator("source_site_commit_sha")
    @classmethod
    def validate_source_site_commit_sha(cls, value: str) -> str:
        return _validate_git_sha(value, field="source_site_commit_sha")

    @model_validator(mode="after")
    def validate_registry(self) -> InstagramReelFactoryRegistry:
        source_ids = tuple(source.source_id for source in self.sources)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Reel registry source IDs must be unique")
        reel_ids = tuple(job.reel_id for job in self.jobs)
        if len(reel_ids) != len(set(reel_ids)):
            raise ValueError("Reel registry job IDs must be unique")
        if len(self.jobs) != self.declared_job_count:
            raise ValueError("declared_job_count differs from actual jobs")

        known_sources = set(source_ids)
        for job in self.jobs:
            missing = sorted(set(job.source_ids) - known_sources)
            if missing:
                raise ValueError(f"Reel job {job.reel_id} references unknown sources: {missing}")

        for source in self.sources:
            if isinstance(source, (SiteAudioReelSource, SiteEditorialReelSource)):
                if source.repository != self.source_site_repository:
                    raise ValueError(f"site source {source.source_id} uses a different repository")
                if source.commit_sha != self.source_site_commit_sha:
                    raise ValueError(f"site source {source.source_id} is not pinned to source_site_commit_sha")
        return self


class InstagramReelQueueRecord(ReelFrozenModel):
    reel_id: str
    family_id: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    source_ids: tuple[str, ...] = Field(min_length=1)
    status: ReelQueueStatus
    blockers: tuple[str, ...] = ()
    source_states: dict[str, ReelSourceState]
    requires_clean_master: bool
    requires_exact_text_span: bool
    requires_exact_timing: bool
    provider_writes_authorized: Literal[False] = False

    @field_validator("reel_id")
    @classmethod
    def validate_queue_reel_id(cls, value: str) -> str:
        if _REEL_ID_RE.fullmatch(value) is None:
            raise ValueError("reel_id must match FAMILY-RNN")
        return value

    @model_validator(mode="after")
    def validate_source_state_coverage(self) -> InstagramReelQueueRecord:
        if set(self.source_states) != set(self.source_ids):
            raise ValueError("source_states must cover exactly the Reel job source_ids")
        if len(self.blockers) != len(set(self.blockers)):
            raise ValueError("queue blockers must be unique")
        return self


class InstagramReelQueueCounts(ReelFrozenModel):
    total: int = Field(ge=0)
    source_led_ready: int = Field(ge=0)
    exact_text_binding_required: int = Field(ge=0)
    source_binding_required: int = Field(ge=0)
    materialization_required: int = Field(ge=0)
    timing_selection_required: int = Field(ge=0)
    media_edit_ready: int = Field(ge=0)
    editorial_rebuild_required: int = Field(ge=0)
    hold: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_partition(self) -> InstagramReelQueueCounts:
        partition = (
            self.source_led_ready
            + self.exact_text_binding_required
            + self.source_binding_required
            + self.materialization_required
            + self.timing_selection_required
            + self.media_edit_ready
            + self.editorial_rebuild_required
            + self.hold
        )
        if partition != self.total:
            raise ValueError("Reel queue counts do not partition total")
        return self


class InstagramReelQueueArtifact(ReelFrozenModel):
    schema_name: Literal["video-manager.instagram-reel-queue"] = "video-manager.instagram-reel-queue"
    schema_version: Literal[1] = 1
    status: Literal["provider-inert"] = "provider-inert"
    provider_effect: Literal["impossible"] = "impossible"
    provider_writes_authorized: Literal[False] = False
    project_key: str = Field(min_length=1)
    source_registry_sha256: str
    source_media_route_sha256: str | None = None
    counts: InstagramReelQueueCounts
    records: tuple[InstagramReelQueueRecord, ...]

    @field_validator("source_registry_sha256", "source_media_route_sha256")
    @classmethod
    def validate_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_sha256(value, field="digest")

    @model_validator(mode="after")
    def validate_records(self) -> InstagramReelQueueArtifact:
        ids = tuple(record.reel_id for record in self.records)
        if len(ids) != len(set(ids)):
            raise ValueError("Reel queue IDs must be unique")
        if len(ids) != self.counts.total:
            raise ValueError("Reel queue record count differs from total")
        return self
