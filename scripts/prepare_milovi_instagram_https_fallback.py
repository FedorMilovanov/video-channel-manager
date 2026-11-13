"""Provider-inert, exact-byte handoff for a Milovi Cake Instagram HTTPS Reel.

This tool has no publication code, no Meta credential, and no Meta API calls.
It only prepares a *new* exact-source manifest after verifying the approved
local MP4, durable duplicate state, and remote immutable HTTPS bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from video_channel_manager.instagram.production import (
    InstagramPublishManifest,
    verify_instagram_public_object,
)

INDEX_SHA256 = "19a211320f32e3c0f16c0aad1ed23db4b2bd89f100bbd22b8d1b801734aba5a4"
ACCOUNT_ID = "17841407843933779"
APP_ID = "989716813600695"
PROJECT = "milovi-cake"


class FallbackHold(ValueError):
    """An immutable or owner-authority gate prevents an unsafe handoff."""


def _sha256(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _require_unused_source(database_path: Path, youtube_id: str) -> None:
    if not database_path.is_file():
        raise FallbackHold("Read-only publication ledger is missing")
    uri = database_path.resolve().as_uri().replace("file:///", "file:///") + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        records = db.execute(
            "SELECT publication_key, status, provider_media_id "
            "FROM instagram_publications WHERE account_id=? AND publication_key LIKE ?",
            (ACCOUNT_ID, f"milovi-cake.%.yt-{youtube_id}.%"),
        ).fetchall()
    if records:
        raise FallbackHold("Source already has a durable publication attempt; reconcile manually before new release")


def prepare_verified_manifest(
    *,
    index_path: Path,
    database_path: Path,
    day: str,
    video_url: str,
    allowed_host: str,
    public_hosting_authorized: bool,
    media_client: httpx.Client,
) -> InstagramPublishManifest:
    """Validate and return a new-key URL manifest; never publish or alter a ledger."""

    if not public_hosting_authorized:
        raise FallbackHold("Separate owner authorization for public HTTPS staging is required")
    try:
        release_date = date.fromisoformat(day)
    except ValueError as exc:
        raise FallbackHold("Invalid exact YYYY-MM-DD release date") from exc
    if release_date < date(2026, 11, 14) or release_date > date(2026, 11, 28):
        raise FallbackHold("Only unused future rows from the reviewed Milovi v5 release are eligible")

    index_bytes = index_path.read_bytes()
    if hashlib.sha256(index_bytes).hexdigest() != INDEX_SHA256:
        raise FallbackHold("Frozen v5 index SHA-256 mismatch")
    index = json.loads(index_bytes.decode("utf-8-sig"))
    if (
        index.get("project_key") != PROJECT
        or index.get("target_instagram_id") != ACCOUNT_ID
        or index.get("meta_app_id") != APP_ID
        or len(index.get("rows", [])) != 20
    ):
        raise FallbackHold("Frozen v5 account, app, or row count mismatch")
    rows = [row for row in index["rows"] if row["proposed_moscow_slot"] == f"{day}T19:00:00"]
    if len(rows) != 1:
        raise FallbackHold("Expected exactly one reviewed 19:00 Moscow source")
    row = rows[0]
    youtube_id = row["youtube_id"]
    expected_hash = row["media_sha256"].removeprefix("sha256:")
    if len(expected_hash) != 64 or any(ch not in "0123456789abcdef" for ch in expected_hash):
        raise FallbackHold("Invalid source media digest")

    folder = Path(row["folder"])
    original = folder / "ORIGINAL-MUSIC-REEL.mp4"
    exact_manifest = json.loads((folder / "exact-local-publish-manifest.json").read_text(encoding="utf-8-sig"))
    owner_ack = json.loads((folder / "OWNER_DIRECTED_RISK_ACCEPTED.json").read_text(encoding="utf-8-sig"))
    if (
        exact_manifest.get("publication_key") != row["publication_key"]
        or exact_manifest.get("account_id") != ACCOUNT_ID
        or exact_manifest.get("media_sha256") != f"sha256:{expected_hash}"
        or owner_ack.get("publication_key") != row["publication_key"]
        or owner_ack.get("project_key") != PROJECT
        or owner_ack.get("owner_directed_repost") is not True
        or owner_ack.get("caption_editorially_reviewed") is not True
    ):
        raise FallbackHold("Source manifest or owner-reviewed original-audio approval mismatch")

    actual_hash, actual_size = _sha256(original)
    if actual_hash != expected_hash or actual_size != exact_manifest["media_size_bytes"]:
        raise FallbackHold("Original source bytes differ from frozen review")
    _require_unused_source(database_path, youtube_id)

    parsed = urlsplit(video_url)
    host = allowed_host.lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or parsed.hostname != host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path.endswith(f"/{expected_hash}.mp4")
    ):
        raise FallbackHold("URL must be a content-addressed direct HTTPS MP4 on the exact allowed host")

    manifest = InstagramPublishManifest(
        publication_key=f"milovi-cake.{day}.yt-{youtube_id}.public-https-v1",
        account_id=ACCOUNT_ID,
        video_url=video_url,
        media_sha256=f"sha256:{expected_hash}",
        media_size_bytes=actual_size,
        media_content_type="video/mp4",
        caption=exact_manifest["caption"],
        share_to_feed=exact_manifest["share_to_feed"],
        thumb_offset_ms=exact_manifest.get("thumb_offset_ms"),
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
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--day", required=True)
    parser.add_argument("--video-url", required=True)
    parser.add_argument("--allowed-host", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--public-hosting-authorized", action="store_true")
    args = parser.parse_args()

    with httpx.Client(timeout=httpx.Timeout(60.0), follow_redirects=False) as client:
        manifest = prepare_verified_manifest(
            index_path=args.index,
            database_path=args.database,
            day=args.day,
            video_url=args.video_url,
            allowed_host=args.allowed_host,
            public_hosting_authorized=args.public_hosting_authorized,
            media_client=client,
        )
    # Exclusive creation: no overwrite or mutation of a previous release key.
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(manifest.model_dump(mode="json"), stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"PROVIDER_INERT_VERIFIED_URL_MANIFEST={manifest.publication_key}")
    print("META_REQUESTS=0 PROVIDER_WRITES=0 PUBLICATION_AUTHORITY=NOT_GRANTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
