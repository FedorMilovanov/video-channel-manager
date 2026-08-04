from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, cast

from video_channel_manager.platforms.vk.wall_safety import (
    DEFAULT_UPLOAD_WALL_POLICY,
    VkWallDeltaStatus,
    VkUploadWallPolicy,
    VkWallSnapshot,
    compare_wall_snapshots,
)


class UploadStage(StrEnum):
    PLANNED = "planned"
    MEDIA_VERIFIED = "media_verified"
    RESERVATION_INTENT_COMMITTED = "reservation_intent_committed"
    RESERVED = "reserved"
    UPLOAD_STARTED = "upload_started"
    UPLOAD_RESPONSE_RECEIVED = "upload_response_received"
    PROCESSING = "processing"
    VERIFIED = "verified"
    REJECTED = "rejected"
    UNKNOWN_REQUIRES_RECONCILIATION = "unknown_requires_reconciliation"


_ALLOWED_TRANSITIONS: Mapping[UploadStage, frozenset[UploadStage]] = {
    UploadStage.PLANNED: frozenset({UploadStage.MEDIA_VERIFIED, UploadStage.REJECTED}),
    UploadStage.MEDIA_VERIFIED: frozenset({UploadStage.RESERVATION_INTENT_COMMITTED, UploadStage.REJECTED}),
    UploadStage.RESERVATION_INTENT_COMMITTED: frozenset(
        {
            UploadStage.RESERVED,
            UploadStage.REJECTED,
            UploadStage.UNKNOWN_REQUIRES_RECONCILIATION,
        }
    ),
    UploadStage.RESERVED: frozenset(
        {
            UploadStage.UPLOAD_STARTED,
            UploadStage.REJECTED,
            UploadStage.UNKNOWN_REQUIRES_RECONCILIATION,
        }
    ),
    UploadStage.UPLOAD_STARTED: frozenset(
        {
            UploadStage.UPLOAD_RESPONSE_RECEIVED,
            UploadStage.PROCESSING,
            UploadStage.VERIFIED,
            UploadStage.UNKNOWN_REQUIRES_RECONCILIATION,
        }
    ),
    UploadStage.UPLOAD_RESPONSE_RECEIVED: frozenset(
        {
            UploadStage.PROCESSING,
            UploadStage.VERIFIED,
            UploadStage.UNKNOWN_REQUIRES_RECONCILIATION,
        }
    ),
    UploadStage.PROCESSING: frozenset({UploadStage.VERIFIED, UploadStage.UNKNOWN_REQUIRES_RECONCILIATION}),
    UploadStage.UNKNOWN_REQUIRES_RECONCILIATION: frozenset({UploadStage.PROCESSING, UploadStage.VERIFIED}),
    UploadStage.VERIFIED: frozenset(),
    UploadStage.REJECTED: frozenset(),
}


class UploadRecoveryRequired(RuntimeError):
    """The operation cannot safely continue without exact reconciliation."""


class UploadRejected(RuntimeError):
    """The provider or local validation rejected the operation before an ambiguous write."""


@dataclass(frozen=True, slots=True)
class VkUploadReadiness:
    expected_title: str
    minimum_duration_seconds: int
    allowed_types: tuple[str, ...] = ("video",)
    require_playable: bool = True

    def __post_init__(self) -> None:
        if not self.expected_title.strip():
            raise ValueError("expected_title cannot be blank")
        if self.minimum_duration_seconds <= 0:
            raise ValueError("minimum_duration_seconds must be positive")
        normalized_types = tuple(sorted({value.strip() for value in self.allowed_types if value.strip()}))
        if not normalized_types:
            raise ValueError("allowed_types cannot be empty")
        object.__setattr__(self, "allowed_types", normalized_types)

    def as_dict(self) -> dict[str, object]:
        return {
            "expected_title": self.expected_title,
            "minimum_duration_seconds": self.minimum_duration_seconds,
            "allowed_types": list(self.allowed_types),
            "require_playable": self.require_playable,
        }


@dataclass(frozen=True, slots=True)
class VkUploadReadinessAssessment:
    ready: bool
    reasons: tuple[str, ...]
    observed: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "reasons": list(self.reasons),
            "observed": self.observed,
        }


class UploadTicketProtocol(Protocol):
    @property
    def owner_id(self) -> int: ...

    @property
    def video_id(self) -> int: ...

    @property
    def upload_url(self) -> str: ...

    @property
    def reservation_response(self) -> dict[str, Any] | None: ...

    @property
    def remote_id(self) -> str: ...


