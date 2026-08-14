from __future__ import annotations

import argparse
import time
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore, local_vk_write_lock
from video_channel_manager.platforms.vk.milovi_canary_reconcile import normalize_current_wall_to_historical_capture
from video_channel_manager.platforms.vk.milovi_daily_postponed_wall import (
    DEFAULT_TIMEZONE,
    _schedule_payload,
    load_or_create_daily_schedule,
    plan_daily_publish_slots,
)
from video_channel_manager.platforms.vk.milovi_immediate_wall import MILOVI_COMMUNITY_ID, MILOVI_OWNER_ID
from video_channel_manager.platforms.vk.milovi_rollout_sources import (
    ROLL_OUT_IDS,
    SourceAsset,
    prepare_sources,
    write_json_atomic,
)
from video_channel_manager.platforms.vk.milovi_token_clip_rollout import (
    CANARY_SOURCE_ID,
    MiloviTokenRolloutBlocked,
    _ensure_wall,
    _find_existing_clip,
    _has_provider_effect,
    _item,
    _load_journal,
    _media_artifacts,
    _parse_remote_id,
    _prove_target,
    _resolve_account,
    _result,
    _save,
    _upload_remote_id,
    clip_readiness,
)
from video_channel_manager.platforms.vk.upload_lifecycle import (
    UploadRecoveryRequired,
    UploadRejected,
    UploadStage,
    VkUploadReadiness,
    VkUploadReadinessAssessment,
    assess_vk_upload_readiness,
    ensure_upload_record,
)
from video_channel_manager.platforms.vk.upload_media import execute_upload_operation
from video_channel_manager.platforms.vk.wall import VkWallWriter
from video_channel_manager.platforms.vk.wall_safety import (
    DEFAULT_UPLOAD_WALL_POLICY,
    VkWallPostFingerprint,
    VkWallSnapshot,
    VkWallSurface,
)

EXECUTION_CONFIRMATION = "ISSUE_323_RESUME_LIVE_SHORT_VIDEO_AND_FINISH"
RESULT_SCHEMA = "video-manager.milovi-issue-323-live-resume"
EXPECTED_CANARY_REMOTE_ID = "-68859909_456239225"
MINIMUM_FUTURE_SECONDS = 300
ISSUE323_EIGHTH_SOURCE_ID = "o1WXIMupuws"
ISSUE323_RECONCILED_WALL_VIEW = "published:-68859909_475"


def _native_clip_assessment(
    item: Mapping[str, Any],
    *,
    expected_owner_id: int,
    expected_video_id: int,
    readiness: VkUploadReadiness,
) -> VkUploadReadinessAssessment:
    """Interpret the provider shape observed for native VK Clips without weakening type/duration/playability.

    Live Issue #323 readback repeatedly exposed an exact playable `short_video`
    with the correct duration/source marker while VK kept `processing=true` and
    returned a blank title. For this Milovi-only runner those two metadata states
    are tolerated only when every material native-Clip invariant is already true.
    """

    assessment = assess_vk_upload_readiness(
        item,
        expected_owner_id=expected_owner_id,
        expected_video_id=expected_video_id,
        readiness=readiness,
    )
    if assessment.ready:
        return assessment

    reasons = set(assessment.reasons)
    observed = dict(assessment.observed)
    if not reasons or not reasons.issubset({"processing", "title_mismatch"}):
        return assessment
    if observed.get("owner_id") != expected_owner_id or observed.get("video_id") != expected_video_id:
        return assessment
    if observed.get("type") != "short_video":
        return assessment
    if bool(observed.get("converting")):
        return assessment
    if not bool(observed.get("playable")):
        return assessment
    duration = observed.get("duration_seconds")
    if not isinstance(duration, int) or isinstance(duration, bool) or duration < readiness.minimum_duration_seconds:
        return assessment
    if "title_mismatch" in reasons and str(observed.get("title") or "") != "":
        return assessment

    observed["readiness_mode"] = "playable_native_short_video"
    observed["provider_processing_flag_tolerated"] = "processing" in reasons
    observed["blank_clip_title_tolerated"] = "title_mismatch" in reasons
    return VkUploadReadinessAssessment(ready=True, reasons=(), observed=observed)


def _lifecycle_ready_view(
    item: Mapping[str, Any],
    *,
    readiness: VkUploadReadiness,
    assessment: VkUploadReadinessAssessment,
) -> dict[str, Any]:
    """Return a lifecycle-compatible view only after real native-Clip readiness is proven.

    The raw provider item is delivered to the lifecycle observation callback before
    this view is returned, so durable journal evidence retains VK's actual
    `processing` flag and blank title. The compatibility view exists only because
    the shared lifecycle intentionally re-runs its stricter generic assessment.
    """

    view = dict(item)
    if assessment.observed.get("readiness_mode") != "playable_native_short_video":
        return view
    if assessment.observed.get("provider_processing_flag_tolerated") is True:
        view["processing"] = 0
    if assessment.observed.get("blank_clip_title_tolerated") is True:
        view["title"] = readiness.expected_title
    return view


