from __future__ import annotations

import hashlib
import ipaddress
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Callable, Self, cast

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from video_channel_manager.config.settings import AppSettings
from video_channel_manager.persistence.database import Database
from video_channel_manager.persistence.models import InstagramPublicationEntity, utc_now


class InstagramProductionError(RuntimeError):
    """Base error for production Instagram publishing."""


class InstagramConfigurationError(InstagramProductionError):
    pass


class InstagramWriteGateError(InstagramProductionError):
    pass


class InstagramIdentityMismatchError(InstagramProductionError):
    pass


class InstagramReconciliationRequired(InstagramProductionError):
    pass


class InstagramProviderError(InstagramProductionError):
    def __init__(self, message: str, *, status_code: int | None = None, error_code: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class InstagramTransportError(InstagramProductionError):
    pass


class InstagramMediaVerificationError(InstagramProductionError):
    def __init__(self, message: str, *, error_code: str, retryable: bool) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.retryable = retryable


class PublicationStatus(StrEnum):
    PLANNED = "planned"
    CONTAINER_REQUESTED = "container_requested"
    CONTAINER_UNKNOWN = "container_unknown"
    CONTAINER_CREATED = "container_created"
    PROCESSING = "processing"
    READY = "ready"
    PUBLISH_REQUESTED = "publish_requested"
    PUBLISHED = "published"
    PUBLISHED_UNRESOLVED = "published_unresolved"
    PUBLISH_UNKNOWN = "publish_unknown"
    RETRYABLE_FAILURE = "retryable_failure"
    TERMINAL_FAILURE = "terminal_failure"


class InstagramPublishManifest(BaseModel):
    """Canonical provider-bound input for one logical Reel publication."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1", pattern=r"^1$")
    publication_key: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    account_id: str = Field(min_length=1, max_length=255)
    video_url: HttpUrl
    media_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    media_size_bytes: int = Field(gt=0)
    media_content_type: str = Field(default="video/mp4", pattern=r"^(video/mp4|video/quicktime)$")
    caption: str = Field(default="", max_length=2200)
    share_to_feed: bool = True
    cover_url: HttpUrl | None = None
    cover_sha256: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    cover_size_bytes: int | None = Field(default=None, gt=0)
    cover_content_type: str | None = Field(default=None, pattern=r"^(image/jpeg|image/png)$")
    thumb_offset_ms: int | None = Field(default=None, ge=0)

    @field_validator("video_url", "cover_url")
    @classmethod
    def require_public_https_url(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is None:
            return None
        if value.scheme != "https":
            raise ValueError("Instagram publishing media URLs must use HTTPS")
        host = value.host
        if host is None or host.lower() == "localhost":
            raise ValueError("Instagram publishing media URLs must use a public host")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return value
        if not address.is_global:
            raise ValueError("Instagram publishing media URLs must not use private or local IP addresses")
        return value

    @model_validator(mode="after")
    def validate_cover_integrity_contract(self) -> Self:
        integrity_fields = (self.cover_sha256, self.cover_size_bytes, self.cover_content_type)
        if self.cover_url is None and any(value is not None for value in integrity_fields):
            raise ValueError("Cover integrity fields require cover_url")
        if self.cover_url is not None and any(value is None for value in integrity_fields):
            raise ValueError("cover_url requires cover_sha256, cover_size_bytes and cover_content_type")
        return self

    def content_hash(self) -> str:
        payload = self.model_dump(mode="json")
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True)
class InstagramRuntimeConfig:
    login_mode: str
    graph_host: str
    api_version: str
    account_id: str
    expected_username: str | None
    access_token: str = field(repr=False)
    writes_enabled: bool
    media_allowed_hosts: tuple[str, ...]
    timeout_seconds: float
    poll_interval_seconds: float
    poll_attempts: int

    @classmethod
    def from_settings(cls, settings: AppSettings) -> InstagramRuntimeConfig:
        api_version = settings.instagram_graph_api_version
        account_id = settings.instagram_account_id
        access_token = settings.instagram_access_token

        missing: list[str] = []
        if api_version is None:
            missing.append("VCM_INSTAGRAM_GRAPH_API_VERSION")
        if account_id is None:
            missing.append("VCM_INSTAGRAM_ACCOUNT_ID")
        if access_token is None:
            missing.append("VCM_INSTAGRAM_ACCESS_TOKEN")
        if missing:
            raise InstagramConfigurationError(f"Missing Instagram provider configuration: {', '.join(missing)}")
        if api_version is None or account_id is None or access_token is None:
            raise InstagramConfigurationError("Instagram provider configuration failed validation")

        expected_host = (
            "https://graph.instagram.com"
            if settings.instagram_login_mode == "instagram"
            else "https://graph.facebook.com"
        )
        if settings.instagram_graph_host != expected_host:
            raise InstagramConfigurationError(
                f"Instagram login mode {settings.instagram_login_mode!r} requires graph host {expected_host!r}"
            )

        return cls(
            login_mode=settings.instagram_login_mode,
            graph_host=settings.instagram_graph_host,
            api_version=api_version,
            account_id=account_id,
            expected_username=settings.instagram_account_username,
            access_token=access_token.get_secret_value(),
            writes_enabled=settings.instagram_writes_enabled,
            media_allowed_hosts=settings.instagram_media_allowed_hosts,
            timeout_seconds=settings.instagram_request_timeout_seconds,
            poll_interval_seconds=settings.instagram_poll_interval_seconds,
            poll_attempts=settings.instagram_poll_attempts,
        )

    @property
    def base_url(self) -> str:
        return f"{self.graph_host}/{self.api_version}"

    def require_write_gate(self, *, execute: bool) -> None:
        if not execute:
            raise InstagramWriteGateError("Provider write refused: pass --execute explicitly")
        if not self.writes_enabled:
            raise InstagramWriteGateError(
                "Provider write refused: VCM_INSTAGRAM_WRITES_ENABLED is false; this is the production kill switch"
            )

    def require_media_host(self, url: HttpUrl) -> None:
        host = (url.host or "").lower().rstrip(".")
        if not self.media_allowed_hosts:
            raise InstagramConfigurationError(
                "Provider write refused: VCM_INSTAGRAM_MEDIA_ALLOWED_HOSTS is empty; configure exact trusted media hosts"
            )
        if host not in self.media_allowed_hosts:
            raise InstagramConfigurationError(
                f"Provider write refused: media host {host!r} is not in VCM_INSTAGRAM_MEDIA_ALLOWED_HOSTS"
            )


@dataclass(frozen=True)
class PublicationSnapshot:
    publication_key: str
    account_id: str
    content_hash: str
    status: PublicationStatus
    provider_container_id: str | None
    provider_media_id: str | None
    provider_status: str | None
    attempt_count: int
    last_error_code: str | None
    last_error_message: str | None
    container_requested_at: datetime | None
    publish_requested_at: datetime | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InstagramPublicationLedger:
    """Transactional ledger with compare-and-set claims around provider mutations."""

    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _snapshot(entity: InstagramPublicationEntity) -> PublicationSnapshot:
        return PublicationSnapshot(
            publication_key=entity.publication_key,
            account_id=entity.account_id,
            content_hash=entity.content_hash,
            status=PublicationStatus(entity.status),
            provider_container_id=entity.provider_container_id,
            provider_media_id=entity.provider_media_id,
            provider_status=entity.provider_status,
            attempt_count=entity.attempt_count,
            last_error_code=entity.last_error_code,
            last_error_message=entity.last_error_message,
            container_requested_at=entity.container_requested_at,
            publish_requested_at=entity.publish_requested_at,
            published_at=entity.published_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @classmethod
    def _snapshot_from_session(cls, session: Session, publication_key: str) -> PublicationSnapshot:
        session.expire_all()
        entity = session.get(InstagramPublicationEntity, publication_key)
        if entity is None:
            raise InstagramProductionError(f"Unknown publication key: {publication_key}")
        return cls._snapshot(entity)

    def get(self, publication_key: str) -> PublicationSnapshot | None:
        with self.database.session() as session:
            entity = session.get(InstagramPublicationEntity, publication_key)
            return None if entity is None else self._snapshot(entity)

    @staticmethod
    def _assert_binding(entity: InstagramPublicationEntity, manifest: InstagramPublishManifest) -> None:
        if entity.account_id != manifest.account_id or entity.content_hash != manifest.content_hash():
            raise InstagramProductionError(
                "Publication key is already bound to different canonical content or a different account"
            )

    def ensure_planned(self, manifest: InstagramPublishManifest) -> PublicationSnapshot:
        content_hash = manifest.content_hash()
        try:
            with self.database.session() as session:
                entity = session.get(InstagramPublicationEntity, manifest.publication_key)
                if entity is not None:
                    self._assert_binding(entity, manifest)
                    return self._snapshot(entity)
                entity = InstagramPublicationEntity(
                    publication_key=manifest.publication_key,
                    account_id=manifest.account_id,
                    content_hash=content_hash,
                    manifest=cast(dict[str, object], manifest.model_dump(mode="json")),
                    status=PublicationStatus.PLANNED.value,
                )
                session.add(entity)
                session.flush()
                return self._snapshot(entity)
        except IntegrityError as exc:
            # A concurrent planner may have inserted the same primary key after
            # our read. Re-read and verify the immutable binding instead of
            # turning a safe idempotent race into an operator-visible failure.
            with self.database.session() as session:
                entity = session.get(InstagramPublicationEntity, manifest.publication_key)
                if entity is None:
                    raise InstagramProductionError(
                        f"Publication {manifest.publication_key} raced during planning but cannot be re-read"
                    ) from exc
                self._assert_binding(entity, manifest)
                return self._snapshot(entity)

    def transition(
        self,
        publication_key: str,
        status: PublicationStatus,
        *,
        expected_statuses: set[PublicationStatus] | None = None,
        container_id: str | None = None,
        media_id: str | None = None,
        provider_status: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        increment_attempt: bool = False,
        container_requested: bool = False,
        publish_requested: bool = False,
        published: bool = False,
    ) -> PublicationSnapshot:
        now = utc_now()
        if expected_statuses is None:
            with self.database.session() as session:
                entity = session.get(InstagramPublicationEntity, publication_key)
                if entity is None:
                    raise InstagramProductionError(f"Unknown publication key: {publication_key}")
                entity.status = status.value
                if container_id is not None:
                    entity.provider_container_id = container_id
                if media_id is not None:
                    entity.provider_media_id = media_id
                if provider_status is not None:
                    entity.provider_status = provider_status
                entity.last_error_code = error_code
                entity.last_error_message = error_message
                if increment_attempt:
                    entity.attempt_count += 1
                if container_requested:
                    entity.container_requested_at = now
                if publish_requested:
                    entity.publish_requested_at = now
                if published:
                    entity.published_at = now
                entity.updated_at = now
                session.flush()
                return self._snapshot(entity)

        values: dict[str, object] = {
            "status": status.value,
            "last_error_code": error_code,
            "last_error_message": error_message,
            "updated_at": now,
        }
        if container_id is not None:
            values["provider_container_id"] = container_id
        if media_id is not None:
            values["provider_media_id"] = media_id
        if provider_status is not None:
            values["provider_status"] = provider_status
        if increment_attempt:
            values["attempt_count"] = InstagramPublicationEntity.attempt_count + 1
        if container_requested:
            values["container_requested_at"] = now
        if publish_requested:
            values["publish_requested_at"] = now
        if published:
            values["published_at"] = now

        with self.database.session() as session:
            statement = (
                update(InstagramPublicationEntity)
                .where(
                    InstagramPublicationEntity.publication_key == publication_key,
                    InstagramPublicationEntity.status.in_([item.value for item in expected_statuses]),
                )
                .values(values)
                .returning(InstagramPublicationEntity.publication_key)
            )
            changed_key = session.execute(statement).scalar_one_or_none()
            if changed_key is None:
                current = self._snapshot_from_session(session, publication_key)
                raise InstagramReconciliationRequired(
                    f"Atomic state transition refused for {publication_key}: current state is {current.status.value}"
                )
            return self._snapshot_from_session(session, publication_key)

    def claim_container_request(self, publication_key: str) -> PublicationSnapshot:
        now = utc_now()
        with self.database.session() as session:
            statement = (
                update(InstagramPublicationEntity)
                .where(
                    InstagramPublicationEntity.publication_key == publication_key,
                    InstagramPublicationEntity.status.in_(
                        [PublicationStatus.PLANNED.value, PublicationStatus.RETRYABLE_FAILURE.value]
                    ),
                    InstagramPublicationEntity.provider_container_id.is_(None),
                )
                .values(
                    status=PublicationStatus.CONTAINER_REQUESTED.value,
                    attempt_count=InstagramPublicationEntity.attempt_count + 1,
                    container_requested_at=now,
                    last_error_code=None,
                    last_error_message=None,
                    updated_at=now,
                )
                .returning(InstagramPublicationEntity.publication_key)
            )
            changed_key = session.execute(statement).scalar_one_or_none()
            if changed_key is None:
                current = self._snapshot_from_session(session, publication_key)
                raise InstagramReconciliationRequired(
                    f"Container creation claim refused for {publication_key}: current state is {current.status.value}"
                )
            return self._snapshot_from_session(session, publication_key)

    def claim_publish_request(self, publication_key: str, container_id: str) -> PublicationSnapshot:
        now = utc_now()
        with self.database.session() as session:
            statement = (
                update(InstagramPublicationEntity)
                .where(
                    InstagramPublicationEntity.publication_key == publication_key,
                    InstagramPublicationEntity.status == PublicationStatus.READY.value,
                    InstagramPublicationEntity.provider_container_id == container_id,
                )
                .values(
                    status=PublicationStatus.PUBLISH_REQUESTED.value,
                    provider_status="FINISHED",
                    attempt_count=InstagramPublicationEntity.attempt_count + 1,
                    publish_requested_at=now,
                    last_error_code=None,
                    last_error_message=None,
                    updated_at=now,
                )
                .returning(InstagramPublicationEntity.publication_key)
            )
            changed_key = session.execute(statement).scalar_one_or_none()
            if changed_key is None:
                current = self._snapshot_from_session(session, publication_key)
                raise InstagramReconciliationRequired(
                    f"Publish claim refused for {publication_key}: current state is {current.status.value}"
                )
            return self._snapshot_from_session(session, publication_key)


RequestValue = str | int | float | bool | None


class InstagramProviderClient:
    """Minimal Meta Graph adapter plus isolated public-media verifier."""

    def __init__(
        self,
        config: InstagramRuntimeConfig,
        *,
        client: httpx.Client | None = None,
        media_client: httpx.Client | None = None,
    ) -> None:
        self.config = config
        self._owns_client = client is None
        self._owns_media_client = media_client is None
        self._client = client or httpx.Client(timeout=config.timeout_seconds)
        self._media_client = media_client or httpx.Client(timeout=config.timeout_seconds)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
        if self._owns_media_client:
            self._media_client.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, RequestValue] | None = None,
        params: dict[str, RequestValue] | None = None,
    ) -> dict[str, object]:
        headers = {"Authorization": f"Bearer {self.config.access_token}"}
        try:
            response = self._client.request(
                method,
                f"{self.config.base_url}/{path.lstrip('/')}",
                headers=headers,
                data=data,
                params=params,
            )
        except httpx.RequestError as exc:
            raise InstagramTransportError(f"Instagram provider transport failure: {exc}") from exc

        payload: object
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if response.is_error:
            error_code: str | None = None
            message = f"Instagram provider returned HTTP {response.status_code}"
            if isinstance(payload, dict):
                raw_error = payload.get("error")
                if isinstance(raw_error, dict):
                    raw_message = raw_error.get("message")
                    if isinstance(raw_message, str) and raw_message:
                        message = raw_message
                    raw_code = raw_error.get("code")
                    if raw_code is not None:
                        error_code = str(raw_code)
            raise InstagramProviderError(message, status_code=response.status_code, error_code=error_code)
        if not isinstance(payload, dict):
            raise InstagramProviderError("Instagram provider returned a non-object JSON response")
        return cast(dict[str, object], payload)

    def get_account_identity(self) -> dict[str, object]:
        return self._request("GET", self.config.account_id, params={"fields": "id,username"})

    def get_publishing_limit(self) -> dict[str, object]:
        return self._request(
            "GET",
            f"{self.config.account_id}/content_publishing_limit",
            params={"fields": "quota_usage,config"},
        )

    def verify_manifest_media(self, manifest: InstagramPublishManifest) -> dict[str, object]:
        video = self._verify_public_object(
            manifest.video_url,
            expected_sha256=manifest.media_sha256,
            expected_size_bytes=manifest.media_size_bytes,
            expected_content_type=manifest.media_content_type,
            label="video",
        )
        result: dict[str, object] = {"video": video}
        if manifest.cover_url is not None:
            if (
                manifest.cover_sha256 is None
                or manifest.cover_size_bytes is None
                or manifest.cover_content_type is None
            ):
                raise InstagramMediaVerificationError(
                    "Cover integrity contract is incomplete",
                    error_code="cover_integrity_contract_incomplete",
                    retryable=False,
                )
            result["cover"] = self._verify_public_object(
                manifest.cover_url,
                expected_sha256=manifest.cover_sha256,
                expected_size_bytes=manifest.cover_size_bytes,
                expected_content_type=manifest.cover_content_type,
                label="cover",
            )
        return result

    def _verify_public_object(
        self,
        url: HttpUrl,
        *,
        expected_sha256: str,
        expected_size_bytes: int,
        expected_content_type: str,
        label: str,
    ) -> dict[str, object]:
        self.config.require_media_host(url)
        try:
            with self._media_client.stream(
                "GET",
                str(url),
                headers={"Accept": expected_content_type},
                follow_redirects=False,
            ) as response:
                if response.is_redirect:
                    raise InstagramMediaVerificationError(
                        f"Instagram {label} URL redirected; redirects are refused at the provider boundary",
                        error_code=f"{label}_redirect_refused",
                        retryable=False,
                    )
                if response.status_code < 200 or response.status_code >= 300:
                    retryable = response.status_code in {408, 425, 429} or response.status_code >= 500
                    raise InstagramMediaVerificationError(
                        f"Instagram {label} URL returned HTTP {response.status_code}",
                        error_code=f"{label}_http_{response.status_code}",
                        retryable=retryable,
                    )

                content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if content_type != expected_content_type:
                    raise InstagramMediaVerificationError(
                        f"Instagram {label} content type mismatch: expected {expected_content_type!r}, got {content_type!r}",
                        error_code=f"{label}_content_type_mismatch",
                        retryable=False,
                    )

                raw_content_length = response.headers.get("content-length")
                if raw_content_length is not None:
                    try:
                        content_length = int(raw_content_length)
                    except ValueError as exc:
                        raise InstagramMediaVerificationError(
                            f"Instagram {label} Content-Length is invalid",
                            error_code=f"{label}_invalid_content_length",
                            retryable=False,
                        ) from exc
                    if content_length != expected_size_bytes:
                        raise InstagramMediaVerificationError(
                            f"Instagram {label} size mismatch: expected {expected_size_bytes}, got {content_length}",
                            error_code=f"{label}_size_mismatch",
                            retryable=False,
                        )

                digest = hashlib.sha256()
                observed_size = 0
                for chunk in response.iter_bytes():
                    observed_size += len(chunk)
                    if observed_size > expected_size_bytes:
                        raise InstagramMediaVerificationError(
                            f"Instagram {label} exceeded expected size {expected_size_bytes}",
                            error_code=f"{label}_size_mismatch",
                            retryable=False,
                        )
                    digest.update(chunk)
        except InstagramMediaVerificationError:
            raise
        except httpx.RequestError as exc:
            raise InstagramMediaVerificationError(
                f"Instagram {label} verification transport failure: {exc}",
                error_code=f"{label}_transport_failure",
                retryable=True,
            ) from exc

        if observed_size != expected_size_bytes:
            raise InstagramMediaVerificationError(
                f"Instagram {label} size mismatch: expected {expected_size_bytes}, got {observed_size}",
                error_code=f"{label}_size_mismatch",
                retryable=False,
            )
        observed_sha256 = f"sha256:{digest.hexdigest()}"
        if observed_sha256 != expected_sha256:
            raise InstagramMediaVerificationError(
                f"Instagram {label} SHA-256 mismatch",
                error_code=f"{label}_sha256_mismatch",
                retryable=False,
            )
        return {
            "url": str(url),
            "sha256": observed_sha256,
            "size_bytes": observed_size,
            "content_type": expected_content_type,
        }

    def create_reel_container(self, manifest: InstagramPublishManifest) -> str:
        data: dict[str, RequestValue] = {
            "media_type": "REELS",
            "video_url": str(manifest.video_url),
            "caption": manifest.caption,
            "share_to_feed": "true" if manifest.share_to_feed else "false",
        }
        if manifest.cover_url is not None:
            data["cover_url"] = str(manifest.cover_url)
        if manifest.thumb_offset_ms is not None:
            data["thumb_offset"] = manifest.thumb_offset_ms
        payload = self._request("POST", f"{self.config.account_id}/media", data=data)
        container_id = payload.get("id")
        if not isinstance(container_id, str) or not container_id:
            raise InstagramProviderError("Instagram container response did not include an id")
        return container_id

    def get_container_status(self, container_id: str) -> tuple[str, str | None]:
        payload = self._request("GET", container_id, params={"fields": "status_code,status"})
        raw_code = payload.get("status_code")
        if not isinstance(raw_code, str) or not raw_code:
            raise InstagramProviderError("Instagram container response did not include status_code")
        raw_status = payload.get("status")
        return raw_code.upper(), raw_status if isinstance(raw_status, str) else None

    def publish_container(self, container_id: str) -> str:
        payload = self._request(
            "POST",
            f"{self.config.account_id}/media_publish",
            data={"creation_id": container_id},
        )
        media_id = payload.get("id")
        if not isinstance(media_id, str) or not media_id:
            raise InstagramProviderError("Instagram publish response did not include a media id")
        return media_id


class InstagramProductionService:
    """Safe orchestration for preflight, publish, resume and reconciliation."""

    _PUBLISH_AMBIGUOUS = {
        PublicationStatus.PUBLISH_REQUESTED,
        PublicationStatus.PUBLISH_UNKNOWN,
        PublicationStatus.PUBLISHED_UNRESOLVED,
    }
    _CONTAINER_AMBIGUOUS = {
        PublicationStatus.CONTAINER_REQUESTED,
        PublicationStatus.CONTAINER_UNKNOWN,
    }

    def __init__(
        self,
        config: InstagramRuntimeConfig,
        ledger: InstagramPublicationLedger,
        *,
        client: InstagramProviderClient | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.ledger = ledger
        self.client = client or InstagramProviderClient(config)
        self._owns_client = client is None
        self._sleep = sleep

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def preflight(self) -> dict[str, object]:
        identity = self.client.get_account_identity()
        provider_id = identity.get("id")
        if str(provider_id) != self.config.account_id:
            raise InstagramIdentityMismatchError(
                f"Configured Instagram account {self.config.account_id!r} resolved to provider id {provider_id!r}"
            )
        provider_username = identity.get("username")
        if self.config.expected_username is not None and provider_username != self.config.expected_username:
            raise InstagramIdentityMismatchError(
                f"Configured Instagram username {self.config.expected_username!r} resolved to {provider_username!r}"
            )
        limit = self.client.get_publishing_limit()
        return {"identity": identity, "publishing_limit": limit}

    def plan(self, manifest: InstagramPublishManifest) -> PublicationSnapshot:
        self._assert_manifest_target(manifest)
        return self.ledger.ensure_planned(manifest)

    def publish(self, manifest: InstagramPublishManifest, *, execute: bool) -> PublicationSnapshot:
        self._assert_manifest_target(manifest)
        self.config.require_write_gate(execute=execute)
        self.preflight()
        snapshot = self.ledger.ensure_planned(manifest)

        if snapshot.status == PublicationStatus.PUBLISHED:
            return snapshot
        if snapshot.status in self._CONTAINER_AMBIGUOUS | self._PUBLISH_AMBIGUOUS:
            raise InstagramReconciliationRequired(
                f"Publication {manifest.publication_key} is {snapshot.status.value}; reconcile before any further write"
            )
        if snapshot.status == PublicationStatus.TERMINAL_FAILURE:
            raise InstagramProductionError(
                f"Publication {manifest.publication_key} is terminally failed; create a corrected manifest/publication key"
            )

        container_id = snapshot.provider_container_id
        if container_id is None:
            try:
                self.client.verify_manifest_media(manifest)
            except InstagramMediaVerificationError as exc:
                status = PublicationStatus.RETRYABLE_FAILURE if exc.retryable else PublicationStatus.TERMINAL_FAILURE
                self.ledger.transition(
                    manifest.publication_key,
                    status,
                    expected_statuses={PublicationStatus.PLANNED, PublicationStatus.RETRYABLE_FAILURE},
                    error_code=exc.error_code,
                    error_message=str(exc),
                )
                raise

            self.ledger.claim_container_request(manifest.publication_key)
            try:
                container_id = self.client.create_reel_container(manifest)
            except InstagramProviderError as exc:
                if exc.status_code is not None and 400 <= exc.status_code < 500:
                    self.ledger.transition(
                        manifest.publication_key,
                        PublicationStatus.TERMINAL_FAILURE,
                        expected_statuses={PublicationStatus.CONTAINER_REQUESTED},
                        error_code=self._error_code(exc),
                        error_message=str(exc),
                    )
                    raise
                self.ledger.transition(
                    manifest.publication_key,
                    PublicationStatus.CONTAINER_UNKNOWN,
                    expected_statuses={PublicationStatus.CONTAINER_REQUESTED},
                    error_code=self._error_code(exc),
                    error_message=str(exc),
                )
                raise InstagramReconciliationRequired(
                    f"Container creation result for {manifest.publication_key} is unknown; exact provider evidence is required"
                ) from exc
            except InstagramTransportError as exc:
                self.ledger.transition(
                    manifest.publication_key,
                    PublicationStatus.CONTAINER_UNKNOWN,
                    expected_statuses={PublicationStatus.CONTAINER_REQUESTED},
                    error_code=self._error_code(exc),
                    error_message=str(exc),
                )
                raise InstagramReconciliationRequired(
                    f"Container creation result for {manifest.publication_key} is unknown; exact provider evidence is required"
                ) from exc

            snapshot = self.ledger.transition(
                manifest.publication_key,
                PublicationStatus.CONTAINER_CREATED,
                expected_statuses={PublicationStatus.CONTAINER_REQUESTED},
                container_id=container_id,
            )

        snapshot = self._wait_for_container(manifest.publication_key, container_id)
        if snapshot.status != PublicationStatus.READY:
            return snapshot

        # CAS is committed before the irreversible publish request. Exactly one
        # process can acquire READY -> PUBLISH_REQUESTED for this container.
        self.ledger.claim_publish_request(manifest.publication_key, container_id)
        try:
            media_id = self.client.publish_container(container_id)
        except InstagramProviderError as exc:
            if exc.status_code is not None and 400 <= exc.status_code < 500:
                self.ledger.transition(
                    manifest.publication_key,
                    PublicationStatus.TERMINAL_FAILURE,
                    expected_statuses={PublicationStatus.PUBLISH_REQUESTED},
                    error_code=self._error_code(exc),
                    error_message=str(exc),
                )
            else:
                self.ledger.transition(
                    manifest.publication_key,
                    PublicationStatus.PUBLISH_UNKNOWN,
                    expected_statuses={PublicationStatus.PUBLISH_REQUESTED},
                    error_code=self._error_code(exc),
                    error_message=str(exc),
                )
            raise
        except InstagramTransportError as exc:
            self.ledger.transition(
                manifest.publication_key,
                PublicationStatus.PUBLISH_UNKNOWN,
                expected_statuses={PublicationStatus.PUBLISH_REQUESTED},
                error_code=self._error_code(exc),
                error_message=str(exc),
            )
            raise InstagramReconciliationRequired(
                f"Publish result for {manifest.publication_key} is unknown; reconcile before retrying"
            ) from exc

        return self.ledger.transition(
            manifest.publication_key,
            PublicationStatus.PUBLISHED,
            expected_statuses={PublicationStatus.PUBLISH_REQUESTED},
            media_id=media_id,
            provider_status="PUBLISHED",
            published=True,
        )

    def reconcile(
        self,
        publication_key: str,
        *,
        published_media_id: str | None = None,
        observed_container_id: str | None = None,
    ) -> PublicationSnapshot:
        snapshot = self.ledger.get(publication_key)
        if snapshot is None:
            raise InstagramProductionError(f"Unknown publication key: {publication_key}")
        if snapshot.account_id != self.config.account_id:
            raise InstagramIdentityMismatchError("Ledger publication belongs to a different Instagram account")
        if snapshot.status == PublicationStatus.PUBLISHED:
            if published_media_id is not None or observed_container_id is not None:
                raise InstagramProductionError("Published publication does not accept reconciliation overrides")
            return snapshot

        if published_media_id is not None:
            normalized = published_media_id.strip()
            if not normalized:
                raise InstagramProductionError("published_media_id must not be empty")
            if snapshot.status not in self._PUBLISH_AMBIGUOUS or snapshot.provider_container_id is None:
                raise InstagramProductionError(
                    "published_media_id is accepted only for an ambiguous publish with an exact known container"
                )
            return self.ledger.transition(
                publication_key,
                PublicationStatus.PUBLISHED,
                expected_statuses={snapshot.status},
                media_id=normalized,
                provider_status="PUBLISHED",
                published=True,
            )

        if observed_container_id is not None:
            normalized_container_id = observed_container_id.strip()
            if not normalized_container_id:
                raise InstagramProductionError("observed_container_id must not be empty")
            if snapshot.status not in self._CONTAINER_AMBIGUOUS or snapshot.provider_container_id is not None:
                raise InstagramProductionError(
                    "observed_container_id is accepted only for ambiguous container creation without a known container"
                )
            snapshot = self.ledger.transition(
                publication_key,
                PublicationStatus.CONTAINER_CREATED,
                expected_statuses={snapshot.status},
                container_id=normalized_container_id,
                error_code="container_id_bound_from_exact_evidence",
                error_message="Exact provider container id bound during reconciliation",
            )

        container_id = snapshot.provider_container_id
        if container_id is None:
            if snapshot.status in self._CONTAINER_AMBIGUOUS:
                raise InstagramReconciliationRequired(
                    f"Container creation result for {publication_key} is ambiguous; supply exact provider container evidence"
                )
            return snapshot

        self.preflight()
        status_code, status_message = self.client.get_container_status(container_id)

        if status_code == "PUBLISHED":
            return self.ledger.transition(
                publication_key,
                PublicationStatus.PUBLISHED_UNRESOLVED,
                expected_statuses={snapshot.status},
                provider_status=status_code,
                error_code="published_media_id_required",
                error_message="Provider confirms publication, but exact media id must be supplied from provider evidence",
            )

        if snapshot.status in self._PUBLISH_AMBIGUOUS:
            # FINISHED is not sufficient evidence that an earlier media_publish
            # had no effect; provider state can lag an in-flight/just-completed
            # mutation. Never reopen READY from an ambiguous publish result.
            return self.ledger.transition(
                publication_key,
                PublicationStatus.PUBLISH_UNKNOWN,
                expected_statuses={snapshot.status},
                provider_status=status_code,
                error_code="publish_effect_unresolved",
                error_message=status_message or f"Publish effect remains unresolved; container reports {status_code}",
            )

        if status_code == "FINISHED":
            return self.ledger.transition(
                publication_key,
                PublicationStatus.READY,
                expected_statuses={snapshot.status},
                provider_status=status_code,
            )
        if status_code == "IN_PROGRESS":
            return self.ledger.transition(
                publication_key,
                PublicationStatus.PROCESSING,
                expected_statuses={snapshot.status},
                provider_status=status_code,
            )
        if status_code in {"ERROR", "EXPIRED"}:
            return self.ledger.transition(
                publication_key,
                PublicationStatus.TERMINAL_FAILURE,
                expected_statuses={snapshot.status},
                provider_status=status_code,
                error_code=status_code.lower(),
                error_message=status_message or f"Instagram container is {status_code}",
            )
        raise InstagramProviderError(f"Unknown Instagram container status: {status_code}")

    def _wait_for_container(self, publication_key: str, container_id: str) -> PublicationSnapshot:
        latest: PublicationSnapshot | None = None
        expected_statuses = {
            PublicationStatus.CONTAINER_CREATED,
            PublicationStatus.PROCESSING,
            PublicationStatus.READY,
        }
        for attempt in range(self.config.poll_attempts):
            status_code, status_message = self.client.get_container_status(container_id)
            if status_code == "FINISHED":
                return self.ledger.transition(
                    publication_key,
                    PublicationStatus.READY,
                    expected_statuses=expected_statuses,
                    provider_status=status_code,
                )
            if status_code == "PUBLISHED":
                self.ledger.transition(
                    publication_key,
                    PublicationStatus.PUBLISHED_UNRESOLVED,
                    expected_statuses=expected_statuses,
                    provider_status=status_code,
                    error_code="published_media_id_required",
                    error_message="Container is already published; exact media id requires reconciliation",
                )
                raise InstagramReconciliationRequired(
                    f"Container for {publication_key} is already published; refusing duplicate publish"
                )
            if status_code in {"ERROR", "EXPIRED"}:
                return self.ledger.transition(
                    publication_key,
                    PublicationStatus.TERMINAL_FAILURE,
                    expected_statuses=expected_statuses,
                    provider_status=status_code,
                    error_code=status_code.lower(),
                    error_message=status_message or f"Instagram container is {status_code}",
                )
            if status_code != "IN_PROGRESS":
                raise InstagramProviderError(f"Unknown Instagram container status: {status_code}")
            latest = self.ledger.transition(
                publication_key,
                PublicationStatus.PROCESSING,
                expected_statuses=expected_statuses,
                provider_status=status_code,
            )
            if attempt + 1 < self.config.poll_attempts:
                self._sleep(self.config.poll_interval_seconds)
        if latest is None:
            raise InstagramProductionError("Instagram poll loop did not execute")
        return latest

    def _assert_manifest_target(self, manifest: InstagramPublishManifest) -> None:
        if manifest.account_id != self.config.account_id:
            raise InstagramIdentityMismatchError(
                f"Manifest account {manifest.account_id!r} does not match configured account {self.config.account_id!r}"
            )

    @staticmethod
    def _error_code(exc: Exception) -> str:
        if isinstance(exc, InstagramProviderError) and exc.error_code is not None:
            return exc.error_code
        return type(exc).__name__