class UploadWriterProtocol(Protocol):
    def begin_upload(
        self,
        *,
        community_id: int,
        title: str,
        description: str,
        wall_policy: VkUploadWallPolicy,
    ) -> UploadTicketProtocol: ...

    def upload_file(self, ticket: UploadTicketProtocol, path: Path) -> dict[str, Any]: ...

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None: ...

    def wait_until_available(
        self,
        ticket: UploadTicketProtocol,
        *,
        readiness: VkUploadReadiness,
        timeout_seconds: int,
        on_observation: Callable[[dict[str, Any] | None, VkUploadReadinessAssessment | None], None] | None = None,
    ) -> dict[str, Any]: ...

    def capture_wall_snapshot(
        self,
        *,
        community_id: int,
        max_posts_per_surface: int = 10000,
    ) -> VkWallSnapshot: ...


@dataclass(frozen=True, slots=True)
class StoredUploadTicket:
    owner_id: int
    video_id: int
    upload_url: str = "journal-reconciliation-only"
    reservation_response: dict[str, Any] | None = None

    @property
    def remote_id(self) -> str:
        return f"{self.owner_id}_{self.video_id}"


PersistCallback = Callable[[], None]
FaultHook = Callable[[str], None]
Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(clock: Clock) -> str:
    return clock().astimezone(UTC).isoformat()


def _canonical_sha256(payload: object) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"


