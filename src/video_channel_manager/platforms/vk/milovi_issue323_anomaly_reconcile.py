from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore, local_vk_write_lock
from video_channel_manager.platforms.vk.milovi_immediate_wall import MILOVI_COMMUNITY_ID, MILOVI_OWNER_ID
from video_channel_manager.platforms.vk.milovi_issue323_finalize import (
    ANOMALY_CLIP_REMOTE_ID,
    ANOMALY_POST_ID,
    ANOMALY_SOURCE_ID,
    MiloviFinalizerBlocked,
    _assert_native_clip,
    _legacy_marker_ok,
    _load_finalizer_journal,
    _one_video_attachment,
    _promote_asset,
    _save_finalizer,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import (
    SourceAsset,
    prepare_sources,
    write_json_atomic,
)
from video_channel_manager.platforms.vk.milovi_token_clip_rollout import (
    _parse_remote_id,
    _prove_target,
    _resolve_account,
)
from video_channel_manager.platforms.vk.wall import VkWallWriter

EXECUTION_CONFIRMATION = "ISSUE_323_RECONCILE_TEXT_DRIFT_AND_CLEANUP_475"
RESULT_SCHEMA = "video-manager.milovi-issue-323-anomaly-text-drift-reconcile"
IDENTITY_CONTRACT = "milovi-wall-475-stable-identity-v1"
ANOMALY_CREATED_AT = 1786645941
ANOMALY_CREATED_BY = 631487


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_wall475_identity(post: Mapping[str, Any], source_id: str) -> None:
    """Prove the exact wall object using provider-stable identity fields only.

    VK may re-project mutable presentation metadata such as wall text and
    ``post_source`` between reads. Those fields are recorded as evidence, but
    they are deliberately not part of the destructive identity predicate.
    """

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

    owner_id, video_id, expanded = _one_video_attachment(post)
    expected_owner, expected_video = _parse_remote_id(ANOMALY_CLIP_REMOTE_ID)
    if (owner_id, video_id) != (expected_owner, expected_video):
        raise MiloviFinalizerBlocked("Wall 475 no longer attaches exact Clip 456239232")
    observed_type = str(expanded.get("type") or "")
    if observed_type and observed_type != "short_video":
        raise MiloviFinalizerBlocked("Wall 475 attachment is not native short_video")
    if not _legacy_marker_ok(expanded, source_id):
        raise MiloviFinalizerBlocked("Wall 475 attachment lost source marker o1WXIMupuws")


def _record_observed_projection(state: dict[str, Any], post: Mapping[str, Any]) -> None:
    raw_text = str(post.get("text") or "")
    raw_post_source = post.get("post_source")
    post_source_type = str(raw_post_source.get("type") or "") if isinstance(raw_post_source, Mapping) else ""
    state.update(
        identity_contract=IDENTITY_CONTRACT,
        observed_provider_text_nonempty=bool(raw_text.strip()),
        observed_provider_text_sha256=_sha256_text(raw_text),
        observed_post_source_type=post_source_type,
        observed_post_source_sha256=_sha256_text(
            json.dumps(raw_post_source, sort_keys=True, ensure_ascii=False, default=str)
        ),
        observed_raw_post_sha256=_sha256_text(
            json.dumps(post, sort_keys=True, ensure_ascii=False, default=str)
        ),
        mutable_projection_fields=["text", "post_source"],
    )


def _cleanup_exact_wall475(
    *,
    writer: VkWallWriter,
    client: VkApiClient,
    legacy_asset: SourceAsset,
    promoted_asset: SourceAsset,
    finalizer: dict[str, Any],
    finalizer_path: Path,
) -> None:
    """Delete only exact wall 475 after fresh stable-identity proofs.

    The intent is persisted before the provider write. Immediately before the
    delete, Milovi target identity is re-proved and wall 475 is re-read through
    the same stable identity contract. An ambiguous delete is never replayed
    blindly: provider state is read back first. The protected Clip is verified
    both before and after the wall deletion.
    """

    state = finalizer["cleanup_475"]
    post = writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=ANOMALY_POST_ID)
    if post is None:
        _assert_native_clip(
            writer,
            promoted_asset,
            ANOMALY_CLIP_REMOTE_ID,
            description_mode="legacy_or_promoted",
        )
        state.update(status="verified_absent", identity_contract=IDENTITY_CONTRACT)
        _save_finalizer(finalizer_path, finalizer)
        return

    _validate_wall475_identity(post, legacy_asset.source_id)
    _assert_native_clip(
        writer,
        promoted_asset,
        ANOMALY_CLIP_REMOTE_ID,
        description_mode="legacy_or_promoted",
    )
    _record_observed_projection(state, post)
    state.update(
        status="delete_intent",
        predelete_post_sha256=_sha256_text(json.dumps(post, sort_keys=True, ensure_ascii=False, default=str)),
    )
    _save_finalizer(finalizer_path, finalizer)

    _prove_target(client)
    dispatch_post = writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=ANOMALY_POST_ID)
    if dispatch_post is None:
        _assert_native_clip(
            writer,
            promoted_asset,
            ANOMALY_CLIP_REMOTE_ID,
            description_mode="legacy_or_promoted",
        )
        state.update(status="verified_absent", identity_contract=IDENTITY_CONTRACT)
        _save_finalizer(finalizer_path, finalizer)
        return
    _validate_wall475_identity(dispatch_post, legacy_asset.source_id)

    try:
        writer._call("wall.delete", params={"owner_id": MILOVI_OWNER_ID, "post_id": ANOMALY_POST_ID})
    except Exception:
        if writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=ANOMALY_POST_ID) is not None:
            raise

    if writer.read_post(community_id=MILOVI_COMMUNITY_ID, post_id=ANOMALY_POST_ID) is not None:
        raise MiloviFinalizerBlocked("Exact anomaly wall 475 still exists after delete response")

    _assert_native_clip(
        writer,
        promoted_asset,
        ANOMALY_CLIP_REMOTE_ID,
        description_mode="legacy_or_promoted",
    )
    state.update(status="verified_absent", identity_contract=IDENTITY_CONTRACT)
    _save_finalizer(finalizer_path, finalizer)


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
    lock_path = settings.data_dir / "locks" / f"vk-{MILOVI_COMMUNITY_ID}-issue-323-finalizer.lock"

    try:
        with local_vk_write_lock(
            lock_path,
            account=alias,
            community_id=MILOVI_COMMUNITY_ID,
            operation="milovi-issue-323-reconcile-wall-475-stable-identity",
        ):
            _prove_target(client)
            _cleanup_exact_wall475(
                writer=writer,
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
                "identity_contract": IDENTITY_CONTRACT,
                "mutable_projection_fields_not_used_for_identity": ["text", "post_source"],
                # Backward-compatible result flags consumed by older operator wrappers.
                "provider_text_drift_tolerated": True,
                "provider_source_drift_tolerated_only_here": True,
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
            "identity_contract": IDENTITY_CONTRACT,
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }
        write_json_atomic(output_path, payload)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile exact Issue #323 wall 475 using provider-stable identity"
    )
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
