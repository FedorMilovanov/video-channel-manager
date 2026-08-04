from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from video_channel_manager.domain.models import StrictModel


class TextPurpose(StrEnum):
    IDENTITY_TITLE = "identity_title"
    DISPLAY_TITLE = "display_title"
    DESCRIPTION = "description"
    COLLECTION_TITLE = "collection_title"
    VARIATION = "variation"


class UrlRouteKind(StrEnum):
    PUBLIC_SITE = "public_site"
    PUBLIC_CHANNEL = "public_channel"
    PUBLIC_COLLECTION = "public_collection"
    PUBLIC_MEDIA = "public_media"
    PUBLIC_PROFILE = "public_profile"


class CanonicalTextEvidence(StrictModel):
    schema_name: str = "video-manager.canonical-text-evidence"
    schema_version: str = "1.0"
    ruleset_version: str = "wave-8b-v1"
    purpose: TextPurpose
    original: str
    canonical: str
    transformations: list[str] = Field(default_factory=list)
    digest: str


class CanonicalUrlEvidence(StrictModel):
    schema_name: str = "video-manager.canonical-url-evidence"
    schema_version: str = "1.0"
    ruleset_version: str = "wave-8b-v1"
    original: str
    canonical: str
    transformations: list[str] = Field(default_factory=list)
    project_key: str | None = None
    route_kind: UrlRouteKind | None = None
    digest: str


class FieldReadbackItem(StrictModel):
    field: str
    purpose: TextPurpose
    expected: CanonicalTextEvidence
    observed: CanonicalTextEvidence | None = None
    exact: bool


class ExactFieldReadback(StrictModel):
    schema_name: str = "video-manager.exact-field-readback"
    schema_version: str = "1.0"
    ruleset_version: str = "wave-8b-v1"
    items: list[FieldReadbackItem] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    unexpected_fields: list[str] = Field(default_factory=list)
    exact: bool
    digest: str
