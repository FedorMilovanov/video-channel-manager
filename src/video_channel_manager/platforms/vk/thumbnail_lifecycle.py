from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from video_channel_manager.editorial._project_profiles import VK_COMMUNITY_ID_TO_PROJECT_KEY
from video_channel_manager.local_media.image_quality import ImageQualityReport, inspect_image
from video_channel_manager.platforms.vk.thumbnails import VkThumbnailWriter
from video_channel_manager.platforms.vk.writer import VkWriteError

THUMBNAIL_EVIDENCE_SCHEMA = "video-manager.vk-thumbnail-evidence"
THUMBNAIL_EVIDENCE_VERSION = "1.0"
THUMBNAIL_RULESET = "wave-8e-v1"


class ThumbnailEvidenceError(RuntimeError):
    """Raised when thumbnail evidence is incomplete, inconsistent, or tampered."""


class ThumbnailPostflightUnverified(ThumbnailEvidenceError):
    """Raised when a thumbnail mutation cannot be proven by exact delayed readback."""

    def __init__(self, message: str, *, record: ThumbnailOperationRecord) -> None:
        super().__init__(message)
        self.record = record


class ThumbnailStatus(StrEnum):
    PREPARED = "prepared"
    SAVED = "saved"
    VERIFIED = "verified"
    UNKNOWN_REQUIRES_RECONCILIATION = "unknown_requires_reconciliation"


@dataclass(frozen=True, slots=True)
class ThumbnailImageDescriptor:
    width: int
    height: int
    canonical_url: str
    digest: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> ThumbnailImageDescriptor | None:
        raw_url = payload.get("url")
        width = payload.get("width")
        height = payload.get("height")
        if not isinstance(raw_url, str) or not raw_url.strip():
            return None
        if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
            return None
        if not isinstance(height, int) or isinstance(height, bool) or height <= 0:
            return None
        canonical_url = canonical_thumbnail_url(raw_url)
        body = {
            "canonical_url": canonical_url,
            "height": height,
            "width": width,
        }
        return cls(
            width=width,
            height=height,
            canonical_url=canonical_url,
            digest=_sha256_json(body),
        )


@dataclass(frozen=True, slots=True)
class SavedThumbnailReceipt:
    owner_id: int
    video_id: int
    photo_owner_id: int
    photo_id: int
    photo_hash: str
    image_descriptors: tuple[ThumbnailImageDescriptor, ...]
    response_digest: str


@dataclass(frozen=True, slots=True)
class ThumbnailReadback:
    owner_id: int
    video_id: int
    image_descriptors: tuple[ThumbnailImageDescriptor, ...]
    response_digest: str
    observed_at: str


@dataclass(frozen=True, slots=True)
class ThumbnailOperationRecord:
    schema_name: str
    schema_version: str
    ruleset: str
    operation_id: str
    project_key: str
    owner_id: int
    video_id: int
    local_thumbnail: dict[str, object]
    status: str
    saved_receipt: dict[str, object] | None
    readback: dict[str, object] | None
    failure: str | None
    created_at: str
    updated_at: str
    evidence_digest: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


