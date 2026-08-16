from __future__ import annotations

import argparse
import hashlib
import io
import json
from collections import Counter
from datetime import datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile, load_channel_profile
from video_channel_manager.telegram_multichannel_release import GenericReleaseItem, GenericReleaseQueue, save_release
from video_channel_manager.telegram_multichannel_transport import render_message_payload, render_photo_payload

EXPECTED_PROJECT_KEY = "milovi-cake"
EXPECTED_CHAT_ID = -1002215328390
EXPECTED_CHAT_USERNAME = "MiloviCake"
EXPECTED_BOT_ID = 8716602202
EXPECTED_BOT_USERNAME = "preaching_mp3_bot"
EXPECTED_TIMEZONE = "Europe/Moscow"
EXPECTED_ITEM_COUNT = 10
EXPECTED_PHOTO_COUNT = 9
EXPECTED_MESSAGE_COUNT = 1
EXPECTED_DAILY_LIMIT = 2
EXPECTED_WINDOW_START = time(9, 0)
EXPECTED_WINDOW_END = time(21, 0)
EXPECTED_SLOTS = {time(10, 30), time(20, 0)}
FORBIDDEN_FIRST_SCREEN_FRAGMENTS = ("milovi school", "french.milovicake.ru", "француз")
RUNTIME_MEDIA_DIR = Path(".runtime/milovi-telegram-bootstrap/media")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid Milovi bootstrap JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Milovi bootstrap JSON must contain an object: {path}")
    return value


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _canonical_digest(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(canonical)


def _exact_identity(value: object, expected: object, label: str) -> None:
    if value != expected:
        raise ValueError(f"{label} differs from frozen Milovi bootstrap contract")


def _validate_profile(profile: TelegramChannelProfile) -> None:
    _exact_identity(profile.project_key, EXPECTED_PROJECT_KEY, "profile project_key")
    _exact_identity(profile.channel_username.casefold(), "@milovicake", "profile channel_username")
    _exact_identity(profile.publication_id_prefix, "milovi-", "profile publication_id_prefix")
    _exact_identity(profile.timezone, EXPECTED_TIMEZONE, "profile timezone")
    _exact_identity(profile.daily_verified_limit, EXPECTED_DAILY_LIMIT, "profile daily_verified_limit")
    if profile.provider_writes_authorized:
        raise ValueError("provider-inert bootstrap compiler refuses a write-enabled Milovi profile")


def validate_bootstrap_bundle(
    profile: TelegramChannelProfile,
    *,
    rollout_path: Path,
    candidates_path: Path,
    transport_proof_path: Path,
    publishing_window_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    _validate_profile(profile)
    rollout = _read_json(rollout_path)
    candidates = _read_json(candidates_path)
    proof = _read_json(transport_proof_path)
    window = _read_json(publishing_window_path)

    _exact_identity(rollout.get("project_key"), EXPECTED_PROJECT_KEY, "rollout project_key")
    _exact_identity(rollout.get("chat_id"), EXPECTED_CHAT_ID, "rollout chat_id")
    _exact_identity(str(rollout.get("chat_username") or "").casefold(), EXPECTED_CHAT_USERNAME.casefold(), "rollout chat_username")
    _exact_identity(rollout.get("bot_id"), EXPECTED_BOT_ID, "rollout bot_id")
    _exact_identity(str(rollout.get("bot_username") or "").casefold(), EXPECTED_BOT_USERNAME.casefold(), "rollout bot_username")
    if rollout.get("execution_authorized") is not False or rollout.get("provider_mutation_allowed") is not False:
        raise ValueError("frozen Milovi rollout must remain provider-inert")

    policy = rollout.get("rollout_policy")
    if not isinstance(policy, dict):
        raise ValueError("Milovi rollout_policy is missing")
    _exact_identity(policy.get("timezone"), EXPECTED_TIMEZONE, "rollout timezone")
    _exact_identity(policy.get("planned_items_per_day"), EXPECTED_DAILY_LIMIT, "rollout items/day")
    _exact_identity(policy.get("planned_span_days"), 5, "rollout span")
    _exact_identity(policy.get("blind_mutation_retries"), 0, "rollout mutation retry count")
    _exact_identity(policy.get("strict_next_only"), True, "rollout strict-next policy")
    _exact_identity(policy.get("unknown_outcome_blocks_successor"), True, "rollout unknown-outcome policy")

    _exact_identity(candidates.get("project_key"), EXPECTED_PROJECT_KEY, "candidate project_key")
    _exact_identity(candidates.get("sequence_size"), EXPECTED_ITEM_COUNT, "candidate sequence size")
    _exact_identity(candidates.get("school_items_in_first_screen"), 0, "candidate School item count")
    if candidates.get("publication_authorized") is not False or candidates.get("provider_mutation_allowed") is not False:
        raise ValueError("Milovi first-screen candidate set must remain provider-inert")

    _exact_identity(proof.get("project_key"), EXPECTED_PROJECT_KEY, "transport proof project_key")
    _exact_identity(proof.get("photo_count"), EXPECTED_PHOTO_COUNT, "transport photo count")
    _exact_identity(proof.get("transport_ready_count"), EXPECTED_PHOTO_COUNT, "transport ready count")
    if proof.get("provider_write_performed") is not False or proof.get("provider_mutation_allowed") is not False:
        raise ValueError("Milovi transport proof must remain provider-inert")

    _exact_identity(window.get("project_key"), EXPECTED_PROJECT_KEY, "publishing-window project_key")
    _exact_identity(window.get("timezone"), EXPECTED_TIMEZONE, "publishing-window timezone")
    _exact_identity(window.get("earliest_publication_local"), "09:00", "publishing-window start")
    _exact_identity(window.get("latest_publication_local"), "21:00", "publishing-window end")
    if window.get("provider_mutation_allowed_by_this_file") is not False:
        raise ValueError("publishing-window policy must not grant provider mutation authority")

    rollout_items = rollout.get("items")
    candidate_items = candidates.get("candidates")
    photo_items = proof.get("photos")
    if not isinstance(rollout_items, list) or len(rollout_items) != EXPECTED_ITEM_COUNT:
        raise ValueError("Milovi rollout must contain exactly ten items")
    if not isinstance(candidate_items, list) or len(candidate_items) != EXPECTED_ITEM_COUNT:
        raise ValueError("Milovi first-screen candidates must contain exactly ten items")
    if not isinstance(photo_items, list) or len(photo_items) != EXPECTED_PHOTO_COUNT:
        raise ValueError("Milovi transport proof must contain exactly nine photos")

    candidate_by_publication = {str(item.get("publication_id")): item for item in candidate_items if isinstance(item, dict)}
    proof_by_media = {str(item.get("media_id")): item for item in photo_items if isinstance(item, dict)}
    if len(candidate_by_publication) != EXPECTED_ITEM_COUNT or len(proof_by_media) != EXPECTED_PHOTO_COUNT:
        raise ValueError("duplicate publication_id or media_id in frozen Milovi bootstrap bundle")

    local_days: Counter[str] = Counter()
    photo_count = 0
    message_count = 0
    previous: datetime | None = None
    zone = ZoneInfo(EXPECTED_TIMEZONE)
    for expected_sequence, rollout_item in enumerate(rollout_items, start=1):
        if not isinstance(rollout_item, dict):
            raise ValueError("Milovi rollout item is not an object")
        publication_id = str(rollout_item.get("publication_id") or "")
        _exact_identity(rollout_item.get("sequence"), expected_sequence, f"sequence for {publication_id}")
        if not publication_id.startswith(profile.publication_id_prefix):
            raise ValueError(f"publication_id {publication_id} does not match Milovi profile prefix")
        candidate = candidate_by_publication.get(publication_id)
        if candidate is None:
            raise ValueError(f"missing first-screen candidate for {publication_id}")
        _exact_identity(candidate.get("sequence"), expected_sequence, f"candidate sequence for {publication_id}")
        operation = str(rollout_item.get("operation") or "")
        _exact_identity(candidate.get("operation"), operation, f"operation for {publication_id}")
        caption = str(candidate.get("caption") or "")
        if not caption:
            raise ValueError(f"empty caption for {publication_id}")
        _exact_identity(_sha256_text(caption), rollout_item.get("caption_sha256"), f"caption digest for {publication_id}")
        lowered = caption.casefold()
        if any(fragment in lowered for fragment in FORBIDDEN_FIRST_SCREEN_FRAGMENTS):
            raise ValueError(f"forbidden Milovi School/French linkage in {publication_id}")
        if candidate.get("publication_authorized") is not False or candidate.get("execution_ready") is not False:
            raise ValueError(f"candidate {publication_id} unexpectedly grants execution authority")

        try:
            scheduled = datetime.fromisoformat(str(rollout_item.get("planned_local") or ""))
        except ValueError as exc:
            raise ValueError(f"invalid planned_local for {publication_id}") from exc
        if scheduled.tzinfo is None:
            raise ValueError(f"planned_local must be timezone-aware for {publication_id}")
        local = scheduled.astimezone(zone)
        if scheduled.utcoffset() != local.utcoffset() or scheduled.replace(tzinfo=None) != local.replace(tzinfo=None):
            raise ValueError(f"planned_local is not expressed in exact Europe/Moscow local time for {publication_id}")
        if not (EXPECTED_WINDOW_START <= local.time().replace(tzinfo=None) <= EXPECTED_WINDOW_END):
            raise ValueError(f"{publication_id} is outside the Milovi daylight window")
        if local.time().replace(tzinfo=None) not in EXPECTED_SLOTS:
            raise ValueError(f"{publication_id} is not on the frozen 10:30/20:00 slot grid")
        if previous is not None and scheduled <= previous:
            raise ValueError("Milovi rollout schedule is not strictly increasing")
        previous = scheduled
        local_days[local.date().isoformat()] += 1

        media_id = rollout_item.get("media_id")
        if operation == "sendPhoto":
            photo_count += 1
            if not isinstance(media_id, str) or not media_id:
                raise ValueError(f"photo publication {publication_id} has no media_id")
            _exact_identity(candidate.get("media_id"), media_id, f"candidate media_id for {publication_id}")
            transport = proof_by_media.get(media_id)
            if transport is None:
                raise ValueError(f"missing exact transport proof for {publication_id}/{media_id}")
            _exact_identity(transport.get("transport_ready"), True, f"transport readiness for {media_id}")
            _exact_identity(transport.get("transport_format"), "image/jpeg", f"transport format for {media_id}")
            _exact_identity(transport.get("transport_sha256"), rollout_item.get("transport_sha256"), f"transport SHA for {media_id}")
            _exact_identity(transport.get("transport_byte_size"), rollout_item.get("transport_byte_size"), f"transport size for {media_id}")
        elif operation == "sendMessage":
            message_count += 1
            if media_id is not None or rollout_item.get("transport_sha256") is not None or rollout_item.get("transport_byte_size") is not None:
                raise ValueError(f"message publication {publication_id} unexpectedly includes media transport identity")
        else:
            raise ValueError(f"unsupported frozen Milovi operation: {operation}")

    if photo_count != EXPECTED_PHOTO_COUNT or message_count != EXPECTED_MESSAGE_COUNT:
        raise ValueError("Milovi rollout must contain nine photos and one message")
    if len(local_days) != 5 or set(local_days.values()) != {EXPECTED_DAILY_LIMIT}:
        raise ValueError("Milovi rollout must contain exactly two items on each of five local days")
    return rollout, candidates, proof, window


def build_release_candidate(
    profile: TelegramChannelProfile,
    *,
    rollout_path: Path,
    candidates_path: Path,
    transport_proof_path: Path,
    publishing_window_path: Path,
) -> GenericReleaseQueue:
    rollout, candidates, proof, _window = validate_bootstrap_bundle(
        profile,
        rollout_path=rollout_path,
        candidates_path=candidates_path,
        transport_proof_path=transport_proof_path,
        publishing_window_path=publishing_window_path,
    )
    candidate_by_publication = {item["publication_id"]: item for item in candidates["candidates"]}
    proof_by_media = {item["media_id"]: item for item in proof["photos"]}
    items: list[GenericReleaseItem] = []
    for rollout_item in rollout["items"]:
        publication_id = rollout_item["publication_id"]
        candidate = candidate_by_publication[publication_id]
        caption = candidate["caption"]
        source_identity = {
            "publication_id": publication_id,
            "operation": rollout_item["operation"],
            "caption_sha256": rollout_item["caption_sha256"],
            "media_id": rollout_item["media_id"],
            "transport_sha256": rollout_item["transport_sha256"],
            "transport_byte_size": rollout_item["transport_byte_size"],
            "planned_local": rollout_item["planned_local"],
        }
        if rollout_item["operation"] == "sendPhoto":
            transport = proof_by_media[rollout_item["media_id"]]
            media_id = rollout_item["media_id"]
            payload = render_photo_payload(
                profile,
                publication_id=publication_id,
                caption=caption,
                media_path=str(RUNTIME_MEDIA_DIR / f"{media_id}.jpg"),
                media_sha256=transport["transport_sha256"],
                media_byte_size=int(transport["transport_byte_size"]),
                media_filename=f"{media_id}.jpg",
            )
        else:
            payload = render_message_payload(profile, publication_id=publication_id, html_text=caption)
        items.append(
            GenericReleaseItem(
                sequence=int(rollout_item["sequence"]),
                publication_id=publication_id,
                scheduled_at=datetime.fromisoformat(rollout_item["planned_local"]),
                source_sha256=_canonical_digest(source_identity),
                payload=payload,
            )
        )
    return GenericReleaseQueue(
        schema_name="video-channel-manager.telegram-release-queue",
        schema_version=1,
        release_id=rollout["release_id"],
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        timezone=profile.timezone,
        daily_verified_limit=profile.daily_verified_limit,
        target_binding_sha256=None,
        chat_id=None,
        bot_id=None,
        bot_username=None,
        release_authorized=False,
        reviewed_candidate_sha256=None,
        reviewed_by=None,
        reviewed_at=None,
        items=tuple(items),
    )


def materialize_exact_photo(
    *,
    transport_proof_path: Path,
    media_id: str,
    source_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    proof = _read_json(transport_proof_path)
    photos = proof.get("photos")
    if not isinstance(photos, list):
        raise ValueError("Milovi photo transport proof has no photos")
    item = next((candidate for candidate in photos if isinstance(candidate, dict) and candidate.get("media_id") == media_id), None)
    if item is None:
        raise ValueError(f"unknown Milovi bootstrap media_id: {media_id}")
    try:
        source = source_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"unable to read Milovi source media: {source_path}") from exc
    _exact_identity(len(source), int(item["source_byte_size"]), f"source byte size for {media_id}")
    _exact_identity(_sha256_bytes(source), item["source_sha256"], f"source SHA-256 for {media_id}")
    blob_sha1 = hashlib.sha1(f"blob {len(source)}\0".encode("ascii") + source, usedforsecurity=False).hexdigest()
    _exact_identity(blob_sha1, item["source_git_blob_sha1"], f"source Git blob for {media_id}")

    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError("Pillow is required to materialize exact Milovi JPEG transport bytes") from exc
    with Image.open(io.BytesIO(source)) as image:
        image.load()
        _exact_identity(image.format, "WEBP", f"source media format for {media_id}")
        _exact_identity(image.size, (int(item["pixel_width"]), int(item["pixel_height"])), f"source dimensions for {media_id}")
        rgb = image.convert("RGB")
    encoded = io.BytesIO()
    rgb.save(
        encoded,
        format="JPEG",
        quality=95,
        subsampling=0,
        optimize=False,
        progressive=False,
        exif=b"",
    )
    jpeg = encoded.getvalue()
    _exact_identity(len(jpeg), int(item["transport_byte_size"]), f"transport byte size for {media_id}")
    _exact_identity(_sha256_bytes(jpeg), item["transport_sha256"], f"transport SHA-256 for {media_id}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(jpeg)
    return {
        "media_id": media_id,
        "output": str(output_path),
        "transport_sha256": item["transport_sha256"],
        "transport_byte_size": len(jpeg),
        "verified": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and compile the provider-inert Milovi Telegram bootstrap")
    parser.add_argument("command", choices=("validate", "build-release", "materialize-photo"))
    parser.add_argument("--profile", type=Path, default=Path("content/telegram/channels/milovi-cake.json"))
    parser.add_argument("--rollout", type=Path, default=Path("content/telegram/milovi-cake/bootstrap-rollout-candidate-2026-08.json"))
    parser.add_argument("--candidates", type=Path, default=Path("content/telegram/milovi-cake/bootstrap-first-screen-candidates-2026-08.json"))
    parser.add_argument("--transport-proof", type=Path, default=Path("content/telegram/milovi-cake/bootstrap-photo-transport-proof-2026-08.json"))
    parser.add_argument("--publishing-window", type=Path, default=Path("content/telegram/milovi-cake/publishing-window-2026-08.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--media-id")
    parser.add_argument("--source", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "materialize-photo":
        if args.media_id is None or args.source is None or args.output is None:
            raise ValueError("materialize-photo requires --media-id, --source and --output")
        result = materialize_exact_photo(
            transport_proof_path=args.transport_proof,
            media_id=args.media_id,
            source_path=args.source,
            output_path=args.output,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0

    profile = load_channel_profile(args.profile)
    if args.command == "validate":
        rollout, _candidates, proof, _window = validate_bootstrap_bundle(
            profile,
            rollout_path=args.rollout,
            candidates_path=args.candidates,
            transport_proof_path=args.transport_proof,
            publishing_window_path=args.publishing_window,
        )
        print(
            json.dumps(
                {
                    "valid": True,
                    "release_id": rollout["release_id"],
                    "profile_sha256": profile.digest,
                    "items": EXPECTED_ITEM_COUNT,
                    "photos": proof["photo_count"],
                    "daily_verified_limit": profile.daily_verified_limit,
                    "provider_writes_authorized": profile.provider_writes_authorized,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.output is None:
        raise ValueError("build-release requires --output")
    release = build_release_candidate(
        profile,
        rollout_path=args.rollout,
        candidates_path=args.candidates,
        transport_proof_path=args.transport_proof,
        publishing_window_path=args.publishing_window,
    )
    save_release(args.output, release)
    print(
        json.dumps(
            {
                "built": True,
                "release_id": release.release_id,
                "release_digest": release.digest,
                "candidate_digest": release.candidate_digest(),
                "profile_sha256": release.profile_sha256,
                "items": len(release.items),
                "release_authorized": release.release_authorized,
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