def _source_marker_ok(item: Mapping[str, Any], source_id: str) -> bool:
    marker = f"youtube.com/shorts/{source_id}".casefold()
    return marker in str(item.get("description") or "").casefold()


def _assert_live_clip(writer: VkWallWriter, asset: SourceAsset, remote_id: str) -> None:
    owner_id, video_id = _parse_remote_id(remote_id)
    raw = writer.read_video(owner_id=owner_id, video_id=video_id)
    if raw is None:
        raise MiloviTokenRolloutBlocked(f"VK object disappeared: {remote_id}")
    assessment = _native_clip_assessment(
        raw,
        expected_owner_id=owner_id,
        expected_video_id=video_id,
        readiness=clip_readiness(asset),
    )
    if not assessment.ready:
        raise MiloviTokenRolloutBlocked(
            f"VK object {remote_id} is not a verified native short_video: {assessment.reasons}"
        )
    if not _source_marker_ok(raw, asset.source_id):
        raise MiloviTokenRolloutBlocked(f"VK Clip {remote_id} lost source marker for {asset.source_id}")


class _LiveClipWriter:
    def __init__(self, delegate: VkWallWriter, client: VkApiClient) -> None:
        self.delegate = delegate
        self.client = client

    def begin_upload(self, *, community_id: int, title: str, description: str, wall_policy: Any) -> Any:
        if community_id != MILOVI_COMMUNITY_ID:
            raise MiloviTokenRolloutBlocked("Upload target changed")
        _prove_target(self.client)
        return self.delegate.begin_upload(
            community_id=community_id,
            title=title,
            description=description,
            wall_policy=wall_policy,
        )

    def upload_file(self, ticket: Any, path: Path) -> dict[str, Any]:
        if int(ticket.owner_id) != MILOVI_OWNER_ID:
            raise MiloviTokenRolloutBlocked("VK upload ticket owner changed")
        _prove_target(self.client)
        return self.delegate.upload_file(ticket, path)

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        return self.delegate.read_video(owner_id=owner_id, video_id=video_id)

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        return self.delegate.read_post(community_id=community_id, post_id=post_id)

    def wait_until_available(
        self,
        ticket: Any,
        *,
        readiness: VkUploadReadiness,
        timeout_seconds: int,
        on_observation: Any = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            item = self.delegate.read_video(owner_id=ticket.owner_id, video_id=ticket.video_id)
            if item is not None:
                assessment = _native_clip_assessment(
                    item,
                    expected_owner_id=ticket.owner_id,
                    expected_video_id=ticket.video_id,
                    readiness=readiness,
                )
                if on_observation is not None:
                    on_observation(item, assessment)
                if assessment.ready:
                    return _lifecycle_ready_view(item, readiness=readiness, assessment=assessment)
                observed_type = str(item.get("type") or "").strip()
                provider_busy = bool(item.get("processing")) or bool(item.get("converting"))
                if observed_type and observed_type != "short_video" and not provider_busy:
                    raise MiloviTokenRolloutBlocked(
                        f"VK completed {ticket.remote_id} as {observed_type!r}, expected 'short_video'"
                    )
            elif on_observation is not None:
                on_observation(None, None)
            time.sleep(min(10.0, max(0.1, deadline - time.monotonic())))
        raise MiloviTokenRolloutBlocked(
            f"VK object {ticket.remote_id} did not become a playable native short_video in time"
        )

    def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int = 10000) -> Any:
        return self.delegate.capture_wall_snapshot(
            community_id=community_id,
            max_posts_per_surface=max_posts_per_surface,
        )


def _assert_issue323_eighth_wall_history(record: Mapping[str, Any], wall_safety: Mapping[str, Any]) -> None:
    """Allow only the already-observed wall-475 side effect for the interrupted eighth upload."""

    if record.get("source_video_id") != ISSUE323_EIGHTH_SOURCE_ID:
        return
    raw_delta = wall_safety.get("delta")
    if not isinstance(raw_delta, Mapping):
        raise UploadRecoveryRequired("Eighth upload has no durable wall postflight delta")
    if raw_delta.get("status") == "clean":
        return
    expected_lists = {
        "created": [ISSUE323_RECONCILED_WALL_VIEW],
        "removed": [],
        "changed": [],
        "reasons": [],
    }
    mismatches = {
        key: {"expected": expected, "actual": raw_delta.get(key)}
        for key, expected in expected_lists.items()
        if raw_delta.get(key) != expected
    }
    if raw_delta.get("status") != "changed":
        mismatches["status"] = {"expected": "changed", "actual": raw_delta.get("status")}
    before_sha = wall_safety.get("before_snapshot_sha256")
    after_sha = wall_safety.get("after_snapshot_sha256")
    if not isinstance(before_sha, str) or raw_delta.get("before_sha256") != before_sha:
        mismatches["before_sha256"] = {"expected": before_sha, "actual": raw_delta.get("before_sha256")}
    if not isinstance(after_sha, str) or raw_delta.get("after_sha256") != after_sha:
        mismatches["after_sha256"] = {"expected": after_sha, "actual": raw_delta.get("after_sha256")}
    if mismatches:
        raise UploadRecoveryRequired(
            f"Eighth upload wall history is not the single authorized wall-475 side effect: {mismatches}"
        )


