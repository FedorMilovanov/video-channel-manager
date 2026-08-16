from __future__ import annotations

import argparse
import hashlib
import io
import json
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile, load_channel_profile
from video_channel_manager.telegram_multichannel_release import (
    GenericProviderPayload,
    GenericReleaseItem,
    GenericReleaseQueue,
    save_release,
)
from video_channel_manager.telegram_multichannel_transport import render_message_payload, render_photo_payload

EXPECTED_PROJECT_KEY = "milovi-cake"
EXPECTED_TIMEZONE = "Europe/Moscow"
EXPECTED_ITEM_COUNT = 12
EXPECTED_PHOTO_COUNT = 9
EXPECTED_MESSAGE_COUNT = 3
EXPECTED_DAILY_LIMIT = 2
EXPECTED_SCHOOL_POSITIONS = (3, 7, 11)
EXPECTED_SLOTS = (time(10, 30), time(20, 0))
EXPECTED_WINDOW_START = time(9, 0)
EXPECTED_WINDOW_END = time(21, 0)
EXPECTED_BOOTSTRAP_FINAL_PUBLICATION_ID = "milovi-bootstrap-010"
EXPECTED_BOOTSTRAP_TERMINAL_STATUS = "verified"
RUNTIME_MEDIA_DIR = Path(".runtime/milovi-telegram-follow-on/media")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid Milovi follow-on JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Milovi follow-on JSON must contain an object: {path}")
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
        raise ValueError(f"{label} differs from frozen Milovi follow-on contract")


def _aware_datetime(value: object, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{label} is not a valid ISO datetime") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware")
    return parsed


def _validate_profile(profile: TelegramChannelProfile) -> None:
    _exact_identity(profile.project_key, EXPECTED_PROJECT_KEY, "profile project_key")
    _exact_identity(profile.channel_username.casefold(), "@milovicake", "profile channel_username")
    _exact_identity(profile.publication_id_prefix, "milovi-", "profile publication_id_prefix")
    _exact_identity(profile.timezone, EXPECTED_TIMEZONE, "profile timezone")
    _exact_identity(profile.daily_verified_limit, EXPECTED_DAILY_LIMIT, "profile daily_verified_limit")


