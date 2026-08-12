from __future__ import annotations

import importlib
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from video_channel_manager.config import get_settings
from video_channel_manager.editorial._project_profiles import MILOVI_CAKE, resolve_project_key
from video_channel_manager.platforms.vk import VkApiClient, VkInventoryService, VkTokenStore, local_vk_write_lock
from video_channel_manager.platforms.vk.milovi_immediate_wall import (
    MILOVI_COMMUNITY_ID,
    MILOVI_OWNER_ID,
    MILOVI_SOURCE_ALLOWLIST,
    MiloviImmediateWallAuthority,
    MiloviImmediateWallWriter,
)
from video_channel_manager.platforms.vk.milovi_native_clip_browser import (
    BrowserRuntime,
    assert_browser_target,
    click_publish,
    detect_browser_runtime,
    open_add_clip,
    select_exact_publisher,
    set_file_and_metadata,
    uncheck_wall,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import (
    ROLL_OUT_IDS,
    SOURCE_SNAPSHOT_ID,
    YOUTUBE_CHANNEL_ID,
    SourceAsset,
    prepare_sources,
    write_json_atomic,
)
from video_channel_manager.platforms.vk.wall_safety import VkWallSurface

ISSUE_NUMBER = 323
EXECUTION_CONFIRMATION = "ISSUE_323_UPLOAD_12_AND_WALL_IMMEDIATE"
CANARY_SOURCE_ID = "d48QLgOuiTs"
ROLLOUT_SCHEMA = "video-manager.milovi-issue-323-rollout"
JOURNAL_SCHEMA = "video-manager.milovi-issue-323-journal"
MILOVI_SCREEN_NAME = "milovi_cake"

if frozenset(ROLL_OUT_IDS) != MILOVI_SOURCE_ALLOWLIST:
    raise RuntimeError("Issue #323 rollout allowlist differs from the reviewed immediate-wall authority")


class MiloviRolloutBlocked(RuntimeError):
    pass


def _utc_stamp() -> str:
    return datetime.now(UTC).isoformat()


def _resolve_vk_account(store: VkTokenStore, api_version: str) -> tuple[str, VkApiClient]:
    candidates: list[tuple[int, str, VkApiClient]] = []
    preferred = {"milovi-cake": 0, "shared-vk-user": 1}
    for account in store.list_accounts():
        if not store.token_exists(account.alias):
            continue
        client = VkApiClient(token_store=store, account_alias=account.alias, api_version=api_version)
        try:
            communities = client.list_managed_communities()
        except Exception:
            continue
        exact = [item for item in communities if int(item.community_id) == MILOVI_COMMUNITY_ID]
        if len(exact) != 1:
            continue
        screen = str(exact[0].screen_name or "").strip().casefold()
        if screen and screen != MILOVI_SCREEN_NAME:
            raise MiloviRolloutBlocked(
                f"Managed-community readback maps {MILOVI_COMMUNITY_ID} to unexpected screen_name {screen!r}"
            )
        candidates.append((preferred.get(account.alias, 10), account.alias, client))
    if not candidates:
        raise MiloviRolloutBlocked("No registered VK credential proved management of exact Milovi community 68859909")
    candidates.sort(key=lambda row: (row[0], row[1]))
    _, alias, client = candidates[0]
    resolved = resolve_project_key(
        {"project_key": MILOVI_CAKE, "community_id": MILOVI_COMMUNITY_ID, "owner_id": MILOVI_OWNER_ID}
    )
    if resolved != MILOVI_CAKE:
        raise MiloviRolloutBlocked("Canonical Milovi project/community/owner identity failed")
    return alias, client


def _inventory_records(client: VkApiClient) -> list[Any]:
    package = VkInventoryService(client).build_audit_package(str(MILOVI_COMMUNITY_ID))
    if int(package.channel.ref.channel_id) != MILOVI_COMMUNITY_ID:
        raise MiloviRolloutBlocked("VK inventory returned the wrong community")
    return list(package.videos)


def _record_type(record: Any) -> str:
    metadata = record.metadata if isinstance(record.metadata, dict) else {}
    return str(metadata.get("vk_video_type") or "")


def _record_matches_source(record: Any, asset: SourceAsset) -> bool:
    marker = f"youtube.com/shorts/{asset.source_id}".casefold()
    if marker not in str(record.description or "").casefold():
        return False
    if record.duration_seconds is not None and abs(int(record.duration_seconds) - asset.duration_seconds) > 4:
        return False
    return True


def _find_existing_clip(records: Iterable[Any], asset: SourceAsset) -> Any | None:
    clips = [
        record for record in records if _record_matches_source(record, asset) and _record_type(record) == "short_video"
    ]
    if len(clips) > 1:
        raise MiloviRolloutBlocked(
            f"Multiple existing native Clips match {asset.source_id}: {[item.ref.remote_id for item in clips]}"
        )
    ordinary = [
        record for record in records if _record_matches_source(record, asset) and _record_type(record) != "short_video"
    ]
    if ordinary and not clips:
        raise MiloviRolloutBlocked(
            f"Existing source marker is attached to ordinary VK video(s) for {asset.source_id}: "
            f"{[item.ref.remote_id for item in ordinary]}"
        )
    return clips[0] if clips else None


def _parse_video_id(remote_id: str) -> int:
    owner_text, separator, video_text = remote_id.partition("_")
    if not separator or int(owner_text) != MILOVI_OWNER_ID:
        raise MiloviRolloutBlocked(f"Unexpected VK remote ID: {remote_id}")
    video_id = int(video_text)
    if video_id <= 0:
        raise MiloviRolloutBlocked(f"Unexpected VK video ID: {remote_id}")
    return video_id


def _wall_attachment_state(writer: MiloviImmediateWallWriter, video_id: int) -> tuple[str, str | None]:
    snapshot = writer.capture_wall_snapshot(community_id=MILOVI_COMMUNITY_ID, max_posts_per_surface=10000)
    if not snapshot.complete:
        raise MiloviRolloutBlocked("Complete published/postponed wall readback is unavailable")
    attachment = f"video{MILOVI_OWNER_ID}_{video_id}"
    matches = [post for post in snapshot.posts if attachment in post.attachments]
    if len(matches) > 1:
        raise MiloviRolloutBlocked(
            f"Clip {MILOVI_OWNER_ID}_{video_id} appears in multiple wall posts: "
            f"{[f'{item.surface.value}:{item.remote_id}' for item in matches]}"
        )
    if not matches:
        return "absent", None
    match = matches[0]
    if match.surface is VkWallSurface.POSTPONED:
        raise MiloviRolloutBlocked(
            f"Clip {MILOVI_OWNER_ID}_{video_id} is already in postponed wall post {match.remote_id}; "
            "Issue #323 requires immediate publication"
        )
    return "published", match.remote_id


def _wait_for_exact_clip(
    client: VkApiClient,
    *,
    asset: SourceAsset,
    baseline: set[str],
    timeout_seconds: int,
) -> Any:
    deadline = time.monotonic() + timeout_seconds
    ordinary: list[str] = []
    while time.monotonic() < deadline:
        records = _inventory_records(client)
        matching = [
            record
            for record in records
            if record.ref.remote_id not in baseline and _record_matches_source(record, asset)
        ]
        clips = [record for record in matching if _record_type(record) == "short_video"]
        ordinary = [record.ref.remote_id for record in matching if _record_type(record) != "short_video"]
        if len(clips) > 1:
            raise MiloviRolloutBlocked(
                f"Multiple new native Clips match {asset.source_id}: {[item.ref.remote_id for item in clips]}"
            )
        if len(clips) == 1:
            return clips[0]
        time.sleep(10)
    if ordinary:
        raise MiloviRolloutBlocked(
            f"VK created ordinary video instead of native Clip for {asset.source_id}: {ordinary}"
        )
    raise MiloviRolloutBlocked(f"Publish outcome for {asset.source_id} was not recovered as an exact native Clip")


def _new_journal() -> dict[str, Any]:
    return {
        "schema_name": JOURNAL_SCHEMA,
        "schema_version": 1,
        "project_key": MILOVI_CAKE,
        "community_id": MILOVI_COMMUNITY_ID,
        "owner_id": MILOVI_OWNER_ID,
        "source_snapshot_id": SOURCE_SNAPSHOT_ID,
        "canary_source_id": CANARY_SOURCE_ID,
        "canary_verified": False,
        "items": {source_id: {"status": "pending"} for source_id in ROLL_OUT_IDS},
        "updated_at": _utc_stamp(),
    }


def _load_journal(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return _new_journal()
    payload = __import__("json").loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MiloviRolloutBlocked("Issue #323 rollout journal is not a JSON object")
    if payload.get("schema_name") != JOURNAL_SCHEMA or int(payload.get("schema_version") or 0) != 1:
        raise MiloviRolloutBlocked("Unexpected Issue #323 rollout journal schema")
    if (
        payload.get("project_key") != MILOVI_CAKE
        or int(payload.get("community_id") or 0) != MILOVI_COMMUNITY_ID
        or int(payload.get("owner_id") or 0) != MILOVI_OWNER_ID
        or payload.get("source_snapshot_id") != SOURCE_SNAPSHOT_ID
    ):
        raise MiloviRolloutBlocked("Issue #323 rollout journal identity/provenance mismatch")
    return payload


def _save_journal(path: Path, journal: dict[str, Any]) -> None:
    journal["updated_at"] = _utc_stamp()
    write_json_atomic(path, journal)


def _item(journal: dict[str, Any], source_id: str) -> dict[str, Any]:
    items = journal.setdefault("items", {})
    raw = items.setdefault(source_id, {"status": "pending"})
    if not isinstance(raw, dict):
        raise MiloviRolloutBlocked(f"Invalid journal item for {source_id}")
    return raw


def _mark(
    journal_path: Path,
    journal: dict[str, Any],
    source_id: str,
    *,
    status: str,
    **fields: object,
) -> None:
    item = _item(journal, source_id)
    item["status"] = status
    item.update(fields)
    item["updated_at"] = _utc_stamp()
    _save_journal(journal_path, journal)


def _reconcile_unresolved(
    *,
    client: VkApiClient,
    writer: MiloviImmediateWallWriter,
    asset: SourceAsset,
    journal_path: Path,
    journal: dict[str, Any],
) -> str:
    item = _item(journal, asset.source_id)
    status = str(item.get("status") or "pending")
    browser_unknown = {"upload_intent", "file_selected", "publish_intent", "publish_clicked", "may_exist"}
    if status in browser_unknown:
        clip = _find_existing_clip(_inventory_records(client), asset)
        if clip is None:
            raise MiloviRolloutBlocked(
                f"Prior browser effect for {asset.source_id} is unresolved ({status}); exact Clip absence is not replay authority"
            )
        _mark(
            journal_path,
            journal,
            asset.source_id,
            status="clip_verified",
            clip_remote_id=clip.ref.remote_id,
            clip_origin="reconciled_after_unknown",
        )
        return "clip_verified"
    if status == "wall_may_exist":
        clip = _find_existing_clip(_inventory_records(client), asset)
        if clip is None:
            raise MiloviRolloutBlocked(f"Wall reconciliation lost exact Clip identity for {asset.source_id}")
        wall_state, wall_id = _wall_attachment_state(writer, _parse_video_id(str(clip.ref.remote_id)))
        if wall_state != "published" or wall_id is None:
            raise MiloviRolloutBlocked(
                f"Prior wall effect for {asset.source_id} remains unresolved; absence is not replay authority"
            )
        _mark(
            journal_path,
            journal,
            asset.source_id,
            status="wall_verified",
            clip_remote_id=clip.ref.remote_id,
            wall_remote_id=wall_id,
            wall_origin="reconciled_after_unknown",
        )
        return "wall_verified"
    return status


def _browser_upload_one(
    *,
    page: Any,
    client: VkApiClient,
    asset: SourceAsset,
    journal_path: Path,
    journal: dict[str, Any],
    verify_timeout_seconds: int,
) -> Any:
    baseline_records = _inventory_records(client)
    existing = _find_existing_clip(baseline_records, asset)
    if existing is not None:
        _mark(
            journal_path,
            journal,
            asset.source_id,
            status="clip_verified",
            clip_remote_id=existing.ref.remote_id,
            clip_origin="adopted_existing",
        )
        return existing

    baseline = {record.ref.remote_id for record in baseline_records}
    open_add_clip(page)
    select_exact_publisher(page)
    assert_browser_target(page, stage="pre-file-final")
    _mark(
        journal_path,
        journal,
        asset.source_id,
        status="upload_intent",
        media_sha256=asset.media_sha256,
        media_path=asset.media_path,
        baseline_count=len(baseline),
    )
    try:
        set_file_and_metadata(page, asset)
        _mark(journal_path, journal, asset.source_id, status="file_selected")
        select_exact_publisher(page)
        assert_browser_target(page, stage="pre-publish")
        uncheck_wall(page)
        _mark(journal_path, journal, asset.source_id, status="publish_intent")
        click_publish(page)
        _mark(journal_path, journal, asset.source_id, status="publish_clicked")
    except Exception as exc:
        _mark(
            journal_path,
            journal,
            asset.source_id,
            status="may_exist",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        raise

    clip = _wait_for_exact_clip(
        client,
        asset=asset,
        baseline=baseline,
        timeout_seconds=verify_timeout_seconds,
    )
    _mark(
        journal_path,
        journal,
        asset.source_id,
        status="clip_verified",
        clip_remote_id=clip.ref.remote_id,
        clip_origin="new_browser_native_clip",
    )
    return clip


def _ensure_immediate_wall(
    *,
    writer: MiloviImmediateWallWriter,
    asset: SourceAsset,
    clip: Any,
    journal_path: Path,
    journal: dict[str, Any],
) -> str:
    video_id = _parse_video_id(str(clip.ref.remote_id))
    state, post_remote_id = _wall_attachment_state(writer, video_id)
    if state == "published" and post_remote_id:
        _mark(
            journal_path,
            journal,
            asset.source_id,
            status="wall_verified",
            clip_remote_id=clip.ref.remote_id,
            wall_remote_id=post_remote_id,
            wall_origin="adopted_existing_published",
        )
        return post_remote_id

    _mark(journal_path, journal, asset.source_id, status="wall_intent", clip_remote_id=clip.ref.remote_id)
    try:
        result = writer.post_verified_clip_now(
            authority=MiloviImmediateWallAuthority(source_video_id=asset.source_id),
            video_id=video_id,
            message=asset.wall_message,
            guid=f"vcm-milovi-323-{asset.source_id}",
        )
    except Exception as exc:
        _mark(
            journal_path,
            journal,
            asset.source_id,
            status="wall_may_exist",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        raise
    _mark(
        journal_path,
        journal,
        asset.source_id,
        status="wall_verified",
        clip_remote_id=clip.ref.remote_id,
        wall_remote_id=result.remote_id,
        wall_origin="new_immediate",
    )
    return result.remote_id


def _result_payload(
    *,
    status: str,
    journal: dict[str, Any],
    assets: list[SourceAsset],
    vk_account_alias: str | None,
    browser: BrowserRuntime | None,
    error: Exception | None = None,
) -> dict[str, Any]:
    return {
        "schema_name": ROLLOUT_SCHEMA,
        "schema_version": 1,
        "status": status,
        "project_key": MILOVI_CAKE,
        "youtube_channel_id": YOUTUBE_CHANNEL_ID,
        "community_id": MILOVI_COMMUNITY_ID,
        "owner_id": MILOVI_OWNER_ID,
        "issue_number": ISSUE_NUMBER,
        "source_snapshot_id": SOURCE_SNAPSHOT_ID,
        "publication_mode": "native_clip_then_immediate_wall",
        "postponed_wall_authorized": False,
        "allowlist": list(ROLL_OUT_IDS),
        "canary_source_id": CANARY_SOURCE_ID,
        "canary_verified": bool(journal.get("canary_verified")),
        "vk_account_alias_used_as_credential_only": vk_account_alias,
        "browser_runtime": asdict(browser) if browser else None,
        "source_assets": [asdict(asset) for asset in assets],
        "items": journal.get("items", {}),
        "error": {"type": type(error).__name__, "message": str(error)} if error is not None else None,
        "observed_at": _utc_stamp(),
    }


def run_issue_323_rollout(
    *,
    confirmation: str,
    output_path: Path,
    journal_path: Path,
    work_dir: Path,
    verify_timeout_seconds: int = 1800,
) -> dict[str, Any]:
    if confirmation != EXECUTION_CONFIRMATION:
        raise MiloviRolloutBlocked("Exact Issue #323 execution confirmation is required")
    settings = get_settings()
    settings.ensure_runtime_directories()
    store = VkTokenStore(settings.data_dir)
    journal = _load_journal(journal_path)
    assets: list[SourceAsset] = []
    alias: str | None = None
    browser: BrowserRuntime | None = None

    try:
        assets = prepare_sources(work_dir)
        alias, client = _resolve_vk_account(store, settings.vk_api_version)
        writer = MiloviImmediateWallWriter(
            token_store=store,
            account_alias=alias,
            api_version=settings.vk_api_version,
        )
        browser = detect_browser_runtime()
        try:
            sync_playwright = importlib.import_module("playwright.sync_api").sync_playwright
        except ImportError as exc:
            raise MiloviRolloutBlocked(
                "Playwright is not installed; install the repository browser-read extra"
            ) from exc

        lock_path = settings.data_dir / "vk" / "milovi-cake-issue-323.lock"
        with local_vk_write_lock(
            lock_path, account=alias, community_id=MILOVI_COMMUNITY_ID, operation="issue-323-rollout"
        ):
            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=browser.user_data_dir,
                    executable_path=browser.executable,
                    headless=False,
                    viewport={"width": 1440, "height": 1000},
                    args=["--disable-features=Translate", f"--profile-directory={browser.profile_directory}"],
                )
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    ordered = sorted(
                        assets,
                        key=lambda asset: (0 if asset.source_id == CANARY_SOURCE_ID else 1, asset.source_id),
                    )
                    for asset in ordered:
                        status = _reconcile_unresolved(
                            client=client,
                            writer=writer,
                            asset=asset,
                            journal_path=journal_path,
                            journal=journal,
                        )
                        if status == "wall_verified":
                            if asset.source_id == CANARY_SOURCE_ID:
                                journal["canary_verified"] = True
                                _save_journal(journal_path, journal)
                            continue
                        if asset.source_id != CANARY_SOURCE_ID and not bool(journal.get("canary_verified")):
                            raise MiloviRolloutBlocked("Batch is blocked until the exact canary is fully verified")

                        if status == "clip_verified":
                            clip = _find_existing_clip(_inventory_records(client), asset)
                            if clip is None:
                                raise MiloviRolloutBlocked(
                                    f"Journal clip_verified state cannot be read back for {asset.source_id}"
                                )
                        else:
                            clip = _browser_upload_one(
                                page=page,
                                client=client,
                                asset=asset,
                                journal_path=journal_path,
                                journal=journal,
                                verify_timeout_seconds=verify_timeout_seconds,
                            )
                        _ensure_immediate_wall(
                            writer=writer,
                            asset=asset,
                            clip=clip,
                            journal_path=journal_path,
                            journal=journal,
                        )
                        if asset.source_id == CANARY_SOURCE_ID:
                            journal["canary_verified"] = True
                            _save_journal(journal_path, journal)
                finally:
                    context.close()

        completed = all(str(_item(journal, source_id).get("status")) == "wall_verified" for source_id in ROLL_OUT_IDS)
        if not completed:
            raise MiloviRolloutBlocked("Issue #323 batch ended without 12 wall_verified items")
        result = _result_payload(
            status="batch_verified",
            journal=journal,
            assets=assets,
            vk_account_alias=alias,
            browser=browser,
        )
        write_json_atomic(output_path, result)
        return result
    except Exception as exc:
        result = _result_payload(
            status="blocked_unknown_requires_reconciliation",
            journal=journal,
            assets=assets,
            vk_account_alias=alias,
            browser=browser,
            error=exc,
        )
        write_json_atomic(output_path, result)
        raise


__all__ = [
    "CANARY_SOURCE_ID",
    "EXECUTION_CONFIRMATION",
    "ISSUE_NUMBER",
    "JOURNAL_SCHEMA",
    "ROLLOUT_SCHEMA",
    "MiloviRolloutBlocked",
    "run_issue_323_rollout",
]
