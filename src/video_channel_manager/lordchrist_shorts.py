from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from collections.abc import Callable, Iterable, Sequence
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Literal, TypeVar
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.editorial.youtube_surface_classification import classify_youtube_surface
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.telegram_channel_profile import TelegramChannelProfile, load_channel_profile
from video_channel_manager.telegram_multichannel_release import GenericReleaseItem, GenericReleaseQueue
from video_channel_manager.telegram_multichannel_video import render_video_payload

PROJECT_KEY = "lord-god-strength"
YOUTUBE_CHANNEL_ID = "UCeSJsC6go2c9pdJCuUI1BYA"
YOUTUBE_OAUTH_ALIAS = "fedor-milovanov"
TELEGRAM_CHANNEL_USERNAME = "@lordchrist"
TELEGRAM_PROFILE_PATH = "content/telegram/channels/lordchrist.json"
EDITORIAL_SCHEDULE_PATH = "content/telegram/lordchrist/production-schedule.json"
HISTORICAL_DURATION_BASELINE_PATH = Path(
    "content/telegram/lordchrist/shorts-historical-duration-baseline-20260729.json"
)
KNOWN_DURATION_ONLY_SNAPSHOT_ID = "5b994503-6107-4cbe-adc8-740b50562075"
MAX_TELEGRAM_VIDEO_BYTES = 50_000_000
TRANSPORT_BUDGET_BYTES = 46_000_000
MAX_SHORT_DURATION_SECONDS = 180.0
DEFAULT_TIMEZONE = "Europe/Moscow"
DEFAULT_SLOT_LOCAL_TIME = "17:17"
DEFAULT_EDITORIAL_TIMES = ("09:17", "21:17")
AUDIO_BITRATE_BPS = 128_000
MIN_VIDEO_BITRATE_BPS = 600_000
MAX_VIDEO_BITRATE_BPS = 4_000_000
_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,32}$")
_TRAILING_SHORTS_TAGS_RE = re.compile(
    r"(?:\s+#(?:shorts?|youtube(?:shorts?)?|ютубшортс)\b)+\s*$",
    flags=re.IGNORECASE,
)

