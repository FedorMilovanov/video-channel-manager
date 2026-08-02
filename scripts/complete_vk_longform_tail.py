#!/usr/bin/env python3
"""Complete the reviewed 26-item VK long-form tail without widening scope.

Default mode is read-only. ``--execute`` may upload only ledger rows that have
no VK ID and no prior VK upload attempt, repairs source YouTube thumbnails for
all exact queue mappings, and creates/fills the five-part Sproul VK album.
Video upload never publishes to the wall.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore
from video_channel_manager.platforms.vk.publishing import render_vk_publication
from video_channel_manager.platforms.vk.thumbnails import VkThumbnailWriter
from video_channel_manager.platforms.vk.writer import VkUploadTicket, VkVideoWriter, VkWriteError

PROJECT_KEY = "lord-god-strength"
COMMUNITY_ID = 60805374
OWNER_ID = -60805374
ACCOUNT_ALIAS = "legendary-poet"
YOUTUBE_CHANNEL_ID = "UCeSJsC6go2c9pdJCuUI1BYA"
SOURCE_PLAYLIST_ID = "PLW_VRhdOSkXo"
TARGET_ALBUM_TITLE = "Архитектура мышления — Р. Ч. Спроул"
SERIES_IDS = [
    "pDU8kdhDfLo",
    "uI-wfRaq2SA",
    "-q2TcD8ldb4",
    "T8s9DNkuavQ",
    "QswEQFZfV2U",
]
MISSING_PART_ID = "uI-wfRaq2SA"
QUEUE_SHA256 = "b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path, default: object) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def operation_dir(repo: Path) -> Path:
    return repo / "data" / "vk-upload" / "verified-longform-26" / "supplemental"


def ledger_path(repo: Path) -> Path:
    return repo / "data" / "vk-upload" / "verified-longform-26" / "upload-ledger.db"


def media_dir(repo: Path) -> Path:
    return repo / "data" / "vk-upload" / "verified-longform-26" / "media"


def load_rows(repo: Path) -> list[dict[str, Any]]:
    path = ledger_path(repo)
    if not path.is_file():
        raise RuntimeError(f"Long-form ledger not found: {path}")
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            """
            SELECT youtube_id,ordinal,title,youtube_url,duration_seconds,published_at,
                   status,local_path,local_sha256,local_size,save_attempted,
                   vk_owner_id,vk_video_id,upload_attempted,last_error
            FROM operations ORDER BY ordinal DESC
            """
        ).fetchall()
    result = [dict(row) for row in rows]
    if len(result) != 26:
        raise RuntimeError(f"Expected the reviewed 26-item queue, found {len(result)} rows")
    if {row["youtube_id"] for row in result}.issuperset(SERIES_IDS) is False:
        raise RuntimeError("The reviewed ledger does not contain the complete five-part Sproul series")
    return result


def update_ledger_after_upload(
    repo: Path,
    row: dict[str, Any],
    *,
    media: Path,
    ticket: VkUploadTicket,
    upload_response: dict[str, Any],
) -> None:
    path = ledger_path(repo)
    now = utc_now()
    with sqlite3.connect(path) as db:
        db.execute(
            """
            UPDATE operations SET
                status='confirmed', local_path=?, local_sha256=?, local_size=?,
                save_attempted=1, vk_owner_id=?, vk_video_id=?, upload_attempted=1,
                upload_response_json=?, last_error=NULL, updated_at=?, confirmed_at=?
            WHERE youtube_id=?
            """,
            (
                str(media),
                sha256_file(media),
                media.stat().st_size,
                ticket.owner_id,
                ticket.video_id,
                json.dumps(upload_response, ensure_ascii=False, separators=(",", ":")),
                now,
                now,
                row["youtube_id"],
            ),
        )
        db.commit()


def parse_remote(row: dict[str, Any]) -> tuple[int, int] | None:
    owner = row.get("vk_owner_id")
    video = row.get("vk_video_id")
    if isinstance(owner, int) and isinstance(video, int):
        return owner, video
    return None


def visible_state(writer: VkVideoWriter, row: dict[str, Any]) -> dict[str, Any] | None:
    remote = parse_remote(row)
    if remote is None:
        return None
    return writer.read_video(owner_id=remote[0], video_id=remote[1])


def yt_dlp_command() -> list[str]:
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    try:
        import yt_dlp  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("yt-dlp is required: python -m pip install -U yt-dlp") from exc
    return [sys.executable, "-m", "yt_dlp"]


def youtube_metadata(url: str) -> dict[str, Any]:
    command = [*yt_dlp_command(), "--no-playlist", "--dump-single-json", "--skip-download", url]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"yt-dlp metadata failed: {completed.stderr[-1500:]}")
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("yt-dlp metadata returned a non-object")
    return payload


def download_video(row: dict[str, Any], target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and target.stat().st_size > 0:
        return target
    template = str(target.with_suffix(".%(ext)s"))
    command = [
        *yt_dlp_command(),
        "--no-playlist",
        "--retries",
        "10",
        "--fragment-retries",
        "10",
        "--merge-output-format",
        "mp4",
        "--recode-video",
        "mp4",
        "-f",
        "bv*+ba/b",
        "-o",
        template,
        str(row["youtube_url"]),
    ]
    completed = subprocess.run(command, check=False)
    candidates = sorted(target.parent.glob(f"{target.stem}*.mp4"), key=lambda item: item.stat().st_size, reverse=True)
    if completed.returncode != 0 or not candidates:
        raise RuntimeError(f"yt-dlp video download failed for {row['youtube_id']}")
    if candidates[0] != target:
        candidates[0].replace(target)
    return target


def download_thumbnail(youtube_id: str, target: Path) -> tuple[Path, str]:
    target.parent.mkdir(parents=True, exist_ok=True)
    urls = [
        f"https://i.ytimg.com/vi/{youtube_id}/maxresdefault.jpg",
        f"https://i.ytimg.com/vi/{youtube_id}/sddefault.jpg",
        f"https://i.ytimg.com/vi/{youtube_id}/hqdefault.jpg",
    ]
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        for url in urls:
            response = client.get(url)
            content_type = response.headers.get("content-type", "")
            if response.status_code == 200 and content_type.startswith("image/") and len(response.content) > 10_000:
                target.write_bytes(response.content)
                return target, url
    raise RuntimeError(f"No usable YouTube thumbnail for {youtube_id}")


def playlist_ids() -> list[str]:
    url = f"https://www.youtube.com/playlist?list={SOURCE_PLAYLIST_ID}"
    command = [*yt_dlp_command(), "--flat-playlist", "--dump-single-json", url]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Cannot inspect YouTube playlist: {completed.stderr[-1500:]}")
    payload = json.loads(completed.stdout)
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return []
    return [str(item["id"]) for item in entries if isinstance(item, dict) and item.get("id")]


def normalized_title(value: str) -> str:
    return " ".join(value.replace("—", "-").split()).casefold()


def target_album(client: VkApiClient) -> Any | None:
    wanted = normalized_title(TARGET_ALBUM_TITLE)
    aliases = {
        wanted,
        normalized_title("Архитектура мышления - Р. Ч. Спроул"),
    }
    for collection in client.list_collections(COMMUNITY_ID):
        if normalized_title(collection.title) in aliases and int(collection.ref.remote_id) > 0:
            return collection
    return None


def load_state(repo: Path) -> dict[str, Any]:
    path = operation_dir(repo) / "supplemental-state.json"
    payload = read_json(path, {})
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("schema_name", "video-manager.vk-longform-supplemental-state")
    payload.setdefault("schema_version", 1)
    payload.setdefault("project_key", PROJECT_KEY)
    payload.setdefault("queue_sha256", QUEUE_SHA256)
    payload.setdefault("uploads", {})
    payload.setdefault("thumbnails", {})
    payload.setdefault("album", {})
    return payload


def save_state(repo: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    write_json(operation_dir(repo) / "supplemental-state.json", state)


def build_report(
    repo: Path,
    rows: list[dict[str, Any]],
    writer: VkVideoWriter,
    client: VkApiClient,
) -> dict[str, Any]:
    live: dict[str, Any] = {}
    missing: list[str] = []
    for row in rows:
        item = visible_state(writer, row)
        if item is None:
            missing.append(str(row["youtube_id"]))
        else:
            live[str(row["youtube_id"])] = {
                "remote_id": f"{item.get('owner_id')}_{item.get('id')}",
                "type": item.get("type"),
                "processing": bool(item.get("processing") or item.get("converting")),
                "duration": item.get("duration"),
                "width": item.get("width"),
                "height": item.get("height"),
            }

    source_members = playlist_ids()
    source_missing = [item for item in SERIES_IDS if item not in source_members]
    source_extra = [item for item in source_members if item not in SERIES_IDS]
    album = target_album(client)
    album_id = int(album.ref.remote_id) if album is not None else None
    target_missing: list[str] = []
    if album_id is not None:
        for youtube_id in SERIES_IDS:
            row = next(item for item in rows if item["youtube_id"] == youtube_id)
            remote = parse_remote(row)
            if remote is None or album_id not in writer.album_ids_for_video(
                community_id=COMMUNITY_ID,
                owner_id=remote[0],
                video_id=remote[1],
            ):
                target_missing.append(youtube_id)
    else:
        target_missing = list(SERIES_IDS)

    state = load_state(repo)
    thumbnail_done = state.get("thumbnails", {})
    pending_thumbnails = [
        str(row["youtube_id"])
        for row in rows
        if not isinstance(thumbnail_done.get(str(row["youtube_id"])), dict)
        or thumbnail_done[str(row["youtube_id"])].get("status") != "verified"
    ]
    return {
        "schema_name": "video-manager.vk-longform-supplemental-plan",
        "schema_version": 1,
        "generated_at": utc_now(),
        "project_key": PROJECT_KEY,
        "youtube_channel_id": YOUTUBE_CHANNEL_ID,
        "vk_community_id": COMMUNITY_ID,
        "vk_owner_id": OWNER_ID,
        "queue_sha256": QUEUE_SHA256,
        "queue_rows": len(rows),
        "live_count": len(live),
        "live": live,
        "missing_youtube_ids": missing,
        "safe_upload_ids": [
            str(row["youtube_id"])
            for row in rows
            if row["youtube_id"] in missing
            and not row.get("vk_video_id")
            and int(row.get("upload_attempted") or 0) == 0
            and int(row.get("save_attempted") or 0) == 0
        ],
        "blocked_missing_ids": [
            str(row["youtube_id"])
            for row in rows
            if row["youtube_id"] in missing
            and (
                row.get("vk_video_id")
                or int(row.get("upload_attempted") or 0) != 0
                or int(row.get("save_attempted") or 0) != 0
            )
        ],
        "thumbnail_repairs_pending": pending_thumbnails,
        "source_playlist": {
            "id": SOURCE_PLAYLIST_ID,
            "members": source_members,
            "missing_expected": source_missing,
            "extra_non_series": source_extra,
        },
        "target_album": {
            "title": TARGET_ALBUM_TITLE,
            "album_id": album_id,
            "missing_series_ids": target_missing,
        },
        "remote_writes": 0,
    }


def upload_missing(
    repo: Path,
    row: dict[str, Any],
    writer: VkVideoWriter,
    state: dict[str, Any],
) -> dict[str, Any]:
    youtube_id = str(row["youtube_id"])
    uploads = state["uploads"]
    existing = uploads.get(youtube_id)
    if isinstance(existing, dict) and existing.get("remote_id"):
        owner_raw, video_raw = str(existing["remote_id"]).split("_", 1)
        item = writer.read_video(owner_id=int(owner_raw), video_id=int(video_raw))
        if item is not None:
            return item

    media = download_video(row, media_dir(repo) / f"{youtube_id}.mp4")
    metadata = youtube_metadata(str(row["youtube_url"]))
    source_title = str(metadata.get("title") or row["title"])
    source_description = str(metadata.get("description") or "")
    publication = render_vk_publication(source_title, source_description)

    uploads[youtube_id] = {"status": "reserve_started", "started_at": utc_now()}
    save_state(repo, state)
    ticket = writer.begin_upload(
        community_id=COMMUNITY_ID,
        title=publication.title,
        description=publication.description,
    )
    uploads[youtube_id].update({"status": "reserved", "remote_id": ticket.remote_id})
    save_state(repo, state)
    response = writer.upload_file(ticket, media)
    uploads[youtube_id].update({"status": "uploaded", "upload_response": response})
    save_state(repo, state)

    deadline = time.monotonic() + 1800
    item: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        item = writer.read_video(owner_id=ticket.owner_id, video_id=ticket.video_id)
        if item is not None:
            usable = (
                item.get("type") == "video"
                and isinstance(item.get("duration"), int)
                and abs(int(item["duration"]) - int(row["duration_seconds"])) <= 5
                and isinstance(item.get("width"), int)
                and isinstance(item.get("height"), int)
            )
            if usable:
                break
        time.sleep(15)
    if item is None:
        raise RuntimeError(f"Uploaded video is not visible: {ticket.remote_id}")
    uploads[youtube_id].update({"status": "verified", "verified_at": utc_now(), "live": item})
    save_state(repo, state)
    update_ledger_after_upload(repo, row, media=media, ticket=ticket, upload_response=response)
    row.update(
        {
            "status": "confirmed",
            "local_path": str(media),
            "local_sha256": sha256_file(media),
            "local_size": media.stat().st_size,
            "save_attempted": 1,
            "vk_owner_id": ticket.owner_id,
            "vk_video_id": ticket.video_id,
            "upload_attempted": 1,
            "last_error": None,
        }
    )
    return item


def repair_thumbnail(
    repo: Path,
    row: dict[str, Any],
    thumbnail_writer: VkThumbnailWriter,
    state: dict[str, Any],
) -> None:
    youtube_id = str(row["youtube_id"])
    remote = parse_remote(row)
    if remote is None:
        raise RuntimeError(f"No VK ID for thumbnail repair: {youtube_id}")
    previous = state["thumbnails"].get(youtube_id)
    if isinstance(previous, dict) and previous.get("status") == "verified" and previous.get("remote_id") == f"{remote[0]}_{remote[1]}":
        return
    target = operation_dir(repo) / "thumbnails" / f"{youtube_id}.jpg"
    image, source_url = download_thumbnail(youtube_id, target)
    state["thumbnails"][youtube_id] = {
        "status": "started",
        "remote_id": f"{remote[0]}_{remote[1]}",
        "source_url": source_url,
        "sha256": sha256_file(image),
    }
    save_state(repo, state)
    result = thumbnail_writer.set_thumbnail(owner_id=remote[0], video_id=remote[1], path=image)
    state["thumbnails"][youtube_id].update(
        {"status": "verified", "result": result, "verified_at": utc_now()}
    )
    save_state(repo, state)


def ensure_album(
    rows: list[dict[str, Any]],
    writer: VkVideoWriter,
    client: VkApiClient,
    state: dict[str, Any],
    repo: Path,
) -> int:
    album = target_album(client)
    album_id = int(album.ref.remote_id) if album is not None else None
    if album_id is None:
        stored = state["album"].get("album_id")
        if isinstance(stored, int) and stored > 0:
            album_id = stored
        else:
            album_id = writer.create_album(community_id=COMMUNITY_ID, title=TARGET_ALBUM_TITLE)
            state["album"].update({"album_id": album_id, "status": "created"})
            save_state(repo, state)
    for youtube_id in SERIES_IDS:
        row = next(item for item in rows if item["youtube_id"] == youtube_id)
        remote = parse_remote(row)
        if remote is None:
            raise RuntimeError(f"Series video has no VK ID: {youtube_id}")
        writer.add_to_album(
            community_id=COMMUNITY_ID,
            album_id=album_id,
            owner_id=remote[0],
            video_id=remote[1],
        )
    state["album"].update({"album_id": album_id, "status": "verified", "verified_at": utc_now()})
    save_state(repo, state)
    return album_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--account", default=ACCOUNT_ALIAS)
    parser.add_argument("--community", type=int, default=COMMUNITY_ID)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    repo = args.repo.resolve()
    if args.account != ACCOUNT_ALIAS or args.community != COMMUNITY_ID:
        raise SystemExit("This focused operation is locked to account alias legendary-poet and community 60805374")
    rows = load_rows(repo)
    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    writer = VkVideoWriter(token_store=store, account_alias=args.account, api_version=settings.vk_api_version)
    client = VkApiClient(token_store=store, account_alias=args.account, api_version=settings.vk_api_version)
    community = client.get_community(COMMUNITY_ID)
    if community.ref.remote_id != str(COMMUNITY_ID) or not community.metadata.get("managed_by_token"):
        raise RuntimeError("Wrong or unmanaged VK community")

    plan = build_report(repo, rows, writer, client)
    plan_path = operation_dir(repo) / "supplemental-plan.json"
    write_json(plan_path, plan)
    print(json.dumps({
        "queue_rows": plan["queue_rows"],
        "live_count": plan["live_count"],
        "missing_youtube_ids": plan["missing_youtube_ids"],
        "safe_upload_ids": plan["safe_upload_ids"],
        "blocked_missing_ids": plan["blocked_missing_ids"],
        "thumbnail_repairs_pending": len(plan["thumbnail_repairs_pending"]),
        "source_playlist_missing": plan["source_playlist"]["missing_expected"],
        "source_playlist_extra": plan["source_playlist"]["extra_non_series"],
        "target_album_id": plan["target_album"]["album_id"],
        "target_album_missing": plan["target_album"]["missing_series_ids"],
        "plan_path": str(plan_path),
    }, ensure_ascii=False, indent=2))

    if plan["blocked_missing_ids"]:
        raise RuntimeError(f"Blocked ambiguous missing rows: {plan['blocked_missing_ids']}")
    if not args.execute:
        print("READ-ONLY COMPLETE. Re-run the same command with --execute to finish the exact scope.")
        return 0
    if os.environ.get("VCM_ALLOW_UPLOAD_OPERATIONS") != "1":
        raise RuntimeError("Execution requires VCM_ALLOW_UPLOAD_OPERATIONS=1")

    state = load_state(repo)
    for youtube_id in plan["safe_upload_ids"]:
        row = next(item for item in rows if item["youtube_id"] == youtube_id)
        print(f"UPLOAD MISSING {youtube_id}", flush=True)
        upload_missing(repo, row, writer, state)

    thumbnail_writer = VkThumbnailWriter(
        token_store=store,
        account_alias=args.account,
        api_version=settings.vk_api_version,
    )
    for index, row in enumerate(rows, start=1):
        print(f"THUMBNAIL {index}/{len(rows)} {row['youtube_id']}", flush=True)
        repair_thumbnail(repo, row, thumbnail_writer, state)

    album_id = ensure_album(rows, writer, client, state, repo)
    final = build_report(repo, rows, writer, client)
    final.update(
        {
            "completed_at": utc_now(),
            "remote_writes": {
                "new_uploads": len(plan["safe_upload_ids"]),
                "thumbnail_repairs_verified": sum(
                    1 for item in state["thumbnails"].values() if isinstance(item, dict) and item.get("status") == "verified"
                ),
                "sproul_album_id": album_id,
            },
        }
    )
    result_path = operation_dir(repo) / "supplemental-result.json"
    write_json(result_path, final)
    print(json.dumps({
        "status": "completed",
        "live_count": final["live_count"],
        "missing_youtube_ids": final["missing_youtube_ids"],
        "thumbnails_verified": final["remote_writes"]["thumbnail_repairs_verified"],
        "sproul_album_id": album_id,
        "sproul_album_missing": final["target_album"]["missing_series_ids"],
        "result_path": str(result_path),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, VkWriteError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
