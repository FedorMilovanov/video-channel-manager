from __future__ import annotations

import hashlib
import ipaddress
import json
import time
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Callable, cast

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

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


class PublicationStatus(StrEnum):
    PLANNED = "planned"
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
    caption: str = Field(default="", max_length=2200)
    share_to_feed: bool = True
    cover_url: HttpUrl | None = None
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
    access_token: str
    writes_enabled: bool
    timeout_seconds: float
    poll_interval_seconds: float
    poll_attempts: int

    @classmethod
    def from_settings(cls, settings: AppSettings) -> InstagramRuntimeConfig:
        missing: list[str] = []
        if settings.instagram_graph_api_version is None:
            missing.append("VCM_INSTAGRAM_GRAPH_API_VERSION")
        if settings.instagram_account_id is None:
            missing.append("VCM_INSTAGRAM_ACCOUNT_ID")
        if settings.instagram_access_token is None:
            missing.append("VCM_INSTAGRAM_ACCESS_TOKEN")
        if missing:
            raise InstagramConfigurationError(f"Missing Instagram provider configuration: {', '.join(missing)}")

        expected_host = (
            "https://graph.instagram.com" if settings.instagram_login_mode == "instagram" else "https://graph.facebook.com"
        )
        if settings.instagram_graph_host != expected_host:
            raise InstagramConfigurationError(
                f"Instagram login mode {settings.instagram_login_mode!r} requires graph host {expected_host!r}"
            )

        return cls(
            login_mode=settings.instagram_login_mode,
            graph_host=settings.instagram_graph_host,
            api_version=cast(str, settings.instagram_graph_api_version),
            account_id=cast(str, settings.instagram_account_id),
            expected_username=settings.instagram_account_username,
            access_token=settings.instagram_access_token.get_secret_value(),
            writes_enabled=settings.instagram_writes_enabled,
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
    publish_requested_at: datetime | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InstagramPublicationLedger:
    """Transactional ledger that makes Instagram write retries crash-safe."""

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
            publish_requested_at=entity.publish_requested_at,
            published_at=entity.published_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def get(self, publication_key: str) -> PublicationSnapshot | None:
        with self.database.session() as session:
            entity = session.get(InstagramPublicationEntity, publication_key)
            return None if entity is None else self._snapshot(entity)

    def ensure_planned(self, manifest: InstagramPublishManifest) -> PublicationSnapshot:
        content_hash = manifest.content_hash()
        with self.database.session() as session:
            entity = session.get(InstagramPublicationEntity, manifest.publication_key)
            if entity is None:
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
            if entity.account_id != manifest.account_id or entity.content_hash != content_hash:
                raise InstagramProductionError(
                    "Publication key is already bound to different canonical content or a different account"
                )
            return self._snapshot(entity)

    def transition(
        self,
        publication_key: str,
        status: PublicationStatus,
        *,
        container_id: str | None = None,
        media_id: str | None = None,
        provider_status: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        increment_attempt: bool = False,
        publish_requested: bool = False,
        published: bool = False,
    ) -> PublicationSnapshot:
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
            if publish_requested:
                entity.publish_requested_at = utc_now()
            if published:
                entity.published_at = utc_now()
            entity.updated_at = utc_now()
            session.flush()
            return self._snapshot(entity)


class InstagramProviderClient:
    """Minimal Meta Graph adapter; canonical content never lives in this layer."""

    def __init__(self, config: InstagramRuntimeConfig, *, client: httpx.Client | None = None) -> None:
        self.config = config
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=config.timeout_seconds)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _request(self, method: str, path: str, *, data: dict[str, object] | None = None, params: dict[str, object] | None = None) -> dict[str, object]:
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
        return self._request("GET", self.config.account_id, params={"fields": "id,username,account_type"})

    def get_publishing_limit(self) -> dict[str, object]:
        return self._request(
            "GET",
            f"{self.config.account_id}/content_publishing_limit",
            params={"fields": "quota_usage,config"},
        )

    def create_reel_container(self, manifest: InstagramPublishManifest) -> str:
        data: dict[str, object] = {
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
        if snapshot.status in {
            PublicationStatus.PUBLISH_REQUESTED,
            PublicationStatus.PUBLISH_UNKNOWN,
            PublicationStatus.PUBLISHED_UNRESOLVED,
        }:
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
                container_id = self.client.create_reel_container(manifest)
            except (InstagramProviderError, InstagramTransportError) as exc:
                self.ledger.transition(
                    manifest.publication_key,
                    PublicationStatus.RETRYABLE_FAILURE,
                    error_code=self._error_code(exc),
                    error_message=str(exc),
                    increment_attempt=True,
                )
                raise
            snapshot = self.ledger.transition(
                manifest.publication_key,
                PublicationStatus.CONTAINER_CREATED,
                container_id=container_id,
                increment_attempt=True,
            )

        snapshot = self._wait_for_container(manifest.publication_key, container_id)
        if snapshot.status != PublicationStatus.READY:
            return snapshot

        # Persist this state before the irreversible publish request. A crash or
        # timeout from this point is intentionally ambiguous and must reconcile.
        self.ledger.transition(
            manifest.publication_key,
            PublicationStatus.PUBLISH_REQUESTED,
            provider_status="FINISHED",
            increment_attempt=True,
            publish_requested=True,
        )
        try:
            media_id = self.client.publish_container(container_id)
        except InstagramProviderError as exc:
            if exc.status_code is not None and 400 <= exc.status_code < 500:
                self.ledger.transition(
                    manifest.publication_key,
                    PublicationStatus.TERMINAL_FAILURE,
                    error_code=self._error_code(exc),
                    error_message=str(exc),
                )
            else:
                self.ledger.transition(
                    manifest.publication_key,
                    PublicationStatus.PUBLISH_UNKNOWN,
                    error_code=self._error_code(exc),
                    error_message=str(exc),
                )
            raise
        except InstagramTransportError as exc:
            self.ledger.transition(
                manifest.publication_key,
                PublicationStatus.PUBLISH_UNKNOWN,
                error_code=self._error_code(exc),
                error_message=str(exc),
            )
            raise InstagramReconciliationRequired(
                f"Publish result for {manifest.publication_key} is unknown; reconcile before retrying"
            ) from exc

        return self.ledger.transition(
            manifest.publication_key,
            PublicationStatus.PUBLISHED,
            media_id=media_id,
            provider_status="PUBLISHED",
            published=True,
        )

    def reconcile(self, publication_key: str, *, published_media_id: str | None = None) -> PublicationSnapshot:
        snapshot = self.ledger.get(publication_key)
        if snapshot is None:
            raise InstagramProductionError(f"Unknown publication key: {publication_key}")
        if snapshot.account_id != self.config.account_id:
            raise InstagramIdentityMismatchError("Ledger publication belongs to a different Instagram account")
        if snapshot.status == PublicationStatus.PUBLISHED:
            return snapshot
        if published_media_id is not None:
            normalized = published_media_id.strip()
            if not normalized:
                raise InstagramProductionError("published_media_id must not be empty")
            return self.ledger.transition(
                publication_key,
                PublicationStatus.PUBLISHED,
                media_id=normalized,
                provider_status="PUBLISHED",
                published=True,
            )
        container_id = snapshot.provider_container_id
        if container_id is None:
            return snapshot

        self.preflight()
        status_code, status_message = self.client.get_container_status(container_id)
        if status_code == "FINISHED":
            return self.ledger.transition(
                publication_key,
                PublicationStatus.READY,
                provider_status=status_code,
            )
        if status_code == "PUBLISHED":
            return self.ledger.transition(
                publication_key,
                PublicationStatus.PUBLISHED_UNRESOLVED,
                provider_status=status_code,
                error_code="published_media_id_required",
                error_message="Provider confirms publication, but exact media id must be supplied from provider evidence",
            )
        if status_code == "IN_PROGRESS":
            return self.ledger.transition(
                publication_key,
                PublicationStatus.PROCESSING,
                provider_status=status_code,
            )
        if status_code in {"ERROR", "EXPIRED"}:
            return self.ledger.transition(
                publication_key,
                PublicationStatus.TERMINAL_FAILURE,
                provider_status=status_code,
                error_code=status_code.lower(),
                error_message=status_message or f"Instagram container is {status_code}",
            )
        raise InstagramProviderError(f"Unknown Instagram container status: {status_code}")

    def _wait_for_container(self, publication_key: str, container_id: str) -> PublicationSnapshot:
        latest: PublicationSnapshot | None = None
        for attempt in range(self.config.poll_attempts):
            status_code, status_message = self.client.get_container_status(container_id)
            if status_code == "FINISHED":
                return self.ledger.transition(
                    publication_key,
                    PublicationStatus.READY,
                    provider_status=status_code,
                )
            if status_code == "PUBLISHED":
                snapshot = self.ledger.transition(
                    publication_key,
                    PublicationStatus.PUBLISHED_UNRESOLVED,
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
                    provider_status=status_code,
                    error_code=status_code.lower(),
                    error_message=status_message or f"Instagram container is {status_code}",
                )
            if status_code != "IN_PROGRESS":
                raise InstagramProviderError(f"Unknown Instagram container status: {status_code}")
            latest = self.ledger.transition(
                publication_key,
                PublicationStatus.PROCESSING,
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