def validate_follow_on_bundle(
    profile: TelegramChannelProfile,
    *,
    candidates_path: Path,
    transport_manifest_path: Path,
    policy_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    _validate_profile(profile)
    candidates = _read_json(candidates_path)
    transport = _read_json(transport_manifest_path)
    policy = _read_json(policy_path)

    _exact_identity(candidates.get("project_key"), EXPECTED_PROJECT_KEY, "candidate project_key")
    _exact_identity(candidates.get("status"), "provider_inert_frozen_copy_candidate", "candidate status")
    _exact_identity(candidates.get("timezone"), EXPECTED_TIMEZONE, "candidate timezone")
    if (
        candidates.get("execution_authorized") is not False
        or candidates.get("provider_mutation_allowed") is not False
        or candidates.get("becomes_operational_queue") is not False
    ):
        raise ValueError("Milovi follow-on copy candidate must remain provider-inert")

    _exact_identity(transport.get("project_key"), EXPECTED_PROJECT_KEY, "transport project_key")
    _exact_identity(
        transport.get("status"),
        "provider_inert_exact_transport_verified",
        "transport status",
    )
    _exact_identity(transport.get("photo_count"), EXPECTED_PHOTO_COUNT, "transport photo count")
    _exact_identity(
        transport.get("transport_ready_count"),
        EXPECTED_PHOTO_COUNT,
        "transport ready count",
    )
    if (
        transport.get("execution_authorized") is not False
        or transport.get("provider_mutation_allowed") is not False
        or transport.get("provider_write_performed") is not False
    ):
        raise ValueError("Milovi follow-on transport proof must remain provider-inert")

    _exact_identity(policy.get("project_key"), EXPECTED_PROJECT_KEY, "policy project_key")
    _exact_identity(
        policy.get("status"),
        "provider_inert_release_compiler_policy",
        "policy status",
    )
    _exact_identity(policy.get("timezone"), EXPECTED_TIMEZONE, "policy timezone")
    _exact_identity(policy.get("daily_verified_limit"), EXPECTED_DAILY_LIMIT, "policy daily limit")
    _exact_identity(policy.get("allowed_slots_local"), ["10:30", "20:00"], "policy slot grid")
    window = policy.get("public_window_local")
    if not isinstance(window, dict):
        raise ValueError("Milovi follow-on public window policy is missing")
    _exact_identity(window.get("start"), "09:00", "policy public window start")
    _exact_identity(window.get("end"), "21:00", "policy public window end")
    _exact_identity(policy.get("strict_next_only"), True, "policy strict-next rule")
    _exact_identity(policy.get("no_catch_up"), True, "policy no-catch-up rule")
    _exact_identity(
        policy.get("first_slot_must_be_strictly_after_anchor"),
        True,
        "policy strict future slot rule",
    )
    _exact_identity(
        policy.get("required_bootstrap_final_publication_id"),
        EXPECTED_BOOTSTRAP_FINAL_PUBLICATION_ID,
        "policy bootstrap terminal publication",
    )
    _exact_identity(
        policy.get("required_bootstrap_terminal_status"),
        EXPECTED_BOOTSTRAP_TERMINAL_STATUS,
        "policy bootstrap terminal status",
    )
    if (
        policy.get("release_authorized") is not False
        or policy.get("execution_authorized") is not False
        or policy.get("provider_mutation_allowed") is not False
        or policy.get("compiler_may_access_telegram_provider") is not False
    ):
        raise ValueError("Milovi follow-on release policy must remain provider-inert")

    items = candidates.get("items")
    photos = transport.get("photos")
    if not isinstance(items, list) or len(items) != EXPECTED_ITEM_COUNT:
        raise ValueError("Milovi follow-on candidate must contain exactly twelve items")
    if not isinstance(photos, list) or len(photos) != EXPECTED_PHOTO_COUNT:
        raise ValueError("Milovi follow-on transport manifest must contain exactly nine photos")

    media_by_id = {str(item.get("media_id")): item for item in photos if isinstance(item, dict)}
    if len(media_by_id) != EXPECTED_PHOTO_COUNT:
        raise ValueError("duplicate media_id in Milovi follow-on transport manifest")

    photo_count = 0
    message_count = 0
    school_positions: list[int] = []
    publication_ids: list[str] = []
    required_revalidation: list[str] = []
    previous_school = False
    for expected_position, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError("Milovi follow-on candidate item is not an object")
        publication_id = str(item.get("publication_id") or "")
        _exact_identity(item.get("position"), expected_position, f"position for {publication_id}")
        _exact_identity(
            publication_id,
            f"milovi-follow-on-{expected_position:03d}",
            f"publication_id at position {expected_position}",
        )
        publication_ids.append(publication_id)
        caption = str(item.get("caption") or "")
        if not caption:
            raise ValueError(f"empty caption for {publication_id}")
        if bool(item.get("must_reverify_before_operational_promotion")):
            required_revalidation.append(publication_id)

        brand_stream = str(item.get("brand_stream") or "")
        operation = str(item.get("operation") or "")
        is_school = brand_stream == "milovi-school"
        if is_school:
            school_positions.append(expected_position)
            message_count += 1
            _exact_identity(operation, "sendMessage", f"School operation for {publication_id}")
            _exact_identity(item.get("product_cta_allowed"), False, f"School product CTA for {publication_id}")
            _exact_identity(
                item.get("must_reverify_before_operational_promotion"),
                True,
                f"School revalidation for {publication_id}",
            )
            if previous_school:
                raise ValueError("Milovi School follow-on posts may not be consecutive")
            if len(caption) > 4096:
                raise ValueError(f"School message exceeds Telegram message limit: {publication_id}")
        elif brand_stream == "milovi-cake":
            photo_count += 1
            _exact_identity(operation, "sendPhoto", f"Cake operation for {publication_id}")
            media_id = str(item.get("media_id") or "")
            media = media_by_id.get(media_id)
            if media is None:
                raise ValueError(f"missing exact media transport for {publication_id}/{media_id}")
            if len(caption) > 1024:
                raise ValueError(f"Cake photo caption exceeds Telegram limit: {publication_id}")
            lowered = caption.casefold()
            if "milovi school" in lowered or "french.milovicake.ru" in lowered or "француз" in lowered:
                raise ValueError(f"Cake caption improperly links production to School/French positioning: {publication_id}")
            for field in (
                "source_git_blob_sha1",
                "source_sha256",
                "pixel_width",
                "pixel_height",
                "transport_byte_size",
                "transport_sha256",
            ):
                if media.get(field) in (None, ""):
                    raise ValueError(f"incomplete exact media proof for {publication_id}/{media_id}: {field}")
        else:
            raise ValueError(f"unsupported Milovi follow-on brand stream: {brand_stream}")
        previous_school = is_school

    if len(publication_ids) != len(set(publication_ids)):
        raise ValueError("duplicate publication_id in Milovi follow-on candidate")
    _exact_identity(tuple(school_positions), EXPECTED_SCHOOL_POSITIONS, "School positions")
    if photo_count != EXPECTED_PHOTO_COUNT or message_count != EXPECTED_MESSAGE_COUNT:
        raise ValueError("Milovi follow-on wave must contain nine Cake photos and three School messages")
    if items[-1].get("brand_stream") != "milovi-cake":
        raise ValueError("Milovi follow-on wave must end with a Cake post")

    policy_required = policy.get("required_revalidation_publication_ids")
    if not isinstance(policy_required, list):
        raise ValueError("Milovi follow-on revalidation policy is missing")
    _exact_identity(required_revalidation, policy_required, "required revalidation publication ids")
    return candidates, transport, policy


def build_readiness_template(
    *,
    candidates: dict[str, Any],
    transport: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_name": "video-channel-manager.milovi-follow-on-readiness-receipt",
        "schema_version": 1,
        "project_key": EXPECTED_PROJECT_KEY,
        "status": "requires_fresh_external_verification",
        "candidate_canonical_sha256": _canonical_digest(candidates),
        "media_manifest_canonical_sha256": _canonical_digest(transport),
        "bootstrap_final_publication_id": EXPECTED_BOOTSTRAP_FINAL_PUBLICATION_ID,
        "bootstrap_terminal_status": "requires_exact_state_read",
        "bootstrap_final_verified_at": None,
        "source_revalidated_at": None,
        "revalidated_publication_ids": policy["required_revalidation_publication_ids"],
        "provider_write_performed": False,
        "telegram_provider_accessed": False,
        "execution_authorized": False,
        "provider_mutation_allowed": False,
    }


def validate_readiness_receipt(
    receipt: dict[str, Any],
    *,
    candidates: dict[str, Any],
    transport: dict[str, Any],
    policy: dict[str, Any],
    now: datetime,
) -> tuple[datetime, datetime, str]:
    if now.tzinfo is None:
        raise ValueError("compile now must be timezone-aware")
    _exact_identity(
        receipt.get("schema_name"),
        "video-channel-manager.milovi-follow-on-readiness-receipt",
        "readiness schema",
    )
    _exact_identity(receipt.get("schema_version"), 1, "readiness schema version")
    _exact_identity(receipt.get("project_key"), EXPECTED_PROJECT_KEY, "readiness project_key")
    _exact_identity(receipt.get("status"), "verified_current_sources", "readiness status")
    _exact_identity(
        receipt.get("candidate_canonical_sha256"),
        _canonical_digest(candidates),
        "readiness candidate digest",
    )
    _exact_identity(
        receipt.get("media_manifest_canonical_sha256"),
        _canonical_digest(transport),
        "readiness media manifest digest",
    )
    _exact_identity(
        receipt.get("bootstrap_final_publication_id"),
        EXPECTED_BOOTSTRAP_FINAL_PUBLICATION_ID,
        "readiness bootstrap final publication",
    )
    _exact_identity(
        receipt.get("bootstrap_terminal_status"),
        EXPECTED_BOOTSTRAP_TERMINAL_STATUS,
        "readiness bootstrap terminal status",
    )
    _exact_identity(
        receipt.get("revalidated_publication_ids"),
        policy["required_revalidation_publication_ids"],
        "readiness revalidated publication ids",
    )
    if (
        receipt.get("provider_write_performed") is not False
        or receipt.get("telegram_provider_accessed") is not False
        or receipt.get("execution_authorized") is not False
        or receipt.get("provider_mutation_allowed") is not False
    ):
        raise ValueError("Milovi follow-on readiness receipt must remain provider-inert")

    bootstrap_verified_at = _aware_datetime(
        receipt.get("bootstrap_final_verified_at"),
        "bootstrap_final_verified_at",
    )
    source_revalidated_at = _aware_datetime(receipt.get("source_revalidated_at"), "source_revalidated_at")
    max_age = timedelta(minutes=int(policy["readiness_receipt_max_age_minutes"]))
    future_skew = timedelta(minutes=int(policy["readiness_receipt_future_clock_skew_minutes"]))
    if source_revalidated_at > now + future_skew:
        raise ValueError("Milovi follow-on source revalidation timestamp is implausibly in the future")
    if now - source_revalidated_at > max_age:
        raise ValueError("Milovi follow-on source revalidation receipt is stale")

    receipt_digest = _canonical_digest(receipt)
    return bootstrap_verified_at, source_revalidated_at, receipt_digest


def _next_release_slots(*, anchor: datetime, count: int) -> tuple[datetime, ...]:
    if anchor.tzinfo is None:
        raise ValueError("release anchor must be timezone-aware")
    zone = ZoneInfo(EXPECTED_TIMEZONE)
    local_anchor = anchor.astimezone(zone)
    cursor = local_anchor.date()
    result: list[datetime] = []
    while len(result) < count:
        for slot in EXPECTED_SLOTS:
            scheduled = datetime.combine(cursor, slot, tzinfo=zone)
            if scheduled <= local_anchor:
                continue
            if not (EXPECTED_WINDOW_START <= slot <= EXPECTED_WINDOW_END):
                raise ValueError("configured Milovi follow-on slot is outside the public window")
            result.append(scheduled)
            if len(result) == count:
                break
        cursor += timedelta(days=1)
    return tuple(result)


def build_release_candidate(
    profile: TelegramChannelProfile,
    *,
    candidates_path: Path,
    transport_manifest_path: Path,
    policy_path: Path,
    readiness_receipt_path: Path,
    now: datetime,
) -> GenericReleaseQueue:
    candidates, transport, policy = validate_follow_on_bundle(
        profile,
        candidates_path=candidates_path,
        transport_manifest_path=transport_manifest_path,
        policy_path=policy_path,
    )
    receipt = _read_json(readiness_receipt_path)
    bootstrap_verified_at, source_revalidated_at, receipt_digest = validate_readiness_receipt(
        receipt,
        candidates=candidates,
        transport=transport,
        policy=policy,
        now=now,
    )
    anchor = max(now, bootstrap_verified_at, source_revalidated_at)
    schedules = _next_release_slots(anchor=anchor, count=EXPECTED_ITEM_COUNT)

    media_by_id = {item["media_id"]: item for item in transport["photos"]}
    items: list[GenericReleaseItem] = []
    candidate_digest = _canonical_digest(candidates)
    media_manifest_digest = _canonical_digest(transport)
    for sequence, (candidate, scheduled_at) in enumerate(zip(candidates["items"], schedules, strict=True), start=1):
        publication_id = candidate["publication_id"]
        caption = candidate["caption"]
        payload: GenericProviderPayload
        media_identity: dict[str, Any] | None = None
        if candidate["operation"] == "sendPhoto":
            media_id = candidate["media_id"]
            media = media_by_id[media_id]
            media_identity = {
                "media_id": media_id,
                "source_git_blob_sha1": media["source_git_blob_sha1"],
                "source_sha256": media["source_sha256"],
                "transport_sha256": media["transport_sha256"],
                "transport_byte_size": media["transport_byte_size"],
            }
            payload = render_photo_payload(
                profile,
                publication_id=publication_id,
                caption=caption,
                media_path=str(RUNTIME_MEDIA_DIR / f"{media_id}.jpg"),
                media_sha256=media["transport_sha256"],
                media_byte_size=int(media["transport_byte_size"]),
                media_filename=f"{media_id}.jpg",
            )
        else:
            payload = render_message_payload(profile, publication_id=publication_id, html_text=caption)

        source_identity = {
            "publication_id": publication_id,
            "sequence": sequence,
            "operation": candidate["operation"],
            "caption_sha256": _sha256_text(caption),
            "candidate_canonical_sha256": candidate_digest,
            "media_manifest_canonical_sha256": media_manifest_digest,
            "readiness_receipt_sha256": receipt_digest,
            "scheduled_at": scheduled_at.isoformat(),
            "media": media_identity,
        }
        items.append(
            GenericReleaseItem(
                sequence=sequence,
                publication_id=publication_id,
                scheduled_at=scheduled_at,
                source_sha256=_canonical_digest(source_identity),
                payload=payload,
            )
        )

    return GenericReleaseQueue(
        schema_name="video-channel-manager.telegram-release-queue",
        schema_version=1,
        release_id=str(policy["release_id"]),
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
    transport_manifest_path: Path,
    media_id: str,
    source_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    transport = _read_json(transport_manifest_path)
    photos = transport.get("photos")
    if not isinstance(photos, list):
        raise ValueError("Milovi follow-on transport manifest has no photos")
    item = next(
        (candidate for candidate in photos if isinstance(candidate, dict) and candidate.get("media_id") == media_id),
        None,
    )
    if item is None:
        raise ValueError(f"unknown Milovi follow-on media_id: {media_id}")
    try:
        source = source_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"unable to read Milovi follow-on source media: {source_path}") from exc
    _exact_identity(len(source), int(item["source_byte_size"]), f"source byte size for {media_id}")
    _exact_identity(_sha256_bytes(source), item["source_sha256"], f"source SHA-256 for {media_id}")
    blob_sha1 = hashlib.sha1(
        f"blob {len(source)}\0".encode("ascii") + source,
        usedforsecurity=False,
    ).hexdigest()
    _exact_identity(blob_sha1, item["source_git_blob_sha1"], f"source Git blob for {media_id}")

    try:
        from PIL import Image  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ValueError("Pillow is required to materialize exact Milovi follow-on JPEG bytes") from exc
    with Image.open(io.BytesIO(source)) as image:
        image.load()
        _exact_identity(image.format, "WEBP", f"source media format for {media_id}")
        _exact_identity(
            image.size,
            (int(item["pixel_width"]), int(item["pixel_height"])),
            f"source dimensions for {media_id}",
        )
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
    parser = argparse.ArgumentParser(description="Validate and compile the frozen Milovi Telegram follow-on wave")
    parser.add_argument("command", choices=("validate", "readiness-template", "build-release", "materialize-photo"))
    parser.add_argument("--profile", type=Path, default=Path("content/telegram/channels/milovi-cake.json"))
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("content/telegram/milovi-cake/follow-on-wave-candidates-2026-08.json"),
    )
    parser.add_argument(
        "--transport-manifest",
        type=Path,
        default=Path("content/telegram/milovi-cake/follow-on-photo-source-manifest-2026-08.json"),
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("content/telegram/milovi-cake/follow-on-release-policy-2026-08.json"),
    )
    parser.add_argument("--readiness", type=Path)
    parser.add_argument("--now")
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
            transport_manifest_path=args.transport_manifest,
            media_id=args.media_id,
            source_path=args.source,
            output_path=args.output,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0

    profile = load_channel_profile(args.profile)
    candidates, transport, policy = validate_follow_on_bundle(
        profile,
        candidates_path=args.candidates,
        transport_manifest_path=args.transport_manifest,
        policy_path=args.policy,
    )
    if args.command == "validate":
        print(
            json.dumps(
                {
                    "valid": True,
                    "release_id": policy["release_id"],
                    "profile_sha256": profile.digest,
                    "items": EXPECTED_ITEM_COUNT,
                    "photos": EXPECTED_PHOTO_COUNT,
                    "messages": EXPECTED_MESSAGE_COUNT,
                    "provider_writes_authorized": profile.provider_writes_authorized,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "readiness-template":
        if args.output is None:
            raise ValueError("readiness-template requires --output")
        template = build_readiness_template(candidates=candidates, transport=transport, policy=policy)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"built": True, "status": template["status"], "output": str(args.output)}))
        return 0

    if args.readiness is None or args.now is None or args.output is None:
        raise ValueError("build-release requires --readiness, --now and --output")
    now = _aware_datetime(args.now, "--now")
    release = build_release_candidate(
        profile,
        candidates_path=args.candidates,
        transport_manifest_path=args.transport_manifest,
        policy_path=args.policy,
        readiness_receipt_path=args.readiness,
        now=now,
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
