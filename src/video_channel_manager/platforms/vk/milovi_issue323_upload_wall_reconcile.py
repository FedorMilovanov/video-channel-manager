from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime
from typing import Any

from video_channel_manager.platforms.vk.milovi_immediate_wall import MILOVI_COMMUNITY_ID, MILOVI_OWNER_ID
from video_channel_manager.platforms.vk.milovi_issue323_live_resume import (
    _resume_wall_baseline,
    _supplement_due_prior_wall_readbacks,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS
from video_channel_manager.platforms.vk.milovi_token_clip_rollout import (
    MiloviTokenRolloutBlocked,
    _parse_remote_id,
    _prove_target,
)
from video_channel_manager.platforms.vk.upload_lifecycle import UploadRecoveryRequired, UploadStage, ticket_from_record
from video_channel_manager.platforms.vk.wall import VkWallWriter
from video_channel_manager.platforms.vk.wall_safety import VkWallPostFingerprint, VkWallSnapshot, VkWallSurface

ISSUE323_UPLOAD_WALL_RECOVERY_SOURCES = frozenset(ROLL_OUT_IDS[8:])
ISSUE323_UPLOAD_WALL_RECONCILE_SCHEMA = "video-manager.milovi-issue-323-upload-wall-reconcile"
_CAPTURE_WINDOW_SLOP_SECONDS = 120


class Issue323UploadWallReconcileBlocked(UploadRecoveryRequired):
    """The upload wall effect cannot be reduced to one exact authorized post."""


def _timestamp(value: object, *, field: str) -> int:
    if not isinstance(value, str) or not value:
        raise Issue323UploadWallReconcileBlocked(f"Upload wall recovery is missing {field}")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise Issue323UploadWallReconcileBlocked(f"Upload wall recovery has invalid {field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise Issue323UploadWallReconcileBlocked(f"Upload wall recovery has naive {field}")
    return int(parsed.timestamp())


def _wall_safety(record: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = record.get("wall_safety")
    if not isinstance(raw, Mapping):
        raise Issue323UploadWallReconcileBlocked("Provider-dispatched upload has no durable wall safety evidence")
    return raw


def _delta(wall_safety: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = wall_safety.get("delta")
    if not isinstance(raw, Mapping):
        raise Issue323UploadWallReconcileBlocked("Provider-dispatched upload has no durable wall delta")
    if raw.get("status") != "changed":
        raise Issue323UploadWallReconcileBlocked(
            f"Upload wall recovery requires a changed durable delta, observed {raw.get('status')!r}"
        )
    if raw.get("before_sha256") != wall_safety.get("before_snapshot_sha256"):
        raise Issue323UploadWallReconcileBlocked("Upload wall delta before digest differs from durable wall safety")
    if raw.get("after_sha256") != wall_safety.get("after_snapshot_sha256"):
        raise Issue323UploadWallReconcileBlocked("Upload wall delta after digest differs from durable wall safety")
    for field in ("created", "removed", "changed", "reasons"):
        values = raw.get(field)
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise Issue323UploadWallReconcileBlocked(f"Upload wall delta {field} list is invalid")
    if raw.get("reasons"):
        raise Issue323UploadWallReconcileBlocked(f"Upload wall delta is incomplete: {raw.get('reasons')}")
    return raw


def _prior_rollout_wall_ids(journal: Mapping[str, Any]) -> set[str]:
    items = journal.get("items")
    if not isinstance(items, Mapping):
        raise Issue323UploadWallReconcileBlocked("Issue #323 journal has no item map")
    result: set[str] = set()
    for raw in items.values():
        if not isinstance(raw, Mapping):
            continue
        remote_id = raw.get("wall_remote_id")
        if isinstance(remote_id, str) and remote_id:
            result.add(remote_id)
    return result


def _created_published_ids(delta: Mapping[str, Any]) -> tuple[str, ...]:
    raw_created = delta.get("created")
    assert isinstance(raw_created, list)
    return tuple(sorted(value.removeprefix("published:") for value in raw_created if value.startswith("published:")))


def _exact_video(post: Mapping[str, Any]) -> tuple[int, int]:
    raw_attachments = post.get("attachments")
    if not isinstance(raw_attachments, list):
        raise Issue323UploadWallReconcileBlocked("Upload-created wall post attachments are unavailable")
    videos: list[Mapping[str, Any]] = []
    for attachment in raw_attachments:
        if not isinstance(attachment, Mapping):
            raise Issue323UploadWallReconcileBlocked("Upload-created wall post has a malformed attachment")
        if attachment.get("type") != "video":
            continue
        video = attachment.get("video")
        if not isinstance(video, Mapping):
            raise Issue323UploadWallReconcileBlocked("Upload-created wall post has a malformed video attachment")
        videos.append(video)
    if len(videos) != 1:
        raise Issue323UploadWallReconcileBlocked(
            f"Upload-created wall post must contain exactly one video; observed {len(videos)}"
        )
    owner_id = videos[0].get("owner_id")
    video_id = videos[0].get("id")
    if type(owner_id) is not int or type(video_id) is not int:
        raise Issue323UploadWallReconcileBlocked("Upload-created wall post video identity is invalid")
    return owner_id, video_id


def _absent_exact(post: Mapping[str, Any] | None, *, post_id: int) -> bool:
    if post is None:
        return True
    return post.get("is_deleted") is True and post.get("owner_id") == MILOVI_OWNER_ID and post.get("id") == post_id


def _remove_fingerprint(snapshot: VkWallSnapshot, remote_id: str) -> VkWallSnapshot:
    kept = tuple(
        post for post in snapshot.posts if not (post.surface is VkWallSurface.PUBLISHED and post.remote_id == remote_id)
    )
    if len(kept) != len(snapshot.posts) - 1:
        raise Issue323UploadWallReconcileBlocked(
            f"Upload-created wall candidate does not occur exactly once on published surface: {remote_id}"
        )
    return replace(snapshot, posts=kept)


def _prove_historical_baseline(
    *,
    record: Mapping[str, Any],
    current: VkWallSnapshot,
    journal: Mapping[str, Any],
    writer: VkWallWriter,
    source_id: str,
) -> tuple[VkWallSnapshot, tuple[str, ...]]:
    effective, exact_read_ids = _supplement_due_prior_wall_readbacks(
        writer,
        current,
        journal=journal,
        source_id=source_id,
    )
    baseline = _resume_wall_baseline(record, effective, journal=journal)
    expected_sha = str(_wall_safety(record).get("before_snapshot_sha256") or "")
    if not expected_sha or baseline.snapshot_sha256 != expected_sha:
        raise Issue323UploadWallReconcileBlocked(
            "Recovered upload wall baseline does not match the durable pre-upload SHA"
        )
    return baseline, exact_read_ids


def _unknown_created_ids(
    *,
    delta: Mapping[str, Any],
    journal: Mapping[str, Any],
) -> tuple[str, ...]:
    prior_ids = _prior_rollout_wall_ids(journal)
    return tuple(remote_id for remote_id in _created_published_ids(delta) if remote_id not in prior_ids)


def _unknown_created_are_absent(
    *,
    writer: VkWallWriter,
    remote_ids: tuple[str, ...],
) -> bool:
    for remote_id in remote_ids:
        try:
            owner_id, post_id = _parse_remote_id(remote_id)
        except Exception:
            return False
        if owner_id != MILOVI_OWNER_ID or post_id <= 0:
            return False
        exact = writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=post_id)
        if not _absent_exact(exact, post_id=post_id):
            return False
    return True


def _candidate_fingerprints(
    *,
    record: Mapping[str, Any],
    current: VkWallSnapshot,
    journal: Mapping[str, Any],
    source_id: str,
    writer: VkWallWriter,
    delta: Mapping[str, Any],
) -> list[tuple[VkWallPostFingerprint, VkWallSnapshot, tuple[str, ...]]]:
    created_remote_ids = _unknown_created_ids(delta=delta, journal=journal)
    if not created_remote_ids:
        raise Issue323UploadWallReconcileBlocked("Upload wall delta has no unknown published created post to reconcile")

    ticket = ticket_from_record(record)
    if ticket.owner_id != MILOVI_OWNER_ID:
        raise Issue323UploadWallReconcileBlocked("Upload reservation left the exact Milovi owner")
    expected_attachment = f"video{ticket.remote_id}"
    wall_safety = _wall_safety(record)
    before_epoch = _timestamp(wall_safety.get("before_captured_at"), field="before_captured_at")
    after_epoch = _timestamp(wall_safety.get("after_captured_at"), field="after_captured_at")
    if after_epoch + _CAPTURE_WINDOW_SLOP_SECONDS < before_epoch:
        raise Issue323UploadWallReconcileBlocked("Upload wall capture window moved backwards")

    matches: list[tuple[VkWallPostFingerprint, VkWallSnapshot, tuple[str, ...]]] = []
    for created_remote_id in created_remote_ids:
        try:
            owner_id, post_id = _parse_remote_id(created_remote_id)
        except Exception:
            continue
        if owner_id != MILOVI_OWNER_ID or post_id <= 0:
            continue
        fingerprints = [
            post
            for post in current.posts
            if post.surface is VkWallSurface.PUBLISHED and post.remote_id == created_remote_id
        ]
        if len(fingerprints) != 1:
            continue
        fingerprint = fingerprints[0]
        video_attachments = [value for value in fingerprint.attachments if value.startswith("video")]
        if video_attachments != [expected_attachment] or fingerprint.publish_date is None:
            continue
        if not (
            before_epoch - _CAPTURE_WINDOW_SLOP_SECONDS
            <= fingerprint.publish_date
            <= after_epoch + _CAPTURE_WINDOW_SLOP_SECONDS
        ):
            continue
        virtual = _remove_fingerprint(current, created_remote_id)
        try:
            baseline, exact_read_ids = _prove_historical_baseline(
                record=record,
                current=virtual,
                journal=journal,
                writer=writer,
                source_id=source_id,
            )
        except (UploadRecoveryRequired, MiloviTokenRolloutBlocked):
            continue
        matches.append((fingerprint, baseline, exact_read_ids))
    return matches


def reconcile_issue323_upload_wall_effect(
    *,
    record: dict[str, Any],
    current_wall: VkWallSnapshot,
    journal: Mapping[str, Any],
    writer: VkWallWriter,
    client: Any,
    source_id: str,
    persist: Callable[[], None],
) -> tuple[VkWallSnapshot, VkWallSnapshot]:
    """Recover one already-dispatched Issue #323 upload without replay.

    Normal scheduled-surface evolution is read-only. For sources 9-12 only,
    exactly one provider-created published wall post may be deleted when the
    durable postflight delta, exact reserved Clip, capture window and exact
    historical pre-upload SHA all identify that single side effect.
    """

    if source_id not in ROLL_OUT_IDS:
        raise Issue323UploadWallReconcileBlocked(
            f"Issue #323 recovery source is outside the exact rollout: {source_id}"
        )
    if record.get("source_video_id") != source_id:
        raise Issue323UploadWallReconcileBlocked("Upload record source binding changed during wall recovery")
    if UploadStage(str(record.get("stage"))) is not UploadStage.UNKNOWN_REQUIRES_RECONCILIATION:
        raise Issue323UploadWallReconcileBlocked(
            f"Upload wall recovery requires unknown_requires_reconciliation stage, observed {record.get('stage')!r}"
        )
    if not current_wall.complete:
        raise Issue323UploadWallReconcileBlocked("Current wall snapshot is incomplete during upload wall recovery")

    wall_safety = _wall_safety(record)
    delta = _delta(wall_safety)
    unknown_created = _unknown_created_ids(delta=delta, journal=journal)

    # A due postponed->published transition of an earlier durable mapping is a
    # read-only explanation. Unknown created IDs are not silently normalized:
    # they must already be exactly absent/tombstoned or enter the narrow delete
    # path below.
    if not unknown_created or _unknown_created_are_absent(writer=writer, remote_ids=unknown_created):
        try:
            normalized_baseline, exact_read_ids = _prove_historical_baseline(
                record=record,
                current=current_wall,
                journal=journal,
                writer=writer,
                source_id=source_id,
            )
        except (UploadRecoveryRequired, MiloviTokenRolloutBlocked):
            pass
        else:
            record["issue323_upload_wall_reconcile"] = {
                "schema_name": ISSUE323_UPLOAD_WALL_RECONCILE_SCHEMA,
                "schema_version": 1,
                "status": "normalized_without_delete",
                "source_id": source_id,
                "clip_remote_id": ticket_from_record(record).remote_id,
                "preupload_snapshot_sha256": normalized_baseline.snapshot_sha256,
                "actual_snapshot_sha256": current_wall.snapshot_sha256,
                "exact_read_ids": list(exact_read_ids),
                "delete_authorized": False,
            }
            persist()
            return current_wall, normalized_baseline

    if source_id not in ISSUE323_UPLOAD_WALL_RECOVERY_SOURCES:
        raise Issue323UploadWallReconcileBlocked(
            "Unexplained upload wall effect is outside the narrowly authorized sources 9-12 recovery scope"
        )

    matches = _candidate_fingerprints(
        record=record,
        current=current_wall,
        journal=journal,
        source_id=source_id,
        writer=writer,
        delta=delta,
    )
    if len(matches) != 1:
        candidate_ids = sorted(post.remote_id for post, _baseline, _reads in matches)
        raise Issue323UploadWallReconcileBlocked(
            f"Upload wall effect does not reduce to exactly one bound published post: {candidate_ids}"
        )
    candidate, virtual_baseline, virtual_exact_read_ids = matches[0]
    candidate_remote_id = candidate.remote_id
    candidate_post_id = candidate.post_id
    ticket = ticket_from_record(record)

    state = record.get("issue323_upload_wall_reconcile")
    if state is None:
        state = {
            "schema_name": ISSUE323_UPLOAD_WALL_RECONCILE_SCHEMA,
            "schema_version": 1,
            "status": "delete_intent_committed",
            "source_id": source_id,
            "clip_remote_id": ticket.remote_id,
            "wall_remote_id": candidate_remote_id,
            "preupload_snapshot_sha256": virtual_baseline.snapshot_sha256,
            "predelete_actual_snapshot_sha256": current_wall.snapshot_sha256,
            "virtual_exact_read_ids": list(virtual_exact_read_ids),
            "original_wall_delta": dict(delta),
            "delete_authorized": True,
            "delete_dispatch_started": False,
        }
        record["issue323_upload_wall_reconcile"] = state
        persist()
    if not isinstance(state, dict):
        raise Issue323UploadWallReconcileBlocked("Upload wall reconciliation journal is invalid")
    expected_binding = {
        "schema_name": ISSUE323_UPLOAD_WALL_RECONCILE_SCHEMA,
        "schema_version": 1,
        "source_id": source_id,
        "clip_remote_id": ticket.remote_id,
        "wall_remote_id": candidate_remote_id,
        "preupload_snapshot_sha256": virtual_baseline.snapshot_sha256,
        "delete_authorized": True,
    }
    mismatches = {key: (value, state.get(key)) for key, value in expected_binding.items() if state.get(key) != value}
    if mismatches:
        raise Issue323UploadWallReconcileBlocked(f"Upload wall reconciliation binding changed: {mismatches}")

    exact = writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=candidate_post_id)
    if _absent_exact(exact, post_id=candidate_post_id):
        postdelete = writer.capture_wall_snapshot(community_id=MILOVI_COMMUNITY_ID, max_posts_per_surface=10000)
        baseline_after, exact_read_ids_after = _prove_historical_baseline(
            record=record,
            current=postdelete,
            journal=journal,
            writer=writer,
            source_id=source_id,
        )
        state.update(
            status="verified_absent",
            absence_evidence="wall.getById:none" if exact is None else "wall.getById:is_deleted_true",
            postdelete_actual_snapshot_sha256=postdelete.snapshot_sha256,
            postdelete_historical_snapshot_sha256=baseline_after.snapshot_sha256,
            postdelete_exact_read_ids=list(exact_read_ids_after),
        )
        persist()
        return postdelete, baseline_after

    assert exact is not None
    if exact.get("owner_id") != MILOVI_OWNER_ID or exact.get("id") != candidate_post_id:
        raise Issue323UploadWallReconcileBlocked("Upload-created wall post exact readback changed identity")
    exact_owner_id, exact_video_id = _exact_video(exact)
    if (exact_owner_id, exact_video_id) != (ticket.owner_id, ticket.video_id):
        raise Issue323UploadWallReconcileBlocked("Upload-created wall post exact readback changed Clip binding")
    exact_date = exact.get("date")
    if type(exact_date) is not int or exact_date != candidate.publish_date:
        raise Issue323UploadWallReconcileBlocked("Upload-created wall post exact readback changed publication date")

    if state.get("delete_dispatch_started") is True:
        raise Issue323UploadWallReconcileBlocked(
            "Upload-created wall delete dispatch may already have occurred and the post is still live; blind retry is forbidden"
        )

    _prove_target(client)
    dispatch_read = writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=candidate_post_id)
    if _absent_exact(dispatch_read, post_id=candidate_post_id):
        state.update(
            status="verified_absent",
            absence_evidence="wall.getById:none-predelete"
            if dispatch_read is None
            else "wall.getById:is_deleted_true-predelete",
        )
        persist()
    else:
        assert dispatch_read is not None
        if dispatch_read.get("owner_id") != MILOVI_OWNER_ID or dispatch_read.get("id") != candidate_post_id:
            raise Issue323UploadWallReconcileBlocked("Upload-created wall predelete readback changed identity")
        dispatch_owner_id, dispatch_video_id = _exact_video(dispatch_read)
        if (dispatch_owner_id, dispatch_video_id) != (ticket.owner_id, ticket.video_id):
            raise Issue323UploadWallReconcileBlocked("Upload-created wall predelete readback changed Clip binding")
        if dispatch_read.get("date") != candidate.publish_date:
            raise Issue323UploadWallReconcileBlocked("Upload-created wall predelete readback changed publication date")
        state["delete_dispatch_started"] = True
        state["status"] = "delete_dispatch_started"
        persist()
        try:
            writer._call(
                "wall.delete",
                params={"owner_id": MILOVI_OWNER_ID, "post_id": candidate_post_id},
            )
        except Exception:
            ambiguous = writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=candidate_post_id)
            if not _absent_exact(ambiguous, post_id=candidate_post_id):
                raise
            state["delete_exception_reconciled_by_readback"] = True
            persist()

    final_readback = writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=candidate_post_id)
    if not _absent_exact(final_readback, post_id=candidate_post_id):
        raise Issue323UploadWallReconcileBlocked("Exact upload-created wall post still exists after delete response")

    postdelete = writer.capture_wall_snapshot(community_id=MILOVI_COMMUNITY_ID, max_posts_per_surface=10000)
    if not postdelete.complete:
        raise Issue323UploadWallReconcileBlocked("Postdelete wall snapshot is incomplete")
    baseline_after, exact_read_ids_after = _prove_historical_baseline(
        record=record,
        current=postdelete,
        journal=journal,
        writer=writer,
        source_id=source_id,
    )
    state.update(
        status="verified_absent",
        absence_evidence="wall.getById:none-postdelete"
        if final_readback is None
        else "wall.getById:is_deleted_true-postdelete",
        postdelete_actual_snapshot_sha256=postdelete.snapshot_sha256,
        postdelete_historical_snapshot_sha256=baseline_after.snapshot_sha256,
        postdelete_exact_read_ids=list(exact_read_ids_after),
        protected_clip_remote_id=ticket.remote_id,
        protected_clip_preserved=True,
    )
    persist()
    return postdelete, baseline_after


__all__ = [
    "ISSUE323_UPLOAD_WALL_RECOVERY_SOURCES",
    "Issue323UploadWallReconcileBlocked",
    "reconcile_issue323_upload_wall_effect",
]
