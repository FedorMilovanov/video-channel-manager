from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO, Literal, cast
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, update
from sqlalchemy.orm import Mapped, mapped_column

from video_channel_manager.instagram.production import (
    InstagramConfigurationError,
    InstagramIdentityMismatchError,
    InstagramMediaVerificationError,
    InstagramProductionError,
    InstagramProductionService,
    InstagramProviderClient,
    InstagramProviderError,
    InstagramPublicationLedger,
    InstagramPublishManifest,
    InstagramReconciliationRequired,
    InstagramRuntimeConfig,
    InstagramTransportError,
    PublicationSnapshot,
    PublicationStatus,
)
from video_channel_manager.persistence.database import Database
from video_channel_manager.persistence.models import Base, utc_now


class InstagramLocalPublishManifest(BaseModel):
    """Immutable provider-bound identity for a local-file resumable Reel publication."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1", pattern=r"^1$")
    transport: Literal["resumable_local"] = "resumable_local"
    publication_key: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    account_id: str = Field(min_length=1, max_length=255)
    media_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    media_size_bytes: int = Field(gt=0)
    media_content_type: Literal["video/mp4"] = "video/mp4"
    caption: str = Field(default="", max_length=2200)
    share_to_feed: bool = True
    thumb_offset_ms: int | None = Field(default=None, ge=0)

    def content_hash(self) -> str:
        payload = self.model_dump(mode="json")
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def inspect_local_reel(path: Path) -> tuple[str, int]:
    """Return exact local MP4 identity without retaining the filesystem path in publication identity."""

    candidate = path.expanduser()
    if candidate.suffix.lower() != ".mp4":
        raise InstagramMediaVerificationError(
            "Instagram local resumable upload currently accepts .mp4 files only",
            error_code="local_video_extension_unsupported",
            retryable=False,
        )
    try:
        if not candidate.is_file():
            raise InstagramMediaVerificationError(
                f"Instagram local video is not a readable file: {candidate}",
                error_code="local_video_missing",
                retryable=True,
            )
        digest = hashlib.sha256()
        size = 0
        with candidate.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                digest.update(chunk)
    except InstagramMediaVerificationError:
        raise
    except OSError as exc:
        raise InstagramMediaVerificationError(
            f"Instagram local video cannot be read: {candidate}",
            error_code="local_video_read_failed",
            retryable=True,
        ) from exc
    if size <= 0:
        raise InstagramMediaVerificationError(
            "Instagram local video is empty",
            error_code="local_video_empty",
            retryable=False,
        )
    return f"sha256:{digest.hexdigest()}", size


def build_local_publish_manifest(
    path: Path,
    *,
    publication_key: str,
    account_id: str,
    caption: str = "",
    share_to_feed: bool = True,
    thumb_offset_ms: int | None = None,
) -> InstagramLocalPublishManifest:
    media_sha256, media_size_bytes = inspect_local_reel(path)
    return InstagramLocalPublishManifest(
        publication_key=publication_key,
        account_id=account_id,
        media_sha256=media_sha256,
        media_size_bytes=media_size_bytes,
        caption=caption,
        share_to_feed=share_to_feed,
        thumb_offset_ms=thumb_offset_ms,
    )


class ResumableUploadState(StrEnum):
    CONTAINER_RETURNED = "container_returned"
    UPLOAD_REQUESTED = "upload_requested"
    UPLOAD_UNKNOWN = "upload_unknown"
    UPLOADED = "uploaded"
    PROVIDER_OBSERVED = "provider_observed"


class InstagramResumableUploadEntity(Base):
    """Durable child-operation ledger for the binary resumable-upload step."""

    __tablename__ = "instagram_resumable_uploads"

    publication_key: Mapped[str] = mapped_column(
        ForeignKey("instagram_publications.publication_key", ondelete="CASCADE"), primary_key=True
    )
    provider_container_id: Mapped[str] = mapped_column(String(255), nullable=False)
    upload_uri: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(200))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    upload_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


@dataclass(frozen=True)
class ResumableUploadSnapshot:
    publication_key: str
    provider_container_id: str
    upload_uri: str
    state: ResumableUploadState
    attempt_count: int
    last_error_code: str | None
    last_error_message: str | None
    upload_requested_at: datetime | None
    uploaded_at: datetime | None


class InstagramResumableUploadLedger:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _snapshot(entity: InstagramResumableUploadEntity) -> ResumableUploadSnapshot:
        return ResumableUploadSnapshot(
            publication_key=entity.publication_key,
            provider_container_id=entity.provider_container_id,
            upload_uri=entity.upload_uri,
            state=ResumableUploadState(entity.state),
            attempt_count=entity.attempt_count,
            last_error_code=entity.last_error_code,
            last_error_message=entity.last_error_message,
            upload_requested_at=entity.upload_requested_at,
            uploaded_at=entity.uploaded_at,
        )

    def get(self, publication_key: str) -> ResumableUploadSnapshot | None:
        with self.database.session() as session:
            entity = session.get(InstagramResumableUploadEntity, publication_key)
            return None if entity is None else self._snapshot(entity)

    def bind_container_response(
        self,
        publication_key: str,
        *,
        provider_container_id: str,
        upload_uri: str,
    ) -> ResumableUploadSnapshot:
        with self.database.session() as session:
            entity = session.get(InstagramResumableUploadEntity, publication_key)
            if entity is not None:
                if entity.provider_container_id != provider_container_id or entity.upload_uri != upload_uri:
                    raise InstagramReconciliationRequired(
                        "Resumable container response conflicts with durable exact provider evidence"
                    )
                return self._snapshot(entity)
            entity = InstagramResumableUploadEntity(
                publication_key=publication_key,
                provider_container_id=provider_container_id,
                upload_uri=upload_uri,
                state=ResumableUploadState.CONTAINER_RETURNED.value,
            )
            session.add(entity)
            session.flush()
            return self._snapshot(entity)

    def claim_upload(self, publication_key: str, provider_container_id: str) -> ResumableUploadSnapshot:
        now = utc_now()
        with self.database.session() as session:
            statement = (
                update(InstagramResumableUploadEntity)
                .where(
                    InstagramResumableUploadEntity.publication_key == publication_key,
                    InstagramResumableUploadEntity.provider_container_id == provider_container_id,
                    InstagramResumableUploadEntity.state == ResumableUploadState.CONTAINER_RETURNED.value,
                )
                .values(
                    state=ResumableUploadState.UPLOAD_REQUESTED.value,
                    attempt_count=InstagramResumableUploadEntity.attempt_count + 1,
                    upload_requested_at=now,
                    last_error_code=None,
                    last_error_message=None,
                    updated_at=now,
                )
                .returning(InstagramResumableUploadEntity.publication_key)
            )
            changed = session.execute(statement).scalar_one_or_none()
            if changed is None:
                entity = session.get(InstagramResumableUploadEntity, publication_key)
                state = entity.state if entity is not None else "missing"
                raise InstagramReconciliationRequired(
                    f"Resumable upload claim refused for {publication_key}: child state is {state}"
                )
            entity = session.get(InstagramResumableUploadEntity, publication_key)
            if entity is None:
                raise InstagramProductionError("Resumable upload claim committed but cannot be re-read")
            session.refresh(entity)
            return self._snapshot(entity)

    def mark_uploaded(self, publication_key: str) -> ResumableUploadSnapshot:
        return self._transition(
            publication_key,
            ResumableUploadState.UPLOADED,
            expected={ResumableUploadState.UPLOAD_REQUESTED},
            uploaded=True,
        )

    def mark_unknown(self, publication_key: str, exc: Exception) -> ResumableUploadSnapshot:
        return self._transition(
            publication_key,
            ResumableUploadState.UPLOAD_UNKNOWN,
            expected={ResumableUploadState.UPLOAD_REQUESTED},
            error_code=type(exc).__name__,
            error_message=str(exc),
        )

    def mark_provider_observed(self, publication_key: str) -> ResumableUploadSnapshot:
        current = self.get(publication_key)
        if current is None:
            raise InstagramProductionError(f"Missing resumable upload child for {publication_key}")
        if current.state == ResumableUploadState.PROVIDER_OBSERVED:
            return current
        return self._transition(
            publication_key,
            ResumableUploadState.PROVIDER_OBSERVED,
            expected={
                ResumableUploadState.UPLOAD_REQUESTED,
                ResumableUploadState.UPLOAD_UNKNOWN,
                ResumableUploadState.UPLOADED,
            },
        )

    def _transition(
        self,
        publication_key: str,
        state: ResumableUploadState,
        *,
        expected: set[ResumableUploadState],
        error_code: str | None = None,
        error_message: str | None = None,
        uploaded: bool = False,
    ) -> ResumableUploadSnapshot:
        now = utc_now()
        values: dict[str, object] = {
            "state": state.value,
            "last_error_code": error_code,
            "last_error_message": error_message,
            "updated_at": now,
        }
        if uploaded:
            values["uploaded_at"] = now
        with self.database.session() as session:
            statement = (
                update(InstagramResumableUploadEntity)
                .where(
                    InstagramResumableUploadEntity.publication_key == publication_key,
                    InstagramResumableUploadEntity.state.in_([item.value for item in expected]),
                )
                .values(values)
                .returning(InstagramResumableUploadEntity.publication_key)
            )
            changed = session.execute(statement).scalar_one_or_none()
            if changed is None:
                entity = session.get(InstagramResumableUploadEntity, publication_key)
                current_state = entity.state if entity is not None else "missing"
                raise InstagramReconciliationRequired(
                    f"Resumable upload transition refused for {publication_key}: child state is {current_state}"
                )
            entity = session.get(InstagramResumableUploadEntity, publication_key)
            if entity is None:
                raise InstagramProductionError("Resumable upload transition committed but cannot be re-read")
            session.refresh(entity)
            return self._snapshot(entity)


def _validated_upload_uri(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme.lower() != "https" or (parts.hostname or "").lower() != "rupload.facebook.com":
        raise InstagramProviderError("Instagram resumable upload URI is outside the exact rupload.facebook.com boundary")
    if parts.username is not None or parts.password is not None or parts.fragment:
        raise InstagramProviderError("Instagram resumable upload URI contains forbidden authority/fragment data")
    if not parts.path or parts.path == "/":
        raise InstagramProviderError("Instagram resumable upload URI has no provider path")
    return value


class InstagramResumableProviderClient(InstagramProviderClient):
    """Facebook Login resumable-upload transport, isolated from the public-URL transport."""

    def _require_supported_mode(self) -> None:
        if self.config.login_mode != "facebook" or self.config.graph_host != "https://graph.facebook.com":
            raise InstagramConfigurationError(
                "Local resumable upload is enabled only for the reviewed Facebook Login / graph.facebook.com mode"
            )

    def create_resumable_reel_container(self, manifest: InstagramLocalPublishManifest) -> tuple[str, str]:
        self._require_supported_mode()
        data: dict[str, str | int] = {
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": manifest.caption,
            "share_to_feed": "true" if manifest.share_to_feed else "false",
        }
        if manifest.thumb_offset_ms is not None:
            data["thumb_offset"] = manifest.thumb_offset_ms
        payload = self._request("POST", f"{self.config.account_id}/media", data=data)
        container_id = payload.get("id")
        upload_uri = payload.get("uri")
        if not isinstance(container_id, str) or not container_id:
            raise InstagramProviderError("Instagram resumable container response did not include an id")
        if not isinstance(upload_uri, str) or not upload_uri:
            raise InstagramProviderError("Instagram resumable container response did not include an upload URI")
        return container_id, _validated_upload_uri(upload_uri)

    def upload_local_video(self, upload_uri: str, stream: BinaryIO, *, file_size: int) -> None:
        self._require_supported_mode()
        target = _validated_upload_uri(upload_uri)

        def chunks() -> Iterator[bytes]:
            while chunk := stream.read(1024 * 1024):
                yield chunk

        try:
            response = self._client.post(
                target,
                headers={
                    "Authorization": f"OAuth {self.config.access_token}",
                    "offset": "0",
                    "file_size": str(file_size),
                    "Content-Length": str(file_size),
                },
                content=chunks(),
            )
        except (httpx.RequestError, OSError) as exc:
            raise InstagramTransportError("Instagram resumable binary upload transport failure") from exc

        payload: object
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if response.is_error:
            error_code: str | None = None
            message = f"Instagram resumable upload returned HTTP {response.status_code}"
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
        if isinstance(payload, dict) and payload.get("success") is False:
            raise InstagramProviderError("Instagram resumable upload response reported success=false")


class InstagramLocalResumableService(InstagramProductionService):
    """Durable local-MP4 -> resumable upload -> process -> publish orchestration."""

    def __init__(
        self,
        config: InstagramRuntimeConfig,
        ledger: InstagramPublicationLedger,
        upload_ledger: InstagramResumableUploadLedger,
        *,
        client: InstagramResumableProviderClient | None = None,
    ) -> None:
        owns_client = client is None
        resumable_client = client or InstagramResumableProviderClient(config)
        super().__init__(config, ledger, client=resumable_client)
        self._owns_client = owns_client
        self.resumable_client = resumable_client
        self.upload_ledger = upload_ledger

    @contextmanager
    def _verified_local_stream(
        self,
        path: Path,
        manifest: InstagramLocalPublishManifest,
    ) -> Iterator[BinaryIO]:
        candidate = path.expanduser()
        if candidate.suffix.lower() != ".mp4":
            raise InstagramMediaVerificationError(
                "Instagram local resumable upload currently accepts .mp4 files only",
                error_code="local_video_extension_unsupported",
                retryable=False,
            )
        try:
            stream = candidate.open("rb")
        except OSError as exc:
            raise InstagramMediaVerificationError(
                f"Instagram local video cannot be opened: {candidate}",
                error_code="local_video_open_failed",
                retryable=True,
            ) from exc
        try:
            digest = hashlib.sha256()
            size = 0
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                digest.update(chunk)
            observed_sha256 = f"sha256:{digest.hexdigest()}"
            if size != manifest.media_size_bytes:
                raise InstagramMediaVerificationError(
                    f"Instagram local video size mismatch: expected {manifest.media_size_bytes}, got {size}",
                    error_code="local_video_size_mismatch",
                    retryable=False,
                )
            if observed_sha256 != manifest.media_sha256:
                raise InstagramMediaVerificationError(
                    "Instagram local video SHA-256 mismatch",
                    error_code="local_video_sha256_mismatch",
                    retryable=False,
                )
            stream.seek(0)
            yield stream
        except OSError as exc:
            raise InstagramMediaVerificationError(
                f"Instagram local video cannot be read: {candidate}",
                error_code="local_video_read_failed",
                retryable=True,
            ) from exc
        finally:
            stream.close()

    def _assert_local_target(self, manifest: InstagramLocalPublishManifest) -> None:
        if manifest.account_id != self.config.account_id:
            raise InstagramIdentityMismatchError(
                f"Manifest account {manifest.account_id!r} does not match configured account {self.config.account_id!r}"
            )

    def _recover_persisted_container_response(
        self,
        snapshot: PublicationSnapshot,
        child: ResumableUploadSnapshot | None,
    ) -> PublicationSnapshot:
        if snapshot.status not in {PublicationStatus.CONTAINER_REQUESTED, PublicationStatus.CONTAINER_UNKNOWN}:
            return snapshot
        if snapshot.provider_container_id is not None or child is None:
            return snapshot
        return self.ledger.transition(
            snapshot.publication_key,
            PublicationStatus.CONTAINER_CREATED,
            expected_statuses={snapshot.status},
            container_id=child.provider_container_id,
            error_code="resumable_container_response_recovered",
            error_message="Recovered exact resumable container response from durable child ledger",
        )

    def publish_local(
        self,
        manifest: InstagramLocalPublishManifest,
        video_path: Path,
        *,
        execute: bool,
    ) -> PublicationSnapshot:
        self._assert_local_target(manifest)
        self.resumable_client._require_supported_mode()
        self.config.require_write_gate(execute=execute)
        self.preflight()

        with self._verified_local_stream(video_path, manifest):
            snapshot = self.ledger.ensure_planned(cast(InstagramPublishManifest, manifest))

        child = self.upload_ledger.get(manifest.publication_key)
        snapshot = self._recover_persisted_container_response(snapshot, child)
        child = self.upload_ledger.get(manifest.publication_key)

        if snapshot.status == PublicationStatus.PUBLISHED:
            return snapshot
        if snapshot.status in self._PUBLISH_AMBIGUOUS:
            raise InstagramReconciliationRequired(
                f"Publication {manifest.publication_key} is {snapshot.status.value}; reconcile before any further write"
            )
        if snapshot.status in self._CONTAINER_AMBIGUOUS:
            raise InstagramReconciliationRequired(
                f"Publication {manifest.publication_key} has an ambiguous container effect; reconcile before retrying"
            )
        if snapshot.status == PublicationStatus.TERMINAL_FAILURE:
            raise InstagramProductionError(
                f"Publication {manifest.publication_key} is terminally failed; use a corrected publication key"
            )

        container_id = snapshot.provider_container_id
        if container_id is None:
            self.ledger.claim_container_request(manifest.publication_key)
            try:
                container_id, upload_uri = self.resumable_client.create_resumable_reel_container(manifest)
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
                    f"Resumable container creation result for {manifest.publication_key} is unknown"
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
                    f"Resumable container creation result for {manifest.publication_key} is unknown"
                ) from exc

            child = self.upload_ledger.bind_container_response(
                manifest.publication_key,
                provider_container_id=container_id,
                upload_uri=upload_uri,
            )
            snapshot = self.ledger.transition(
                manifest.publication_key,
                PublicationStatus.CONTAINER_CREATED,
                expected_statuses={PublicationStatus.CONTAINER_REQUESTED},
                container_id=container_id,
            )

        if child is None:
            child = self.upload_ledger.get(manifest.publication_key)
        if child is None:
            raise InstagramReconciliationRequired(
                f"Publication {manifest.publication_key} has a resumable container but no durable upload URI evidence"
            )
        if child.provider_container_id != container_id:
            raise InstagramReconciliationRequired("Resumable child container does not match the publication ledger")

        if snapshot.status in {PublicationStatus.PROCESSING, PublicationStatus.READY} and child.state in {
            ResumableUploadState.UPLOAD_REQUESTED,
            ResumableUploadState.UPLOAD_UNKNOWN,
            ResumableUploadState.UPLOADED,
        }:
            child = self.upload_ledger.mark_provider_observed(manifest.publication_key)

        if snapshot.status == PublicationStatus.CONTAINER_CREATED:
            if child.state in {ResumableUploadState.UPLOAD_REQUESTED, ResumableUploadState.UPLOAD_UNKNOWN}:
                raise InstagramReconciliationRequired(
                    f"Binary upload effect for {manifest.publication_key} is ambiguous; run read-only reconcile first"
                )
            if child.state == ResumableUploadState.CONTAINER_RETURNED:
                with self._verified_local_stream(video_path, manifest) as stream:
                    self.upload_ledger.claim_upload(manifest.publication_key, container_id)
                    try:
                        self.resumable_client.upload_local_video(
                            child.upload_uri,
                            stream,
                            file_size=manifest.media_size_bytes,
                        )
                    except (InstagramProviderError, InstagramTransportError) as exc:
                        self.upload_ledger.mark_unknown(manifest.publication_key, exc)
                        raise InstagramReconciliationRequired(
                            f"Binary upload result for {manifest.publication_key} is unknown; refusing blind replay"
                        ) from exc
                child = self.upload_ledger.mark_uploaded(manifest.publication_key)
            if child.state == ResumableUploadState.UPLOADED:
                snapshot = self.ledger.transition(
                    manifest.publication_key,
                    PublicationStatus.PROCESSING,
                    expected_statuses={PublicationStatus.CONTAINER_CREATED},
                    provider_status="UPLOAD_ACCEPTED",
                )

        if snapshot.status == PublicationStatus.PROCESSING:
            snapshot = self._wait_for_container(manifest.publication_key, container_id)
        if snapshot.status != PublicationStatus.READY:
            return snapshot

        self.ledger.claim_publish_request(manifest.publication_key, container_id)
        try:
            media_id = self.resumable_client.publish_container(container_id)
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
