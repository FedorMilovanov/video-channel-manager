from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.editorial._project_profiles import (
    PROJECT_CHANNEL_IDS,
    resolve_project_key,
)
from video_channel_manager.local_media.artifact import (
    MediaArtifactError,
    MediaArtifactEvidence,
    MediaProbe,
    validate_cached_media_artifact,
    validate_media_artifact_evidence,
)
from video_channel_manager.local_media.quality import probe_media
from video_channel_manager.platforms.vk.upload_lifecycle import (
    Clock,
    FaultHook,
    PersistCallback,
    UploadRejected,
    UploadStage,
    UploadTicketProtocol,
    UploadWriterProtocol,
    VkUploadReadiness,
    VkUploadReadinessAssessment,
    _canonical_sha256,
    _utc_now,
    execute_upload_operation as _execute_legacy_upload_operation,
)
from video_channel_manager.platforms.vk.wall_safety import (
    VkUploadWallPolicy,
    VkWallSnapshot,
)


class UploadMediaAuthorityError(RuntimeError):
    """Upload media cannot be bound to exact project/source/artifact evidence."""


def _exact_project_channel_id(project_key: str) -> str:
    channel_ids = PROJECT_CHANNEL_IDS.get(project_key, frozenset())
    if len(channel_ids) != 1:
        raise UploadMediaAuthorityError(f"project {project_key!r} does not have exactly one registered source channel")
    return next(iter(channel_ids))


def verify_upload_media_authority(
    record: Mapping[str, Any],
    *,
    community_id: int,
    media_path: Path,
    media_artifact: MediaArtifactEvidence | Mapping[str, Any] | None,
    previous_media: Mapping[str, Any] | None,
    probe: MediaProbe = probe_media,
) -> MediaArtifactEvidence:
    if media_artifact is None:
        raise UploadMediaAuthorityError("authoritative media artifact evidence is required")
    project_key = resolve_project_key({"community_id": community_id})
    if project_key is None:
        raise UploadMediaAuthorityError(f"community_id {community_id} does not resolve to one registered project")
    source_video_id = record.get("source_video_id")
    if not isinstance(source_video_id, str) or not source_video_id.strip():
        raise UploadMediaAuthorityError("upload journal has no exact source_video_id")
    raw_duration = record.get("source_duration_seconds")
    source_duration = (
        float(raw_duration)
        if isinstance(raw_duration, int | float) and not isinstance(raw_duration, bool) and raw_duration > 0
        else None
    )
    try:
        evidence = validate_cached_media_artifact(
            media_artifact,
            expected_project_key=project_key,
            expected_source_platform=PlatformName.YOUTUBE,
            expected_source_channel_id=_exact_project_channel_id(project_key),
            expected_source_id=source_video_id,
            expected_source_duration_seconds=source_duration,
            expected_path=media_path,
            probe=probe,
        )
    except MediaArtifactError as exc:
        raise UploadMediaAuthorityError(str(exc)) from exc

    if previous_media is not None:
        previous_payload = previous_media.get("artifact")
        if not isinstance(previous_payload, Mapping):
            raise UploadMediaAuthorityError(
                "verified upload journal contains legacy media evidence without an artifact manifest"
            )
        try:
            previous = MediaArtifactEvidence.model_validate(previous_payload)
            validate_media_artifact_evidence(previous)
        except Exception as exc:
            raise UploadMediaAuthorityError(f"journaled media artifact is invalid: {exc}") from exc
        top_level_digest = previous_media.get("manifest_sha256")
        if top_level_digest != previous.manifest_sha256:
            raise UploadMediaAuthorityError("journaled media manifest digest does not match its nested artifact")
        if previous.manifest_sha256 != evidence.manifest_sha256:
            raise UploadMediaAuthorityError("media artifact manifest changed after MEDIA_VERIFIED")
    return evidence


def journal_media_evidence(evidence: MediaArtifactEvidence) -> dict[str, object]:
    return {
        "schema_name": "video-manager.vk-upload-media-evidence",
        "schema_version": 2,
        "manifest_sha256": evidence.manifest_sha256,
        "path": evidence.acquisition.authoritative_final_path,
        "size_bytes": evidence.probe.size_bytes,
        "sha256": evidence.probe.sha256,
        "profile_name": evidence.profile.profile_name,
        "artifact": evidence.model_dump(mode="json"),
    }


def _bind_media_record(record: dict[str, Any], evidence: MediaArtifactEvidence) -> None:
    previous = record.get("media")
    verified_at = previous.get("verified_at") if isinstance(previous, Mapping) else None
    bound = journal_media_evidence(evidence)
    if isinstance(verified_at, str) and verified_at:
        bound["verified_at"] = verified_at
    record["media"] = bound


def _bind_reservation_intent(record: dict[str, Any], manifest_sha256: str) -> None:
    raw_intent = record.get("reservation_intent")
    if not isinstance(raw_intent, dict):
        return
    existing = raw_intent.get("media_manifest_sha256")
    if existing not in {None, manifest_sha256}:
        raise UploadMediaAuthorityError("reservation intent is bound to another media artifact manifest")
    payload = {key: value for key, value in raw_intent.items() if key not in {"committed_at", "intent_sha256"}}
    payload["media_manifest_sha256"] = manifest_sha256
    raw_intent.update(payload)
    raw_intent["intent_sha256"] = _canonical_sha256(payload)
    transitions = record.get("transitions")
    if isinstance(transitions, list):
        for transition in reversed(transitions):
            if not isinstance(transition, dict):
                continue
            if transition.get("to") != UploadStage.RESERVATION_INTENT_COMMITTED.value:
                continue
            evidence = transition.get("evidence")
            if isinstance(evidence, dict):
                evidence["intent_sha256"] = raw_intent["intent_sha256"]
            break