ProbeRunner = Callable[[Path], dict[str, Any]]
TranscodeRunner = Callable[[list[str]], None]
ModelT = TypeVar("ModelT", bound=BaseModel)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LordChristShortsPolicy(FrozenModel):
    schema_name: Literal["video-channel-manager.lordchrist-shorts-policy"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    youtube_channel_id: Literal["UCeSJsC6go2c9pdJCuUI1BYA"]
    youtube_oauth_alias: Literal["fedor-milovanov"]
    telegram_channel_username: Literal["@lordchrist"]
    telegram_profile_path: Literal["content/telegram/channels/lordchrist.json"]
    owner_media_sources: tuple[Literal["google_takeout", "local_master"], ...]
    automated_youtube_download_allowed: Literal[False]
    telegram_provider_mutation_allowed: Literal[False]
    telegram_stories_enabled: Literal[False]
    timezone: Literal["Europe/Moscow"]
    slot_local_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    daily_short_limit: Literal[1]
    min_gap_from_editorial_hours: int = Field(ge=4, le=12)
    order: Literal["oldest_first"]
    max_video_bytes: Literal[50_000_000]
    max_duration_seconds: Literal[180]

    @model_validator(mode="after")
    def validate_policy(self) -> "LordChristShortsPolicy":
        if set(self.owner_media_sources) != {"google_takeout", "local_master"}:
            raise ValueError("owner_media_sources must contain exactly google_takeout and local_master")
        ZoneInfo(self.timezone)
        return self


class ShortsInventoryItem(FrozenModel):
    youtube_video_id: str = Field(min_length=6, max_length=32)
    publication_id: str = Field(min_length=20, max_length=96)
    title: str = Field(min_length=1, max_length=500)
    description: str
    published_at: datetime | None
    duration_seconds: int | None = Field(default=None, ge=0, le=3600)
    source_revision: str = Field(min_length=1)
    surface_status: Literal["short", "candidate"]
    classification_reason: str = Field(min_length=1)
    owner_confirmation_required: bool
    canonical_watch_url: str
    canonical_shorts_url: str

    @model_validator(mode="after")
    def validate_identity(self) -> "ShortsInventoryItem":
        if _YOUTUBE_ID_RE.fullmatch(self.youtube_video_id) is None:
            raise ValueError("invalid YouTube video id")
        if self.publication_id != publication_id_for(self.youtube_video_id):
            raise ValueError("publication_id must be derived from the exact YouTube video id")
        expected_watch = f"https://www.youtube.com/watch?v={self.youtube_video_id}"
        expected_shorts = f"https://www.youtube.com/shorts/{self.youtube_video_id}"
        if self.canonical_watch_url != expected_watch or self.canonical_shorts_url != expected_shorts:
            raise ValueError("YouTube URLs must be derived from the exact video id")
        if self.owner_confirmation_required != (self.surface_status == "candidate"):
            raise ValueError("candidate status and owner_confirmation_required disagree")
        return self


class LordChristShortsInventory(FrozenModel):
    schema_name: Literal["video-channel-manager.lordchrist-shorts-inventory"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    youtube_channel_id: Literal["UCeSJsC6go2c9pdJCuUI1BYA"]
    youtube_oauth_alias: Literal["fedor-milovanov"]
    source_snapshot_id: str = Field(min_length=1)
    generated_at: datetime
    items: tuple[ShortsInventoryItem, ...]
    excluded_longform_count: int = Field(ge=0)
    unresolved_non_candidate_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_inventory(self) -> "LordChristShortsInventory":
        video_ids = [item.youtube_video_id for item in self.items]
        publication_ids = [item.publication_id for item in self.items]
        if len(video_ids) != len(set(video_ids)):
            raise ValueError("inventory YouTube video ids must be unique")
        if len(publication_ids) != len(set(publication_ids)):
            raise ValueError("inventory publication ids must be unique")
        return self


class OwnerMediaBinding(FrozenModel):
    youtube_video_id: str = Field(min_length=6, max_length=32)
    source_kind: Literal["google_takeout", "local_master"]
    source_path: str = Field(min_length=1)
    expected_source_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    expected_source_byte_size: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_binding(self) -> "OwnerMediaBinding":
        if _YOUTUBE_ID_RE.fullmatch(self.youtube_video_id) is None:
            raise ValueError("invalid YouTube video id in owner media binding")
        return self


class OwnerMediaBindingManifest(FrozenModel):
    schema_name: Literal["video-channel-manager.lordchrist-shorts-owner-media-bindings"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    youtube_channel_id: Literal["UCeSJsC6go2c9pdJCuUI1BYA"]
    items: tuple[OwnerMediaBinding, ...]

    @model_validator(mode="after")
    def validate_bindings(self) -> "OwnerMediaBindingManifest":
        video_ids = [item.youtube_video_id for item in self.items]
        paths = [str(Path(item.source_path).expanduser()) for item in self.items]
        if len(video_ids) != len(set(video_ids)):
            raise ValueError("owner media binding video ids must be unique")
        if len(paths) != len(set(paths)):
            raise ValueError("one owner file path cannot be bound to multiple YouTube video ids")
        return self


class CandidateApprovalManifest(FrozenModel):
    schema_name: Literal["video-channel-manager.lordchrist-shorts-candidate-approval"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    youtube_channel_id: Literal["UCeSJsC6go2c9pdJCuUI1BYA"]
    inventory_snapshot_id: str = Field(min_length=1)
    approved_video_ids: tuple[str, ...]
    reviewed_by: str = Field(min_length=1, max_length=200)
    reviewed_at: datetime

    @model_validator(mode="after")
    def validate_approval(self) -> "CandidateApprovalManifest":
        if self.reviewed_at.tzinfo is None or self.reviewed_at.utcoffset() is None:
            raise ValueError("candidate approval reviewed_at must be timezone-aware")
        normalized = [value.strip() for value in self.approved_video_ids]
        if any(_YOUTUBE_ID_RE.fullmatch(value) is None for value in normalized):
            raise ValueError("candidate approval contains an invalid YouTube video id")
        if len(normalized) != len(set(normalized)):
            raise ValueError("candidate approval video ids must be unique")
        return self


class MediaProbeSummary(FrozenModel):
    container: str = Field(min_length=1)
    video_codec: str = Field(min_length=1)
    pixel_format: str | None
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    rotation_degrees: int
    duration_seconds: float = Field(gt=0, le=MAX_SHORT_DURATION_SECONDS)
    audio_stream_count: int = Field(ge=0, le=1)
    audio_codec: str | None


class AcceptedShortMedia(FrozenModel):
    youtube_video_id: str = Field(min_length=6, max_length=32)
    publication_id: str = Field(min_length=20, max_length=96)
    source_kind: Literal["google_takeout", "local_master"]
    source_path: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_byte_size: int = Field(gt=0)
    source_probe: MediaProbeSummary
    transport_path: str = Field(min_length=1)
    media_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    media_byte_size: int = Field(gt=0, le=MAX_TELEGRAM_VIDEO_BYTES)
    transport_probe: MediaProbeSummary
    transcoded: bool

    @model_validator(mode="after")
    def validate_accepted_media(self) -> "AcceptedShortMedia":
        if self.publication_id != publication_id_for(self.youtube_video_id):
            raise ValueError("accepted media publication_id mismatch")
        transport = self.transport_probe
        if "mp4" not in {part.strip().casefold() for part in transport.container.split(",")}:
            raise ValueError("accepted Telegram transport container must include mp4")
        if transport.video_codec.casefold() != "h264":
            raise ValueError("accepted Telegram transport must use H.264")
        if (transport.pixel_format or "").casefold() != "yuv420p":
            raise ValueError("accepted Telegram transport must use yuv420p")
        if transport.rotation_degrees != 0:
            raise ValueError(
                "accepted Telegram transport must bake orientation instead of relying on rotation metadata"
            )
        if transport.width > transport.height:
            raise ValueError("accepted Telegram Short media must be square or vertical")
        if transport.audio_stream_count == 1 and (transport.audio_codec or "").casefold() != "aac":
            raise ValueError("accepted Telegram transport audio must be AAC")
        if transport.audio_stream_count == 0 and transport.audio_codec is not None:
            raise ValueError("silent media cannot declare an audio codec")
        if not self.transcoded and self.source_sha256 != self.media_sha256:
            raise ValueError("non-transcoded transport must preserve exact owner bytes")
        return self


class LordChristShortsMediaAcceptance(FrozenModel):
    schema_name: Literal["video-channel-manager.lordchrist-shorts-media-acceptance"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    youtube_channel_id: Literal["UCeSJsC6go2c9pdJCuUI1BYA"]
    inventory_snapshot_id: str = Field(min_length=1)
    provider_access_performed: Literal[False]
    provider_write_performed: Literal[False]
    ffmpeg_version: str | None
    ffprobe_version: str
    items: tuple[AcceptedShortMedia, ...]

    @model_validator(mode="after")
    def validate_acceptance(self) -> "LordChristShortsMediaAcceptance":
        video_ids = [item.youtube_video_id for item in self.items]
        publication_ids = [item.publication_id for item in self.items]
        digests = [item.media_sha256 for item in self.items]
        if len(video_ids) != len(set(video_ids)):
            raise ValueError("accepted media YouTube video ids must be unique")
        if len(publication_ids) != len(set(publication_ids)):
            raise ValueError("accepted media publication ids must be unique")
        if len(digests) != len(set(digests)):
            raise ValueError("exact duplicate media bytes are forbidden across the Shorts feed")
        if any(item.transcoded for item in self.items) and not self.ffmpeg_version:
            raise ValueError("transcoded media acceptance requires an ffmpeg version record")
        return self


class HistoricalDurationBaselineItem(FrozenModel):
    youtube_video_id: str = Field(min_length=6, max_length=32)
    published_on: date
    duration_seconds: int = Field(ge=1, le=180)

    @model_validator(mode="after")
    def validate_item(self) -> "HistoricalDurationBaselineItem":
        if _YOUTUBE_ID_RE.fullmatch(self.youtube_video_id) is None:
            raise ValueError("invalid YouTube video id in historical duration baseline")
        return self


class HistoricalDurationBaseline(FrozenModel):
    schema_name: Literal["video-channel-manager.lordchrist-shorts-historical-duration-baseline"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    youtube_channel_id: Literal["UCeSJsC6go2c9pdJCuUI1BYA"]
    youtube_oauth_alias: Literal["fedor-milovanov"]
    evidence_scope: Literal["historical_duration_only_not_current_provider_state"]
    provider_effect: Literal["impossible"]
    provider_writes_authorized: Literal[False]
    source_snapshot_id: str = Field(min_length=1)
    source_generated_at: datetime
    source_package_filename: str = Field(min_length=1)
    source_record_count: int = Field(ge=1)
    source_channel_video_count: int = Field(ge=1)
    selection_rule: Literal["published_on_or_after_2025-12-08_and_duration_le_180s"]
    owner_file_details_present: Literal[False]
    proven_shorts: Literal[False]
    items: tuple[HistoricalDurationBaselineItem, ...]

    @model_validator(mode="after")
    def validate_baseline(self) -> "HistoricalDurationBaseline":
        if self.source_generated_at.tzinfo is None or self.source_generated_at.utcoffset() is None:
            raise ValueError("historical baseline source_generated_at must be timezone-aware")
        video_ids = [item.youtube_video_id for item in self.items]
        if len(video_ids) != len(set(video_ids)):
            raise ValueError("historical duration baseline YouTube video ids must be unique")
        if not self.items:
            raise ValueError("historical duration baseline must contain at least one item")
        return self


class BaselineReconciliationRecord(FrozenModel):
    youtube_video_id: str = Field(min_length=6, max_length=32)
    historical_published_on: date
    historical_duration_seconds: int = Field(ge=1, le=180)
    fresh_status: Literal[
        "present_as_short",
        "present_as_candidate",
        "present_as_longform",
        "present_unresolved",
        "absent_from_snapshot",
    ]
    fresh_duration_seconds: int | None = Field(default=None, ge=0, le=3600)
    duration_drift_seconds: int | None = None


class BaselineReconciliationCounts(FrozenModel):
    historical_item_count: int = Field(ge=0)
    present_as_short: int = Field(ge=0)
    present_as_candidate: int = Field(ge=0)
    present_as_longform: int = Field(ge=0)
    present_unresolved: int = Field(ge=0)
    absent_from_snapshot: int = Field(ge=0)
    new_shorts_not_in_baseline: int = Field(ge=0)
    new_candidates_not_in_baseline: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> "BaselineReconciliationCounts":
        partitioned = (
            self.present_as_short
            + self.present_as_candidate
            + self.present_as_longform
            + self.present_unresolved
            + self.absent_from_snapshot
        )
        if partitioned != self.historical_item_count:
            raise ValueError("historical baseline reconciliation counts do not partition the frozen ID set")
        return self


class BaselineReconciliationArtifact(FrozenModel):
    schema_name: Literal["video-channel-manager.lordchrist-shorts-baseline-reconciliation"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    youtube_channel_id: Literal["UCeSJsC6go2c9pdJCuUI1BYA"]
    evidence_scope: Literal["historical_duration_only_versus_fresh_owner_snapshot"]
    provider_effect: Literal["impossible"]
    provider_writes_authorized: Literal[False]
    provider_access_performed: Literal[False]
    provider_write_performed: Literal[False]
    source_baseline_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    historical_snapshot_id: str = Field(min_length=1)
    compared_snapshot_id: str = Field(min_length=1)
    counts: BaselineReconciliationCounts
    records: tuple[BaselineReconciliationRecord, ...]
    new_short_video_ids: tuple[str, ...]
    new_candidate_video_ids: tuple[str, ...]

    @model_validator(mode="after")
    def validate_artifact(self) -> "BaselineReconciliationArtifact":
        if self.compared_snapshot_id == self.historical_snapshot_id:
            raise ValueError("fresh snapshot id must differ from the frozen duration-only snapshot")
        if len(self.records) != self.counts.historical_item_count:
            raise ValueError("reconciliation record count differs from historical_item_count")
        if len(self.new_short_video_ids) != self.counts.new_shorts_not_in_baseline:
            raise ValueError("new short id count differs from counts")
        if len(self.new_candidate_video_ids) != self.counts.new_candidates_not_in_baseline:
            raise ValueError("new candidate id count differs from counts")
        return self


class ShortsBacklogStatusItem(FrozenModel):
    youtube_video_id: str = Field(min_length=6, max_length=32)
    publication_id: str = Field(min_length=20, max_length=96)
    surface_status: Literal["short", "candidate"]
    backlog_state: Literal["accepted", "media_missing", "candidate_unconfirmed"]
    media_bound: bool
    media_accepted: bool
    candidate_approved: bool

    @model_validator(mode="after")
    def validate_status(self) -> "ShortsBacklogStatusItem":
        if self.publication_id != publication_id_for(self.youtube_video_id):
            raise ValueError("backlog publication_id must be derived from the exact YouTube video id")
        selected = self.surface_status == "short" or self.candidate_approved
        if self.surface_status == "candidate" and not self.candidate_approved:
            if self.backlog_state != "candidate_unconfirmed":
                raise ValueError("unapproved candidates must be recorded as candidate_unconfirmed")
        elif selected and self.media_accepted:
            if self.backlog_state != "accepted":
                raise ValueError("selected items with accepted owner media must be recorded as accepted")
        elif selected and not self.media_accepted:
            if self.backlog_state != "media_missing":
                raise ValueError("selected items without accepted owner media must be recorded as media_missing")
        else:
            raise ValueError("backlog state is not a valid combination of surface and approval")
        if self.candidate_approved and self.surface_status != "candidate":
            raise ValueError("only inventory candidates may be marked candidate_approved")
        if self.media_accepted and not self.media_bound:
            raise ValueError("accepted media requires a bound owner file")
        return self


class ShortsBacklogStatusCounts(FrozenModel):
    inventory_item_count: int = Field(ge=0)
    accepted: int = Field(ge=0)
    media_missing: int = Field(ge=0)
    candidate_unconfirmed: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> "ShortsBacklogStatusCounts":
        if self.accepted + self.media_missing + self.candidate_unconfirmed != self.inventory_item_count:
            raise ValueError("backlog status counts do not partition the inventory")
        return self


class LordChristShortsBacklogStatus(FrozenModel):
    schema_name: Literal["video-channel-manager.lordchrist-shorts-backlog-status"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    youtube_channel_id: Literal["UCeSJsC6go2c9pdJCuUI1BYA"]
    inventory_snapshot_id: str = Field(min_length=1)
    provider_access_performed: Literal[False]
    provider_write_performed: Literal[False]
    release_authorized: Literal[False]
    counts: ShortsBacklogStatusCounts
    items: tuple[ShortsBacklogStatusItem, ...]

    @model_validator(mode="after")
    def validate_status(self) -> "LordChristShortsBacklogStatus":
        video_ids = [item.youtube_video_id for item in self.items]
        if len(video_ids) != len(set(video_ids)):
            raise ValueError("backlog status YouTube video ids must be unique")
        if len(self.items) != self.counts.inventory_item_count:
            raise ValueError("backlog status item count differs from inventory_item_count")
        return self


class EffectSnapshot(FrozenModel):
    publication_id: str
    state: str
    provider_effect: str


def publication_id_for(video_id: str) -> str:
    value = video_id.strip()
    if _YOUTUBE_ID_RE.fullmatch(value) is None:
        raise ValueError(f"invalid YouTube video id: {video_id!r}")
    return f"lordchrist-short-{value}"


def _read_model(path: Path, model: type[ModelT]) -> ModelT:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid {model.__name__} file {path}: {exc}") from exc


def _write_model(path: Path, value: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.model_dump_json(indent=2) + "\n", encoding="utf-8")


def load_policy(path: Path) -> LordChristShortsPolicy:
    return _read_model(path, LordChristShortsPolicy)


def load_inventory(path: Path) -> LordChristShortsInventory:
    return _read_model(path, LordChristShortsInventory)


def load_bindings(path: Path) -> OwnerMediaBindingManifest:
    return _read_model(path, OwnerMediaBindingManifest)


def load_candidate_approval(path: Path) -> CandidateApprovalManifest:
    return _read_model(path, CandidateApprovalManifest)


def load_media_acceptance(path: Path) -> LordChristShortsMediaAcceptance:
    return _read_model(path, LordChristShortsMediaAcceptance)


def load_historical_baseline(path: Path) -> tuple[HistoricalDurationBaseline, str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read historical duration baseline {path}: {exc}") from exc
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    try:
        baseline = HistoricalDurationBaseline.model_validate_json(raw)
    except ValidationError as exc:
        raise ValueError(f"invalid HistoricalDurationBaseline file {path}: {exc}") from exc
    return baseline, digest


def _fresh_status_for(
    classification_status: str, short_candidate: bool
) -> Literal[
    "present_as_short",
    "present_as_candidate",
    "present_as_longform",
    "present_unresolved",
]:
    if classification_status == "short":
        return "present_as_short"
    if classification_status == "longform":
        return "present_as_longform"
    if short_candidate:
        return "present_as_candidate"
    return "present_unresolved"


def reconcile_historical_baseline(
    package: AuditPackage,
    baseline: HistoricalDurationBaseline,
    *,
    source_baseline_sha256: str,
    as_of: datetime | None = None,
    max_age_hours: int = 48,
) -> BaselineReconciliationArtifact:
    from video_channel_manager.lordchrist_shorts_snapshot_readiness import require_snapshot_ready

    if package.channel.ref.channel_id != YOUTUBE_CHANNEL_ID:
        raise ValueError(
            f"AuditPackage channel mismatch: expected {YOUTUBE_CHANNEL_ID}, got {package.channel.ref.channel_id}"
        )
    if baseline.youtube_channel_id != YOUTUBE_CHANNEL_ID or baseline.project_key != PROJECT_KEY:
        raise ValueError("historical duration baseline is not bound to lord-god-strength")
    compared_snapshot_id = str(package.snapshot_id)
    if compared_snapshot_id == baseline.source_snapshot_id:
        raise ValueError(
            "cannot reconcile the frozen 2026-07-29 duration-only snapshot against itself; "
            "run a fresh read-only video-manager youtube scan"
        )
    require_snapshot_ready(package, as_of=as_of, max_age_hours=max_age_hours)

    videos_by_id = {video.ref.remote_id: video for video in package.videos}
    records: list[BaselineReconciliationRecord] = []
    counts = {
        "present_as_short": 0,
        "present_as_candidate": 0,
        "present_as_longform": 0,
        "present_unresolved": 0,
        "absent_from_snapshot": 0,
    }
    for item in baseline.items:
        video = videos_by_id.get(item.youtube_video_id)
        if video is None:
            status: Literal[
                "present_as_short",
                "present_as_candidate",
                "present_as_longform",
                "present_unresolved",
                "absent_from_snapshot",
            ] = "absent_from_snapshot"
            fresh_duration = None
            drift = None
        else:
            classification = classify_youtube_surface(video)
            status = _fresh_status_for(classification.status, classification.short_candidate)
            fresh_duration = video.duration_seconds
            drift = None if fresh_duration is None else abs(fresh_duration - item.duration_seconds)
        counts[status] += 1
        records.append(
            BaselineReconciliationRecord(
                youtube_video_id=item.youtube_video_id,
                historical_published_on=item.published_on,
                historical_duration_seconds=item.duration_seconds,
                fresh_status=status,
                fresh_duration_seconds=fresh_duration,
                duration_drift_seconds=drift,
            )
        )

    baseline_ids = {item.youtube_video_id for item in baseline.items}
    new_shorts: list[str] = []
    new_candidates: list[str] = []
    for video in package.videos:
        video_id = video.ref.remote_id
        if video_id in baseline_ids:
            continue
        classification = classify_youtube_surface(video)
        if classification.status == "short":
            new_shorts.append(video_id)
        elif classification.short_candidate:
            new_candidates.append(video_id)
    new_shorts.sort()
    new_candidates.sort()

    return BaselineReconciliationArtifact(
        schema_name="video-channel-manager.lordchrist-shorts-baseline-reconciliation",
        schema_version=1,
        project_key=PROJECT_KEY,
        youtube_channel_id=YOUTUBE_CHANNEL_ID,
        evidence_scope="historical_duration_only_versus_fresh_owner_snapshot",
        provider_effect="impossible",
        provider_writes_authorized=False,
        provider_access_performed=False,
        provider_write_performed=False,
        source_baseline_sha256=source_baseline_sha256,
        historical_snapshot_id=baseline.source_snapshot_id,
        compared_snapshot_id=compared_snapshot_id,
        counts=BaselineReconciliationCounts(
            historical_item_count=len(baseline.items),
            present_as_short=counts["present_as_short"],
            present_as_candidate=counts["present_as_candidate"],
            present_as_longform=counts["present_as_longform"],
            present_unresolved=counts["present_unresolved"],
            absent_from_snapshot=counts["absent_from_snapshot"],
            new_shorts_not_in_baseline=len(new_shorts),
            new_candidates_not_in_baseline=len(new_candidates),
        ),
        records=tuple(records),
        new_short_video_ids=tuple(new_shorts),
        new_candidate_video_ids=tuple(new_candidates),
    )


def build_backlog_status(
    inventory: LordChristShortsInventory,
    *,
    bindings: OwnerMediaBindingManifest | None = None,
    acceptance: LordChristShortsMediaAcceptance | None = None,
    candidate_approval: CandidateApprovalManifest | None = None,
) -> LordChristShortsBacklogStatus:
    if inventory.youtube_channel_id != YOUTUBE_CHANNEL_ID or inventory.project_key != PROJECT_KEY:
        raise ValueError("inventory is not bound to lord-god-strength")

    bound_ids: set[str] = set()
    if bindings is not None:
        if bindings.youtube_channel_id != YOUTUBE_CHANNEL_ID or bindings.project_key != PROJECT_KEY:
            raise ValueError("owner media bindings are not bound to lord-god-strength")
        inventory_ids = {item.youtube_video_id for item in inventory.items}
        unknown_bindings = [
            item.youtube_video_id for item in bindings.items if item.youtube_video_id not in inventory_ids
        ]
        if unknown_bindings:
            raise ValueError(
                "owner media binding references video outside the exact Shorts inventory: "
                + ", ".join(unknown_bindings)
            )
        bound_ids = {item.youtube_video_id for item in bindings.items}

    accepted_ids: set[str] = set()
    if acceptance is not None:
        if acceptance.inventory_snapshot_id != inventory.source_snapshot_id:
            raise ValueError("media acceptance belongs to a different YouTube inventory snapshot")
        inventory_ids = {item.youtube_video_id for item in inventory.items}
        unknown_accepted = [
            item.youtube_video_id for item in acceptance.items if item.youtube_video_id not in inventory_ids
        ]
        if unknown_accepted:
            raise ValueError(
                "accepted media references video outside the exact Shorts inventory: " + ", ".join(unknown_accepted)
            )
        accepted_ids = {item.youtube_video_id for item in acceptance.items}

    approved_ids: set[str] = set()
    if candidate_approval is not None:
        if candidate_approval.inventory_snapshot_id != inventory.source_snapshot_id:
            raise ValueError("candidate approval belongs to a different YouTube inventory snapshot")
        candidates = {item.youtube_video_id for item in inventory.items if item.surface_status == "candidate"}
        unknown_approvals = {value.strip() for value in candidate_approval.approved_video_ids} - candidates
        if unknown_approvals:
            raise ValueError(
                "candidate approvals do not match candidate inventory ids: " + ", ".join(sorted(unknown_approvals))
            )
        approved_ids = {value.strip() for value in candidate_approval.approved_video_ids}

    items: list[ShortsBacklogStatusItem] = []
    for item in inventory.items:
        media_bound = item.youtube_video_id in bound_ids
        media_accepted = item.youtube_video_id in accepted_ids
        candidate_approved = item.youtube_video_id in approved_ids
        selected = item.surface_status == "short" or candidate_approved
        if item.surface_status == "candidate" and not candidate_approved:
            state: Literal["accepted", "media_missing", "candidate_unconfirmed"] = "candidate_unconfirmed"
        elif selected and media_accepted:
            state = "accepted"
        else:
            state = "media_missing"
        items.append(
            ShortsBacklogStatusItem(
                youtube_video_id=item.youtube_video_id,
                publication_id=item.publication_id,
                surface_status=item.surface_status,
                backlog_state=state,
                media_bound=media_bound,
                media_accepted=media_accepted,
                candidate_approved=candidate_approved,
            )
        )

    accepted_count = sum(item.backlog_state == "accepted" for item in items)
    missing_count = sum(item.backlog_state == "media_missing" for item in items)
    unconfirmed_count = sum(item.backlog_state == "candidate_unconfirmed" for item in items)
    return LordChristShortsBacklogStatus(
        schema_name="video-channel-manager.lordchrist-shorts-backlog-status",
        schema_version=1,
        project_key=PROJECT_KEY,
        youtube_channel_id=YOUTUBE_CHANNEL_ID,
        inventory_snapshot_id=inventory.source_snapshot_id,
        provider_access_performed=False,
        provider_write_performed=False,
        release_authorized=False,
        counts=ShortsBacklogStatusCounts(
            inventory_item_count=len(items),
            accepted=accepted_count,
            media_missing=missing_count,
            candidate_unconfirmed=unconfirmed_count,
        ),
        items=tuple(items),
    )


def build_inventory(package: AuditPackage, *, include_candidates: bool = True) -> LordChristShortsInventory:
    if package.channel.ref.channel_id != YOUTUBE_CHANNEL_ID:
        raise ValueError(
            f"AuditPackage channel mismatch: expected {YOUTUBE_CHANNEL_ID}, got {package.channel.ref.channel_id}"
        )
    if package.channel.ref.platform.value != "youtube":
        raise ValueError("LordChrist Shorts intake requires a YouTube AuditPackage")

    items: list[ShortsInventoryItem] = []
    excluded_longform = 0
    unresolved_non_candidate = 0
    for video in package.videos:
        if video.ref.channel_id != YOUTUBE_CHANNEL_ID:
            raise ValueError(f"cross-channel video in AuditPackage: {video.ref.remote_id}")
        classification = classify_youtube_surface(video)
        if classification.status == "longform":
            excluded_longform += 1
            continue
        if classification.status == "unknown" and not classification.short_candidate:
            unresolved_non_candidate += 1
            continue
        if classification.status == "unknown" and not include_candidates:
            continue
        status: Literal["short", "candidate"] = "short" if classification.status == "short" else "candidate"
        video_id = video.ref.remote_id
        items.append(
            ShortsInventoryItem(
                youtube_video_id=video_id,
                publication_id=publication_id_for(video_id),
                title=video.title.strip(),
                description=video.description,
                published_at=video.published_at,
                duration_seconds=video.duration_seconds,
                source_revision=video.revision,
                surface_status=status,
                classification_reason=classification.reason,
                owner_confirmation_required=status == "candidate",
                canonical_watch_url=f"https://www.youtube.com/watch?v={video_id}",
                canonical_shorts_url=f"https://www.youtube.com/shorts/{video_id}",
            )
        )

    def sort_key(item: ShortsInventoryItem) -> tuple[float, str]:
        if item.published_at is None:
            return (float("inf"), item.youtube_video_id)
        return (item.published_at.timestamp(), item.youtube_video_id)

    items.sort(key=sort_key)
    return LordChristShortsInventory(
        schema_name="video-channel-manager.lordchrist-shorts-inventory",
        schema_version=1,
        project_key=PROJECT_KEY,
        youtube_channel_id=YOUTUBE_CHANNEL_ID,
        youtube_oauth_alias=YOUTUBE_OAUTH_ALIAS,
        source_snapshot_id=str(package.snapshot_id),
        generated_at=package.generated_at,
        items=tuple(items),
        excluded_longform_count=excluded_longform,
        unresolved_non_candidate_count=unresolved_non_candidate,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _tool_version(tool: str) -> str:
    try:
        completed = subprocess.run([tool, "-version"], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f"required tool unavailable: {tool}") from exc
    first_line = completed.stdout.splitlines()
    return first_line[0].strip() if first_line else tool


def ffprobe_media(path: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f"ffprobe failed for {path}: {exc}") from exc
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"ffprobe returned invalid JSON for {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"ffprobe returned a non-object for {path}")
    return payload


def run_ffmpeg(argv: list[str]) -> None:
    try:
        subprocess.run(argv, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f"ffmpeg conversion failed: {exc}") from exc


def _rotation_degrees(stream: dict[str, Any]) -> int:
    candidates: list[object] = []
    tags = stream.get("tags")
    if isinstance(tags, dict):
        candidates.append(tags.get("rotate"))
    side_data = stream.get("side_data_list")
    if isinstance(side_data, list):
        for item in side_data:
            if isinstance(item, dict):
                candidates.append(item.get("rotation"))
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            rotation = int(round(float(str(candidate))))
        except ValueError:
            continue
        return rotation % 360
    return 0


def _positive_float(value: object) -> float | None:
    try:
        parsed = float(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def normalize_probe(probe: dict[str, Any]) -> MediaProbeSummary:
    streams_raw = probe.get("streams")
    streams = [item for item in streams_raw if isinstance(item, dict)] if isinstance(streams_raw, list) else []
    videos = [item for item in streams if item.get("codec_type") == "video"]
    audios = [item for item in streams if item.get("codec_type") == "audio"]
    if len(videos) != 1:
        raise ValueError(f"expected exactly one video stream, found {len(videos)}")
    if len(audios) > 1:
        raise ValueError(f"at most one audio stream is supported, found {len(audios)}")
    video = videos[0]
    try:
        source_width = int(video["width"])
        source_height = int(video["height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("missing valid video dimensions") from exc
    if source_width <= 0 or source_height <= 0:
        raise ValueError("video dimensions must be positive")
    rotation = _rotation_degrees(video)
    if rotation in {90, 270}:
        width, height = source_height, source_width
    elif rotation in {0, 180}:
        width, height = source_width, source_height
    else:
        raise ValueError(f"unsupported video rotation {rotation}")

    format_raw = probe.get("format")
    format_info = format_raw if isinstance(format_raw, dict) else {}
    duration = _positive_float(video.get("duration")) or _positive_float(format_info.get("duration"))
    if duration is None:
        raise ValueError("media duration is unavailable")
    if duration > MAX_SHORT_DURATION_SECONDS:
        raise ValueError("media exceeds the 180-second Shorts cap")
    if width > height:
        raise ValueError("Short media must be square or vertical after rotation")

    audio_codec: str | None = None
    if audios:
        audio_codec = str(audios[0].get("codec_name") or "") or None
        if audio_codec is None:
            raise ValueError("audio stream codec is unavailable")

    container = str(format_info.get("format_name") or "").strip()
    if not container:
        raise ValueError("media container is unavailable")
    video_codec = str(video.get("codec_name") or "").strip()
    if not video_codec:
        raise ValueError("video codec is unavailable")
    pixel_format = str(video.get("pix_fmt") or "").strip() or None
    return MediaProbeSummary(
        container=container,
        video_codec=video_codec,
        pixel_format=pixel_format,
        width=width,
        height=height,
        rotation_degrees=rotation,
        duration_seconds=duration,
        audio_stream_count=len(audios),
        audio_codec=audio_codec,
    )


def is_telegram_ready(source_path: Path, summary: MediaProbeSummary) -> bool:
    containers = {part.strip().casefold() for part in summary.container.split(",")}
    return (
        "mp4" in containers
        and source_path.stat().st_size <= MAX_TELEGRAM_VIDEO_BYTES
        and summary.video_codec.casefold() == "h264"
        and (summary.pixel_format or "").casefold() == "yuv420p"
        and summary.rotation_degrees == 0
        and summary.width % 2 == 0
        and summary.height % 2 == 0
        and (
            summary.audio_stream_count == 0
            or (summary.audio_stream_count == 1 and (summary.audio_codec or "").casefold() == "aac")
        )
    )


def conversion_argv(source: Path, output: Path, *, source_summary: MediaProbeSummary) -> list[str]:
    duration = source_summary.duration_seconds
    audio_bps = AUDIO_BITRATE_BPS if source_summary.audio_stream_count else 0
    budget_bps = int((TRANSPORT_BUDGET_BYTES * 8) / duration)
    video_bps = min(MAX_VIDEO_BITRATE_BPS, max(MIN_VIDEO_BITRATE_BPS, budget_bps - audio_bps - 100_000))
    argv = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-v",
        "error",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
    ]
    if source_summary.audio_stream_count:
        argv.extend(["-map", "0:a:0"])
    else:
        argv.append("-an")
    argv.extend(
        [
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-b:v",
            str(video_bps),
            "-maxrate",
            str(video_bps),
            "-bufsize",
            str(video_bps * 2),
            "-pix_fmt",
            "yuv420p",
            "-threads",
            "1",
        ]
    )
    if source_summary.audio_stream_count:
        argv.extend(["-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2"])
    argv.extend(["-movflags", "+faststart", str(output)])
    return argv


def _validate_transport(inventory_item: ShortsInventoryItem, path: Path, summary: MediaProbeSummary) -> None:
    containers = {part.strip().casefold() for part in summary.container.split(",")}
    if "mp4" not in containers:
        raise ValueError(f"{inventory_item.youtube_video_id}: transport container is not MP4")
    if path.stat().st_size > MAX_TELEGRAM_VIDEO_BYTES:
        raise ValueError(f"{inventory_item.youtube_video_id}: transport exceeds {MAX_TELEGRAM_VIDEO_BYTES} bytes")
    if summary.video_codec.casefold() != "h264":
        raise ValueError(f"{inventory_item.youtube_video_id}: transport video codec is not H.264")
    if (summary.pixel_format or "").casefold() != "yuv420p":
        raise ValueError(f"{inventory_item.youtube_video_id}: transport pixel format is not yuv420p")
    if summary.rotation_degrees != 0:
        raise ValueError(f"{inventory_item.youtube_video_id}: transport retains rotation metadata")
    if summary.width > summary.height:
        raise ValueError(f"{inventory_item.youtube_video_id}: transport is landscape")
    if summary.width % 2 or summary.height % 2:
        raise ValueError(f"{inventory_item.youtube_video_id}: transport dimensions must be even")
    if summary.audio_stream_count == 1 and (summary.audio_codec or "").casefold() != "aac":
        raise ValueError(f"{inventory_item.youtube_video_id}: transport audio codec is not AAC")
    if (
        inventory_item.duration_seconds is not None
        and abs(summary.duration_seconds - inventory_item.duration_seconds) > 3.0
    ):
        raise ValueError(
            f"{inventory_item.youtube_video_id}: transport duration differs from YouTube inventory by over 3 seconds"
        )


def prepare_owner_media(
    inventory: LordChristShortsInventory,
    bindings: OwnerMediaBindingManifest,
    *,
    output_dir: Path,
    probe_runner: ProbeRunner = ffprobe_media,
    transcode_runner: TranscodeRunner = run_ffmpeg,
    ffprobe_version: str | None = None,
    ffmpeg_version: str | None = None,
) -> LordChristShortsMediaAcceptance:
    inventory_by_id = {item.youtube_video_id: item for item in inventory.items}
    output_dir.mkdir(parents=True, exist_ok=True)
    accepted: list[AcceptedShortMedia] = []
    used_ffmpeg = False
    for binding in bindings.items:
        item = inventory_by_id.get(binding.youtube_video_id)
        if item is None:
            raise ValueError(
                f"owner media binding references video outside the exact Shorts inventory: {binding.youtube_video_id}"
            )
        source = Path(binding.source_path).expanduser().resolve()
        if not source.is_file():
            raise ValueError(f"owner media file does not exist: {source}")

        source_size_before = source.stat().st_size
        source_sha256_before = _sha256(source)
        if source_size_before != binding.expected_source_byte_size:
            raise ValueError(f"{item.youtube_video_id}: owner media byte size differs from frozen binding")
        if source_sha256_before != binding.expected_source_sha256:
            raise ValueError(f"{item.youtube_video_id}: owner media SHA-256 differs from frozen binding")
        if source.stat().st_size != source_size_before:
            raise ValueError(f"{item.youtube_video_id}: owner media changed while hashing")

        source_probe = normalize_probe(probe_runner(source))
        if item.duration_seconds is not None and abs(source_probe.duration_seconds - item.duration_seconds) > 3.0:
            raise ValueError(
                f"{item.youtube_video_id}: owner media duration differs from YouTube inventory by over 3 seconds"
            )

        output = output_dir / f"{item.publication_id}.mp4"
        if output.exists():
            raise ValueError(f"refusing to overwrite an existing prepared transport: {output}")
        transcoded = not is_telegram_ready(source, source_probe)
        if transcoded:
            used_ffmpeg = True
            transcode_runner(conversion_argv(source, output, source_summary=source_probe))
        else:
            shutil.copyfile(source, output)
        if not output.is_file():
            raise ValueError(f"prepared Telegram transport was not created: {output}")

        source_size_after = source.stat().st_size
        source_sha256_after = _sha256(source)
        if source_size_after != source_size_before or source_sha256_after != source_sha256_before:
            output.unlink(missing_ok=True)
            raise ValueError(f"{item.youtube_video_id}: owner media changed during preparation")

        transport_probe = normalize_probe(probe_runner(output))
        _validate_transport(item, output, transport_probe)
        accepted.append(
            AcceptedShortMedia(
                youtube_video_id=item.youtube_video_id,
                publication_id=item.publication_id,
                source_kind=binding.source_kind,
                source_path=str(source),
                source_sha256=source_sha256_before,
                source_byte_size=source_size_before,
                source_probe=source_probe,
                transport_path=str(output.resolve()),
                media_sha256=_sha256(output),
                media_byte_size=output.stat().st_size,
                transport_probe=transport_probe,
                transcoded=transcoded,
            )
        )

    actual_ffprobe_version = ffprobe_version or _tool_version("ffprobe")
    actual_ffmpeg_version = ffmpeg_version
    if used_ffmpeg and actual_ffmpeg_version is None:
        actual_ffmpeg_version = _tool_version("ffmpeg")
    return LordChristShortsMediaAcceptance(
        schema_name="video-channel-manager.lordchrist-shorts-media-acceptance",
        schema_version=1,
        project_key=PROJECT_KEY,
        youtube_channel_id=YOUTUBE_CHANNEL_ID,
        inventory_snapshot_id=inventory.source_snapshot_id,
        provider_access_performed=False,
        provider_write_performed=False,
        ffmpeg_version=actual_ffmpeg_version,
        ffprobe_version=actual_ffprobe_version,
        items=tuple(accepted),
    )


def _clean_title(title: str) -> str:
    cleaned = _TRAILING_SHORTS_TAGS_RE.sub("", " ".join(title.split())).strip(" -—|")
    return cleaned or "Видео"


def render_short_caption(item: ShortsInventoryItem) -> str:
    link = item.canonical_shorts_url
    suffix = f"\n\n▶️ YouTube: {link}"
    available = 1024 - len(suffix)
    title = _clean_title(item.title)
    if len(title) > available:
        title = title[: max(1, available - 1)].rstrip() + "…"
    return title + suffix


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read LordChrist state JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"LordChrist state JSON must be an object: {path}")
    return payload


def _validate_state_identity(path: Path, payload: dict[str, Any]) -> None:
    project_key = payload.get("project_key")
    if project_key is not None and str(project_key) != PROJECT_KEY:
        raise ValueError(f"LordChrist state project mismatch in {path}")
    channel_username = payload.get("channel_username")
    if channel_username is not None and str(channel_username).casefold() != TELEGRAM_CHANNEL_USERNAME.casefold():
        raise ValueError(f"LordChrist state channel mismatch in {path}")
    target = payload.get("target")
    if isinstance(target, dict):
        target_username = target.get("chat_username")
        if target_username is not None and str(target_username).casefold().lstrip(
            "@"
        ) != TELEGRAM_CHANNEL_USERNAME.casefold().lstrip("@"):
            raise ValueError(f"LordChrist state target mismatch in {path}")


def _effect_entries_from_payload(path: Path, payload: dict[str, Any]) -> tuple[EffectSnapshot, ...]:
    _validate_state_identity(path, payload)
    entries = payload.get("entries")
    if isinstance(entries, dict):
        result: list[EffectSnapshot] = []
        for publication_id, raw in entries.items():
            if not isinstance(raw, dict):
                raise ValueError(f"invalid ledger entry {publication_id!r} in {path}")
            result.append(
                EffectSnapshot(
                    publication_id=str(raw.get("publication_id") or publication_id),
                    state=str(raw.get("state") or ""),
                    provider_effect=str(raw.get("provider_effect") or ""),
                )
            )
        return tuple(result)
    if all(key in payload for key in ("publication_id", "state", "provider_effect")):
        return (
            EffectSnapshot(
                publication_id=str(payload["publication_id"]),
                state=str(payload["state"]),
                provider_effect=str(payload["provider_effect"]),
            ),
        )
    return ()


def _retired_publication_id(path: Path, payload: dict[str, Any]) -> str | None:
    if payload.get("schema_name") != "video-channel-manager.lordchrist-research-retirement":
        return None
    _validate_state_identity(path, payload)
    if payload.get("disposition") != "retired_no_replay" or payload.get("provider_retry_forbidden") is not True:
        raise ValueError(f"invalid LordChrist retirement disposition in {path}")
    publication_id = str(payload.get("publication_id") or "").strip()
    if not publication_id:
        raise ValueError(f"LordChrist retirement has no publication_id in {path}")
    return publication_id


def _require_effect_tracks_clear(
    tracks: dict[str, tuple[EffectSnapshot, ...]],
    *,
    retired_publication_ids: frozenset[str] = frozenset(),
) -> set[str]:
    from video_channel_manager.lordchrist_cross_track_effect_guard import (
        require_no_unresolved_provider_effects_across_tracks,
    )

    if not tracks:
        raise ValueError("LordChrist durable state proof contains no provider-effect records")
    retired_by_track = {track: retired_publication_ids for track in tracks}
    require_no_unresolved_provider_effects_across_tracks(
        tracks=tracks,
        retired_publication_ids_by_track=retired_by_track,
    )
    return {entry.publication_id for entries in tracks.values() for entry in entries}


def require_existing_lordchrist_state_clear(paths: Sequence[Path]) -> set[str]:
    if not paths:
        raise ValueError("at least one LordChrist durable state ledger is required")
    tracks: dict[str, tuple[EffectSnapshot, ...]] = {}
    retired: set[str] = set()
    for index, path in enumerate(paths):
        payload = _read_json_object(path)
        entries = _effect_entries_from_payload(path, payload)
        if not entries:
            raise ValueError(f"LordChrist state file contains no provider-effect entries: {path}")
        tracks[f"ledger{index + 1}"] = entries
        retirement_path = path.parent / "retirement.json"
        if retirement_path.is_file():
            retirement_payload = _read_json_object(retirement_path)
            retired_id = _retired_publication_id(retirement_path, retirement_payload)
            if retired_id is not None:
                retired.add(retired_id)
    return _require_effect_tracks_clear(tracks, retired_publication_ids=frozenset(retired))


def require_lordchrist_state_root_clear(state_root: Path) -> set[str]:
    root = state_root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"LordChrist durable state root does not exist: {root}")
    required_relative = (
        Path("publication-ledger.json"),
        Path("research-v2/publication-ledger.json"),
        Path("research-v2/retirement.json"),
        Path("rich-v1/live-canary-ledger.json"),
    )
    missing = [str(relative) for relative in required_relative if not (root / relative).is_file()]
    if missing:
        raise ValueError("LordChrist durable state root is incomplete; missing: " + ", ".join(missing))

    tracks: dict[str, tuple[EffectSnapshot, ...]] = {}
    retired: set[str] = set()
    for path in sorted(root.rglob("*.json")):
        payload = _read_json_object(path)
        retired_id = _retired_publication_id(path, payload)
        if retired_id is not None:
            retired.add(retired_id)
        entries = _effect_entries_from_payload(path, payload)
        if entries:
            tracks[path.relative_to(root).as_posix()] = entries
    return _require_effect_tracks_clear(tracks, retired_publication_ids=frozenset(retired))


def _minutes_of_day(value: str) -> int:
    try:
        hour_text, minute_text = value.split(":", maxsplit=1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"invalid local time: {value!r}") from exc
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"invalid local time: {value!r}")
    return hour * 60 + minute


def require_min_editorial_gap(policy: LordChristShortsPolicy, editorial_times: Sequence[str]) -> None:
    short_minutes = _minutes_of_day(policy.slot_local_time)
    required_gap = policy.min_gap_from_editorial_hours * 60
    for editorial_time in editorial_times:
        editorial_minutes = _minutes_of_day(editorial_time)
        delta = abs(short_minutes - editorial_minutes)
        circular_gap = min(delta, 24 * 60 - delta)
        if circular_gap < required_gap:
            raise ValueError(
                f"Shorts slot {policy.slot_local_time} is only {circular_gap} minutes from editorial slot "
                f"{editorial_time}; policy requires at least {required_gap} minutes"
            )


def load_and_validate_editorial_schedule(path: Path, policy: LordChristShortsPolicy) -> tuple[str, str]:
    payload = _read_json_object(path)
    if payload.get("project_key") != PROJECT_KEY:
        raise ValueError("editorial schedule project differs from LordChrist")
    if str(payload.get("channel_username") or "").casefold() != TELEGRAM_CHANNEL_USERNAME.casefold():
        raise ValueError("editorial schedule channel differs from LordChrist")
    if payload.get("timezone") != policy.timezone:
        raise ValueError("editorial schedule timezone differs from Shorts policy")
    primary = str(payload.get("primary_time") or "")
    catchup = str(payload.get("catchup_time") or "")
    require_min_editorial_gap(policy, (primary, catchup))
    return primary, catchup


def _release_identity(
    inventory: LordChristShortsInventory,
    selected: Sequence[ShortsInventoryItem],
    media_by_id: dict[str, AcceptedShortMedia],
    *,
    start_date: date,
    policy: LordChristShortsPolicy,
    profile: TelegramChannelProfile,
) -> str:
    payload = {
        "project_key": PROJECT_KEY,
        "channel_username": TELEGRAM_CHANNEL_USERNAME,
        "profile_sha256": profile.digest,
        "inventory_snapshot_id": inventory.source_snapshot_id,
        "start_date": start_date.isoformat(),
        "timezone": policy.timezone,
        "slot_local_time": policy.slot_local_time,
        "items": [
            {
                "publication_id": item.publication_id,
                "media_sha256": media_by_id[item.youtube_video_id].media_sha256,
            }
            for item in selected
        ],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    suffix = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    return f"lordchrist-shorts-{start_date.isoformat()}-{suffix}"


def build_provider_inert_release(
    inventory: LordChristShortsInventory,
    acceptance: LordChristShortsMediaAcceptance,
    *,
    profile: TelegramChannelProfile,
    policy: LordChristShortsPolicy,
    start_date: date,
    candidate_approval: CandidateApprovalManifest | None = None,
    existing_publication_ids: Iterable[str] = (),
    editorial_times: Sequence[str] = DEFAULT_EDITORIAL_TIMES,
) -> GenericReleaseQueue:
    if (
        profile.project_key != PROJECT_KEY
        or profile.channel_username.casefold() != TELEGRAM_CHANNEL_USERNAME.casefold()
    ):
        raise ValueError("Telegram profile is not the canonical LordChrist profile")
    if profile.provider_writes_authorized:
        raise ValueError("Shorts release builder requires a write-disabled LordChrist profile")
    if profile.timezone != policy.timezone or profile.daily_verified_limit != policy.daily_short_limit:
        raise ValueError("LordChrist profile and Shorts policy cadence disagree")
    if acceptance.inventory_snapshot_id != inventory.source_snapshot_id:
        raise ValueError("media acceptance belongs to a different YouTube inventory snapshot")
    require_min_editorial_gap(policy, editorial_times)

    media_by_id = {item.youtube_video_id: item for item in acceptance.items}
    candidates = {item.youtube_video_id for item in inventory.items if item.surface_status == "candidate"}
    approved: set[str] = set()
    if candidate_approval is not None:
        if candidate_approval.inventory_snapshot_id != inventory.source_snapshot_id:
            raise ValueError("candidate approval belongs to a different YouTube inventory snapshot")
        approved = {value.strip() for value in candidate_approval.approved_video_ids}
        unknown_approvals = approved - candidates
        if unknown_approvals:
            raise ValueError(
                "candidate approvals do not match candidate inventory ids: " + ", ".join(sorted(unknown_approvals))
            )

    selected = [item for item in inventory.items if item.surface_status == "short" or item.youtube_video_id in approved]
    missing_media = [item.youtube_video_id for item in selected if item.youtube_video_id not in media_by_id]
    if missing_media:
        raise ValueError("exact accepted owner media is missing for: " + ", ".join(missing_media))
    if not selected:
        raise ValueError("no exact Shorts are ready for a provider-inert release")

    existing = set(existing_publication_ids)
    collisions = sorted(item.publication_id for item in selected if item.publication_id in existing)
    if collisions:
        raise ValueError("publication ids already exist in LordChrist durable state: " + ", ".join(collisions))

    hour, minute = (int(part) for part in policy.slot_local_time.split(":", maxsplit=1))
    zone = ZoneInfo(policy.timezone)
    first_slot = datetime.combine(start_date, time(hour=hour, minute=minute), tzinfo=zone)
    release_items: list[GenericReleaseItem] = []
    for index, item in enumerate(selected):
        media = media_by_id[item.youtube_video_id]
        runtime_path = f".runtime/lordchrist-shorts/{item.publication_id}.mp4"
        payload = render_video_payload(
            profile,
            publication_id=item.publication_id,
            caption=render_short_caption(item),
            media_path=runtime_path,
            media_sha256=media.media_sha256,
            media_byte_size=media.media_byte_size,
            media_filename=f"{item.publication_id}.mp4",
        )
        release_items.append(
            GenericReleaseItem(
                sequence=index + 1,
                publication_id=item.publication_id,
                scheduled_at=first_slot + timedelta(days=index),
                source_sha256=media.media_sha256,
                payload=payload,
            )
        )

    return GenericReleaseQueue(
        schema_name="video-channel-manager.telegram-release-queue",
        schema_version=1,
        release_id=_release_identity(
            inventory,
            selected,
            media_by_id,
            start_date=start_date,
            policy=policy,
            profile=profile,
        ),
        project_key=PROJECT_KEY,
        channel_username=TELEGRAM_CHANNEL_USERNAME,
        profile_sha256=profile.digest,
        timezone=policy.timezone,
        daily_verified_limit=policy.daily_short_limit,
        target_binding_sha256=None,
        chat_id=None,
        bot_id=None,
        bot_username=None,
        release_authorized=False,
        reviewed_candidate_sha256=None,
        reviewed_by=None,
        reviewed_at=None,
        items=tuple(release_items),
    )


def _load_audit(path: Path) -> AuditPackage:
    try:
        return AuditPackage.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid YouTube AuditPackage {path}: {exc}") from exc


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Provider-inert LordChrist YouTube Shorts intake, owner-media preparation, and release planning."
    )
    sub = root.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-policy")
    validate.add_argument("--policy", type=Path, default=Path("content/telegram/lordchrist/shorts-feed-policy.json"))
    validate.add_argument("--editorial-schedule", type=Path, default=Path(EDITORIAL_SCHEDULE_PATH))

    inventory = sub.add_parser("inventory")
    inventory.add_argument("--audit", type=Path, required=True)
    inventory.add_argument("--output", type=Path, required=True)
    inventory.add_argument("--exclude-candidates", action="store_true")
    inventory.add_argument("--max-snapshot-age-hours", type=int, default=48)

    prepare = sub.add_parser("prepare-media")
    prepare.add_argument("--inventory", type=Path, required=True)
    prepare.add_argument("--bindings", type=Path, required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)

    release = sub.add_parser("build-release")
    release.add_argument("--inventory", type=Path, required=True)
    release.add_argument("--media", type=Path, required=True)
    release.add_argument("--profile", type=Path, default=Path(TELEGRAM_PROFILE_PATH))
    release.add_argument("--policy", type=Path, default=Path("content/telegram/lordchrist/shorts-feed-policy.json"))
    release.add_argument("--editorial-schedule", type=Path, default=Path(EDITORIAL_SCHEDULE_PATH))
    release.add_argument("--start-date", type=date.fromisoformat, required=True)
    release.add_argument("--candidate-approval", type=Path)
    release.add_argument("--state-root", type=Path, required=True)
    release.add_argument("--output", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "validate-policy":
            policy = load_policy(args.policy)
            load_and_validate_editorial_schedule(args.editorial_schedule, policy)
            print(policy.model_dump_json(indent=2))
            return 0
        if args.command == "inventory":
            from video_channel_manager.lordchrist_shorts_snapshot_readiness import require_snapshot_ready

            package = _load_audit(args.audit)
            require_snapshot_ready(package, max_age_hours=args.max_snapshot_age_hours)
            inventory_result = build_inventory(package, include_candidates=not args.exclude_candidates)
            _write_model(args.output, inventory_result)
            print(
                json.dumps(
                    {
                        "items": len(inventory_result.items),
                        "exact_shorts": sum(item.surface_status == "short" for item in inventory_result.items),
                        "candidates": sum(item.surface_status == "candidate" for item in inventory_result.items),
                        "excluded_longform": inventory_result.excluded_longform_count,
                        "unresolved_non_candidate": inventory_result.unresolved_non_candidate_count,
                        "output": str(args.output),
                        "provider_write_performed": False,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if args.command == "reconcile-baseline":
            from video_channel_manager.lordchrist_shorts_snapshot_readiness import require_snapshot_ready

            package = _load_audit(args.audit)
            require_snapshot_ready(package, max_age_hours=args.max_snapshot_age_hours)
            baseline, digest = load_historical_baseline(args.baseline)
            reconciliation = reconcile_historical_baseline(
                package,
                baseline,
                source_baseline_sha256=digest,
                max_age_hours=args.max_snapshot_age_hours,
            )
            _write_model(args.output, reconciliation)
            print(
                json.dumps(
                    {
                        "historical_item_count": reconciliation.counts.historical_item_count,
                        "present_as_short": reconciliation.counts.present_as_short,
                        "present_as_candidate": reconciliation.counts.present_as_candidate,
                        "present_as_longform": reconciliation.counts.present_as_longform,
                        "present_unresolved": reconciliation.counts.present_unresolved,
                        "absent_from_snapshot": reconciliation.counts.absent_from_snapshot,
                        "new_shorts_not_in_baseline": reconciliation.counts.new_shorts_not_in_baseline,
                        "new_candidates_not_in_baseline": reconciliation.counts.new_candidates_not_in_baseline,
                        "compared_snapshot_id": reconciliation.compared_snapshot_id,
                        "output": str(args.output),
                        "provider_write_performed": False,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if args.command == "backlog-status":
            inventory_result = load_inventory(args.inventory)
            status = build_backlog_status(
                inventory_result,
                bindings=load_bindings(args.bindings) if args.bindings else None,
                acceptance=load_media_acceptance(args.media) if args.media else None,
                candidate_approval=load_candidate_approval(args.candidate_approval)
                if args.candidate_approval
                else None,
            )
            _write_model(args.output, status)
            print(
                json.dumps(
                    {
                        "inventory_item_count": status.counts.inventory_item_count,
                        "accepted": status.counts.accepted,
                        "media_missing": status.counts.media_missing,
                        "candidate_unconfirmed": status.counts.candidate_unconfirmed,
                        "release_authorized": status.release_authorized,
                        "output": str(args.output),
                        "provider_write_performed": False,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if args.command == "prepare-media":
            media_result = prepare_owner_media(
                load_inventory(args.inventory),
                load_bindings(args.bindings),
                output_dir=args.output_dir,
            )
            _write_model(args.output, media_result)
            print(
                json.dumps(
                    {
                        "accepted": len(media_result.items),
                        "transcoded": sum(item.transcoded for item in media_result.items),
                        "output": str(args.output),
                        "provider_access_performed": False,
                        "provider_write_performed": False,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if args.command == "build-release":
            inventory_result = load_inventory(args.inventory)
            policy = load_policy(args.policy)
            editorial_times = load_and_validate_editorial_schedule(args.editorial_schedule, policy)
            existing_ids = require_lordchrist_state_root_clear(args.state_root)
            approval = load_candidate_approval(args.candidate_approval) if args.candidate_approval else None
            release_result = build_provider_inert_release(
                inventory_result,
                load_media_acceptance(args.media),
                profile=load_channel_profile(args.profile),
                policy=policy,
                start_date=args.start_date,
                candidate_approval=approval,
                existing_publication_ids=existing_ids,
                editorial_times=editorial_times,
            )
            _write_model(args.output, release_result)
            print(
                json.dumps(
                    {
                        "release_id": release_result.release_id,
                        "items": len(release_result.items),
                        "release_authorized": release_result.release_authorized,
                        "provider_write_performed": False,
                        "output": str(args.output),
                    },
                    ensure_ascii=False,
                )
            )
            return 0
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2
    raise RuntimeError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
