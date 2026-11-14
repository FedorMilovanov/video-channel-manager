"""Prepare one owned LordGod Reel for a verified HTTPS ingestion path.

This is a provider-inert handoff: it never calls Graph, never publishes, never
changes Scheduler or SQLite, and never hosts the video. The actual publisher
must independently enforce its existing write and reconciliation gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from video_channel_manager.instagram.local_resumable import verify_local_reel
from video_channel_manager.instagram.production import (
    InstagramPublishManifest,
    verify_instagram_public_object,
)

PROJECT = "lord-god-strength"
ACCOUNT = "17841433845016161"
SOURCE = "article-heart"
SOURCE_URL = "https://gospod-bog.ru/articles/chto-bibliya-nazyvaet-serdcem/"
SOURCE_REPO = "FedorMilovanov/gb-is-my-strength"


class HandoffHold(ValueError):
    """A required identity, approval, receipt, or immutable-media gate failed."""


def _sha256(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _assert_unattempted(db_path: Path) -> None:
    """Any previous source-specific attempt blocks another transport/key."""
    if not db_path.is_file():
        raise HandoffHold("Canonical Instagram SQLite database is missing")
    # SQLite URI mode=ro prevents accidental database or journal mutation.
    uri = db_path.resolve().as_uri() + "?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as db:
            attempts = db.execute(
                "SELECT publication_key FROM instagram_publications "
                "WHERE account_id=? AND publication_key LIKE 'lord-god-strength.%' "
                "AND instr(publication_key, ?) > 0 LIMIT 1",
                (ACCOUNT, f".{SOURCE}."),
            ).fetchone()
    except sqlite3.Error as exc:
        raise HandoffHold("Publication ledger cannot be verified read-only") from exc
    if attempts:
        raise HandoffHold("Source has a previous Instagram attempt; manual reconcile required")


def prepare_verified_handoff(
    *,
    evidence_path: Path,
    db_path: Path,
    day: str,
    video_url: str,
    allowed_host: str,
    public_hosting_authorized: bool,
    media_client: httpx.Client,
) -> InstagramPublishManifest:
    """Verify an exact new future owned-media URL; return manifest, never post."""
    if not public_hosting_authorized:
        raise HandoffHold("Separate public HTTPS hosting authorization is missing")
    try:
        release_day = date.fromisoformat(day)
    except ValueError as exc:
        raise HandoffHold("Invalid YYYY-MM-DD release date") from exc
    # Do not collide with the original, frozen Nov 10-21 Reels queue.
    if not (date(2026, 11, 22) <= release_day <= date(2026, 12, 31)):
        raise HandoffHold("Only a newly approved post-Nov21 release can be prepared")

    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise HandoffHold("Owned-source evidence is missing or malformed") from exc
    if (
        evidence.get("schema") != "lord-god-owned-site-reel-pilot-v1"
        or evidence.get("project_key") != PROJECT
        or evidence.get("instagram_account_id") != ACCOUNT
        or evidence.get("source_url") != SOURCE_URL
        or evidence.get("source_repo") != SOURCE_REPO
        or evidence.get("source_article_author") != "fedor-milovanov"
        or evidence.get("original_media_only") is not True
        or evidence.get("borrowed_footage_or_audio") is not False
        or evidence.get("visual_qa") != "all_7_storyboard_screens_previewed_no_clipping"
        or evidence.get("auditory_qa") != "human_listened_pass"
        or evidence.get("publication_authorized") is not True
        or evidence.get("public_hosting_authorized") is not True
        or evidence.get("approved_release_slot") != f"{day}T19:00:00+03:00"
        or not re.fullmatch(r"[0-9a-f]{40}", str(evidence.get("source_commit", "")))
    ):
        raise HandoffHold("Owned media, final review, public hosting, or exact slot not approved")

    media_sha = str(evidence.get("video_sha256", "")).removeprefix("sha256:")
    caption_sha = str(evidence.get("caption_sha256", "")).removeprefix("sha256:")
    if not re.fullmatch(r"[0-9a-f]{64}", media_sha) or not re.fullmatch(r"[0-9a-f]{64}", caption_sha):
        raise HandoffHold("Invalid frozen media/caption SHA-256")
    video_path = Path(str(evidence["video_path"]))
    caption_path = Path(str(evidence["caption_path"]))
    if not video_path.is_file() or not caption_path.is_file():
        raise HandoffHold("Original video or caption file not present")
    real_sha, size = _sha256(video_path)
    raw_caption = caption_path.read_bytes()
    if real_sha != media_sha or hashlib.sha256(raw_caption).hexdigest() != caption_sha:
        raise HandoffHold("Original video or caption differs from reviewed bytes")
    if size != int(evidence.get("ffprobe", {}).get("format", {}).get("size", -1)):
        raise HandoffHold("Media size differs from frozen source evidence")
    try:
        caption = raw_caption.decode("utf-8-sig")
    except UnicodeError as exc:
        raise HandoffHold("Caption must be valid UTF-8") from exc
    if not caption.strip() or len(caption) > 2200:
        raise HandoffHold("Caption missing or longer than Instagram limit")
    verify_local_reel(
        video_path,
        expected_sha256=f"sha256:{media_sha}",
        expected_size_bytes=size,
    )
    _assert_unattempted(db_path)

    parsed = urlsplit(video_url)
    host = allowed_host.lower()
    try:
        port = parsed.port
    except ValueError as exc:
        raise HandoffHold("Invalid public HTTPS port") from exc
    if (
        not host
        or host != host.strip(".")
        or parsed.scheme != "https"
        or parsed.hostname != host
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path.endswith(f"/{media_sha}.mp4")
    ):
        raise HandoffHold("Expected exact-host HTTPS MP4 with content-addressed filename")

    manifest = InstagramPublishManifest(
        publication_key=f"{PROJECT}.{day}.{SOURCE}.public-https-v1",
        account_id=ACCOUNT,
        video_url=video_url,
        media_sha256=f"sha256:{media_sha}",
        media_size_bytes=size,
        media_content_type="video/mp4",
        caption=caption,
        share_to_feed=True,
    )
    verify_instagram_public_object(
        manifest.video_url,
        allowed_hosts=(host,),
        expected_sha256=manifest.media_sha256,
        expected_size_bytes=manifest.media_size_bytes,
        expected_content_type=manifest.media_content_type,
        label="video",
        media_client=media_client,
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--day", required=True)
    parser.add_argument("--video-url", required=True)
    parser.add_argument("--allowed-host", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--public-hosting-authorized", action="store_true")
    args = parser.parse_args()
    with httpx.Client(timeout=httpx.Timeout(60.0), follow_redirects=False) as client:
        manifest = prepare_verified_handoff(
            evidence_path=args.evidence,
            db_path=args.database,
            day=args.day,
            video_url=args.video_url,
            allowed_host=args.allowed_host,
            public_hosting_authorized=args.public_hosting_authorized,
            media_client=client,
        )
    # Exclusive file creation prevents silent overrides of approval/handoff receipts.
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(manifest.model_dump(mode="json"), stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"PROVIDER_INERT_OWNED_REEL_HANDOFF={manifest.publication_key}")
    print("META_POST=0 SCHEDULE_WRITES=0 PUBLISH_AUTHORITY=NOT_GRANTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
