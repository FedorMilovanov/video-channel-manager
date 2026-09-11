from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.editorial._project_profiles import PROJECT_CHANNEL_IDS
from video_channel_manager.local_media.artifact import load_media_artifact_manifest
from video_channel_manager.platforms.vk.lock import community_vk_write_lock_path, local_vk_write_lock
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.text import render_vk_video_description
from video_channel_manager.platforms.vk.upload_lifecycle import (
    UploadRecoveryRequired,
    UploadRejected,
    UploadStage,
    VkUploadReadiness,
    ensure_upload_record,
)
from video_channel_manager.platforms.vk.upload_media import execute_upload_operation
from video_channel_manager.platforms.vk.wall import VkWallWriter
from video_channel_manager.wave_engine.canonical import (
    file_sha256,
    resolve_repository_relative_path,
    write_json_atomic,
)
from video_channel_manager.wave_engine.engine import (
    KnownProviderRejectionError,
    OperationRejectedError,
    UnknownProviderOutcomeError,
)
from video_channel_manager.wave_engine.models import MutationClass, WaveOperation


VK_VIDEO_OPERATION_KIND = "vk.video.upload"
VK_VIDEO_POLICY_VERSION = "vk-native-video-wave-v2"
VK_VIDEO_DEFAULT_ACCOUNT_ALIAS = "legendary-poet"


def _minimum_duration_seconds(source_duration_seconds: int) -> int:
    tolerance = max(5, min(30, round(source_duration_seconds * 0.02)))
    return max(1, source_duration_seconds - tolerance)


