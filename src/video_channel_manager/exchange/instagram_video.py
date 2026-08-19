from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

InstagramMediaRightsStatus = Literal["cleared", "blocked", "unknown"]
InstagramMasterProvenance = Literal[
    "project_owned_clean_master",
    "derived_from_project_owned_master",
    "social_delivery_copy",
    "unknown",
]
InstagramVideoRoute = Literal[
    "source_binding_required",
    "direct_remaster",
    "editorial_extract",
    "editorial_rebuild",
    "hold",
]
InstagramSourceGeometry = Literal["vertical", "non_vertical", "unknown"]


class InstagramFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InstagramIntakeSourceEvidence(InstagramFrozenModel):
    audit_package_sha256: str
    frozen_mapping_sha256: str | None = None
    reviewed_corpus_sha256: str | None = None

    @field_validator("audit_package_sha256", "frozen_mapping_sha256", "reviewed_corpus_sha256")
    @classmethod
    def validate_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if _SHA256_RE.fullmatch(value) is None:
            raise ValueError("digest must use sha256:<64 lowercase hex>")
        return value


class InstagramVideoIntakeCounts(InstagramFrozenModel):
    current_videos: int = Field(ge=0)
    frozen_mapping_ids: int = Field(ge=0)
    reviewed_editorial_ids: int = Field(ge=0)
    current_also_in_frozen_mapping: int = Field(ge=0)
    new_current_vs_frozen_mapping: int = Field(ge=0)
    historical_mapped_missing_from_current_snapshot: int = Field(ge=0)
    confirmed_short: Literal[0] = 0
    confirmed_longform: Literal[0] = 0
    format_unknown: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> InstagramVideoIntakeCounts:
        if self.current_also_in_frozen_mapping + self.new_current_vs_frozen_mapping != self.current_videos:
            raise ValueError("current intake counts do not partition the current video set")
        if self.format_unknown != self.current_videos:
            raise ValueError("v1 intake must keep every current video format fail-closed as unknown")
        return self


class InstagramVideoIntakeReconciliation(InstagramFrozenModel):
    new_current_ids: tuple[str, ...] = ()
    historical_mapped_missing_from_current_snapshot: tuple[str, ...] = ()
    reviewed_missing_from_current_snapshot: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_unique_ids(self) -> InstagramVideoIntakeReconciliation:
        for field_name in (
            "new_current_ids",
            "historical_mapped_missing_from_current_snapshot",
            "reviewed_missing_from_current_snapshot",
        ):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must contain unique IDs")
            if tuple(sorted(values)) != values:
                raise ValueError(f"{field_name} must be sorted")
        return self


class InstagramVideoClassificationPolicy(InstagramFrozenModel):
    shorts: str = Field(min_length=1)
    longform: str = Field(min_length=1)
    unknown_is_not_excluded: Literal[True] = True
    social_delivery_encoding_is_not_source_master: Literal[True] = True


class InstagramVideoIntakeRecord(InstagramFrozenModel):
    youtube_video_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    duration_seconds: int | None = Field(default=None, ge=0)
    published_at: datetime | None = None
    privacy_status: str | None = None
    tags: tuple[str, ...] = ()
    thumbnail_url: str | None = None
    revision: str = Field(min_length=1)
    present_in_frozen_mapping: bool
    exact_vk_video_id: str | None = None
    reviewed_editorial_record: str | None = None
    youtube_format_status: Literal["unknown"] = "unknown"
    source_aspect_ratio: None = None
    clean_master_status: Literal["unbound"] = "unbound"
    instagram_route: Literal["source_binding_required"] = "source_binding_required"
    provider_writes_authorized: Literal[False] = False


class InstagramVideoIntakeArtifact(InstagramFrozenModel):
    schema_name: Literal["video-manager.instagram-youtube-video-intake"] = (
        "video-manager.instagram-youtube-video-intake"
    )
    schema_version: Literal[1] = 1
    status: Literal["provider-inert"] = "provider-inert"
    provider_effect: Literal["impossible"] = "impossible"
    provider_writes_authorized: Literal[False] = False
    project_key: str = Field(min_length=1)
    channel_id: str = Field(min_length=1)
    source_snapshot_id: str = Field(min_length=1)
    source_generated_at: datetime
    source_evidence: InstagramIntakeSourceEvidence
    counts: InstagramVideoIntakeCounts
    reconciliation: InstagramVideoIntakeReconciliation
    classification_policy: InstagramVideoClassificationPolicy
    records: tuple[InstagramVideoIntakeRecord, ...]

    @model_validator(mode="after")
    def validate_record_coverage(self) -> InstagramVideoIntakeArtifact:
        ids = tuple(record.youtube_video_id for record in self.records)
        if len(ids) != len(set(ids)):
            raise ValueError("intake records must contain unique YouTube video IDs")
        if len(ids) != self.counts.current_videos:
            raise ValueError("intake record count differs from current_videos")
        current = set(ids)
        if not set(self.reconciliation.new_current_ids).issubset(current):
            raise ValueError("new_current_ids must be present in current intake records")
        return self