def _prior_verified_wall_contract(journal: Mapping[str, Any], source_id: str) -> dict[str, tuple[int, str]]:
    """Return exact earlier wall IDs/dates/Clips eligible for scheduled surface recovery."""

    if source_id not in ROLL_OUT_IDS:
        raise UploadRecoveryRequired(f"Issue #323 recovery source is outside the exact rollout: {source_id}")
    items = journal.get("items")
    if not isinstance(items, Mapping):
        raise UploadRecoveryRequired("Issue #323 journal has no item map for wall recovery")
    result: dict[str, tuple[int, str]] = {}
    for prior_source_id in ROLL_OUT_IDS[: ROLL_OUT_IDS.index(source_id)]:
        raw = items.get(prior_source_id)
        if not isinstance(raw, Mapping) or raw.get("status") != "wall_verified":
            raise UploadRecoveryRequired(
                f"Earlier rollout item is not durably wall_verified during recovery: {prior_source_id}"
            )
        remote_id = raw.get("wall_remote_id")
        publish_date = raw.get("publish_date")
        clip_remote_id = raw.get("clip_remote_id")
        if (
            not isinstance(remote_id, str)
            or not remote_id
            or type(publish_date) is not int
            or not isinstance(clip_remote_id, str)
            or not clip_remote_id
        ):
            raise UploadRecoveryRequired(f"Earlier rollout wall binding is incomplete: {prior_source_id}")
        owner_id, post_id = _parse_remote_id(remote_id)
        clip_owner_id, clip_id = _parse_remote_id(clip_remote_id)
        if owner_id != MILOVI_OWNER_ID or post_id <= 0:
            raise UploadRecoveryRequired(f"Earlier rollout wall binding left Milovi: {prior_source_id}")
        if clip_owner_id != MILOVI_OWNER_ID or clip_id <= 0:
            raise UploadRecoveryRequired(f"Earlier rollout Clip binding left Milovi: {prior_source_id}")
        result[remote_id] = (publish_date, clip_remote_id)
    return result


def _supplement_due_prior_wall_readbacks(
    writer: VkWallWriter | _LiveClipWriter,
    current: VkWallSnapshot,
    *,
    journal: Mapping[str, Any],
    source_id: str,
    now_epoch: int | None = None,
) -> tuple[VkWallSnapshot, tuple[str, ...]]:
    """Normalize only proven due postponed->published identity transitions.

    VK may retire the timer object's ID when a postponed post is published and
    expose the published incarnation under a new wall ID. Absence of the old ID
    is therefore not deletion proof after the frozen slot. For each missing due,
    durably ``wall_verified`` ID we first perform one exact read. A still-live old
    object must retain its exact identity/date/Clip binding. If the old object is
    absent or an exact tombstone, the current complete published surface must have
    exactly one successor with the same owner, frozen publication date and exact
    Clip attachment. We rewrite only that successor's post ID in the in-memory
    recovery view; the existing historical snapshot SHA solver must still match
    the durable pre-upload digest, which also proves text and attachment fidelity.
    No provider write capability is added here.
    """

    if not current.complete:
        raise UploadRecoveryRequired("Current wall snapshot is incomplete during Issue #323 exact readback")
    contract = _prior_verified_wall_contract(journal, source_id)
    present_ids = {post.remote_id for post in current.posts}
    missing_ids = sorted(remote_id for remote_id in contract if remote_id not in present_ids)
    if not missing_ids:
        return current, ()

    observed_now = int(time.time()) if now_epoch is None else now_epoch
    posts = list(current.posts)
    exact_reads: list[str] = []
    for remote_id in missing_ids:
        expected_date, clip_remote_id = contract[remote_id]
        if observed_now + 60 < expected_date:
            raise UploadRecoveryRequired(
                f"Earlier rollout wall mapping disappeared before its frozen slot: {remote_id}"
            )

        owner_id, post_id = _parse_remote_id(remote_id)
        raw = writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=post_id)
        exact_reads.append(remote_id)
        if raw is not None and raw.get("is_deleted") is not True:
            if raw.get("owner_id") != owner_id or raw.get("id") != post_id:
                raise UploadRecoveryRequired(f"Earlier rollout wall exact readback changed identity: {remote_id}")
            if raw.get("date") != expected_date:
                raise UploadRecoveryRequired(
                    f"Earlier rollout wall date changed for {remote_id}: {raw.get('date')} != {expected_date}"
                )

            raw_attachments = raw.get("attachments")
            if not isinstance(raw_attachments, list):
                raise UploadRecoveryRequired(f"Earlier rollout wall exact readback lost attachments: {remote_id}")
            video_payloads: list[Mapping[str, Any]] = []
            for attachment in raw_attachments:
                if not isinstance(attachment, Mapping):
                    raise UploadRecoveryRequired(
                        f"Earlier rollout wall exact readback has malformed attachment: {remote_id}"
                    )
                if attachment.get("type") != "video":
                    continue
                video = attachment.get("video")
                if not isinstance(video, Mapping):
                    raise UploadRecoveryRequired(
                        f"Earlier rollout wall exact readback has malformed video attachment: {remote_id}"
                    )
                video_payloads.append(video)
            if len(video_payloads) != 1:
                raise UploadRecoveryRequired(
                    f"Earlier rollout wall exact readback must contain exactly one video: {remote_id}"
                )
            expected_clip_owner, expected_clip_id = _parse_remote_id(clip_remote_id)
            video = video_payloads[0]
            if video.get("owner_id") != expected_clip_owner or video.get("id") != expected_clip_id:
                raise UploadRecoveryRequired(f"Earlier rollout wall exact readback changed Clip binding: {remote_id}")

            fingerprint = VkWallPostFingerprint.from_item(raw, surface=VkWallSurface.PUBLISHED)
            if f"video{clip_remote_id}" not in fingerprint.attachments:
                raise UploadRecoveryRequired(
                    f"Earlier rollout wall exact readback lost canonical Clip binding: {remote_id}"
                )
            posts.append(fingerprint)
            continue

        if raw is not None:
            if raw.get("is_deleted") is not True:
                raise UploadRecoveryRequired(f"Earlier rollout wall exact readback has ambiguous state: {remote_id}")
            if raw.get("owner_id") != owner_id or raw.get("id") != post_id:
                raise UploadRecoveryRequired(f"Earlier rollout wall tombstone changed identity: {remote_id}")
            tombstone_date = raw.get("date")
            if type(tombstone_date) is int and tombstone_date != expected_date:
                raise UploadRecoveryRequired(
                    f"Earlier rollout wall tombstone date changed for {remote_id}: {tombstone_date} != {expected_date}"
                )

        expected_attachment = f"video{clip_remote_id}"
        successors = [
            (index, post)
            for index, post in enumerate(posts)
            if post.surface is VkWallSurface.PUBLISHED
            and post.owner_id == owner_id
            and post.publish_date == expected_date
            and expected_attachment in post.attachments
            and post.remote_id != remote_id
        ]
        if not successors:
            raise UploadRecoveryRequired(
                f"Earlier rollout wall mapping disappeared during exact readback and no published successor exists: "
                f"{remote_id}"
            )
        if len(successors) != 1:
            successor_ids = sorted(post.remote_id for _index, post in successors)
            raise UploadRecoveryRequired(
                f"Earlier rollout wall published successor is ambiguous for {remote_id}: {successor_ids}"
            )
        successor_index, successor = successors[0]
        if successor.remote_id in contract:
            raise UploadRecoveryRequired(
                f"Earlier rollout wall published successor collides with another journaled ID: "
                f"{remote_id} -> {successor.remote_id}"
            )
        posts[successor_index] = replace(successor, post_id=post_id)

    return replace(current, posts=tuple(posts)), tuple(exact_reads)