def _text_sha256(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _normalized_title(value: str) -> str:
    return " ".join(value.split()).casefold()


def _is_playable(item: Mapping[str, Any]) -> bool:
    can_watch = item.get("can_watch")
    if can_watch is True or can_watch == 1 or can_watch == "1":
        return True
    player = item.get("player")
    if isinstance(player, str) and player.strip():
        return True
    files = item.get("files")
    if isinstance(files, Mapping):
        return any(isinstance(value, str) and value.strip() for value in files.values())
    return False


def assess_vk_upload_readiness(
    item: Mapping[str, Any],
    *,
    expected_owner_id: int,
    expected_video_id: int,
    readiness: VkUploadReadiness,
) -> VkUploadReadinessAssessment:
    reasons: list[str] = []
    observed_owner = item.get("owner_id")
    observed_video = item.get("id")
    observed_title = str(item.get("title") or "")
    raw_duration = item.get("duration")
    duration = int(raw_duration) if isinstance(raw_duration, int | str) and str(raw_duration).isdigit() else 0
    observed_type = str(item.get("type") or "").strip()
    processing = bool(item.get("processing"))
    converting = bool(item.get("converting"))
    playable = _is_playable(item)

    if observed_owner != expected_owner_id or observed_video != expected_video_id:
        reasons.append("identity_mismatch")
    if processing:
        reasons.append("processing")
    if converting:
        reasons.append("converting")
    if _normalized_title(observed_title) != _normalized_title(readiness.expected_title):
        reasons.append("title_mismatch")
    if duration < readiness.minimum_duration_seconds:
        reasons.append("duration_below_minimum")
    if observed_type not in readiness.allowed_types:
        reasons.append("unexpected_type" if observed_type else "type_missing")
    if readiness.require_playable and not playable:
        reasons.append("not_playable")

    observed = {
        "owner_id": observed_owner,
        "video_id": observed_video,
        "title": observed_title,
        "duration_seconds": duration,
        "type": observed_type,
        "processing": processing,
        "converting": converting,
        "playable": playable,
    }
    return VkUploadReadinessAssessment(ready=not reasons, reasons=tuple(reasons), observed=observed)


def create_upload_record(
    *,
    source_snapshot_id: str,
    community_id: int,
    source_video_id: str,
    source_title: str,
    source_duration_seconds: int | None,
    published_title: str,
    published_description: str,
    readiness: VkUploadReadiness,
    wall_policy: VkUploadWallPolicy = DEFAULT_UPLOAD_WALL_POLICY,
    clock: Clock = _utc_now,
) -> dict[str, Any]:
    if community_id <= 0:
        raise ValueError("community_id must be positive")
    if not source_snapshot_id.strip() or not source_video_id.strip():
        raise ValueError("source_snapshot_id and source_video_id cannot be blank")
    if not isinstance(wall_policy, VkUploadWallPolicy):
        raise TypeError("wall_policy must be a validated VkUploadWallPolicy")
    operation_payload = {
        "source_snapshot_id": source_snapshot_id,
        "community_id": community_id,
        "source_video_id": source_video_id,
        "source_title": source_title,
        "source_duration_seconds": source_duration_seconds,
        "published_title": published_title,
        "published_description_sha256": _text_sha256(published_description),
        "readiness": readiness.as_dict(),
        "wall_policy": wall_policy.as_dict(),
    }
    created_at = _iso(clock)
    return {
        "schema_name": "video-manager.vk-upload-operation",
        "schema_version": 1,
        "operation_id": _canonical_sha256(operation_payload),
        **operation_payload,
        "stage": UploadStage.PLANNED.value,
        "created_at": created_at,
        "updated_at": created_at,
        "media": None,
        "reservation": None,
        "upload": {},
        "verification": None,
        "last_error": None,
        "transitions": [
            {
                "from": None,
                "to": UploadStage.PLANNED.value,
                "at": created_at,
                "evidence": {"operation_id": _canonical_sha256(operation_payload)},
            }
        ],
    }


def _parse_remote_id(remote_id: str) -> tuple[int, int]:
    owner_text, separator, video_text = remote_id.partition("_")
    if separator != "_":
        raise ValueError(f"Invalid VK remote ID: {remote_id}")
    owner_id = int(owner_text)
    video_id = int(video_text)
    if owner_id == 0 or video_id <= 0:
        raise ValueError(f"Invalid VK remote ID: {remote_id}")
    return owner_id, video_id


def migrate_legacy_upload_record(
    legacy: Mapping[str, Any],
    *,
    source_snapshot_id: str,
    community_id: int,
    source_video_id: str,
    source_title: str,
    source_duration_seconds: int | None,
    published_title: str,
    published_description: str,
    readiness: VkUploadReadiness,
    wall_policy: VkUploadWallPolicy = DEFAULT_UPLOAD_WALL_POLICY,
    clock: Clock = _utc_now,
) -> dict[str, Any]:
    record = create_upload_record(
        source_snapshot_id=source_snapshot_id,
        community_id=community_id,
        source_video_id=source_video_id,
        source_title=source_title,
        source_duration_seconds=source_duration_seconds,
        published_title=published_title,
        published_description=published_description,
        readiness=readiness,
        wall_policy=wall_policy,
        clock=clock,
    )
    remote_id = legacy.get("remote_id")
    if isinstance(remote_id, str) and remote_id.strip():
        owner_id, video_id = _parse_remote_id(remote_id.strip())
        record["reservation"] = {
            "owner_id": owner_id,
            "video_id": video_id,
            "remote_id": remote_id.strip(),
            "upload_url": None,
            "upload_url_sha256": None,
            "reservation_response": None,
            "legacy_migration": True,
        }
        _transition(
            record,
            UploadStage.MEDIA_VERIFIED,
            evidence={"legacy_migration": True, "legacy_status": legacy.get("status")},
            clock=clock,
        )
        _transition(
            record,
            UploadStage.RESERVATION_INTENT_COMMITTED,
            evidence={"legacy_migration": True},
            clock=clock,
        )
        _transition(
            record,
            UploadStage.RESERVED,
            evidence={"remote_id": remote_id.strip(), "legacy_migration": True},
            clock=clock,
        )
        _transition(
            record,
            UploadStage.UPLOAD_STARTED,
            evidence={"legacy_migration": True},
            clock=clock,
        )
        _transition(
            record,
            UploadStage.PROCESSING,
            evidence={"legacy_migration": True, "requires_exact_reconciliation": True},
            clock=clock,
        )
    else:
        _transition(
            record,
            UploadStage.MEDIA_VERIFIED,
            evidence={"legacy_migration": True, "media_evidence_unavailable": True},
            clock=clock,
        )
        _transition(
            record,
            UploadStage.RESERVATION_INTENT_COMMITTED,
            evidence={"legacy_migration": True},
            clock=clock,
        )
        _transition(
            record,
            UploadStage.UNKNOWN_REQUIRES_RECONCILIATION,
            evidence={"legacy_migration": True, "reason": "legacy_record_without_remote_id"},
            clock=clock,
        )
    record["legacy_record"] = dict(legacy)
    return record


def ensure_upload_record(
    existing: Mapping[str, Any] | None,
    *,
    source_snapshot_id: str,
    community_id: int,
    source_video_id: str,
    source_title: str,
    source_duration_seconds: int | None,
    published_title: str,
    published_description: str,
    readiness: VkUploadReadiness,
    wall_policy: VkUploadWallPolicy = DEFAULT_UPLOAD_WALL_POLICY,
    clock: Clock = _utc_now,
) -> tuple[dict[str, Any], bool]:
    if existing is None:
        return (
            create_upload_record(
                source_snapshot_id=source_snapshot_id,
                community_id=community_id,
                source_video_id=source_video_id,
                source_title=source_title,
                source_duration_seconds=source_duration_seconds,
                published_title=published_title,
                published_description=published_description,
                readiness=readiness,
                wall_policy=wall_policy,
                clock=clock,
            ),
            True,
        )
    if existing.get("schema_name") != "video-manager.vk-upload-operation":
        return (
            migrate_legacy_upload_record(
                existing,
                source_snapshot_id=source_snapshot_id,
                community_id=community_id,
                source_video_id=source_video_id,
                source_title=source_title,
                source_duration_seconds=source_duration_seconds,
                published_title=published_title,
                published_description=published_description,
                readiness=readiness,
                wall_policy=wall_policy,
                clock=clock,
            ),
            True,
        )
    record = dict(existing)
    changed = False
    raw_wall_policy = record.get("wall_policy")
    if raw_wall_policy is None:
        record["wall_policy"] = wall_policy.as_dict()
        changed = True
    elif not isinstance(raw_wall_policy, Mapping):
        raise ValueError("Upload journal wall_policy must be an object")
    _validate_record_binding(
        record,
        source_snapshot_id=source_snapshot_id,
        community_id=community_id,
        source_video_id=source_video_id,
        published_title=published_title,
        published_description=published_description,
        readiness=readiness,
        wall_policy=wall_policy,
    )
    return record, changed


def _validate_record_binding(
    record: Mapping[str, Any],
    *,
    source_snapshot_id: str,
    community_id: int,
    source_video_id: str,
    published_title: str,
    published_description: str,
    readiness: VkUploadReadiness,
    wall_policy: VkUploadWallPolicy,
) -> None:
    raw_policy = record.get("wall_policy")
    if not isinstance(raw_policy, Mapping):
        raise ValueError("Upload journal is missing its wall policy")
    observed_policy = VkUploadWallPolicy.from_mapping(raw_policy)
    expected = {
        "source_snapshot_id": source_snapshot_id,
        "community_id": community_id,
        "source_video_id": source_video_id,
        "published_title": published_title,
        "published_description_sha256": _text_sha256(published_description),
        "readiness": readiness.as_dict(),
        "wall_policy": wall_policy.as_dict(),
    }
    mismatches = {
        key: {"expected": value, "actual": record.get(key)}
        for key, value in expected.items()
        if record.get(key) != value
    }
    if observed_policy != wall_policy:
        mismatches["wall_policy_value"] = {"expected": wall_policy.as_dict(), "actual": observed_policy.as_dict()}
    if mismatches:
        raise ValueError(f"Upload journal binding mismatch: {mismatches}")
    UploadStage(str(record.get("stage")))


def _transition(
    record: dict[str, Any],
    target: UploadStage,
    *,
    evidence: Mapping[str, Any] | None = None,
    clock: Clock = _utc_now,
) -> None:
    current = UploadStage(str(record.get("stage")))
    if current == target:
        return
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise RuntimeError(f"Invalid upload transition {current.value} -> {target.value}")
    changed_at = _iso(clock)
    record["stage"] = target.value
    record["updated_at"] = changed_at
    transitions = record.setdefault("transitions", [])
    if not isinstance(transitions, list):
        raise ValueError("Upload transitions must be a list")
    transitions.append(
        {
            "from": current.value,
            "to": target.value,
            "at": changed_at,
            "evidence": dict(evidence or {}),
        }
    )


def _record_error(record: dict[str, Any], exc: BaseException, *, clock: Clock) -> None:
    record["last_error"] = {
        "at": _iso(clock),
        "type": type(exc).__name__,
        "message": str(exc),
    }
    record["updated_at"] = _iso(clock)


def _fault(fault_hook: FaultHook | None, boundary: str) -> None:
    if fault_hook is not None:
        fault_hook(boundary)


def _persist_transition(
    record: dict[str, Any],
    target: UploadStage,
    *,
    persist: PersistCallback,
    evidence: Mapping[str, Any] | None = None,
    clock: Clock,
) -> None:
    _transition(record, target, evidence=evidence, clock=clock)
    persist()


def _verify_media(path: Path, previous: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    size = path.stat().st_size
    if size <= 0:
        raise ValueError(f"Upload media is empty: {path}")
    evidence = {
        "path": str(path),
        "size_bytes": size,
        "sha256": _file_sha256(path),
    }
    if previous is not None:
        for key in ("size_bytes", "sha256"):
            if previous.get(key) != evidence[key]:
                raise ValueError(f"Upload media changed after verification: {key}")
    return evidence


def ticket_from_record(record: Mapping[str, Any]) -> StoredUploadTicket:
    reservation = record.get("reservation")
    if not isinstance(reservation, Mapping):
        raise UploadRecoveryRequired("Upload journal has no reservation ticket")
    owner_id = reservation.get("owner_id")
    video_id = reservation.get("video_id")
    upload_url = reservation.get("upload_url")
    if not isinstance(owner_id, int) or not isinstance(video_id, int):
        raise UploadRecoveryRequired("Upload journal has an incomplete reservation identity")
    return StoredUploadTicket(
        owner_id=owner_id,
        video_id=video_id,
        upload_url=upload_url if isinstance(upload_url, str) and upload_url else "journal-reconciliation-only",
        reservation_response=(
            dict(reservation["reservation_response"])
            if isinstance(reservation.get("reservation_response"), Mapping)
            else None
        ),
    )


def _wall_baseline_evidence(snapshot: VkWallSnapshot) -> dict[str, object]:
    return {
        "before_snapshot_sha256": snapshot.snapshot_sha256,
        "before_captured_at": snapshot.captured_at,
        "before_published_pages": snapshot.published_pages,
        "before_postponed_pages": snapshot.postponed_pages,
    }


def _bind_wall_baseline(
    record: dict[str, Any],
    *,
    community_id: int,
    wall_before_snapshot: VkWallSnapshot,
    persist: PersistCallback,
) -> None:
    if wall_before_snapshot.community_id != community_id:
        raise UploadRejected("Upload wall baseline belongs to another community")
    if not wall_before_snapshot.complete:
        raise UploadRejected("Upload wall baseline is incomplete")
    stage = UploadStage(str(record.get("stage")))
    expected = _wall_baseline_evidence(wall_before_snapshot)
    raw_wall_safety = record.get("wall_safety")
    if raw_wall_safety is None:
        safe_to_bind = stage in {UploadStage.PLANNED, UploadStage.MEDIA_VERIFIED} or (
            stage == UploadStage.RESERVATION_INTENT_COMMITTED and not record.get("reservation_dispatch_started_at")
        )
        if not safe_to_bind:
            raise UploadRecoveryRequired(
                "Historical upload has no pre-dispatch wall baseline; exact wall reconciliation is required"
            )
        record["wall_safety"] = {
            **expected,
            "after_snapshot_sha256": None,
            "after_captured_at": None,
            "delta": None,
        }
        persist()
        return
    if not isinstance(raw_wall_safety, Mapping):
        raise UploadRecoveryRequired("Upload journal wall_safety evidence is invalid")
    mismatches = {
        key: {"expected": value, "actual": raw_wall_safety.get(key)}
        for key, value in expected.items()
        if raw_wall_safety.get(key) != value
    }
    if mismatches:
        raise UploadRecoveryRequired(f"Upload wall baseline binding mismatch: {mismatches}")


def _verified_wall_evidence_is_clean(record: Mapping[str, Any]) -> bool:
    raw_wall_safety = record.get("wall_safety")
    if not isinstance(raw_wall_safety, Mapping):
        return False
    raw_delta = raw_wall_safety.get("delta")
    return isinstance(raw_delta, Mapping) and raw_delta.get("status") == VkWallDeltaStatus.CLEAN.value


def _commit_verified(
    record: dict[str, Any],
    *,
    writer: UploadWriterProtocol,
    community_id: int,
    wall_before_snapshot: VkWallSnapshot,
    item: Mapping[str, Any],
    assessment: VkUploadReadinessAssessment,
    persist: PersistCallback,
    fault_hook: FaultHook | None,
    clock: Clock,
) -> None:
    _fault(fault_hook, "after_remote_ready_before_wall_postflight")
    wall_after_snapshot = writer.capture_wall_snapshot(community_id=community_id)
    wall_delta = compare_wall_snapshots(wall_before_snapshot, wall_after_snapshot)
    raw_wall_safety = record.get("wall_safety")
    if not isinstance(raw_wall_safety, dict):
        raise UploadRecoveryRequired("Upload journal lost its wall baseline evidence")
    raw_wall_safety.update(
        {
            "after_snapshot_sha256": wall_after_snapshot.snapshot_sha256,
            "after_captured_at": wall_after_snapshot.captured_at,
            "after_published_pages": wall_after_snapshot.published_pages,
            "after_postponed_pages": wall_after_snapshot.postponed_pages,
            "delta": wall_delta.as_dict(),
        }
    )
    persist()
    _fault(fault_hook, "after_wall_postflight_commit")
    if wall_delta.status is not VkWallDeltaStatus.CLEAN:
        _persist_transition(
            record,
            UploadStage.UNKNOWN_REQUIRES_RECONCILIATION,
            persist=persist,
            evidence={
                "reason": "upload_wall_postflight_not_clean",
                "wall_delta": wall_delta.as_dict(),
            },
            clock=clock,
        )
        raise UploadRecoveryRequired(
            f"Upload wall postflight is {wall_delta.status.value}; wall reconciliation is required"
        )

    _fault(fault_hook, "after_remote_ready_before_verified_commit")
    record["verification"] = {
        "verified_at": _iso(clock),
        "assessment": assessment.as_dict(),
        "item_sha256": _canonical_sha256(dict(item)),
        "wall_before_snapshot_sha256": wall_before_snapshot.snapshot_sha256,
        "wall_after_snapshot_sha256": wall_after_snapshot.snapshot_sha256,
        "wall_delta_status": wall_delta.status.value,
    }
    _persist_transition(
        record,
        UploadStage.VERIFIED,
        persist=persist,
        evidence={
            "assessment": assessment.as_dict(),
            "wall_delta": wall_delta.as_dict(),
        },
        clock=clock,
    )
    _fault(fault_hook, "after_verified_commit")


def _resume_or_reconcile(
    record: dict[str, Any],
    *,
    writer: UploadWriterProtocol,
    community_id: int,
    wall_before_snapshot: VkWallSnapshot,
    readiness: VkUploadReadiness,
    processing_timeout: int,
    persist: PersistCallback,
    fault_hook: FaultHook | None,
    clock: Clock,
) -> dict[str, Any]:
    stage = UploadStage(str(record["stage"]))
    reservation = record.get("reservation")
    if not isinstance(reservation, Mapping):
        if stage == UploadStage.RESERVATION_INTENT_COMMITTED:
            _persist_transition(
                record,
                UploadStage.UNKNOWN_REQUIRES_RECONCILIATION,
                persist=persist,
                evidence={"reason": "reservation_outcome_unknown_no_ticket"},
                clock=clock,
            )
        raise UploadRecoveryRequired("Reservation outcome is unknown and no exact VK ID was journaled")

    ticket = ticket_from_record(record)
    if stage in {UploadStage.UPLOAD_STARTED, UploadStage.UNKNOWN_REQUIRES_RECONCILIATION}:
        item = writer.read_video(owner_id=ticket.owner_id, video_id=ticket.video_id)
        if item is None:
            if stage != UploadStage.UNKNOWN_REQUIRES_RECONCILIATION:
                _persist_transition(
                    record,
                    UploadStage.UNKNOWN_REQUIRES_RECONCILIATION,
                    persist=persist,
                    evidence={"reason": "exact_remote_id_not_visible_after_ambiguous_upload"},
                    clock=clock,
                )
            raise UploadRecoveryRequired(
                f"Upload outcome for {ticket.remote_id} is unknown; exact VK object is not visible"
            )
        assessment = assess_vk_upload_readiness(
            item,
            expected_owner_id=ticket.owner_id,
            expected_video_id=ticket.video_id,
            readiness=readiness,
        )
        if assessment.ready:
            _commit_verified(
                record,
                writer=writer,
                community_id=community_id,
                wall_before_snapshot=wall_before_snapshot,
                item=item,
                assessment=assessment,
                persist=persist,
                fault_hook=fault_hook,
                clock=clock,
            )
            return record
        _persist_transition(
            record,
            UploadStage.PROCESSING,
            persist=persist,
            evidence={"reconciled_remote_id": ticket.remote_id, "assessment": assessment.as_dict()},
            clock=clock,
        )

    if UploadStage(str(record["stage"])) == UploadStage.UPLOAD_RESPONSE_RECEIVED:
        _persist_transition(
            record,
            UploadStage.PROCESSING,
            persist=persist,
            evidence={"upload_response_journaled": True},
            clock=clock,
        )
        _fault(fault_hook, "after_processing_commit")

    def on_observation(
        item: dict[str, Any] | None,
        assessment: VkUploadReadinessAssessment | None,
    ) -> None:
        record["last_observation"] = {
            "at": _iso(clock),
            "item_sha256": _canonical_sha256(item) if item is not None else None,
            "assessment": assessment.as_dict() if assessment is not None else None,
        }
        persist()

    try:
        item = writer.wait_until_available(
            ticket,
            readiness=readiness,
            timeout_seconds=processing_timeout,
            on_observation=on_observation,
        )
    except Exception as exc:
        _record_error(record, exc, clock=clock)
        persist()
        raise
    assessment = assess_vk_upload_readiness(
        item,
        expected_owner_id=ticket.owner_id,
        expected_video_id=ticket.video_id,
        readiness=readiness,
    )
    if not assessment.ready:
        raise RuntimeError(f"Writer returned a non-ready upload: {assessment.reasons}")
    _commit_verified(
        record,
        writer=writer,
        community_id=community_id,
        wall_before_snapshot=wall_before_snapshot,
        item=item,
        assessment=assessment,
        persist=persist,
        fault_hook=fault_hook,
        clock=clock,
    )
    return record


def execute_upload_operation(
    record: dict[str, Any],
    *,
    writer: UploadWriterProtocol,
    community_id: int,
    title: str,
    description: str,
    media_path: Path | None,
    readiness: VkUploadReadiness,
    processing_timeout: int,
    wall_before_snapshot: VkWallSnapshot,
    persist: PersistCallback,
    fault_hook: FaultHook | None = None,
    clock: Clock = _utc_now,
) -> dict[str, Any]:
    raw_wall_policy = record.get("wall_policy")
    if not isinstance(raw_wall_policy, Mapping):
        raise UploadRejected("Upload record is missing its fail-closed wall policy")
    try:
        wall_policy = VkUploadWallPolicy.from_mapping(raw_wall_policy)
    except ValueError as exc:
        raise UploadRejected(f"Upload wall policy is invalid: {exc}") from exc

    _bind_wall_baseline(
        record,
        community_id=community_id,
        wall_before_snapshot=wall_before_snapshot,
        persist=persist,
    )

    stage = UploadStage(str(record.get("stage")))
    if stage == UploadStage.VERIFIED:
        if not _verified_wall_evidence_is_clean(record):
            raise UploadRecoveryRequired("Verified upload lacks a clean wall postflight and cannot be reused")
        return record
    if stage == UploadStage.REJECTED:
        raise UploadRejected(str(record.get("last_error") or "Upload was rejected"))
    if stage == UploadStage.RESERVATION_INTENT_COMMITTED and record.get("reservation_dispatch_started_at"):
        return _resume_or_reconcile(
            record,
            writer=writer,
            community_id=community_id,
            wall_before_snapshot=wall_before_snapshot,
            readiness=readiness,
            processing_timeout=processing_timeout,
            persist=persist,
            fault_hook=fault_hook,
            clock=clock,
        )
    if stage in {
        UploadStage.UPLOAD_STARTED,
        UploadStage.UPLOAD_RESPONSE_RECEIVED,
        UploadStage.PROCESSING,
        UploadStage.UNKNOWN_REQUIRES_RECONCILIATION,
    }:
        return _resume_or_reconcile(
            record,
            writer=writer,
            community_id=community_id,
            wall_before_snapshot=wall_before_snapshot,
            readiness=readiness,
            processing_timeout=processing_timeout,
            persist=persist,
            fault_hook=fault_hook,
            clock=clock,
        )

    if media_path is None:
        raise ValueError(f"media_path is required while upload stage is {stage.value}")

    media = record.get("media")
    previous_media = cast(Mapping[str, Any] | None, media if isinstance(media, Mapping) else None)
    media_evidence = _verify_media(media_path, previous_media)
    if stage == UploadStage.PLANNED:
        record["media"] = {**media_evidence, "verified_at": _iso(clock)}
        _persist_transition(
            record,
            UploadStage.MEDIA_VERIFIED,
            persist=persist,
            evidence={"media": media_evidence},
            clock=clock,
        )
        _fault(fault_hook, "after_media_verified_commit")
        stage = UploadStage.MEDIA_VERIFIED

    if stage in {UploadStage.MEDIA_VERIFIED, UploadStage.RESERVATION_INTENT_COMMITTED}:
        if stage == UploadStage.MEDIA_VERIFIED:
            _fault(fault_hook, "before_reservation_intent_commit")
            intent = {
                "community_id": community_id,
                "title": title,
                "description_sha256": _text_sha256(description),
                "media_sha256": media_evidence["sha256"],
                "wall_policy_sha256": raw_wall_policy["policy_sha256"],
            }
            record["reservation_intent"] = {
                **intent,
                "intent_sha256": _canonical_sha256(intent),
                "committed_at": _iso(clock),
            }
            _persist_transition(
                record,
                UploadStage.RESERVATION_INTENT_COMMITTED,
                persist=persist,
                evidence={"intent_sha256": record["reservation_intent"]["intent_sha256"]},
                clock=clock,
            )
            _fault(fault_hook, "after_reservation_intent_commit")
        record["reservation_dispatch_started_at"] = _iso(clock)
        persist()
        _fault(fault_hook, "after_reservation_dispatch_started_commit")
        try:
            ticket = writer.begin_upload(
                community_id=community_id,
                title=title,
                description=description,
                wall_policy=wall_policy,
            )
        except Exception as exc:
            _record_error(record, exc, clock=clock)
            if bool(getattr(exc, "retryable", False)):
                _persist_transition(
                    record,
                    UploadStage.UNKNOWN_REQUIRES_RECONCILIATION,
                    persist=persist,
                    evidence={"reason": "ambiguous_reservation_failure"},
                    clock=clock,
                )
                raise UploadRecoveryRequired(
                    "video.save outcome is ambiguous; a second reservation is forbidden"
                ) from exc
            _persist_transition(
                record,
                UploadStage.REJECTED,
                persist=persist,
                evidence={"reason": "reservation_rejected"},
                clock=clock,
            )
            raise UploadRejected("video.save was rejected") from exc
        _fault(fault_hook, "after_provider_reservation_before_ticket_commit")
        response = ticket.reservation_response
        record["reservation"] = {
            "owner_id": ticket.owner_id,
            "video_id": ticket.video_id,
            "remote_id": ticket.remote_id,
            "upload_url": ticket.upload_url,
            "upload_url_sha256": _text_sha256(ticket.upload_url),
            "reservation_response": dict(response) if response is not None else None,
            "reserved_at": _iso(clock),
            "wall_policy_sha256": raw_wall_policy["policy_sha256"],
        }
        _persist_transition(
            record,
            UploadStage.RESERVED,
            persist=persist,
            evidence={
                "remote_id": ticket.remote_id,
                "upload_url_sha256": record["reservation"]["upload_url_sha256"],
                "wall_policy_sha256": raw_wall_policy["policy_sha256"],
            },
            clock=clock,
        )
        _fault(fault_hook, "after_ticket_commit")
        stage = UploadStage.RESERVED

    if stage == UploadStage.RESERVED:
        ticket = ticket_from_record(record)
        _verify_media(media_path, cast(Mapping[str, Any], record["media"]))
        record.setdefault("upload", {})["started_at"] = _iso(clock)
        _persist_transition(
            record,
            UploadStage.UPLOAD_STARTED,
            persist=persist,
            evidence={"remote_id": ticket.remote_id, "media_sha256": media_evidence["sha256"]},
            clock=clock,
        )
        _fault(fault_hook, "after_upload_started_commit")
        try:
            upload_response = writer.upload_file(ticket, media_path)
        except Exception as exc:
            _record_error(record, exc, clock=clock)
            _persist_transition(
                record,
                UploadStage.UNKNOWN_REQUIRES_RECONCILIATION,
                persist=persist,
                evidence={"reason": "upload_dispatch_or_response_unknown", "remote_id": ticket.remote_id},
                clock=clock,
            )
            raise UploadRecoveryRequired(
                f"Upload outcome for {ticket.remote_id} is ambiguous; retransmission is forbidden"
            ) from exc
        record.setdefault("upload", {})["response"] = upload_response
        record["upload"]["response_sha256"] = _canonical_sha256(upload_response)
        record["upload"]["response_received_at"] = _iso(clock)
        _persist_transition(
            record,
            UploadStage.UPLOAD_RESPONSE_RECEIVED,
            persist=persist,
            evidence={"response_sha256": record["upload"]["response_sha256"]},
            clock=clock,
        )
        _fault(fault_hook, "after_upload_response_commit")

    return _resume_or_reconcile(
        record,
        writer=writer,
        community_id=community_id,
        wall_before_snapshot=wall_before_snapshot,
        readiness=readiness,
        processing_timeout=processing_timeout,
        persist=persist,
        fault_hook=fault_hook,
        clock=clock,
    )


__all__ = [
    "StoredUploadTicket",
    "UploadRecoveryRequired",
    "UploadRejected",
    "UploadStage",
    "VkUploadReadiness",
    "VkUploadReadinessAssessment",
    "assess_vk_upload_readiness",
    "create_upload_record",
    "ensure_upload_record",
    "execute_upload_operation",
    "migrate_legacy_upload_record",
    "ticket_from_record",
]
