from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

InstagramProjectKey = Literal["legendary-poet", "lord-god-strength"]
InstagramSurface = Literal["reel", "feed", "carousel"]
InstagramCandidateStatus = Literal["candidate", "reviewed", "approved-for-plan"]
InstagramMetricState = Literal["observed", "unavailable", "not_observed"]
InstagramMetricUnit = Literal["count", "seconds", "ratio"]

_STABLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,159}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_BLOB_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_NUMERIC_ID_RE = re.compile(r"^[0-9]+$")
_HASHTAG_RE = re.compile(r"^#[^\s#]+$", re.UNICODE)


class InstagramContentFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InstagramLaunchSource(InstagramContentFrozenModel):
    source_id: str
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    blob_sha: str | None = None

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        normalized = value.strip()
        if _STABLE_ID_RE.fullmatch(normalized) is None:
            raise ValueError("source_id must be a stable 2-160 character identifier")
        return normalized

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith(("https://", "http://")):
            raise ValueError("source URL must be absolute HTTP(S)")
        return normalized

    @field_validator("blob_sha")
    @classmethod
    def validate_blob_sha(cls, value: str | None) -> str | None:
        if value is not None and _BLOB_SHA_RE.fullmatch(value) is None:
            raise ValueError("blob_sha must be 40 lowercase hexadecimal characters")
        return value


class InstagramExcludedSource(InstagramContentFrozenModel):
    path: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class InstagramLaunchCandidate(InstagramContentFrozenModel):
    candidate_id: str
    status: InstagramCandidateStatus
    surface: InstagramSurface
    variation_key: str
    source_ids: tuple[str, ...] = Field(min_length=1)
    source_content_ids: tuple[str, ...] = ()
    topic_line: str = Field(min_length=5)
    caption_body: str = Field(min_length=20)
    provenance_line: str | None = None
    cta: str = Field(min_length=1)
    hashtags: tuple[str, ...] = Field(min_length=3, max_length=6)
    media_intent: str = Field(min_length=10)
    ai_audio_disclosure_required: bool = False
    quote_state: str | None = None
    scripture_quote_state: str | None = None
    blocking_unknowns: tuple[str, ...] = Field(min_length=1)

    @field_validator("candidate_id", "variation_key")
    @classmethod
    def validate_stable_id(cls, value: str) -> str:
        normalized = value.strip()
        if _STABLE_ID_RE.fullmatch(normalized) is None:
            raise ValueError("candidate_id and variation_key must be stable 2-160 character identifiers")
        return normalized

    @field_validator("source_ids", "source_content_ids", "blocking_unknowns")
    @classmethod
    def validate_unique_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(item.strip() for item in value)
        if any(not item for item in normalized):
            raise ValueError("list values must not contain blanks")
        if len(normalized) != len(set(normalized)):
            raise ValueError("list values must be unique")
        return normalized

    @field_validator("hashtags")
    @classmethod
    def validate_hashtags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(item.strip() for item in value)
        if any(_HASHTAG_RE.fullmatch(item) is None for item in normalized):
            raise ValueError("hashtags must use #token syntax without spaces")
        folded = tuple(item.casefold() for item in normalized)
        if len(folded) != len(set(folded)):
            raise ValueError("hashtags must be unique ignoring case")
        return normalized

    @model_validator(mode="after")
    def validate_disclosure_shape(self) -> InstagramLaunchCandidate:
        if self.ai_audio_disclosure_required and not (self.provenance_line or "").strip():
            raise ValueError("AI-audio disclosure requires provenance_line")
        return self