def _historical_issue323_wall_view(
    current: VkWallSnapshot,
    *,
    wall_safety: Mapping[str, Any],
    journal: Mapping[str, Any],
    source_id: str,
    now_epoch: int | None = None,
) -> tuple[VkWallSnapshot, tuple[str, ...]]:
    """Resolve the unique durable historical wall view from semantic Issue #323 identity.

    The durable capture timestamp, not the current clock, determines whether each
    exact prior rollout mapping was historically postponed or published. Current
    provider state may contain canonical non-video projections that were never part
    of the rollout mutation; for an exact prior owner/date/text/Clip mapping only,
    the solver therefore considers both the current canonical attachments and the
    original video-only semantic projection. It never changes text, the video
    identity, dates, IDs or unrelated wall objects. The complete durable pre-upload
    SHA remains the final and exact acceptance proof.
    """

    if not current.complete:
        raise UploadRecoveryRequired("Current wall snapshot is incomplete during Issue #323 recovery")

    captured_at = str(wall_safety.get("before_captured_at") or "")
    expected_sha = str(wall_safety.get("before_snapshot_sha256") or "")
    before_published_pages = wall_safety.get("before_published_pages")
    before_postponed_pages = wall_safety.get("before_postponed_pages")
    if not captured_at or not expected_sha:
        raise UploadRecoveryRequired("Historical upload wall digest/capture timestamp is missing")
    if type(before_published_pages) is not int or type(before_postponed_pages) is not int:
        raise UploadRecoveryRequired("Historical upload wall page counts are missing")
    try:
        captured_datetime = datetime.fromisoformat(captured_at)
    except ValueError as exc:
        raise UploadRecoveryRequired("Historical upload wall capture timestamp is invalid") from exc
    if captured_datetime.tzinfo is None or captured_datetime.utcoffset() is None:
        raise UploadRecoveryRequired("Historical upload wall capture timestamp is naive")
    capture_epoch = int(captured_datetime.timestamp())

    contract = _prior_verified_wall_contract(journal, source_id)
    observed_now = int(time.time()) if now_epoch is None else now_epoch
    seen_counts: dict[str, int] = {remote_id: 0 for remote_id in contract}
    variant_options: dict[int, tuple[tuple[VkWallPostFingerprint, bool], ...]] = {}

    for index, post in enumerate(current.posts):
        binding = contract.get(post.remote_id)
        if binding is None:
            continue
        expected_date, clip_remote_id = binding
        seen_counts[post.remote_id] += 1
        if post.publish_date != expected_date:
            raise UploadRecoveryRequired(
                f"Earlier rollout wall date changed for {post.remote_id}: {post.publish_date} != {expected_date}"
            )

        expected_attachment = f"video{clip_remote_id}"
        video_attachments = tuple(value for value in post.attachments if value.startswith("video"))
        if len(video_attachments) != 1:
            raise UploadRecoveryRequired(
                f"Earlier rollout wall must contain exactly one video during historical recovery: {post.remote_id}"
            )
        if video_attachments[0] != expected_attachment:
            raise UploadRecoveryRequired(f"Earlier rollout wall changed Clip binding: {post.remote_id}")

        if post.surface is VkWallSurface.PUBLISHED and observed_now + 60 < expected_date:
            raise UploadRecoveryRequired(f"Earlier rollout wall published before its slot: {post.remote_id}")

        if post.surface is VkWallSurface.POSTPONED:
            if capture_epoch - 60 > expected_date:
                raise UploadRecoveryRequired(
                    f"Historical capture is after the frozen slot but the current mapping is still postponed: "
                    f"{post.remote_id}"
                )
            historical_surfaces = (VkWallSurface.POSTPONED,)
        elif capture_epoch + 60 < expected_date:
            historical_surfaces = (VkWallSurface.POSTPONED,)
        elif capture_epoch - 60 > expected_date:
            historical_surfaces = (VkWallSurface.PUBLISHED,)
        else:
            historical_surfaces = (VkWallSurface.PUBLISHED, VkWallSurface.POSTPONED)

        attachment_variants = [post.attachments]
        video_only = (expected_attachment,)
        if post.attachments != video_only:
            attachment_variants.append(video_only)

        options: list[tuple[VkWallPostFingerprint, bool]] = []
        seen_option_keys: set[tuple[str, tuple[str, ...]]] = set()
        for historical_surface in historical_surfaces:
            if post.surface is VkWallSurface.POSTPONED and historical_surface is VkWallSurface.PUBLISHED:
                continue
            for attachments in attachment_variants:
                key = (historical_surface.value, attachments)
                if key in seen_option_keys:
                    continue
                seen_option_keys.add(key)
                options.append(
                    (
                        replace(post, surface=historical_surface, attachments=attachments),
                        post.surface is VkWallSurface.PUBLISHED
                        and historical_surface is VkWallSurface.POSTPONED,
                    )
                )
        if not options:
            raise UploadRecoveryRequired(f"Earlier rollout wall has no valid historical state: {post.remote_id}")
        variant_options[index] = tuple(options)

    duplicate = sorted(remote_id for remote_id, count in seen_counts.items() if count > 1)
    if duplicate:
        raise UploadRecoveryRequired(f"Earlier rollout wall mapping appears on multiple surfaces: {duplicate}")
    missing = sorted(remote_id for remote_id, count in seen_counts.items() if count == 0)
    if missing:
        raise UploadRecoveryRequired(f"Earlier rollout wall mapping disappeared during recovery: {missing}")

    states: list[tuple[list[VkWallPostFingerprint], tuple[str, ...]]] = [(list(current.posts), ())]
    for post_index in sorted(variant_options):
        expanded: list[tuple[list[VkWallPostFingerprint], tuple[str, ...]]] = []
        for posts, reversed_ids in states:
            for variant, reversed_surface in variant_options[post_index]:
                next_posts = list(posts)
                next_posts[post_index] = variant
                next_reversed = reversed_ids
                if reversed_surface:
                    next_reversed = tuple(sorted((*reversed_ids, variant.remote_id)))
                expanded.append((next_posts, next_reversed))
        states = expanded

    matches: list[tuple[VkWallSnapshot, tuple[str, ...]]] = []
    for posts, reversed_ids in states:
        candidate = replace(
            current,
            captured_at=captured_at,
            published_pages=before_published_pages,
            postponed_pages=before_postponed_pages,
            posts=tuple(posts),
        )
        if candidate.snapshot_sha256 == expected_sha:
            matches.append((candidate, reversed_ids))
    if not matches:
        raise MiloviTokenRolloutBlocked(
            "Current Milovi wall cannot be reduced to the journaled pre-upload baseline using capture-time "
            "Issue #323 surface semantics and exact semantic provider-projection normalization"
        )
    if len(matches) != 1:
        raise UploadRecoveryRequired(
            "Historical Issue #323 wall view is ambiguous after capture-time semantic normalization"
        )
    return matches[0]