class _AuthorityWriter:
    def __init__(
        self,
        delegate: UploadWriterProtocol,
        *,
        record: dict[str, Any],
        community_id: int,
        media_artifact: MediaArtifactEvidence,
        probe: MediaProbe,
    ) -> None:
        self._delegate = delegate
        self._record = record
        self._community_id = community_id
        self._media_artifact = media_artifact
        self._probe = probe

    def begin_upload(
        self,
        *,
        community_id: int,
        title: str,
        description: str,
        wall_policy: VkUploadWallPolicy,
    ) -> UploadTicketProtocol:
        return self._delegate.begin_upload(
            community_id=community_id,
            title=title,
            description=description,
            wall_policy=wall_policy,
        )

    def upload_file(
        self,
        ticket: UploadTicketProtocol,
        path: Path,
    ) -> dict[str, Any]:
        previous = self._record.get("media")
        previous_media = previous if isinstance(previous, Mapping) else None
        try:
            verify_upload_media_authority(
                self._record,
                community_id=self._community_id,
                media_path=path,
                media_artifact=self._media_artifact,
                previous_media=previous_media,
                probe=self._probe,
            )
        except UploadMediaAuthorityError as exc:
            raise UploadRejected(f"Upload media authority is invalid: {exc}") from exc
        return self._delegate.upload_file(ticket, path)

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        return self._delegate.read_video(owner_id=owner_id, video_id=video_id)

    def wait_until_available(
        self,
        ticket: UploadTicketProtocol,
        *,
        readiness: VkUploadReadiness,
        timeout_seconds: int,
        on_observation: Callable[
            [dict[str, Any] | None, VkUploadReadinessAssessment | None],
            None,
        ]
        | None = None,
    ) -> dict[str, Any]:
        return self._delegate.wait_until_available(
            ticket,
            readiness=readiness,
            timeout_seconds=timeout_seconds,
            on_observation=on_observation,
        )

    def capture_wall_snapshot(
        self,
        *,
        community_id: int,
        max_posts_per_surface: int = 10000,
    ) -> VkWallSnapshot:
        return self._delegate.capture_wall_snapshot(
            community_id=community_id,
            max_posts_per_surface=max_posts_per_surface,
        )


def _legacy_media_change_error(exc: ValueError) -> bool:
    return str(exc).startswith("Upload media changed after verification:")


def execute_upload_operation(
    record: dict[str, Any],
    *,
    writer: UploadWriterProtocol,
    community_id: int,
    title: str,
    description: str,
    media_path: Path | None,
    media_artifact: MediaArtifactEvidence | Mapping[str, Any] | None,
    readiness: VkUploadReadiness,
    processing_timeout: int,
    wall_before_snapshot: VkWallSnapshot,
    persist: PersistCallback,
    media_probe: MediaProbe = probe_media,
    fault_hook: FaultHook | None = None,
    clock: Clock = _utc_now,
) -> dict[str, Any]:
    """Run the VK upload lifecycle through mandatory Wave 8D media authority.

    The wrapped state machine remains responsible for mutation ordering and
    reconciliation. This facade makes the immutable media manifest part of the
    durable journal and reservation intent, and revalidates it at dispatch.
    """

    stage = UploadStage(str(record.get("stage")))
    reservation_dispatched = stage == UploadStage.RESERVATION_INTENT_COMMITTED and bool(
        record.get("reservation_dispatch_started_at")
    )
    requires_media = (
        stage
        in {
            UploadStage.PLANNED,
            UploadStage.MEDIA_VERIFIED,
            UploadStage.RESERVATION_INTENT_COMMITTED,
            UploadStage.RESERVED,
        }
        and not reservation_dispatched
    )

    authoritative: MediaArtifactEvidence | None = None
    if requires_media:
        if media_path is None:
            raise UploadRejected(f"media_path is required while upload stage is {stage.value}")
        previous = record.get("media")
        previous_media = previous if isinstance(previous, Mapping) else None
        try:
            authoritative = verify_upload_media_authority(
                record,
                community_id=community_id,
                media_path=media_path,
                media_artifact=media_artifact,
                previous_media=previous_media,
                probe=media_probe,
            )
            _bind_media_record(record, authoritative)
            _bind_reservation_intent(record, authoritative.manifest_sha256)
        except UploadMediaAuthorityError as exc:
            raise UploadRejected(f"Upload media authority is invalid: {exc}") from exc

    def persist_with_authority() -> None:
        if authoritative is not None:
            _bind_media_record(record, authoritative)
            _bind_reservation_intent(record, authoritative.manifest_sha256)
        persist()

    delegated_writer: UploadWriterProtocol = writer
    if authoritative is not None and media_path is not None:
        delegated_writer = _AuthorityWriter(
            writer,
            record=record,
            community_id=community_id,
            media_artifact=authoritative,
            probe=media_probe,
        )

    try:
        return _execute_legacy_upload_operation(
            record,
            writer=delegated_writer,
            community_id=community_id,
            title=title,
            description=description,
            media_path=media_path,
            readiness=readiness,
            processing_timeout=processing_timeout,
            wall_before_snapshot=wall_before_snapshot,
            persist=persist_with_authority,
            fault_hook=fault_hook,
            clock=clock,
        )
    except ValueError as exc:
        if _legacy_media_change_error(exc):
            raise UploadRejected(
                "Upload media changed after reservation; restore the exact authoritative artifact and resume the same reservation"
            ) from exc
        raise


__all__ = [
    "UploadMediaAuthorityError",
    "execute_upload_operation",
    "journal_media_evidence",
    "verify_upload_media_authority",
]