JsonMapping = Mapping[str, Any]


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _sha256_json(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_thumbnail_url(value: str) -> str:
    """Remove volatile query/fragment while preserving exact CDN host and path."""

    normalized = value.strip()
    parsed = urlsplit(normalized)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ThumbnailEvidenceError("thumbnail image URL must be absolute http(s)")
    host = parsed.hostname.lower() if parsed.hostname else ""
    port = parsed.port
    if port is not None:
        host = f"{host}:{port}"
    return urlunsplit((parsed.scheme.lower(), host, parsed.path or "/", "", ""))


def image_descriptors(payload: object) -> tuple[ThumbnailImageDescriptor, ...]:
    if not isinstance(payload, list):
        return ()
    values: dict[str, ThumbnailImageDescriptor] = {}
    for raw in payload:
        if not isinstance(raw, Mapping):
            continue
        descriptor = ThumbnailImageDescriptor.from_payload(raw)
        if descriptor is not None:
            values[descriptor.digest] = descriptor
    return tuple(sorted(values.values(), key=lambda item: (item.width, item.height, item.digest)))


def _receipt_from_response(
    *,
    owner_id: int,
    video_id: int,
    response: JsonMapping,
) -> SavedThumbnailReceipt:
    photo_owner_id = response.get("photo_owner_id")
    photo_id = response.get("photo_id")
    photo_hash = response.get("photo_hash")
    if not isinstance(photo_owner_id, int) or isinstance(photo_owner_id, bool) or photo_owner_id != owner_id:
        raise ThumbnailEvidenceError("thumbnail save receipt does not contain the exact expected photo owner")
    if not isinstance(photo_id, int) or isinstance(photo_id, bool) or photo_id <= 0:
        raise ThumbnailEvidenceError("thumbnail save receipt does not contain a positive photo ID")
    if not isinstance(photo_hash, str) or not photo_hash.strip():
        raise ThumbnailEvidenceError("thumbnail save receipt does not contain a photo hash")
    return SavedThumbnailReceipt(
        owner_id=owner_id,
        video_id=video_id,
        photo_owner_id=photo_owner_id,
        photo_id=photo_id,
        photo_hash=photo_hash.strip(),
        image_descriptors=image_descriptors(response.get("image")),
        response_digest=_sha256_json(response),
    )


def _readback_from_response(
    *,
    owner_id: int,
    video_id: int,
    response: JsonMapping,
) -> ThumbnailReadback:
    actual_owner_id = response.get("owner_id")
    actual_video_id = response.get("id")
    if actual_owner_id != owner_id or actual_video_id != video_id:
        raise ThumbnailEvidenceError("thumbnail readback does not identify the exact expected video")
    return ThumbnailReadback(
        owner_id=owner_id,
        video_id=video_id,
        image_descriptors=image_descriptors(response.get("image")),
        response_digest=_sha256_json(response),
        observed_at=_utc_now(),
    )


def _descriptor_digests(values: Iterable[ThumbnailImageDescriptor]) -> tuple[str, ...]:
    return tuple(sorted(item.digest for item in values))


def readback_proves_saved_thumbnail(
    receipt: SavedThumbnailReceipt,
    readback: ThumbnailReadback,
) -> bool:
    """Require exact video identity and a non-empty canonical descriptor-set match."""

    if (receipt.owner_id, receipt.video_id) != (readback.owner_id, readback.video_id):
        return False
    expected = _descriptor_digests(receipt.image_descriptors)
    actual = _descriptor_digests(readback.image_descriptors)
    return bool(expected) and expected == actual


def _local_identity(report: ImageQualityReport) -> dict[str, object]:
    return {
        "format": report.format,
        "height": report.height,
        "path": report.path,
        "sha256": report.sha256,
        "size_bytes": report.size_bytes,
        "width": report.width,
    }


def _operation_id(
    *,
    project_key: str,
    owner_id: int,
    video_id: int,
    local_thumbnail: Mapping[str, object],
) -> str:
    return _sha256_json(
        {
            "local_sha256": local_thumbnail["sha256"],
            "owner_id": owner_id,
            "project_key": project_key,
            "video_id": video_id,
        }
    )


def _record_payload(record: ThumbnailOperationRecord) -> dict[str, object]:
    payload = record.to_dict()
    payload.pop("evidence_digest", None)
    return payload


def _seal(record: ThumbnailOperationRecord) -> ThumbnailOperationRecord:
    return replace(record, evidence_digest=_sha256_json(_record_payload(record)))


def _new_record(
    *,
    project_key: str,
    owner_id: int,
    video_id: int,
    local_thumbnail: Mapping[str, object],
) -> ThumbnailOperationRecord:
    now = _utc_now()
    return _seal(
        ThumbnailOperationRecord(
            schema_name=THUMBNAIL_EVIDENCE_SCHEMA,
            schema_version=THUMBNAIL_EVIDENCE_VERSION,
            ruleset=THUMBNAIL_RULESET,
            operation_id=_operation_id(
                project_key=project_key,
                owner_id=owner_id,
                video_id=video_id,
                local_thumbnail=local_thumbnail,
            ),
            project_key=project_key,
            owner_id=owner_id,
            video_id=video_id,
            local_thumbnail=dict(local_thumbnail),
            status=ThumbnailStatus.PREPARED.value,
            saved_receipt=None,
            readback=None,
            failure=None,
            created_at=now,
            updated_at=now,
            evidence_digest="",
        )
    )


def _transition(
    record: ThumbnailOperationRecord,
    *,
    status: ThumbnailStatus,
    receipt: SavedThumbnailReceipt | None = None,
    readback: ThumbnailReadback | None = None,
    failure: str | None = None,
) -> ThumbnailOperationRecord:
    return _seal(
        replace(
            record,
            status=status.value,
            saved_receipt=asdict(receipt) if receipt is not None else record.saved_receipt,
            readback=asdict(readback) if readback is not None else record.readback,
            failure=failure,
            updated_at=_utc_now(),
            evidence_digest="",
        )
    )


def write_thumbnail_record(path: Path, record: ThumbnailOperationRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(record.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _record_from_payload(payload: JsonMapping) -> ThumbnailOperationRecord:
    try:
        record = ThumbnailOperationRecord(
            schema_name=str(payload["schema_name"]),
            schema_version=str(payload["schema_version"]),
            ruleset=str(payload["ruleset"]),
            operation_id=str(payload["operation_id"]),
            project_key=str(payload["project_key"]),
            owner_id=int(payload["owner_id"]),
            video_id=int(payload["video_id"]),
            local_thumbnail=dict(payload["local_thumbnail"]),
            status=str(payload["status"]),
            saved_receipt=dict(payload["saved_receipt"]) if isinstance(payload.get("saved_receipt"), Mapping) else None,
            readback=dict(payload["readback"]) if isinstance(payload.get("readback"), Mapping) else None,
            failure=str(payload["failure"]) if payload.get("failure") is not None else None,
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            evidence_digest=str(payload["evidence_digest"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ThumbnailEvidenceError("thumbnail evidence record is malformed") from exc
    if record.schema_name != THUMBNAIL_EVIDENCE_SCHEMA or record.schema_version != THUMBNAIL_EVIDENCE_VERSION:
        raise ThumbnailEvidenceError("thumbnail evidence record has an unsupported schema")
    if record.ruleset != THUMBNAIL_RULESET:
        raise ThumbnailEvidenceError("thumbnail evidence record has an unsupported ruleset")
    if record.status not in {item.value for item in ThumbnailStatus}:
        raise ThumbnailEvidenceError("thumbnail evidence record has an unknown status")
    if record.evidence_digest != _sha256_json(_record_payload(record)):
        raise ThumbnailEvidenceError("thumbnail evidence digest does not match the record")
    return record


def read_thumbnail_record(path: Path) -> ThumbnailOperationRecord:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ThumbnailEvidenceError(f"cannot read thumbnail evidence record: {path}") from exc
    if not isinstance(payload, Mapping):
        raise ThumbnailEvidenceError("thumbnail evidence record must be a JSON object")
    return _record_from_payload(payload)


def _receipt_from_record(record: ThumbnailOperationRecord) -> SavedThumbnailReceipt | None:
    payload = record.saved_receipt
    if payload is None:
        return None
    raw_descriptors = payload.get("image_descriptors")
    descriptors: list[ThumbnailImageDescriptor] = []
    if isinstance(raw_descriptors, list):
        for raw in raw_descriptors:
            if not isinstance(raw, Mapping):
                continue
            try:
                descriptors.append(
                    ThumbnailImageDescriptor(
                        width=int(raw["width"]),
                        height=int(raw["height"]),
                        canonical_url=str(raw["canonical_url"]),
                        digest=str(raw["digest"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ThumbnailEvidenceError("saved thumbnail receipt is malformed") from exc
    try:
        return SavedThumbnailReceipt(
            owner_id=int(payload["owner_id"]),
            video_id=int(payload["video_id"]),
            photo_owner_id=int(payload["photo_owner_id"]),
            photo_id=int(payload["photo_id"]),
            photo_hash=str(payload["photo_hash"]),
            image_descriptors=tuple(descriptors),
            response_digest=str(payload["response_digest"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ThumbnailEvidenceError("saved thumbnail receipt is malformed") from exc


def _validate_scope(*, project_key: str, owner_id: int, video_id: int) -> None:
    if owner_id >= 0:
        raise ThumbnailEvidenceError("VK community video owner_id must be negative")
    if video_id <= 0:
        raise ThumbnailEvidenceError("video_id must be positive")
    expected_project = VK_COMMUNITY_ID_TO_PROJECT_KEY.get(-owner_id)
    if expected_project is None or expected_project != project_key:
        raise ThumbnailEvidenceError("project key and VK community owner do not identify the same registered project")


def _validate_existing_record(
    record: ThumbnailOperationRecord,
    *,
    project_key: str,
    owner_id: int,
    video_id: int,
    local_thumbnail: Mapping[str, object],
) -> None:
    expected_operation_id = _operation_id(
        project_key=project_key,
        owner_id=owner_id,
        video_id=video_id,
        local_thumbnail=local_thumbnail,
    )
    if record.operation_id != expected_operation_id:
        raise ThumbnailEvidenceError("existing thumbnail journal belongs to a different operation")
    if record.project_key != project_key or record.owner_id != owner_id or record.video_id != video_id:
        raise ThumbnailEvidenceError("existing thumbnail journal has conflicting project or video identity")
    if record.local_thumbnail != dict(local_thumbnail):
        raise ThumbnailEvidenceError("existing thumbnail journal has conflicting local image identity")


def _reconcile_saved_thumbnail(
    *,
    writer: VkThumbnailWriter,
    record: ThumbnailOperationRecord,
    receipt: SavedThumbnailReceipt,
    journal_path: Path,
    postflight_delays: tuple[float, ...],
    sleep: Callable[[float], None],
) -> ThumbnailOperationRecord:
    latest_readback: ThumbnailReadback | None = None
    if not receipt.image_descriptors:
        unknown = _transition(
            record,
            status=ThumbnailStatus.UNKNOWN_REQUIRES_RECONCILIATION,
            failure="save receipt has no image descriptors that can be compared with video.get readback",
        )
        write_thumbnail_record(journal_path, unknown)
        raise ThumbnailPostflightUnverified(unknown.failure or "thumbnail postflight is unverified", record=unknown)

    for delay in postflight_delays:
        if delay < 0:
            raise ValueError("postflight delays cannot be negative")
        if delay:
            sleep(delay)
        payload = writer.get_video_thumbnail_state(owner_id=record.owner_id, video_id=record.video_id)
        latest_readback = _readback_from_response(
            owner_id=record.owner_id,
            video_id=record.video_id,
            response=payload,
        )
        if readback_proves_saved_thumbnail(receipt, latest_readback):
            verified = _transition(
                record,
                status=ThumbnailStatus.VERIFIED,
                receipt=receipt,
                readback=latest_readback,
                failure=None,
            )
            write_thumbnail_record(journal_path, verified)
            return verified

    unknown = _transition(
        record,
        status=ThumbnailStatus.UNKNOWN_REQUIRES_RECONCILIATION,
        receipt=receipt,
        readback=latest_readback,
        failure="delayed video.get readback did not prove the saved thumbnail descriptor set",
    )
    write_thumbnail_record(journal_path, unknown)
    raise ThumbnailPostflightUnverified(unknown.failure or "thumbnail postflight is unverified", record=unknown)


def execute_thumbnail_operation(
    *,
    writer: VkThumbnailWriter,
    project_key: str,
    owner_id: int,
    video_id: int,
    image_path: Path,
    journal_path: Path,
    postflight_delays: tuple[float, ...] = (0.0, 0.5, 2.0),
    sleep: Callable[[float], None] = time.sleep,
) -> ThumbnailOperationRecord:
    """Execute or reconcile one exact VK thumbnail operation without blind replay."""

    _validate_scope(project_key=project_key, owner_id=owner_id, video_id=video_id)
    report = inspect_image(image_path)
    local_thumbnail = _local_identity(report)

    if journal_path.exists():
        record = read_thumbnail_record(journal_path)
        _validate_existing_record(
            record,
            project_key=project_key,
            owner_id=owner_id,
            video_id=video_id,
            local_thumbnail=local_thumbnail,
        )
        if record.status == ThumbnailStatus.VERIFIED.value:
            return record
        receipt = _receipt_from_record(record)
        if record.status in {
            ThumbnailStatus.SAVED.value,
            ThumbnailStatus.UNKNOWN_REQUIRES_RECONCILIATION.value,
        }:
            if receipt is None:
                raise ThumbnailPostflightUnverified(
                    "thumbnail mutation outcome is unknown and no exact save receipt is available",
                    record=record,
                )
            return _reconcile_saved_thumbnail(
                writer=writer,
                record=record,
                receipt=receipt,
                journal_path=journal_path,
                postflight_delays=postflight_delays,
                sleep=sleep,
            )
    else:
        record = _new_record(
            project_key=project_key,
            owner_id=owner_id,
            video_id=video_id,
            local_thumbnail=local_thumbnail,
        )
        write_thumbnail_record(journal_path, record)

    try:
        upload_url = writer.get_upload_url(owner_id=owner_id)
        upload_payload = writer.upload_image(upload_url=upload_url, path=image_path)
        save_response = writer.save_uploaded_thumbnail(
            owner_id=owner_id,
            video_id=video_id,
            upload_payload=upload_payload,
        )
        receipt = _receipt_from_response(
            owner_id=owner_id,
            video_id=video_id,
            response=save_response,
        )
    except (VkWriteError, ThumbnailEvidenceError) as exc:
        method = exc.method if isinstance(exc, VkWriteError) else "video.saveUploadedThumb"
        if method in {"video.thumbUpload", "video.saveUploadedThumb"}:
            unknown = _transition(
                record,
                status=ThumbnailStatus.UNKNOWN_REQUIRES_RECONCILIATION,
                failure=f"{method} did not produce a fully verifiable outcome: {exc}",
            )
            write_thumbnail_record(journal_path, unknown)
            raise ThumbnailPostflightUnverified(unknown.failure or str(exc), record=unknown) from exc
        raise

    saved = _transition(
        record,
        status=ThumbnailStatus.SAVED,
        receipt=receipt,
        failure=None,
    )
    write_thumbnail_record(journal_path, saved)
    return _reconcile_saved_thumbnail(
        writer=writer,
        record=saved,
        receipt=receipt,
        journal_path=journal_path,
        postflight_delays=postflight_delays,
        sleep=sleep,
    )


__all__ = [
    "THUMBNAIL_EVIDENCE_SCHEMA",
    "THUMBNAIL_EVIDENCE_VERSION",
    "THUMBNAIL_RULESET",
    "SavedThumbnailReceipt",
    "ThumbnailEvidenceError",
    "ThumbnailImageDescriptor",
    "ThumbnailOperationRecord",
    "ThumbnailPostflightUnverified",
    "ThumbnailReadback",
    "ThumbnailStatus",
    "canonical_thumbnail_url",
    "execute_thumbnail_operation",
    "image_descriptors",
    "read_thumbnail_record",
    "readback_proves_saved_thumbnail",
    "write_thumbnail_record",
]