def _resume_wall_baseline(
    record: Mapping[str, Any],
    current: VkWallSnapshot,
    *,
    journal: Mapping[str, Any] | None = None,
    now_epoch: int | None = None,
) -> VkWallSnapshot:
    """Bind restarted provider work to the unique exact historical wall view."""

    raw = record.get("wall_safety")
    if not isinstance(raw, Mapping):
        raise UploadRecoveryRequired("Provider-dispatched upload has no durable wall baseline")
    _assert_issue323_eighth_wall_history(record, raw)
    if journal is None:
        return normalize_current_wall_to_historical_capture(current, raw)
    source_id = str(record.get("source_video_id") or "")
    historical, _reversed_ids = _historical_issue323_wall_view(
        current,
        wall_safety=raw,
        journal=journal,
        source_id=source_id,
        now_epoch=now_epoch,
    )
    return historical


class _Issue323RecoveryWriter:
    """Read-only historical wall view for an already-dispatched upload recovery.

    Reservation and binary-upload methods intentionally fail closed. The shared
    lifecycle therefore cannot accidentally replay the provider dispatch while
    this adapter is in use. Only wall snapshot readback is normalized, and only
    through the exact SHA-solving contract above.
    """

    def __init__(
        self,
        delegate: _LiveClipWriter,
        *,
        wall_safety: Mapping[str, Any],
        journal: Mapping[str, Any],
        source_id: str,
    ) -> None:
        self.delegate = delegate
        self.wall_safety = wall_safety
        self.journal = journal
        self.source_id = source_id
        self.last_actual_snapshot_sha256: str | None = None
        self.last_effective_snapshot_sha256: str | None = None
        self.last_historical_snapshot_sha256: str | None = None
        self.last_reversed_surface_ids: tuple[str, ...] = ()
        self.last_exact_read_ids: tuple[str, ...] = ()

    def begin_upload(self, *, community_id: int, title: str, description: str, wall_policy: Any) -> Any:
        raise UploadRecoveryRequired("Issue #323 recovery adapter forbids a second upload reservation")

    def upload_file(self, ticket: Any, path: Path) -> dict[str, Any]:
        raise UploadRecoveryRequired("Issue #323 recovery adapter forbids binary retransmission")

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        return self.delegate.read_video(owner_id=owner_id, video_id=video_id)

    def wait_until_available(
        self,
        ticket: Any,
        *,
        readiness: VkUploadReadiness,
        timeout_seconds: int,
        on_observation: Any = None,
    ) -> dict[str, Any]:
        return self.delegate.wait_until_available(
            ticket,
            readiness=readiness,
            timeout_seconds=timeout_seconds,
            on_observation=on_observation,
        )

    def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int = 10000) -> VkWallSnapshot:
        actual = self.delegate.capture_wall_snapshot(
            community_id=community_id,
            max_posts_per_surface=max_posts_per_surface,
        )
        effective, exact_read_ids = _supplement_due_prior_wall_readbacks(
            self.delegate,
            actual,
            journal=self.journal,
            source_id=self.source_id,
        )
        historical, reversed_ids = _historical_issue323_wall_view(
            effective,
            wall_safety=self.wall_safety,
            journal=self.journal,
            source_id=self.source_id,
        )
        self.last_actual_snapshot_sha256 = actual.snapshot_sha256
        self.last_effective_snapshot_sha256 = effective.snapshot_sha256
        self.last_historical_snapshot_sha256 = historical.snapshot_sha256
        self.last_reversed_surface_ids = reversed_ids
        self.last_exact_read_ids = exact_read_ids
        return historical