class VkNativeVideoUploadAdapter:
    reconciliation_replay_safe = True

    """Reviewed Wave adapter for ordinary native VK Video uploads.

    The adapter delegates reservation, binary transfer, exact-ID readback, and
    media authority to the shared VK writer/upload lifecycle. Wall publication is
    a separate workflow and is not a prerequisite for a native video upload.
    """

    def __init__(
        self,
        *,
        repository_root: Path,
        journal_directory: Path,
        account_alias: str = VK_VIDEO_DEFAULT_ACCOUNT_ALIAS,
        writer: VkWallWriter | None = None,
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.journal_directory = journal_directory.resolve()
        try:
            self.journal_directory.relative_to(self.repository_root)
        except ValueError as exc:
            raise ValueError("VK video provider journal must remain inside repository root") from exc
        self.account_alias = account_alias.strip()
        if not self.account_alias:
            raise ValueError("VK video account alias cannot be blank")

        settings = get_settings()
        self.store = VkTokenStore(settings.data_dir)
        account = self.store.get_account(self.account_alias)
        self._community_ids = {int(item.community_id) for item in account.communities}

        self.writer = writer or VkWallWriter(
            token_store=self.store,
            account_alias=self.account_alias,
            api_version=settings.vk_api_version,
        )
        self._owns_writer = writer is None

    def close(self) -> None:
        if self._owns_writer:
            self.writer.close()

    def _provider_journal_path(self, operation: WaveOperation) -> Path:
        return (
            self.repository_root
            / "operator-output"
            / "vk-upload-state"
            / operation.project.project_key
            / f"{operation.operation_id}.json"
        )

    def _validate_operation(self, operation: WaveOperation) -> dict[str, Any]:
        if operation.operation_kind != VK_VIDEO_OPERATION_KIND:
            raise OperationRejectedError(f"Unsupported VK video operation kind: {operation.operation_kind}")
        if operation.mutation_class is not MutationClass.AMBIGUOUS_MUTATION:
            raise OperationRejectedError("VK native video upload must be an ambiguous mutation")
        if operation.policy_version != VK_VIDEO_POLICY_VERSION:
            raise OperationRejectedError(f"Unsupported VK video policy: {operation.policy_version}")
        community_id = operation.project.community_id
        if community_id not in self._community_ids:
            raise OperationRejectedError(f"VK account registry does not bind community {community_id}")
        if operation.project.owner_id != -community_id:
            raise OperationRejectedError("VK video owner/community binding is inconsistent")

        payload = dict(operation.payload)
        registered_channels = tuple(PROJECT_CHANNEL_IDS.get(operation.project.project_key, ()))
        if len(registered_channels) != 1:
            raise OperationRejectedError("VK video project must have exactly one registered YouTube source channel")
        if payload.get("source_channel_id") != str(registered_channels[0]):
            raise OperationRejectedError("VK video source channel does not match the registered project channel")
        required_text = (
            "source_video_id",
            "source_channel_id",
            "source_title",
            "published_title",
            "published_description",
            "media_manifest_path",
            "media_manifest_sha256",
            "media_artifact_manifest_sha256",
        )
        for field in required_text:
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                raise OperationRejectedError(f"VK video payload field {field} is required")
        duration = payload.get("source_duration_seconds")
        if type(duration) is not int or duration <= 180:
            raise OperationRejectedError("VK video upload requires long-form duration > 180 seconds")
        if payload.get("privacy_status") != "public":
            raise OperationRejectedError("VK video upload source must be public")
        for field in ("wallpost", "auto_publish", "repeat"):
            if payload.get(field) is not False:
                raise OperationRejectedError(f"VK video payload field {field} must be exactly false")
        return payload

    @staticmethod
    def _requires_new_reservation(record: Mapping[str, Any]) -> bool:
        return not bool(record.get("reservation_dispatch_started_at")) and not isinstance(
            record.get("reservation"), Mapping
        )

    @staticmethod
    def _normalized_title(value: object) -> str:
        return " ".join(str(value or "").split()).casefold()

    def _assert_source_absent_live(self, *, payload: Mapping[str, Any], community_id: int) -> None:
        source_video_id = str(payload["source_video_id"])
        source_url = f"https://www.youtube.com/watch?v={source_video_id}"
        expected_title = self._normalized_title(payload["published_title"])
        expected_duration = int(payload["source_duration_seconds"])
        tolerance = max(5, min(30, round(expected_duration * 0.02)))
        matches: list[str] = []
        for item in self.writer.list_community_videos(community_id=community_id):
            owner_id = item.get("owner_id")
            video_id = item.get("id")
            remote_id = (
                f"{owner_id}_{video_id}" if isinstance(owner_id, int) and isinstance(video_id, int) else "unknown"
            )
            description = str(item.get("description") or "")
            if source_url in description:
                matches.append(remote_id)
                continue
            raw_duration = item.get("duration")
            duration = int(raw_duration) if isinstance(raw_duration, int | str) and str(raw_duration).isdigit() else 0
            if (
                self._normalized_title(item.get("title")) == expected_title
                and abs(duration - expected_duration) <= tolerance
            ):
                matches.append(remote_id)
        if matches:
            raise OperationRejectedError(
                "VK target already contains the source video or an exact title/duration collision: "
                + ", ".join(sorted(set(matches)))
            )

    @staticmethod
    def _provider_dispatch_started(record: Mapping[str, Any]) -> bool:
        if bool(record.get("reservation_dispatch_started_at")):
            return True
        reservation = record.get("reservation")
        if isinstance(reservation, Mapping):
            return True
        upload = record.get("upload")
        return isinstance(upload, Mapping) and bool(upload.get("started_at"))

    def _load_record(
        self,
        operation: WaveOperation,
        *,
        payload: Mapping[str, Any],
        readiness: VkUploadReadiness,
    ) -> dict[str, Any]:
        path = self._provider_journal_path(operation)
        existing: Mapping[str, Any] | None = None
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise UnknownProviderOutcomeError(f"Cannot read existing VK upload provider journal: {path}") from exc
            if not isinstance(raw, Mapping):
                raise UnknownProviderOutcomeError("VK upload provider journal is not an object")
            existing = raw

        record, changed = ensure_upload_record(
            existing,
            source_snapshot_id=operation.source_snapshot_id,
            community_id=operation.project.community_id,
            source_video_id=str(payload["source_video_id"]),
            source_title=str(payload["source_title"]),
            source_duration_seconds=int(payload["source_duration_seconds"]),
            published_title=str(payload["published_title"]),
            published_description=str(payload["published_description"]),
            readiness=readiness,
            retry_known_rejection=True,
        )
        if changed or not path.exists():
            write_json_atomic(path, record)
        return record

    def execute(self, operation: WaveOperation) -> Mapping[str, Any]:
        payload = self._validate_operation(operation)
        community_id = operation.project.community_id

        manifest_path = resolve_repository_relative_path(
            self.repository_root,
            str(payload["media_manifest_path"]),
            require_file=True,
        )
        if file_sha256(manifest_path) != str(payload["media_manifest_sha256"]):
            raise OperationRejectedError("VK video media manifest file SHA-256 mismatch")
        artifact = load_media_artifact_manifest(manifest_path)
        if artifact.source.project_key != operation.project.project_key:
            raise OperationRejectedError("Media artifact project does not match Wave operation")
        if artifact.source.source_channel_id != str(payload["source_channel_id"]):
            raise OperationRejectedError("Media artifact source channel does not match Wave operation")
        if artifact.source.source_id != str(payload["source_video_id"]):
            raise OperationRejectedError("Media artifact source ID does not match Wave operation")
        if artifact.manifest_sha256 != str(payload["media_artifact_manifest_sha256"]):
            raise OperationRejectedError("Media artifact internal digest does not match Wave operation")

        rendered = render_vk_video_description(
            str(payload["published_description"]),
            source_video_id=str(payload["source_video_id"]),
        )
        if rendered.text != str(payload["published_description"]) or rendered.has_errors:
            raise OperationRejectedError("Published VK description is not already stable under the current renderer")

        description = str(payload["published_description"])
        readiness = VkUploadReadiness(
            expected_title=str(payload["published_title"]),
            minimum_duration_seconds=_minimum_duration_seconds(int(payload["source_duration_seconds"])),
            expected_description_sha256="sha256:" + hashlib.sha256(description.encode("utf-8")).hexdigest(),
            require_public=True,
            allowed_types=("video",),
            require_playable=True,
        )
        record = self._load_record(operation, payload=payload, readiness=readiness)
        journal_path = self._provider_journal_path(operation)
        media_path = Path(artifact.acquisition.authoritative_final_path).resolve()

        def persist() -> None:
            write_json_atomic(journal_path, record)

        try:
            lock_path = community_vk_write_lock_path(self.store.data_dir, community_id=community_id)
            with local_vk_write_lock(
                lock_path,
                account=self.account_alias,
                community_id=community_id,
                operation=f"vk-video-upload:{payload['source_video_id']}",
            ):
                if self._requires_new_reservation(record):
                    self._assert_source_absent_live(payload=payload, community_id=community_id)
                execute_upload_operation(
                    record,
                    writer=self.writer,
                    community_id=community_id,
                    title=str(payload["published_title"]),
                    description=description,
                    media_path=media_path,
                    media_artifact=artifact,
                    readiness=readiness,
                    processing_timeout=int(payload.get("processing_timeout_seconds") or 3600),
                    wall_before_snapshot=None,
                    persist=persist,
                )
        except UploadRejected as exc:
            if self._provider_dispatch_started(record):
                raise KnownProviderRejectionError(str(exc)) from exc
            raise OperationRejectedError(str(exc)) from exc
        except UploadRecoveryRequired as exc:
            if self._provider_dispatch_started(record):
                raise UnknownProviderOutcomeError(str(exc)) from exc
            raise OperationRejectedError(str(exc)) from exc
        except Exception as exc:
            if self._provider_dispatch_started(record):
                raise UnknownProviderOutcomeError(f"VK upload failed after provider dispatch began: {exc}") from exc
            raise OperationRejectedError(f"VK upload failed before provider dispatch: {exc}") from exc

        if record.get("stage") != UploadStage.VERIFIED.value:
            raise UnknownProviderOutcomeError(f"VK upload returned without VERIFIED stage: {record.get('stage')}")
        reservation = record.get("reservation")
        verification = record.get("verification")
        if not isinstance(reservation, Mapping) or not isinstance(verification, Mapping):
            raise UnknownProviderOutcomeError("Verified VK upload lacks reservation/verification evidence")

        return {
            "source_video_id": str(payload["source_video_id"]),
            "remote_id": str(reservation.get("remote_id")),
            "owner_id": reservation.get("owner_id"),
            "video_id": reservation.get("video_id"),
            "upload_stage": record["stage"],
            "media_manifest_sha256": artifact.manifest_sha256,
            "provider_journal_path": str(journal_path.relative_to(self.repository_root)).replace(os.sep, "/"),
        }

    def reconcile(self, operation: WaveOperation) -> Mapping[str, Any]:
        payload = self._validate_operation(operation)
        journal_path = self._provider_journal_path(operation)
        if not journal_path.is_file():
            raise RuntimeError("VK video reconciliation has no provider journal")
        raw = json.loads(journal_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise RuntimeError("VK video provider journal is invalid")
        record = raw
        stage = UploadStage(str(record.get("stage")))

        reservation = record.get("reservation")
        if stage is UploadStage.VERIFIED:
            verification = record.get("verification")
            if not isinstance(reservation, Mapping) or not isinstance(verification, Mapping):
                raise RuntimeError("Verified VK upload has incomplete evidence")
            return {
                "source_video_id": str(payload["source_video_id"]),
                "remote_id": str(reservation.get("remote_id")),
                "owner_id": reservation.get("owner_id"),
                "video_id": reservation.get("video_id"),
                "upload_stage": stage.value,
                "reconciliation": "already_verified",
            }

        if not isinstance(reservation, Mapping):
            raise RuntimeError(
                "VK upload reservation outcome is unknown and no exact remote ID was journaled; "
                "reconciliation cannot infer identity from title or aggregate inventory"
            )
        if stage not in {
            UploadStage.UPLOAD_STARTED,
            UploadStage.UPLOAD_RESPONSE_RECEIVED,
            UploadStage.PROCESSING,
            UploadStage.UNKNOWN_REQUIRES_RECONCILIATION,
        }:
            raise RuntimeError(f"VK upload stage {stage.value} is not eligible for read-only exact-ID reconciliation")

        description = str(payload["published_description"])
        readiness = VkUploadReadiness(
            expected_title=str(payload["published_title"]),
            minimum_duration_seconds=_minimum_duration_seconds(int(payload["source_duration_seconds"])),
            expected_description_sha256="sha256:" + hashlib.sha256(description.encode("utf-8")).hexdigest(),
            require_public=True,
            allowed_types=("video",),
            require_playable=True,
        )

        def persist() -> None:
            write_json_atomic(journal_path, record)

        # Stages admitted above never retransmit media. Reconciliation uses only
        # the exact journaled VK video ID and does not consult wall state.
        execute_upload_operation(
            record,
            writer=self.writer,
            community_id=operation.project.community_id,
            title=str(payload["published_title"]),
            description=str(payload["published_description"]),
            media_path=None,
            media_artifact=None,
            readiness=readiness,
            processing_timeout=int(payload.get("processing_timeout_seconds") or 3600),
            wall_before_snapshot=None,
            persist=persist,
        )
        persist()

        if record.get("stage") != UploadStage.VERIFIED.value:
            raise RuntimeError(f"VK exact-ID reconciliation did not reach verified: {record.get('stage')}")
        reservation = record.get("reservation")
        verification = record.get("verification")
        if not isinstance(reservation, Mapping) or not isinstance(verification, Mapping):
            raise RuntimeError("Reconciled VK upload lacks exact verification evidence")
        return {
            "source_video_id": str(payload["source_video_id"]),
            "remote_id": str(reservation.get("remote_id")),
            "owner_id": reservation.get("owner_id"),
            "video_id": reservation.get("video_id"),
            "upload_stage": record["stage"],
            "reconciliation": "exact_remote_id_verified",
        }


__all__ = [
    "VK_VIDEO_DEFAULT_ACCOUNT_ALIAS",
    "VK_VIDEO_OPERATION_KIND",
    "VK_VIDEO_POLICY_VERSION",
    "VkNativeVideoUploadAdapter",
]
