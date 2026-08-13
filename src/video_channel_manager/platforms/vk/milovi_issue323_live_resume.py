from __future__ import annotations

import argparse
import time
from collections.abc import Mapping
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
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS, SourceAsset, prepare_sources, write_json_atomic
from video_channel_manager.platforms.vk.milovi_token_clip_rollout import (
    CANARY_SOURCE_ID,
    MiloviTokenRolloutBlocked,
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
    _ensure_wall,
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
from video_channel_manager.platforms.vk.wall_safety import DEFAULT_UPLOAD_WALL_POLICY, VkWallSurface

EXECUTION_CONFIRMATION = "ISSUE_323_RESUME_LIVE_SHORT_VIDEO_AND_FINISH"
RESULT_SCHEMA = "video-manager.milovi-issue-323-live-resume"
EXPECTED_CANARY_REMOTE_ID = "-68859909_456239225"
MINIMUM_FUTURE_SECONDS = 300


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
    if int(observed.get("duration_seconds") or 0) < readiness.minimum_duration_seconds:
        return assessment
    if "title_mismatch" in reasons and str(observed.get("title") or "") != "":
        return assessment

    observed["readiness_mode"] = "playable_native_short_video"
    observed["provider_processing_flag_tolerated"] = "processing" in reasons
    observed["blank_clip_title_tolerated"] = "title_mismatch" in reasons
    return VkUploadReadinessAssessment(ready=True, reasons=(), observed=observed)


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
        raise MiloviTokenRolloutBlocked(f"VK object {remote_id} is not a verified native short_video: {assessment.reasons}")
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
                    return item
                observed_type = str(item.get("type") or "").strip()
                provider_busy = bool(item.get("processing")) or bool(item.get("converting"))
                if observed_type and observed_type != "short_video" and not provider_busy:
                    raise MiloviTokenRolloutBlocked(
                        f"VK completed {ticket.remote_id} as {observed_type!r}, expected 'short_video'"
                    )
            elif on_observation is not None:
                on_observation(None, None)
            time.sleep(min(10.0, max(0.1, deadline - time.monotonic())))
        raise MiloviTokenRolloutBlocked(f"VK object {ticket.remote_id} did not become a playable native short_video in time")

    def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int = 10000) -> Any:
        return self.delegate.capture_wall_snapshot(
            community_id=community_id,
            max_posts_per_surface=max_posts_per_surface,
        )


def _resume_wall_baseline(record: Mapping[str, Any], current: Any) -> Any:
    """Bind a restarted provider-dispatched upload to its original wall content, not a fresh capture timestamp."""

    raw = record.get("wall_safety")
    if not isinstance(raw, Mapping):
        raise UploadRecoveryRequired("Provider-dispatched upload has no durable wall baseline")
    return normalize_current_wall_to_historical_capture(current, raw)


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
    wall_before = _resume_wall_baseline(record, current_wall) if _has_provider_effect(record) else current_wall

    journal["provider_write_attempted"] = True
    item["status"] = "upload_in_progress"
    _save(journal_path, journal)
    execute_upload_operation(
        record,
        writer=upload_writer,
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
        raise MiloviTokenRolloutBlocked("Frozen Issue #323 schedule expired after a wall effect; automatic rebase is forbidden")

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
                _assert_live_clip(writer, asset, clip_id)
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

        incomplete = [source_id for source_id in ROLL_OUT_IDS if _item(journal, source_id).get("status") != "wall_verified"]
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