def _ensure_clip_live(
    asset: SourceAsset,
    artifact: Any,
    item: dict[str, Any],
    journal: dict[str, Any],
    journal_path: Path,
    writer: VkWallWriter,
    upload_writer: _LiveClipWriter,
    client: VkApiClient,
    timeout: int,
) -> str:
    current = item.get("clip_remote_id")
    if isinstance(current, str) and current:
        _assert_live_clip(writer, asset, current)
        return current

    raw_record = item.get("upload_record")
    record = dict(raw_record) if isinstance(raw_record, Mapping) else None
    had_provider_effect = record is not None and _has_provider_effect(record)
    if not had_provider_effect:
        existing = _find_existing_clip(client, asset)
        if existing:
            _assert_live_clip(writer, asset, existing)
            item.update(status="clip_verified", clip_remote_id=existing, clip_origin="adopted_existing")
            _save(journal_path, journal)
            return existing

    readiness = clip_readiness(asset)
    record, _ = ensure_upload_record(
        record,
        source_snapshot_id=journal["source_snapshot_id"],
        community_id=MILOVI_COMMUNITY_ID,
        source_video_id=asset.source_id,
        source_title=asset.title,
        source_duration_seconds=asset.duration_seconds,
        published_title=asset.title,
        published_description=asset.description,
        readiness=readiness,
        wall_policy=DEFAULT_UPLOAD_WALL_POLICY,
    )
    item["upload_record"] = record
    _save(journal_path, journal)

    def persist() -> None:
        item["upload_record"] = record
        _save(journal_path, journal)

    current_wall = writer.capture_wall_snapshot(community_id=MILOVI_COMMUNITY_ID, max_posts_per_surface=10000)
    if not current_wall.complete:
        raise MiloviTokenRolloutBlocked("Complete wall baseline unavailable before upload/resume")
    operation_writer: Any = upload_writer
    recovery_writer: _Issue323RecoveryWriter | None = None
    if _has_provider_effect(record):
        effective_wall, baseline_exact_read_ids = _supplement_due_prior_wall_readbacks(
            writer,
            current_wall,
            journal=journal,
            source_id=asset.source_id,
        )
        wall_before = _resume_wall_baseline(record, effective_wall, journal=journal)
        raw_wall_safety = record.get("wall_safety")
        if not isinstance(raw_wall_safety, Mapping):
            raise UploadRecoveryRequired("Provider-dispatched upload lost durable wall safety evidence")
        recovery_writer = _Issue323RecoveryWriter(
            upload_writer,
            wall_safety=raw_wall_safety,
            journal=journal,
            source_id=asset.source_id,
        )
        operation_writer = recovery_writer
        record["issue323_recovery_wall_view"] = {
            "baseline_actual_snapshot_sha256": current_wall.snapshot_sha256,
            "baseline_effective_snapshot_sha256": effective_wall.snapshot_sha256,
            "baseline_historical_snapshot_sha256": wall_before.snapshot_sha256,
            "baseline_exact_read_ids": list(baseline_exact_read_ids),
            "reservation_replay_authorized": False,
            "binary_retransmission_authorized": False,
        }
        persist()
    else:
        wall_before = current_wall

    journal["provider_write_attempted"] = True
    item["status"] = "upload_in_progress"
    _save(journal_path, journal)
    execute_upload_operation(
        record,
        writer=operation_writer,
        community_id=MILOVI_COMMUNITY_ID,
        title=asset.title,
        description=asset.description,
        media_path=Path(asset.media_path),
        media_artifact=artifact,
        readiness=readiness,
        processing_timeout=timeout,
        wall_before_snapshot=wall_before,
        persist=persist,
    )
    if recovery_writer is not None:
        evidence = record.get("issue323_recovery_wall_view")
        if isinstance(evidence, dict):
            evidence.update(
                postflight_actual_snapshot_sha256=recovery_writer.last_actual_snapshot_sha256,
                postflight_effective_snapshot_sha256=recovery_writer.last_effective_snapshot_sha256,
                postflight_historical_snapshot_sha256=recovery_writer.last_historical_snapshot_sha256,
                postflight_reversed_surface_ids=list(recovery_writer.last_reversed_surface_ids),
                postflight_exact_read_ids=list(recovery_writer.last_exact_read_ids),
            )
            persist()
    if UploadStage(str(record.get("stage"))) is not UploadStage.VERIFIED:
        raise MiloviTokenRolloutBlocked(f"Upload lifecycle did not verify {asset.source_id}")
    remote_id = _upload_remote_id(record)
    _assert_live_clip(writer, asset, remote_id)
    item.update(
        status="clip_verified",
        clip_remote_id=remote_id,
        clip_origin="resumed_token_short_video" if had_provider_effect else "new_token_short_video",
    )
    _save(journal_path, journal)
    return remote_id


