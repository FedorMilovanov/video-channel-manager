#!/usr/bin/env python3
"""Finish the reviewed 26-video VK tail, thumbnails, and Sproul album.

Without ``--execute`` this is a read-only live audit. Execution is locked to the
current theological project and may upload only ledger rows with no VK ID and no
prior upload attempt. It also sets each source YouTube thumbnail and fills the
five-part Sproul VK album. Video uploads always use ``wallpost=0`` through the
standard writer; this script has no wall or delete methods.
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
from video_channel_manager.platforms.vk.thumbnails import VkThumbnailWriter
from video_channel_manager.platforms.vk.writer import VkUploadTicket, VkVideoWriter, VkWriteError

PROJECT_KEY = "lord-god-strength"
COMMUNITY_ID = 60805374
OWNER_ID = -60805374
ACCOUNT_ALIAS = "legendary-poet"
YOUTUBE_CHANNEL_ID = "UCeSJsC6go2c9pdJCuUI1BYA"
SOURCE_PLAYLIST_ID = "PLW_VRhdOSkXo"
TARGET_ALBUM_TITLE = "Архитектура мышления — Р. Ч. Спроул"
QUEUE_SHA256 = "b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed"
SERIES_IDS = ["pDU8kdhDfLo", "uI-wfRaq2SA", "-q2TcD8ldb4", "T8s9DNkuavQ", "QswEQFZfV2U"]


def now() -> str:
    return datetime.now(UTC).isoformat()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def read_json(path: Path, fallback: object) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else fallback


def root(repo: Path) -> Path:
    return repo / "data" / "vk-upload" / "verified-longform-26"


def op_root(repo: Path) -> Path:
    return root(repo) / "supplemental"


def ledger(repo: Path) -> Path:
    return root(repo) / "upload-ledger.db"


def rows(repo: Path) -> list[dict[str, Any]]:
    path = ledger(repo)
    if not path.is_file():
        raise RuntimeError(f"Long-form ledger not found: {path}")
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        result = [
            dict(row)
            for row in db.execute(
                """
                SELECT youtube_id,ordinal,title,youtube_url,duration_seconds,published_at,
                       status,local_path,local_sha256,local_size,save_attempted,
                       vk_owner_id,vk_video_id,upload_attempted,last_error
                FROM operations ORDER BY ordinal DESC
                """
            ).fetchall()
        ]
    if len(result) != 26:
        raise RuntimeError(f"Expected reviewed 26-item queue, found {len(result)}")
    if not set(SERIES_IDS).issubset({str(item["youtube_id"]) for item in result}):
        raise RuntimeError("The ledger lacks part of the five-video Sproul series")
    return result


def remote(row: dict[str, Any]) -> tuple[int, int] | None:
    owner, video = row.get("vk_owner_id"), row.get("vk_video_id")
    return (owner, video) if isinstance(owner, int) and isinstance(video, int) else None


def state(repo: Path) -> dict[str, Any]:
    path = op_root(repo) / "state.json"
    value = read_json(path, {})
    if not isinstance(value, dict):
        value = {}
    value.setdefault("schema_name", "video-manager.vk-longform-tail-completion")
    value.setdefault("schema_version", 1)
    value.setdefault("project_key", PROJECT_KEY)
    value.setdefault("queue_sha256", QUEUE_SHA256)
    value.setdefault("uploads", {})
    value.setdefault("thumbnails", {})
    value.setdefault("album", {})
    return value


def save_state(repo: Path, value: dict[str, Any]) -> None:
    value["updated_at"] = now()
    write_json(op_root(repo) / "state.json", value)


def ytdlp() -> list[str]:
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    try:
        import yt_dlp  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("Install yt-dlp: python -m pip install -U yt-dlp") from exc
    return [sys.executable, "-m", "yt_dlp"]


def run_json(arguments: list[str], label: str) -> dict[str, Any]:
    result = subprocess.run(arguments, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed: {result.stderr[-1500:]}")
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} returned a non-object")
    return value


def source_metadata(row: dict[str, Any]) -> dict[str, Any]:
    return run_json(
        [*ytdlp(), "--no-playlist", "--dump-single-json", "--skip-download", str(row["youtube_url"])],
        f"YouTube metadata {row['youtube_id']}",
    )


def source_playlist_members() -> list[str]:
    value = run_json(
        [
            *ytdlp(),
            "--flat-playlist",
            "--dump-single-json",
            f"https://www.youtube.com/playlist?list={SOURCE_PLAYLIST_ID}",
        ],
        "YouTube playlist audit",
    )
    entries = value.get("entries")
    return [str(item["id"]) for item in entries if isinstance(item, dict) and item.get("id")] if isinstance(entries, list) else []


def download_video(row: dict[str, Any], target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and target.stat().st_size > 0:
        return target
    result = subprocess.run(
        [
            *ytdlp(),
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
            str(target.with_suffix(".%(ext)s")),
            str(row["youtube_url"]),
        ],
        check=False,
    )
    found = sorted(target.parent.glob(f"{target.stem}*.mp4"), key=lambda item: item.stat().st_size, reverse=True)
    if result.returncode != 0 or not found:
        raise RuntimeError(f"YouTube download failed for {row['youtube_id']}")
    if found[0] != target:
        found[0].replace(target)
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
            if (
                response.status_code == 200
                and response.headers.get("content-type", "").startswith("image/")
                and len(response.content) > 10_000
            ):
                target.write_bytes(response.content)
                return target, url
    raise RuntimeError(f"No usable source thumbnail for {youtube_id}")


def normalize(value: str) -> str:
    return " ".join(value.replace("—", "-").split()).casefold()


def find_album(client: VkApiClient) -> Any | None:
    aliases = {normalize(TARGET_ALBUM_TITLE), normalize("Архитектура мышления - Р. Ч. Спроул")}
    for item in client.list_collections(COMMUNITY_ID):
        if int(item.ref.remote_id) > 0 and normalize(item.title) in aliases:
            return item
    return None


def live_video(writer: VkVideoWriter, row: dict[str, Any]) -> dict[str, Any] | None:
    identity = remote(row)
    return writer.read_video(owner_id=identity[0], video_id=identity[1]) if identity else None


def audit(
    repo: Path,
    queue: list[dict[str, Any]],
    writer: VkVideoWriter,
    client: VkApiClient,
) -> dict[str, Any]:
    live: dict[str, Any] = {}
    missing: list[str] = []
    for row in queue:
        item = live_video(writer, row)
        youtube_id = str(row["youtube_id"])
        if item is None:
            missing.append(youtube_id)
        else:
            live[youtube_id] = {
                "remote_id": f"{item.get('owner_id')}_{item.get('id')}",
                "type": item.get("type"),
                "processing": bool(item.get("processing") or item.get("converting")),
                "duration": item.get("duration"),
                "width": item.get("width"),
                "height": item.get("height"),
            }

    safe = [
        str(row["youtube_id"])
        for row in queue
        if row["youtube_id"] in missing
        and remote(row) is None
        and int(row.get("save_attempted") or 0) == 0
        and int(row.get("upload_attempted") or 0) == 0
    ]
    blocked = [item for item in missing if item not in safe]
    source_members = source_playlist_members()
    source_missing = [item for item in SERIES_IDS if item not in source_members]
    source_extra = [item for item in source_members if item not in SERIES_IDS]

    album = find_album(client)
    album_id = int(album.ref.remote_id) if album is not None else None
    album_missing: list[str] = []
    for youtube_id in SERIES_IDS:
        row = next(item for item in queue if item["youtube_id"] == youtube_id)
        identity = remote(row)
        if (
            album_id is None
            or identity is None
            or album_id
            not in writer.album_ids_for_video(
                community_id=COMMUNITY_ID,
                owner_id=identity[0],
                video_id=identity[1],
            )
        ):
            album_missing.append(youtube_id)

    journal = state(repo)
    pending_thumbnails = [
        str(row["youtube_id"])
        for row in queue
        if not isinstance(journal["thumbnails"].get(str(row["youtube_id"])), dict)
        or journal["thumbnails"][str(row["youtube_id"])].get("status") != "verified"
    ]
    return {
        "schema_name": "video-manager.vk-longform-tail-plan",
        "schema_version": 1,
        "generated_at": now(),
        "project_key": PROJECT_KEY,
        "youtube_channel_id": YOUTUBE_CHANNEL_ID,
        "vk_community_id": COMMUNITY_ID,
        "vk_owner_id": OWNER_ID,
        "queue_sha256": QUEUE_SHA256,
        "queue_rows": len(queue),
        "live_count": len(live),
        "live": live,
        "missing_youtube_ids": missing,
        "safe_upload_ids": safe,
        "blocked_missing_ids": blocked,
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
            "missing_series_ids": album_missing,
        },
        "remote_writes": 0,
    }


def update_ledger(repo: Path, row: dict[str, Any], media: Path, ticket: VkUploadTicket, response: dict[str, Any]) -> None:
    timestamp = now()
    with sqlite3.connect(ledger(repo)) as db:
        db.execute(
            """
            UPDATE operations SET status='confirmed',local_path=?,local_sha256=?,local_size=?,
                save_attempted=1,vk_owner_id=?,vk_video_id=?,upload_attempted=1,
                upload_response_json=?,last_error=NULL,updated_at=?,confirmed_at=?
            WHERE youtube_id=?
            """,
            (
                str(media),
                digest(media),
                media.stat().st_size,
                ticket.owner_id,
                ticket.video_id,
                json.dumps(response, ensure_ascii=False, separators=(",", ":")),
                timestamp,
                timestamp,
                row["youtube_id"],
            ),
        )
        db.commit()


def upload_missing(repo: Path, row: dict[str, Any], writer: VkVideoWriter, journal: dict[str, Any]) -> None:
    youtube_id = str(row["youtube_id"])
    previous = journal["uploads"].get(youtube_id)
    if isinstance(previous, dict) and previous.get("remote_id"):
        owner_text, video_text = str(previous["remote_id"]).split("_", 1)
        if writer.read_video(owner_id=int(owner_text), video_id=int(video_text)) is not None:
            row["vk_owner_id"], row["vk_video_id"] = int(owner_text), int(video_text)
            return

    media = download_video(row, root(repo) / "media" / f"{youtube_id}.mp4")
    metadata = source_metadata(row)
    title = " ".join(str(metadata.get("title") or row["title"]).split())[:128]
    description = str(metadata.get("description") or "").strip()
    source_line = f"Источник YouTube: {row['youtube_url']}"
    if str(row["youtube_url"]) not in description:
        description = f"{source_line}\n\n{description}" if description else source_line

    journal["uploads"][youtube_id] = {"status": "reserve_started", "started_at": now()}
    save_state(repo, journal)
    ticket = writer.begin_upload(community_id=COMMUNITY_ID, title=title, description=description)
    journal["uploads"][youtube_id].update({"status": "reserved", "remote_id": ticket.remote_id})
    save_state(repo, journal)
    response = writer.upload_file(ticket, media)
    journal["uploads"][youtube_id].update({"status": "uploaded", "response": response})
    save_state(repo, journal)

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
        raise RuntimeError(f"New VK video is not visible: {ticket.remote_id}")
    journal["uploads"][youtube_id].update({"status": "verified", "verified_at": now(), "live": item})
    save_state(repo, journal)
    update_ledger(repo, row, media, ticket, response)
    row.update(
        {
            "status": "confirmed",
            "local_path": str(media),
            "local_sha256": digest(media),
            "local_size": media.stat().st_size,
            "save_attempted": 1,
            "vk_owner_id": ticket.owner_id,
            "vk_video_id": ticket.video_id,
            "upload_attempted": 1,
            "last_error": None,
        }
    )


def set_source_thumbnail(
    repo: Path,
    row: dict[str, Any],
    writer: VkThumbnailWriter,
    journal: dict[str, Any],
) -> None:
    youtube_id = str(row["youtube_id"])
    identity = remote(row)
    if identity is None:
        raise RuntimeError(f"Cannot set thumbnail without VK ID: {youtube_id}")
    remote_id = f"{identity[0]}_{identity[1]}"
    previous = journal["thumbnails"].get(youtube_id)
    if isinstance(previous, dict):
        if previous.get("status") == "verified" and previous.get("remote_id") == remote_id:
            return
        if previous.get("status") in {"started", "unknown"}:
            raise RuntimeError(f"Thumbnail outcome requires manual reconciliation: {youtube_id}")

    image, source_url = download_thumbnail(
        youtube_id,
        op_root(repo) / "thumbnails" / f"{youtube_id}.jpg",
    )
    journal["thumbnails"][youtube_id] = {
        "status": "started",
        "remote_id": remote_id,
        "source_url": source_url,
        "sha256": digest(image),
        "started_at": now(),
    }
    save_state(repo, journal)
    try:
        result = writer.set_thumbnail(owner_id=identity[0], video_id=identity[1], path=image)
    except BaseException as exc:
        journal["thumbnails"][youtube_id].update(
            {"status": "unknown", "error": f"{type(exc).__name__}: {exc}"}
        )
        save_state(repo, journal)
        raise
    journal["thumbnails"][youtube_id].update(
        {"status": "verified", "verified_at": now(), "result": result}
    )
    save_state(repo, journal)


def fill_album(
    repo: Path,
    queue: list[dict[str, Any]],
    writer: VkVideoWriter,
    client: VkApiClient,
    journal: dict[str, Any],
) -> int:
    album = find_album(client)
    album_id = int(album.ref.remote_id) if album is not None else journal["album"].get("album_id")
    if not isinstance(album_id, int) or album_id <= 0:
        album_id = writer.create_album(community_id=COMMUNITY_ID, title=TARGET_ALBUM_TITLE)
        journal["album"] = {"album_id": album_id, "status": "created", "created_at": now()}
        save_state(repo, journal)
    for youtube_id in SERIES_IDS:
        row = next(item for item in queue if item["youtube_id"] == youtube_id)
        identity = remote(row)
        if identity is None:
            raise RuntimeError(f"Sproul series video has no VK ID: {youtube_id}")
        writer.add_to_album(
            community_id=COMMUNITY_ID,
            album_id=album_id,
            owner_id=identity[0],
            video_id=identity[1],
        )
    journal["album"].update({"status": "verified", "verified_at": now()})
    save_state(repo, journal)
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
        raise RuntimeError("This operation is locked to alias legendary-poet and community 60805374")
    queue = rows(repo)
    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    video_writer = VkVideoWriter(token_store=store, account_alias=args.account, api_version=settings.vk_api_version)
    client = VkApiClient(token_store=store, account_alias=args.account, api_version=settings.vk_api_version)
    community = client.get_community(COMMUNITY_ID)
    if community.ref.remote_id != str(COMMUNITY_ID) or not community.metadata.get("managed_by_token"):
        raise RuntimeError("Wrong or unmanaged VK community")

    plan = audit(repo, queue, video_writer, client)
    plan_path = op_root(repo) / "plan.json"
    write_json(plan_path, plan)
    print(
        json.dumps(
            {
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
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if plan["blocked_missing_ids"]:
        raise RuntimeError(f"Ambiguous missing rows: {plan['blocked_missing_ids']}")
    if not args.execute:
        print("READ-ONLY COMPLETE. Add --execute to finish this exact scope.")
        return 0
    if os.environ.get("VCM_ALLOW_UPLOAD_OPERATIONS") != "1":
        raise RuntimeError("Execution requires VCM_ALLOW_UPLOAD_OPERATIONS=1")

    journal = state(repo)
    for youtube_id in plan["safe_upload_ids"]:
        print(f"UPLOAD MISSING {youtube_id}", flush=True)
        upload_missing(repo, next(item for item in queue if item["youtube_id"] == youtube_id), video_writer, journal)

    thumbnail_writer = VkThumbnailWriter(
        token_store=store,
        account_alias=args.account,
        api_version=settings.vk_api_version,
    )
    for index, row in enumerate(queue, start=1):
        print(f"THUMBNAIL {index}/26 {row['youtube_id']}", flush=True)
        set_source_thumbnail(repo, row, thumbnail_writer, journal)

    album_id = fill_album(repo, queue, video_writer, client, journal)
    final = audit(repo, queue, video_writer, client)
    final["completed_at"] = now()
    final["remote_writes"] = {
        "new_uploads": len(plan["safe_upload_ids"]),
        "thumbnail_repairs_verified": sum(
            1
            for item in journal["thumbnails"].values()
            if isinstance(item, dict) and item.get("status") == "verified"
        ),
        "sproul_album_id": album_id,
    }
    result_path = op_root(repo) / "result.json"
    write_json(result_path, final)
    print(
        json.dumps(
            {
                "status": "completed",
                "live_count": final["live_count"],
                "missing_youtube_ids": final["missing_youtube_ids"],
                "thumbnails_verified": final["remote_writes"]["thumbnail_repairs_verified"],
                "sproul_album_id": album_id,
                "sproul_album_missing": final["target_album"]["missing_series_ids"],
                "result_path": str(result_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, VkWriteError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
