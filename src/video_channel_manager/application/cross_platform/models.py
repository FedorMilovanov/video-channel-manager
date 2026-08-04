from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field

from video_channel_manager.application.catalog_identity import CatalogIdentityEvidence
from video_channel_manager.application.identity import CanonicalTextEvidence
from video_channel_manager.domain.models import RemoteRef, StrictModel

MatchMethod = Literal["reviewed_mapping", "exact_normalized_title", "fuzzy_unique"]
ConflictReason = Literal[
    "duplicate_exact_title",
    "exact_title_duration_mismatch",
    "non_unique_fallback",
]


class MatchCandidateEvidence(StrictModel):
    source_ref: RemoteRef
    target_ref: RemoteRef
    source_title_identity: CanonicalTextEvidence
    target_title_identity: CanonicalTextEvidence
    score: float = Field(ge=0.0, le=1.0)
    duration_delta_seconds: int | None = Field(default=None, ge=0)
    exact_normalized_title: bool


class VideoMatch(StrictModel):
    source_ref: RemoteRef
    target_ref: RemoteRef
    source_title: str
    target_title: str
    source_title_identity: CanonicalTextEvidence
    target_title_identity: CanonicalTextEvidence
    source_description_identity: CanonicalTextEvidence
    target_description_identity: CanonicalTextEvidence
    score: float = Field(ge=0.0, le=1.0)
    duration_delta_seconds: int | None = Field(default=None, ge=0)
    exact_normalized_title: bool
    exact_description: bool
    match_method: MatchMethod
    ambiguous: bool = False


class MatchConflict(StrictModel):
    reason: ConflictReason
    normalized_title: str | None = None
    source_refs: list[RemoteRef] = Field(min_length=1)
    target_refs: list[RemoteRef] = Field(min_length=1)
    source_title_identities: list[CanonicalTextEvidence] = Field(default_factory=list)
    target_title_identities: list[CanonicalTextEvidence] = Field(default_factory=list)
    candidates: list[MatchCandidateEvidence] = Field(default_factory=list)


class MissingVideo(StrictModel):
    ref: RemoteRef
    title: str
    title_identity: CanonicalTextEvidence
    duration_seconds: int | None = Field(default=None, ge=0)
    privacy_status: str | None = None
    collection_titles: list[str] = Field(default_factory=list)


class CollectionGap(StrictModel):
    source_collection_id: str
    source_title: str
    source_title_identity: CanonicalTextEvidence
    decision: Literal["mapped", "create", "conflict"]
    conflict_reason: str | None = None
    target_collection_id: str | None = None
    target_title: str | None = None
    target_title_identity: CanonicalTextEvidence | None = None
    source_member_count: int = Field(ge=0)
    matched_source_member_count: int = Field(ge=0)
    target_member_count: int = Field(ge=0)
    unmapped_source_video_ids: list[str] = Field(default_factory=list)
    missing_target_video_ids: list[str] = Field(default_factory=list)
    extra_target_video_ids: list[str] = Field(default_factory=list)

    @property
    def missing_placement_count(self) -> int:
        return len(self.missing_target_video_ids)


class CrossPlatformComparison(StrictModel):
    schema_name: str = "video-manager.cross-platform-comparison"
    schema_version: str = "3.0"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_snapshot_id: str
    target_snapshot_id: str
    source_channel: RemoteRef
    target_channel: RemoteRef
    matches: list[VideoMatch] = Field(default_factory=list)
    conflicts: list[MatchConflict] = Field(default_factory=list)
    missing_on_target: list[MissingVideo] = Field(default_factory=list)
    extra_on_target: list[MissingVideo] = Field(default_factory=list)
    catalog_identity: CatalogIdentityEvidence | None = None
    collection_gaps: list[CollectionGap] = Field(default_factory=list)

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    @property
    def ambiguous_match_count(self) -> int:
        """Compatibility alias: ambiguity is a conflict, never a selected pair."""
        return self.conflict_count

    @property
    def unresolved_source_count(self) -> int:
        return sum(len(item.source_refs) for item in self.conflicts)

    @property
    def unresolved_target_count(self) -> int:
        return sum(len(item.target_refs) for item in self.conflicts)

    @property
    def title_drift_count(self) -> int:
        return sum(item.source_title != item.target_title for item in self.matches)

    @property
    def description_drift_count(self) -> int:
        return sum(not item.exact_description for item in self.matches)

    @property
    def collection_conflict_count(self) -> int:
        return sum(item.decision == "conflict" for item in self.collection_gaps)

    @property
    def missing_collection_count(self) -> int:
        return sum(item.decision == "create" for item in self.collection_gaps)

    @property
    def missing_placement_count(self) -> int:
        return sum(
            item.missing_placement_count
            for item in self.collection_gaps
            if item.decision != "conflict"
        )