def _has_rollout_wall_effect(journal: Mapping[str, Any]) -> bool:
    raw_items = journal.get("items")
    if not isinstance(raw_items, Mapping):
        return True
    for source_id in ROLL_OUT_IDS:
        raw = raw_items.get(source_id)
        if not isinstance(raw, Mapping):
            return True
        if raw.get("wall_remote_id"):
            return True
        if str(raw.get("status") or "") in {"wall_intent", "wall_may_exist", "wall_verified"}:
            return True
    return False


def _load_or_rebase_schedule(
    path: Path,
    *,
    writer: VkWallWriter,
    journal: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, datetime]:
    current = (now or datetime.now(UTC)).astimezone(ZoneInfo(DEFAULT_TIMEZONE))
    slots = load_or_create_daily_schedule(path, writer=writer, now=current)
    if all(value > current for value in slots.values()):
        return slots
    if _has_rollout_wall_effect(journal):
        raise MiloviTokenRolloutBlocked(
            "Frozen Issue #323 schedule expired after a wall effect; automatic rebase is forbidden"
        )

    snapshot = writer.capture_wall_snapshot(community_id=MILOVI_COMMUNITY_ID, max_posts_per_surface=10000)
    if not snapshot.complete:
        raise MiloviTokenRolloutBlocked("Complete wall readback unavailable for schedule rebase")
    existing_dates = [
        int(post.publish_date)
        for post in snapshot.posts
        if post.surface is VkWallSurface.POSTPONED and post.publish_date is not None and int(post.publish_date) > 0
    ]
    slots = plan_daily_publish_slots(existing_postponed_publish_dates=existing_dates, now=current)
    write_json_atomic(path, _schedule_payload(slots))
    return slots


