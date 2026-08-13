from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkTokenStore, local_vk_write_lock
from video_channel_manager.platforms.vk.milovi_immediate_wall import MILOVI_COMMUNITY_ID, MILOVI_OWNER_ID
from video_channel_manager.platforms.vk.milovi_issue323_finalize import (
    ANOMALY_CLIP_REMOTE_ID,
    ANOMALY_POST_ID,
    ANOMALY_SOURCE_ID,
    MiloviFinalizerBlocked,
    _cleanup_anomaly_475,
    _legacy_marker_ok,
    _load_finalizer_journal,
    _one_video_attachment,
    _parse_remote_id,
    _promote_asset,
    _prove_target,
    _save_finalizer,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import prepare_sources, write_json_atomic
from video_channel_manager.platforms.vk.milovi_token_clip_rollout import _resolve_account
from video_channel_manager.platforms.vk.wall import VkWallWriter

EXECUTION_CONFIRMATION = "ISSUE_323_RECONCILE_TEXT_DRIFT_AND_CLEANUP_475"
RESULT_SCHEMA = "video-manager.milovi-issue-323-anomaly-text-drift-reconcile"
ANOMALY_CREATED_AT = 1786645941
ANOMALY_CREATED_BY = 631487


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _strict_raw_anomaly(post: Mapping[str, Any], source_id: str) -> None:
    if post.get("owner_id") != MILOVI_OWNER_ID or post.get("id") != ANOMALY_POST_ID:
        raise MiloviFinalizerBlocked("Wall 475 identity changed")
    if post.get("date") != ANOMALY_CREATED_AT:
        raise MiloviFinalizerBlocked("Wall 475 original timestamp changed")
    if post.get("from_id") != MILOVI_OWNER_ID:
        raise MiloviFinalizerBlocked("Wall 475 author identity changed")
    created_by = post.get("created_by")
    if created_by is not None and created_by != ANOMALY_CREATED_BY:
        raise MiloviFinalizerBlocked("Wall 475 creator identity changed")
    if str(post.get("post_type") or "post") != "post":
        raise MiloviFinalizerBlocked("Wall 475 post type changed")
    post_source = post.get("post_source")
    if not isinstance(post_source, Mapping) or post_source.get("type") != "vk":
        raise MiloviFinalizerBlocked("Wall 475 provider source changed")

    owner_id, video_id, expanded = _one_video_attachment(post)
    expected_owner, expected_video = _parse_remote_id(ANOMALY_CLIP_REMOTE_ID)
    if (owner_id, video_id) != (expected_owner, expected_video):
        raise MiloviFinalizerBlocked("Wall 475 no longer attaches exact Clip 456239232")
    observed_type = str(expanded.get("type") or "")
    if observed_type and observed_type != "short_video":
        raise MiloviFinalizerBlocked("Wall 475 attachment is not native short_video")
    if not _legacy_marker_ok(expanded, source_id):
        raise MiloviFinalizerBlocked("Wall 475 attachment lost source marker o1WXIMupuws")


class _TextNormalizedAnomalyWriter:
    def __init__(self, delegate: VkWallWriter, source_id: str) -> None:
        self._delegate = delegate
        self._source_id = source_id

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        post = self._delegate.read_post(community_id=community_id, post_id=post_id)
        if post is None:
            return None
        if community_id != MILOVI_COMMUNITY_ID or post_id != ANOMALY_POST_ID:
            return post
        _strict_raw_anomaly(post, self._source_id)
        normalized = dict(post)
        normalized["text"] = ""
        return normalized


def run_reconcile(
    *,
    confirmation: str,
    output_path: Path,
    finalizer_journal_path: Path,
    work_dir: Path,
) -> dict[str, Any]:
    if confirmation != EXECUTION_CONFIRMATION:
        raise MiloviFinalizerBlocked(f"Exact confirmation required: {EXECUTION_CONFIRMATION}")

    legacy_assets = prepare_sources(work_dir)
    legacy_by_id = {asset.source_id: asset for asset in legacy_assets}
    promoted_assets = [_promote_asset(asset) for asset in legacy_assets]
    promoted_by_id = {asset.source_id: asset for asset in promoted_assets}
    if ANOMALY_SOURCE_ID not in legacy_by_id:
        raise MiloviFinalizerBlocked("Exact anomaly source is absent from reviewed source set")

    finalizer = _load_finalizer_journal(finalizer_journal_path, promoted_assets)
    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    alias, client = _resolve_account(store, settings.vk_api_version)
    writer = VkWallWriter(token_store=store, account_alias=alias, api_version=settings.vk_api_version)
    normalized_writer = _TextNormalizedAnomalyWriter(writer, ANOMALY_SOURCE_ID)
    lock_path = settings.data_dir / "locks" / f"vk-{MILOVI_COMMUNITY_ID}-issue-323-finalizer.lock"

    try:
        with local_vk_write_lock(
            lock_path,
            account=alias,
            community_id=MILOVI_COMMUNITY_ID,
            operation="milovi-issue-323-reconcile-wall-475-text-drift",
        ):
            _prove_target(client)
            raw_post = writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=ANOMALY_POST_ID)
            if raw_post is not None:
                _strict_raw_anomaly(raw_post, ANOMALY_SOURCE_ID)
                raw_text = str(raw_post.get("text") or "")
                state = finalizer["cleanup_475"]
                state.update(
                    observed_provider_text_nonempty=bool(raw_text.strip()),
                    observed_provider_text_sha256=_sha256_text(raw_text),
                    observed_raw_post_sha256=_sha256_text(json.dumps(raw_post, sort_keys=True, ensure_ascii=False)),
                )
                _save_finalizer(finalizer_journal_path, finalizer)

            _cleanup_anomaly_475(
                writer=normalized_writer,  # type: ignore[arg-type]
                client=client,
                legacy_asset=legacy_by_id[ANOMALY_SOURCE_ID],
                promoted_asset=promoted_by_id[ANOMALY_SOURCE_ID],
                finalizer=finalizer,
                finalizer_path=finalizer_journal_path,
            )

            if writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=ANOMALY_POST_ID) is not None:
                raise MiloviFinalizerBlocked("Exact anomaly wall 475 still exists after reconciliation")

            payload = {
                "schema_name": RESULT_SCHEMA,
                "schema_version": 1,
                "status": "verified_absent",
                "project_key": "milovi-cake",
                "community_id": MILOVI_COMMUNITY_ID,
                "owner_id": MILOVI_OWNER_ID,
                "wall_remote_id": f"{MILOVI_OWNER_ID}_{ANOMALY_POST_ID}",
                "clip_remote_id": ANOMALY_CLIP_REMOTE_ID,
                "source_id": ANOMALY_SOURCE_ID,
                "provider_text_drift_tolerated": True,
                "cleanup_state": finalizer["cleanup_475"],
            }
            write_json_atomic(output_path, payload)
            return payload
    except Exception as exc:
        payload = {
            "schema_name": RESULT_SCHEMA,
            "schema_version": 1,
            "status": "blocked",
            "project_key": "milovi-cake",
            "community_id": MILOVI_COMMUNITY_ID,
            "owner_id": MILOVI_OWNER_ID,
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }
        write_json_atomic(output_path, payload)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile exact Issue #323 wall 475 after provider text drift")
    parser.add_argument("--execute", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("operator-output/milovi-cake-issue-323-anomaly-text-drift-reconcile.json"),
    )
    parser.add_argument(
        "--finalizer-journal",
        type=Path,
        default=Path("data/vk/milovi-cake/issue-323-finalizer-journal.json"),
    )
    parser.add_argument("--work-dir", type=Path, default=Path("operator-output/milovi-cake-issue-323-work"))
    args = parser.parse_args()
    result = run_reconcile(
        confirmation=args.execute,
        output_path=args.output,
        finalizer_journal_path=args.finalizer_journal,
        work_dir=args.work_dir,
    )
    print(f"Milovi #323 anomaly reconcile: {result['status']} | result={args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MiloviFinalizerBlocked, OSError, ValueError) as exc:
        print(f"STOP: {type(exc).__name__}: {exc}")
        raise SystemExit(3) from exc