class InstagramMediaReview(InstagramFrozenModel):
    schema_name: Literal["video-manager.instagram-media-review"] = "video-manager.instagram-media-review"
    schema_version: Literal[1] = 1
    project_key: str = Field(min_length=1)
    youtube_channel_id: str = Field(min_length=1)
    youtube_video_id: str = Field(min_length=1)
    media_manifest_sha256: str
    rights_status: InstagramMediaRightsStatus
    master_provenance: InstagramMasterProvenance
    reviewed_at: datetime
    reviewed_by: str = Field(min_length=1)
    editorial_rebuild_authorized: bool = False
    note: str | None = None

    @field_validator("media_manifest_sha256")
    @classmethod
    def validate_manifest_sha256(cls, value: str) -> str:
        if _SHA256_RE.fullmatch(value) is None:
            raise ValueError("media_manifest_sha256 must use sha256:<64 lowercase hex>")
        return value

    @model_validator(mode="after")
    def validate_review_contract(self) -> InstagramMediaReview:
        if self.reviewed_at.tzinfo is None or self.reviewed_at.utcoffset() is None:
            raise ValueError("reviewed_at must be timezone-aware")
        if self.editorial_rebuild_authorized and self.rights_status == "blocked":
            raise ValueError("blocked rights cannot authorize editorial rebuild")
        return self


class InstagramVideoRouteRecord(InstagramFrozenModel):
    youtube_video_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    route: InstagramVideoRoute
    reasons: tuple[str, ...]
    source_geometry: InstagramSourceGeometry
    media_manifest_sha256: str | None = None
    media_sha256: str | None = None
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    acquisition_method: str | None = None
    rights_status: InstagramMediaRightsStatus | None = None
    master_provenance: InstagramMasterProvenance | None = None
    reviewed_editorial_record: str | None = None
    provider_writes_authorized: Literal[False] = False

    @field_validator("media_manifest_sha256", "media_sha256")
    @classmethod
    def validate_optional_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if _SHA256_RE.fullmatch(value) is None:
            raise ValueError("digest must use sha256:<64 lowercase hex>")
        return value


class InstagramVideoRouteCounts(InstagramFrozenModel):
    total: int = Field(ge=0)
    source_binding_required: int = Field(ge=0)
    direct_remaster: int = Field(ge=0)
    editorial_extract: int = Field(ge=0)
    editorial_rebuild: int = Field(ge=0)
    hold: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_partition(self) -> InstagramVideoRouteCounts:
        partition = (
            self.source_binding_required
            + self.direct_remaster
            + self.editorial_extract
            + self.editorial_rebuild
            + self.hold
        )
        if partition != self.total:
            raise ValueError("route counts do not partition total records")
        return self


class InstagramVideoRouteArtifact(InstagramFrozenModel):
    schema_name: Literal["video-manager.instagram-video-route"] = "video-manager.instagram-video-route"
    schema_version: Literal[1] = 1
    status: Literal["provider-inert"] = "provider-inert"
    provider_effect: Literal["impossible"] = "impossible"
    provider_writes_authorized: Literal[False] = False
    project_key: str = Field(min_length=1)
    channel_id: str = Field(min_length=1)
    source_intake_sha256: str
    counts: InstagramVideoRouteCounts
    records: tuple[InstagramVideoRouteRecord, ...]

    @field_validator("source_intake_sha256")
    @classmethod
    def validate_intake_sha256(cls, value: str) -> str:
        if _SHA256_RE.fullmatch(value) is None:
            raise ValueError("source_intake_sha256 must use sha256:<64 lowercase hex>")
        return value

    @model_validator(mode="after")
    def validate_records(self) -> InstagramVideoRouteArtifact:
        ids = tuple(record.youtube_video_id for record in self.records)
        if len(ids) != len(set(ids)):
            raise ValueError("route records must contain unique YouTube video IDs")
        if len(ids) != self.counts.total:
            raise ValueError("route record count differs from route counts total")
        return self