class InstagramLaunchPack(InstagramContentFrozenModel):
    schema_name: Literal["video-manager.instagram-launch-pack"] = "video-manager.instagram-launch-pack"
    schema_version: Literal[1] = 1
    project_key: InstagramProjectKey
    public_handle_hint: str | None = None
    provider_account_id: None = None
    provider_writes_authorized: Literal[False] = False
    approval_state: InstagramCandidateStatus = "candidate"
    generated_from: dict[str, str]
    source_ledger: tuple[InstagramLaunchSource, ...] = Field(min_length=1)
    excluded_current_sources: tuple[InstagramExcludedSource, ...] = ()
    house_rules: dict[str, Any]
    candidates: tuple[InstagramLaunchCandidate, ...] = Field(min_length=9, max_length=12)

    @field_validator("public_handle_hint")
    @classmethod
    def validate_handle_hint(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("public_handle_hint cannot be blank")
        return normalized

    @model_validator(mode="after")
    def validate_pack(self) -> InstagramLaunchPack:
        source_ids = tuple(item.source_id for item in self.source_ledger)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source_ledger source_id values must be unique")
        candidate_ids = tuple(item.candidate_id for item in self.candidates)
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate_id values must be unique")
        variations = tuple(item.variation_key for item in self.candidates)
        if len(variations) != len(set(variations)):
            raise ValueError("variation_key values must be unique")

        known_sources = set(source_ids)
        for candidate in self.candidates:
            missing = sorted(set(candidate.source_ids) - known_sources)
            if missing:
                raise ValueError(
                    f"candidate {candidate.candidate_id} references unknown source_ids: {', '.join(missing)}"
                )
            if self.project_key == "legendary-poet":
                if candidate.quote_state is None:
                    raise ValueError(f"candidate {candidate.candidate_id} requires quote_state")
                if candidate.scripture_quote_state is not None:
                    raise ValueError("Legendary Poet candidates must not use scripture_quote_state")
            else:
                if candidate.scripture_quote_state is None:
                    raise ValueError(f"candidate {candidate.candidate_id} requires scripture_quote_state")
                if candidate.quote_state is not None:
                    raise ValueError("Lord God candidates must not use literary quote_state")
        return self


class InstagramLaunchPreviewIssue(InstagramContentFrozenModel):
    code: str = Field(min_length=1)
    severity: Literal["warning", "error"]
    message: str = Field(min_length=1)
    line_number: int | None = Field(default=None, ge=1)


class InstagramLaunchPreviewItem(InstagramContentFrozenModel):
    candidate_id: str
    surface: InstagramSurface
    rendered_caption: str
    character_count: int = Field(ge=0)
    hashtag_count: int = Field(ge=0)
    blocking_unknowns: tuple[str, ...]
    issues: tuple[InstagramLaunchPreviewIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


class InstagramLaunchPreviewCounts(InstagramContentFrozenModel):
    total: int = Field(ge=0)
    valid: int = Field(ge=0)
    blocked: int = Field(ge=0)
    warnings: int = Field(ge=0)
    errors: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_partition(self) -> InstagramLaunchPreviewCounts:
        if self.valid + self.blocked != self.total:
            raise ValueError("valid + blocked must equal total")
        return self


class InstagramLaunchPreviewArtifact(InstagramContentFrozenModel):
    schema_name: Literal["video-manager.instagram-launch-preview"] = "video-manager.instagram-launch-preview"
    schema_version: Literal[1] = 1
    project_key: InstagramProjectKey
    source_pack_sha256: str
    evidence_scope: Literal["exact_launch_pack_bytes"] = "exact_launch_pack_bytes"
    provider_effect: Literal["impossible"] = "impossible"
    provider_writes_authorized: Literal[False] = False
    items: tuple[InstagramLaunchPreviewItem, ...]
    counts: InstagramLaunchPreviewCounts

    @field_validator("source_pack_sha256")
    @classmethod
    def validate_source_pack_sha256(cls, value: str) -> str:
        if _SHA256_RE.fullmatch(value) is None:
            raise ValueError("source_pack_sha256 must use sha256:<64 lowercase hex>")
        return value

    @model_validator(mode="after")
    def validate_counts(self) -> InstagramLaunchPreviewArtifact:
        if self.counts.total != len(self.items):
            raise ValueError("preview counts.total must equal item count")
        return self


class InstagramMetricValue(InstagramContentFrozenModel):
    state: InstagramMetricState = "not_observed"
    unit: InstagramMetricUnit
    value: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_metric(self) -> InstagramMetricValue:
        if self.state == "observed" and self.value is None:
            raise ValueError("observed metric requires a value")
        if self.state != "observed" and self.value is not None:
            raise ValueError("unavailable/not_observed metric value must be null")
        if self.unit == "ratio" and self.value is not None and self.value > 1:
            raise ValueError("ratio metric must be between 0 and 1")
        return self


def _count_metric() -> InstagramMetricValue:
    return InstagramMetricValue(unit="count")


def _seconds_metric() -> InstagramMetricValue:
    return InstagramMetricValue(unit="seconds")


def _ratio_metric() -> InstagramMetricValue:
    return InstagramMetricValue(unit="ratio")


class InstagramAnalyticsMetrics(InstagramContentFrozenModel):
    reach: InstagramMetricValue = Field(default_factory=_count_metric)
    non_follower_reach: InstagramMetricValue = Field(default_factory=_count_metric)
    views: InstagramMetricValue = Field(default_factory=_count_metric)
    plays: InstagramMetricValue = Field(default_factory=_count_metric)
    watch_time_seconds: InstagramMetricValue = Field(default_factory=_seconds_metric)
    average_watch_time_seconds: InstagramMetricValue = Field(default_factory=_seconds_metric)
    completion_ratio: InstagramMetricValue = Field(default_factory=_ratio_metric)
    saves: InstagramMetricValue = Field(default_factory=_count_metric)
    shares: InstagramMetricValue = Field(default_factory=_count_metric)
    comments: InstagramMetricValue = Field(default_factory=_count_metric)
    follows: InstagramMetricValue = Field(default_factory=_count_metric)
    profile_actions: InstagramMetricValue = Field(default_factory=_count_metric)
    link_actions: InstagramMetricValue = Field(default_factory=_count_metric)

    @model_validator(mode="after")
    def validate_units(self) -> InstagramAnalyticsMetrics:
        expected = {
            "reach": "count",
            "non_follower_reach": "count",
            "views": "count",
            "plays": "count",
            "watch_time_seconds": "seconds",
            "average_watch_time_seconds": "seconds",
            "completion_ratio": "ratio",
            "saves": "count",
            "shares": "count",
            "comments": "count",
            "follows": "count",
            "profile_actions": "count",
            "link_actions": "count",
        }
        for field_name, unit in expected.items():
            if getattr(self, field_name).unit != unit:
                raise ValueError(f"{field_name} must use unit={unit}")
        return self


class InstagramAnalyticsSnapshot(InstagramContentFrozenModel):
    schema_name: Literal["video-manager.instagram-analytics-snapshot"] = "video-manager.instagram-analytics-snapshot"
    schema_version: Literal[1] = 1
    project_key: InstagramProjectKey
    candidate_id: str
    instagram_professional_account_id: str
    instagram_media_id: str
    creative_sha256: str
    published_at: datetime
    observed_at: datetime
    source_evidence_sha256: str
    source: Literal["instagram_api", "manual_export"]
    provider_effect: Literal["read_only"] = "read_only"
    provider_writes_authorized: Literal[False] = False
    metrics: InstagramAnalyticsMetrics = Field(default_factory=InstagramAnalyticsMetrics)

    @field_validator("candidate_id")
    @classmethod
    def validate_candidate_id(cls, value: str) -> str:
        normalized = value.strip()
        if _STABLE_ID_RE.fullmatch(normalized) is None:
            raise ValueError("candidate_id must be a stable 2-160 character identifier")
        return normalized

    @field_validator("instagram_professional_account_id", "instagram_media_id")
    @classmethod
    def validate_numeric_provider_id(cls, value: str) -> str:
        if _NUMERIC_ID_RE.fullmatch(value) is None:
            raise ValueError("Instagram account/media IDs must be exact numeric provider IDs")
        return value

    @field_validator("creative_sha256", "source_evidence_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if _SHA256_RE.fullmatch(value) is None:
            raise ValueError("digest must use sha256:<64 lowercase hex>")
        return value

    @model_validator(mode="after")
    def validate_time_order(self) -> InstagramAnalyticsSnapshot:
        if self.published_at.tzinfo is None or self.published_at.utcoffset() is None:
            raise ValueError("published_at must be timezone-aware")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.observed_at < self.published_at:
            raise ValueError("observed_at cannot precede published_at")
        return self
