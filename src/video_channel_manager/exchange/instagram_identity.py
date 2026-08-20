from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_NUMERIC_ID_RE = re.compile(r"^[0-9]+$")
_API_VERSION_RE = re.compile(r"^v[0-9]+\.[0-9]+$")

InstagramLoginMode = Literal["instagram_login", "facebook_login"]
InstagramGraphHost = Literal["graph.instagram.com", "graph.facebook.com"]


class InstagramIdentityFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _validate_numeric_id(value: str, *, field_name: str) -> str:
    if _NUMERIC_ID_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be an exact numeric provider ID")
    return value


def _validate_sha256(value: str, *, field_name: str) -> str:
    if _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must use sha256:<64 lowercase hex>")
    return value


class InstagramAccountObservation(InstagramIdentityFrozenModel):
    schema_name: Literal["video-manager.instagram-account-observation"] = "video-manager.instagram-account-observation"
    schema_version: Literal[1] = 1
    status: Literal["provider-read-evidence"] = "provider-read-evidence"
    provider_effect: Literal["read_only"] = "read_only"
    provider_writes_authorized: Literal[False] = False
    login_mode: InstagramLoginMode
    provider_host: InstagramGraphHost
    api_version: str
    instagram_professional_account_id: str
    username_observed: str | None = None
    account_type_observed: str | None = None
    facebook_page_id: str | None = None
    granted_scopes: tuple[str, ...]
    observed_at: datetime
    account_evidence_sha256: str
    scope_evidence_sha256: str

    @field_validator("api_version")
    @classmethod
    def validate_api_version(cls, value: str) -> str:
        if _API_VERSION_RE.fullmatch(value) is None:
            raise ValueError("api_version must use v<major>.<minor>")
        return value

    @field_validator("instagram_professional_account_id")
    @classmethod
    def validate_instagram_id(cls, value: str) -> str:
        return _validate_numeric_id(value, field_name="instagram_professional_account_id")

    @field_validator("facebook_page_id")
    @classmethod
    def validate_page_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_numeric_id(value, field_name="facebook_page_id")

    @field_validator("account_evidence_sha256", "scope_evidence_sha256")
    @classmethod
    def validate_evidence_sha256(cls, value: str) -> str:
        return _validate_sha256(value, field_name="evidence digest")

    @model_validator(mode="after")
    def validate_observation(self) -> InstagramAccountObservation:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.account_evidence_sha256 == self.scope_evidence_sha256:
            raise ValueError("account and scope evidence must come from distinct provider-read artifacts")
        if not self.granted_scopes:
            raise ValueError("granted_scopes must not be empty")
        if len(self.granted_scopes) != len(set(self.granted_scopes)):
            raise ValueError("granted_scopes must be unique")
        if tuple(sorted(self.granted_scopes)) != self.granted_scopes:
            raise ValueError("granted_scopes must be sorted")

        scopes = set(self.granted_scopes)
        if self.login_mode == "instagram_login":
            if self.provider_host != "graph.instagram.com":
                raise ValueError("instagram_login observations must use graph.instagram.com")
            if "instagram_business_basic" not in scopes:
                raise ValueError("instagram_login identity proof requires instagram_business_basic")
            if self.facebook_page_id is not None:
                raise ValueError("instagram_login identity proof must not depend on a Facebook Page")
        else:
            if self.provider_host != "graph.facebook.com":
                raise ValueError("facebook_login observations must use graph.facebook.com")
            if "instagram_basic" not in scopes:
                raise ValueError("facebook_login identity proof requires instagram_basic")
            if "pages_show_list" not in scopes:
                raise ValueError("facebook_login Page discovery requires pages_show_list")
            if self.facebook_page_id is None:
                raise ValueError("facebook_login identity proof requires the linked Facebook Page ID")
        return self


class InstagramProjectBinding(InstagramIdentityFrozenModel):
    schema_name: Literal["video-manager.instagram-project-binding"] = "video-manager.instagram-project-binding"
    schema_version: Literal[1] = 1
    status: Literal["human-reviewed-binding"] = "human-reviewed-binding"
    provider_effect: Literal["impossible"] = "impossible"
    provider_writes_authorized: Literal[False] = False
    project_key: str = Field(min_length=1)
    instagram_professional_account_id: str
    observation_sha256: str
    username_observed: str | None = None
    approved_at: datetime
    approved_by: str = Field(min_length=1)

    @field_validator("instagram_professional_account_id")
    @classmethod
    def validate_instagram_id(cls, value: str) -> str:
        return _validate_numeric_id(value, field_name="instagram_professional_account_id")

    @field_validator("observation_sha256")
    @classmethod
    def validate_observation_sha256(cls, value: str) -> str:
        return _validate_sha256(value, field_name="observation_sha256")

    @model_validator(mode="after")
    def validate_binding(self) -> InstagramProjectBinding:
        if self.approved_at.tzinfo is None or self.approved_at.utcoffset() is None:
            raise ValueError("approved_at must be timezone-aware")
        return self


class InstagramProjectBindingRegistry(InstagramIdentityFrozenModel):
    schema_name: Literal["video-manager.instagram-project-binding-registry"] = (
        "video-manager.instagram-project-binding-registry"
    )
    schema_version: Literal[1] = 1
    status: Literal["provider-inert"] = "provider-inert"
    provider_effect: Literal["impossible"] = "impossible"
    provider_writes_authorized: Literal[False] = False
    bindings: tuple[InstagramProjectBinding, ...]

    @model_validator(mode="after")
    def validate_uniqueness(self) -> InstagramProjectBindingRegistry:
        project_keys = tuple(binding.project_key for binding in self.bindings)
        if len(project_keys) != len(set(project_keys)):
            raise ValueError("Instagram project bindings must use unique project keys")
        provider_ids = tuple(binding.instagram_professional_account_id for binding in self.bindings)
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("one Instagram professional account cannot bind to multiple projects")
        return self