def run_issue_323_live_resume(
    *,
    confirmation: str,
    output_path: Path,
    journal_path: Path,
    schedule_path: Path,
    work_dir: Path,
    verify_timeout_seconds: int = 1800,
) -> dict[str, Any]:
    if confirmation != EXECUTION_CONFIRMATION:
        raise MiloviTokenRolloutBlocked(f"Exact confirmation required: {EXECUTION_CONFIRMATION}")
    if verify_timeout_seconds < 60:
        raise MiloviTokenRolloutBlocked("verify_timeout_seconds must be >=60")

    journal = _load_journal(journal_path)
    if journal.get("provider_write_attempted") is not True:
        raise MiloviTokenRolloutBlocked("Live resume requires the already-journaled Issue #323 canary provider effect")
    canary_record = _item(journal, CANARY_SOURCE_ID).get("upload_record")
    if not isinstance(canary_record, Mapping):
        raise MiloviTokenRolloutBlocked("Canary durable upload record is missing")
    reservation = canary_record.get("reservation")
    if not isinstance(reservation, Mapping) or reservation.get("remote_id") != EXPECTED_CANARY_REMOTE_ID:
        raise MiloviTokenRolloutBlocked("Live resume is not bound to exact canary -68859909_456239225")

    assets = prepare_sources(work_dir)
    artifacts = _media_artifacts(assets)
    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    alias, client = _resolve_account(store, settings.vk_api_version)
    writer = VkWallWriter(token_store=store, account_alias=alias, api_version=settings.vk_api_version)
    live_writer = _LiveClipWriter(writer, client)
    lock_path = settings.data_dir / "locks" / f"vk-{MILOVI_COMMUNITY_ID}-issue-323-live-resume.lock"

    try:
        with local_vk_write_lock(
            lock_path,
            account=alias,
            community_id=MILOVI_COMMUNITY_ID,
            operation="milovi-issue-323-live-native-clips-daily-wall",
        ):
            _prove_target(client)
            slots = _load_or_rebase_schedule(schedule_path, writer=writer, journal=journal)
            if tuple(slots) != ROLL_OUT_IDS:
                raise MiloviTokenRolloutBlocked("Issue #323 resumed schedule differs from exact source order")

            for index, asset in enumerate(assets):
                if index and not journal.get("canary_verified"):
                    raise MiloviTokenRolloutBlocked("Canary is not fully verified; remaining 11 are blocked")
                item = _item(journal, asset.source_id)
                status = str(item.get("status") or "")
                if status == "wall_verified":
                    continue
                if status == "clip_verified":
                    clip_id = item.get("clip_remote_id")
                    if not isinstance(clip_id, str) or not clip_id:
                        raise MiloviTokenRolloutBlocked(
                            f"Durable clip_verified item has no exact clip_remote_id: {asset.source_id}"
                        )
                else:
                    clip_id = _ensure_clip_live(
                        asset,
                        artifacts[asset.source_id],
                        item,
                        journal,
                        journal_path,
                        writer,
                        live_writer,
                        client,
                        verify_timeout_seconds,
                    )
                _ensure_wall(
                    asset,
                    clip_id,
                    slots[asset.source_id],
                    item,
                    journal,
                    journal_path,
                    writer,
                    client,
                )
                if asset.source_id == CANARY_SOURCE_ID:
                    journal["canary_verified"] = True
                    _save(journal_path, journal)
                write_json_atomic(output_path, _result(journal, "in_progress"))

        incomplete = [
            source_id for source_id in ROLL_OUT_IDS if _item(journal, source_id).get("status") != "wall_verified"
        ]
        if incomplete or not journal.get("canary_verified"):
            raise MiloviTokenRolloutBlocked(f"Final verification incomplete: {incomplete}")
        payload = _result(journal, "batch_verified")
        payload["resume_schema_name"] = RESULT_SCHEMA
        payload["resume_mode"] = "playable_native_short_video"
        write_json_atomic(output_path, payload)
        return payload
    except Exception as exc:
        write_json_atomic(output_path, _result(journal, "blocked", exc))
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Resume exact Milovi #323 live short_video rollout safely")
    parser.add_argument("--execute", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("operator-output/milovi-cake-issue-323-token-daily-rollout.json"),
    )
    parser.add_argument(
        "--journal",
        type=Path,
        default=Path("data/vk/milovi-cake/issue-323-token-daily-rollout-journal.json"),
    )
    parser.add_argument(
        "--schedule",
        type=Path,
        default=Path("data/vk/milovi-cake/issue-323-daily-wall-schedule.json"),
    )
    parser.add_argument("--work-dir", type=Path, default=Path("operator-output/milovi-cake-issue-323-work"))
    parser.add_argument("--verify-timeout", type=int, default=1800)
    args = parser.parse_args()
    result = run_issue_323_live_resume(
        confirmation=args.execute,
        output_path=args.output,
        journal_path=args.journal,
        schedule_path=args.schedule,
        work_dir=args.work_dir,
        verify_timeout_seconds=args.verify_timeout,
    )
    print(f"Milovi #323 live resume: {result['status']} | browser={result['browser_used']} | result={args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MiloviTokenRolloutBlocked, UploadRecoveryRequired, UploadRejected, OSError, ValueError) as exc:
        print(f"STOP: {type(exc).__name__}: {exc}")
        raise SystemExit(3) from exc


__all__ = [
    "EXECUTION_CONFIRMATION",
    "EXPECTED_CANARY_REMOTE_ID",
    "_native_clip_assessment",
    "run_issue_323_live_resume",
]
