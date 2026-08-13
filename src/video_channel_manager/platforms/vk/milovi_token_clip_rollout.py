from __future__ import annotations

import argparse
import json
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.editorial._project_profiles import MILOVI_CAKE, resolve_project_key
from video_channel_manager.local_media.artifact import (
    MediaArtifactEvidence,
    MediaSourceIdentity,
    controlled_master_acquisition,
    probe_media_artifact,
)
from video_channel_manager.platforms.vk import VkApiClient, VkInventoryService, VkTokenStore, local_vk_write_lock
from video_channel_manager.platforms.vk.milovi_daily_postponed_wall import (
    ensure_postponed_wall_post,
    load_or_create_daily_schedule,
)
from video_channel_manager.platforms.vk.milovi_immediate_wall import (
    MILOVI_COMMUNITY_ID,
    MILOVI_OWNER_ID,
    MILOVI_SOURCE_ALLOWLIST,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import (
    ROLL_OUT_IDS,
    SOURCE_SNAPSHOT_ID,
    YOUTUBE_CHANNEL_ID,
    SourceAsset,
    prepare_sources,
    write_json_atomic,
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

EXECUTION_CONFIRMATION = "ISSUE_323_UPLOAD_12_CLIPS_AND_POSTPONE_DAILY"
CANARY_SOURCE_ID = "d48QLgOuiTs"
ROLLOUT_SCHEMA = "video-manager.milovi-issue-323-token-daily-rollout"
JOURNAL_SCHEMA = "video-manager.milovi-issue-323-token-daily-journal"
MAX_TOKEN_CLIP_SECONDS = 60.0
MILOVI_SCREEN_NAME = "milovi_cake"

if frozenset(ROLL_OUT_IDS) != MILOVI_SOURCE_ALLOWLIST or ROLL_OUT_IDS[0] != CANARY_SOURCE_ID:
    raise RuntimeError("Issue #323 token rollout allowlist/canary differs from reviewed authority")


class MiloviTokenRolloutBlocked(RuntimeError):
    pass


def _new_journal() -> dict[str, Any]:
    return {
        "schema_name": JOURNAL_SCHEMA,
        "schema_version": 1,
        "project_key": MILOVI_CAKE,
        "community_id": MILOVI_COMMUNITY_ID,
        "owner_id": MILOVI_OWNER_ID,
        "youtube_channel_id": YOUTUBE_CHANNEL_ID,
        "source_snapshot_id": SOURCE_SNAPSHOT_ID,
        "transport": "official_vk_api_token",
        "browser_used": False,
        "canary_source_id": CANARY_SOURCE_ID,
        "canary_verified": False,
        "provider_write_attempted": False,
        "items": {source_id: {"status": "pending"} for source_id in ROLL_OUT_IDS},
    }


def _load_journal(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return _new_journal()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MiloviTokenRolloutBlocked("Issue #323 token journal is not a JSON object")
    expected = {
        "schema_name": JOURNAL_SCHEMA,
        "schema_version": 1,
        "project_key": MILOVI_CAKE,
        "community_id": MILOVI_COMMUNITY_ID,
        "owner_id": MILOVI_OWNER_ID,
        "youtube_channel_id": YOUTUBE_CHANNEL_ID,
        "source_snapshot_id": SOURCE_SNAPSHOT_ID,
        "transport": "official_vk_api_token",
        "browser_used": False,
        "canary_source_id": CANARY_SOURCE_ID,
    }
    mismatch = {key: (value, payload.get(key)) for key, value in expected.items() if payload.get(key) != value}
    if mismatch:
        raise MiloviTokenRolloutBlocked(f"Issue #323 token journal binding mismatch: {mismatch}")
    items = payload.get("items")
    if not isinstance(items, dict) or tuple(items) != ROLL_OUT_IDS:
        raise MiloviTokenRolloutBlocked("Issue #323 token journal allowlist/order differs")
    return payload


def _save(path: Path, journal: dict[str, Any]) -> None:
    write_json_atomic(path, journal)


def _item(journal: dict[str, Any], source_id: str) -> dict[str, Any]:
    value = journal["items"].get(source_id)
    if not isinstance(value, dict):
        raise MiloviTokenRolloutBlocked(f"Invalid journal item: {source_id}")
    return value


def validate_token_clip_media_facts(facts: Mapping[str, tuple[int, int, float]]) -> None:
    if tuple(facts) != ROLL_OUT_IDS:
        raise MiloviTokenRolloutBlocked("Token Clip media facts differ from exact Issue #323 order")
    blockers: list[str] = []
    for source_id in ROLL_OUT_IDS:
        width, height, duration = facts[source_id]
        if width <= 0 or height <= width:
            blockers.append(f"{source_id}:not_vertical:{width}x{height}")
        if duration <= 0 or duration > MAX_TOKEN_CLIP_SECONDS:
            blockers.append(f"{source_id}:duration={duration:.3f}s")
    if blockers:
        raise MiloviTokenRolloutBlocked(
            "Provider-inert token Clip preflight failed; all 12 must be vertical and <=60.0s: " + ", ".join(blockers)
        )


def _media_artifacts(assets: list[SourceAsset]) -> dict[str, MediaArtifactEvidence]:
    if tuple(asset.source_id for asset in assets) != ROLL_OUT_IDS:
        raise MiloviTokenRolloutBlocked("Prepared sources differ from exact Issue #323 order")
    result: dict[str, MediaArtifactEvidence] = {}
    facts: dict[str, tuple[int, int, float]] = {}
    for asset in assets:
        path = Path(asset.media_path).expanduser().resolve()
        source = MediaSourceIdentity(
            project_key=MILOVI_CAKE,
            platform=PlatformName.YOUTUBE,
            source_channel_id=YOUTUBE_CHANNEL_ID,
            source_id=asset.source_id,
            source_url=asset.source_url,
            expected_duration_seconds=float(asset.duration_seconds),
        )
        evidence = probe_media_artifact(
            source=source,
            acquisition=controlled_master_acquisition(
                path,
                tool_name="milovi-issue-323-reviewed-source-freeze",
                tool_version="1",
            ),
        )
        if evidence.probe.sha256 != f"sha256:{asset.media_sha256}":
            raise MiloviTokenRolloutBlocked(f"Media digest changed for {asset.source_id}")
        result[asset.source_id] = evidence
        facts[asset.source_id] = (
            int(evidence.probe.width or 0),
            int(evidence.probe.height or 0),
            float(evidence.probe.duration_seconds),
        )
    validate_token_clip_media_facts(facts)
    return result


def clip_readiness(asset: SourceAsset) -> VkUploadReadiness:
    return VkUploadReadiness(
        expected_title=asset.title,
        minimum_duration_seconds=max(1, asset.duration_seconds - 4),
        allowed_types=("short_video",),
        require_playable=True,
    )


def _prove_target(client: VkApiClient) -> None:
    matches = [item for item in client.list_managed_communities() if int(item.community_id) == MILOVI_COMMUNITY_ID]
    if len(matches) != 1:
        raise MiloviTokenRolloutBlocked("Stored VK user token does not prove management of Milovi community 68859909")
    screen = str(matches[0].screen_name or "").strip().casefold()
    if screen and screen != MILOVI_SCREEN_NAME:
        raise MiloviTokenRolloutBlocked(f"Community 68859909 resolved to unexpected screen_name {screen!r}")
    if resolve_project_key(
        {"project_key": MILOVI_CAKE, "community_id": MILOVI_COMMUNITY_ID, "owner_id": MILOVI_OWNER_ID}
    ) != MILOVI_CAKE:
        raise MiloviTokenRolloutBlocked("Canonical Milovi project/community/owner identity failed")


def _resolve_account(store: VkTokenStore, api_version: str) -> tuple[str, VkApiClient]:
    preferred = {"milovi-cake": 0, "shared-vk-user": 1, "legendary-poet": 2}
    found: list[tuple[int, str, VkApiClient]] = []
    for account in store.list_accounts():
        if not store.token_exists(account.alias):
            continue
        client = VkApiClient(token_store=store, account_alias=account.alias, api_version=api_version)
        try:
            _prove_target(client)
        except Exception:
            continue
        found.append((preferred.get(account.alias, 10), account.alias, client))
    if not found:
        raise MiloviTokenRolloutBlocked("No stored VK user token proved administration of Milovi community 68859909")
    found.sort(key=lambda row: (row[0], row[1]))
    return found[0][1], found[0][2]


def _find_existing_clip(client: VkApiClient, asset: SourceAsset) -> str | None:
    package = VkInventoryService(client).build_audit_package(str(MILOVI_COMMUNITY_ID))
    if int(package.channel.ref.channel_id) != MILOVI_COMMUNITY_ID:
        raise MiloviTokenRolloutBlocked("VK inventory returned another community")
    marker = f"youtube.com/shorts/{asset.source_id}".casefold()
    matching = [
        record
        for record in package.videos
        if marker in str(record.description or "").casefold()
        and (record.duration_seconds is None or abs(int(record.duration_seconds) - asset.duration_seconds) <= 4)
    ]
    clips = [
        record
        for record in matching
        if str((record.metadata if isinstance(record.metadata, dict) else {}).get("vk_video_type") or "") == "short_video"
    ]
    ordinary = [record for record in matching if record not in clips]
    if len(clips) > 1:
        raise MiloviTokenRolloutBlocked(f"Multiple native Clips match {asset.source_id}")
    if not clips and ordinary:
        raise MiloviTokenRolloutBlocked(
            f"Source marker for {asset.source_id} already belongs to ordinary VK video(s); duplicate upload forbidden"
        )
    return str(clips[0].ref.remote_id) if clips else None


def _parse_remote_id(remote_id: str) -> tuple[int, int]:
    owner_text, sep, video_text = remote_id.partition("_")
    if not sep:
        raise MiloviTokenRolloutBlocked(f"Invalid VK remote ID: {remote_id}")
    owner_id, video_id = int(owner_text), int(video_text)
    if owner_id != MILOVI_OWNER_ID or video_id <= 0:
        raise MiloviTokenRolloutBlocked(f"VK object {remote_id} is outside exact Milovi owner")
    return owner_id, video_id


def _assert_clip(writer: VkWallWriter, asset: SourceAsset, remote_id: str) -> None:
    owner_id, video_id = _parse_remote_id(remote_id)
    raw = writer.read_video(owner_id=owner_id, video_id=video_id)
    if raw is None:
        raise MiloviTokenRolloutBlocked(f"VK object disappeared: {remote_id}")
    assessment = assess_vk_upload_readiness(
        raw,
        expected_owner_id=owner_id,
        expected_video_id=video_id,
        readiness=clip_readiness(asset),
    )
    if not assessment.ready:
        raise MiloviTokenRolloutBlocked(f"VK object {remote_id} is not verified short_video: {assessment.reasons}")
    marker = f"youtube.com/shorts/{asset.source_id}".casefold()
    if marker not in str(raw.get("description") or "").casefold():
        raise MiloviTokenRolloutBlocked(f"VK Clip {remote_id} lost source marker for {asset.source_id}")


class _StrictClipWriter:
    def __init__(self, delegate: VkWallWriter, client: VkApiClient) -> None:
        self.delegate, self.client = delegate, client

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
                assessment: VkUploadReadinessAssessment = assess_vk_upload_readiness(
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
                processing = bool(item.get("processing")) or bool(item.get("converting"))
                if observed_type and observed_type not in readiness.allowed_types and not processing:
                    raise MiloviTokenRolloutBlocked(
                        f"VK completed {ticket.remote_id} as {observed_type!r}, expected 'short_video'"
                    )
            elif on_observation is not None:
                on_observation(None, None)
            time.sleep(min(10.0, max(0.1, deadline - time.monotonic())))
        raise MiloviTokenRolloutBlocked(f"VK object {ticket.remote_id} did not verify as short_video in time")

    def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int = 10000) -> Any:
        return self.delegate.capture_wall_snapshot(
            community_id=community_id,
            max_posts_per_surface=max_posts_per_surface,
        )


def _has_provider_effect(record: Mapping[str, Any]) -> bool:
    stage = UploadStage(str(record.get("stage")))
    if stage in {
        UploadStage.RESERVED,
        UploadStage.UPLOAD_STARTED,
        UploadStage.UPLOAD_RESPONSE_RECEIVED,
        UploadStage.PROCESSING,
        UploadStage.UNKNOWN_REQUIRES_RECONCILIATION,
        UploadStage.VERIFIED,
    }:
        return True
    return stage is UploadStage.RESERVATION_INTENT_COMMITTED and bool(record.get("reservation_dispatch_started_at"))


def _upload_remote_id(record: Mapping[str, Any]) -> str:
    reservation = record.get("reservation")
    if not isinstance(reservation, Mapping) or not isinstance(reservation.get("remote_id"), str):
        raise MiloviTokenRolloutBlocked("Upload journal lost exact reservation identity")
    return str(reservation["remote_id"])


def _ensure_clip(
    asset: SourceAsset,
    artifact: MediaArtifactEvidence,
    item: dict[str, Any],
    journal: dict[str, Any],
    journal_path: Path,
    writer: VkWallWriter,
    upload_writer: _StrictClipWriter,
    client: VkApiClient,
    timeout: int,
) -> str:
    current = item.get("clip_remote_id")
    if isinstance(current, str) and current:
        _assert_clip(writer, asset, current)
        return current

    raw_record = item.get("upload_record")
    record = dict(raw_record) if isinstance(raw_record, Mapping) else None
    if record is None or not _has_provider_effect(record):
        existing = _find_existing_clip(client, asset)
        if existing:
            _assert_clip(writer, asset, existing)
            item.update(status="clip_verified", clip_remote_id=existing, clip_origin="adopted_existing")
            _save(journal_path, journal)
            return existing

    readiness = clip_readiness(asset)
    record, _ = ensure_upload_record(
        record,
        source_snapshot_id=SOURCE_SNAPSHOT_ID,
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

    wall_before = writer.capture_wall_snapshot(community_id=MILOVI_COMMUNITY_ID, max_posts_per_surface=10000)
    if not wall_before.complete:
        raise MiloviTokenRolloutBlocked("Complete wall baseline unavailable before upload")
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
    _assert_clip(writer, asset, remote_id)
    item.update(status="clip_verified", clip_remote_id=remote_id, clip_origin="new_token_short_video")
    _save(journal_path, journal)
    return remote_id


def _read_wall_attachment(writer: VkWallWriter, clip_remote_id: str, publish_at: Any) -> str | None:
    _owner, video_id = _parse_remote_id(clip_remote_id)
    snapshot = writer.capture_wall_snapshot(community_id=MILOVI_COMMUNITY_ID, max_posts_per_surface=10000)
    if not snapshot.complete:
        raise MiloviTokenRolloutBlocked("Complete wall readback unavailable")
    attachment = f"video{MILOVI_OWNER_ID}_{video_id}"
    matches = [post for post in snapshot.posts if attachment in post.attachments]
    if len(matches) > 1:
        raise MiloviTokenRolloutBlocked(f"Clip {clip_remote_id} appears in multiple wall posts")
    if not matches:
        return None
    match = matches[0]
    if match.surface is not VkWallSurface.POSTPONED or match.publish_date != int(publish_at.timestamp()):
        raise MiloviTokenRolloutBlocked(f"Clip {clip_remote_id} has unexpected wall state")
    return match.remote_id


def _ensure_wall(
    asset: SourceAsset,
    clip_remote_id: str,
    publish_at: Any,
    item: dict[str, Any],
    journal: dict[str, Any],
    journal_path: Path,
    writer: VkWallWriter,
    client: VkApiClient,
) -> str:
    existing = item.get("wall_remote_id")
    if isinstance(existing, str) and existing:
        if _read_wall_attachment(writer, clip_remote_id, publish_at) != existing:
            raise MiloviTokenRolloutBlocked(f"Journaled wall post changed for {asset.source_id}")
        return existing
    if str(item.get("status") or "") in {"wall_intent", "wall_may_exist"}:
        reconciled = _read_wall_attachment(writer, clip_remote_id, publish_at)
        if reconciled is None:
            raise MiloviTokenRolloutBlocked(f"Prior wall effect unresolved for {asset.source_id}; blind replay forbidden")
        item.update(status="wall_verified", wall_remote_id=reconciled, wall_origin="reconciled")
        _save(journal_path, journal)
        return reconciled

    item.update(status="wall_intent", clip_remote_id=clip_remote_id, publish_at=publish_at.isoformat())
    _save(journal_path, journal)
    _prove_target(client)
    journal["provider_write_attempted"] = True
    _save(journal_path, journal)
    try:
        result = ensure_postponed_wall_post(
            writer=writer,
            asset=asset,
            clip_remote_id=clip_remote_id,
            publish_at=publish_at,
        )
    except Exception:
        item["status"] = "wall_may_exist"
        _save(journal_path, journal)
        raise
    remote_id = str(result["wall_remote_id"])
    item.update(
        status="wall_verified",
        wall_remote_id=remote_id,
        wall_origin=str(result["origin"]),
        publish_at=str(result["publish_at"]),
        publish_date=int(result["publish_date"]),
    )
    _save(journal_path, journal)
    return remote_id


def _result(journal: Mapping[str, Any], status: str, error: Exception | None = None) -> dict[str, Any]:
    item_map = journal.get("items") if isinstance(journal.get("items"), Mapping) else {}
    items = []
    for source_id in ROLL_OUT_IDS:
        raw = item_map.get(source_id) if isinstance(item_map, Mapping) else None
        item = raw if isinstance(raw, Mapping) else {}
        items.append(
            {
                "source_id": source_id,
                "status": item.get("status"),
                "clip_remote_id": item.get("clip_remote_id"),
                "wall_remote_id": item.get("wall_remote_id"),
                "publish_at": item.get("publish_at"),
                "publish_date": item.get("publish_date"),
            }
        )
    payload: dict[str, Any] = {
        "schema_name": ROLLOUT_SCHEMA,
        "schema_version": 1,
        "status": status,
        "project_key": MILOVI_CAKE,
        "community_id": MILOVI_COMMUNITY_ID,
        "owner_id": MILOVI_OWNER_ID,
        "youtube_channel_id": YOUTUBE_CHANNEL_ID,
        "transport": "official_vk_api_token",
        "browser_used": False,
        "publication_mode": "native_clip_then_postponed_wall",
        "cadence": "one_post_per_calendar_day",
        "postponed_wall_authorized": True,
        "immediate_wall_authorized": False,
        "delete_hide_edit_authorized": False,
        "canary_source_id": CANARY_SOURCE_ID,
        "canary_verified": bool(journal.get("canary_verified")),
        "provider_write_attempted": bool(journal.get("provider_write_attempted")),
        "items": items,
    }
    if error:
        payload["error"] = {"type": type(error).__name__, "message": str(error)}
    return payload


def run_issue_323_token_rollout(
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
    _save(journal_path, journal)
    try:
        assets = prepare_sources(work_dir)
        artifacts = _media_artifacts(assets)  # all 12 <=60s/vertical before any VK write
        settings = get_settings()
        store = VkTokenStore(settings.data_dir)
        alias, client = _resolve_account(store, settings.vk_api_version)
        writer = VkWallWriter(token_store=store, account_alias=alias, api_version=settings.vk_api_version)
        strict_writer = _StrictClipWriter(writer, client)
        lock_path = settings.data_dir / "locks" / f"vk-{MILOVI_COMMUNITY_ID}-issue-323-token-daily.lock"
        with local_vk_write_lock(
            lock_path,
            account=alias,
            community_id=MILOVI_COMMUNITY_ID,
            operation="milovi-issue-323-token-native-clips-daily-wall",
        ):
            _prove_target(client)
            slots = load_or_create_daily_schedule(schedule_path, writer=writer)
            if tuple(slots) != ROLL_OUT_IDS:
                raise MiloviTokenRolloutBlocked("Frozen daily schedule differs from exact Issue #323 order")
            for index, asset in enumerate(assets):
                if index and not journal["canary_verified"]:
                    raise MiloviTokenRolloutBlocked("Canary is not fully verified; remaining 11 are blocked")
                item = _item(journal, asset.source_id)
                clip_id = _ensure_clip(
                    asset,
                    artifacts[asset.source_id],
                    item,
                    journal,
                    journal_path,
                    writer,
                    strict_writer,
                    client,
                    verify_timeout_seconds,
                )
                _assert_clip(writer, asset, clip_id)
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
        incomplete = [sid for sid in ROLL_OUT_IDS if _item(journal, sid).get("status") != "wall_verified"]
        if incomplete or not journal["canary_verified"]:
            raise MiloviTokenRolloutBlocked(f"Final verification incomplete: {incomplete}")
        payload = _result(journal, "batch_verified")
        write_json_atomic(output_path, payload)
        return payload
    except Exception as exc:
        write_json_atomic(output_path, _result(journal, "blocked", exc))
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Milovi #323 token-only native Clips + one postponed wall post/day")
    parser.add_argument("--execute", required=True)
    parser.add_argument("--output", type=Path, default=Path("operator-output/milovi-cake-issue-323-token-daily-rollout.json"))
    parser.add_argument("--journal", type=Path, default=Path("data/vk/milovi-cake/issue-323-token-daily-rollout-journal.json"))
    parser.add_argument("--schedule", type=Path, default=Path("data/vk/milovi-cake/issue-323-daily-wall-schedule.json"))
    parser.add_argument("--work-dir", type=Path, default=Path("operator-output/milovi-cake-issue-323-work"))
    parser.add_argument("--verify-timeout", type=int, default=1800)
    args = parser.parse_args()
    result = run_issue_323_token_rollout(
        confirmation=args.execute,
        output_path=args.output,
        journal_path=args.journal,
        schedule_path=args.schedule,
        work_dir=args.work_dir,
        verify_timeout_seconds=args.verify_timeout,
    )
    print(f"Milovi #323: {result['status']} | browser={result['browser_used']} | result={args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MiloviTokenRolloutBlocked, UploadRecoveryRequired, UploadRejected, OSError, ValueError) as exc:
        print(f"STOP: {type(exc).__name__}: {exc}")
        raise SystemExit(3) from exc


__all__ = [
    "CANARY_SOURCE_ID",
    "EXECUTION_CONFIRMATION",
    "MAX_TOKEN_CLIP_SECONDS",
    "MiloviTokenRolloutBlocked",
    "clip_readiness",
    "run_issue_323_token_rollout",
    "validate_token_clip_media_facts",
]
