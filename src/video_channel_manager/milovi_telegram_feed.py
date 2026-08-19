from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue, load_release
from video_channel_manager.telegram_multichannel_state import (
    initialize_ledger,
    load_ledger,
    save_ledger,
)
from video_channel_manager.telegram_multichannel_transport import GenericPhotoPayload
from video_channel_manager.telegram_target_binding import load_target_binding

PROJECT_KEY = "milovi-cake"
CHANNEL_USERNAME = "@MiloviCake"
STATE_BRANCH = "state/milovi-cake-telegram"
CONCURRENCY_GROUP = "milovi-cake-telegram-publisher"
EXPECTED_CHAT_ID = -1002215328390
EXPECTED_BOT_ID = 8716602202
EXPECTED_BOT_USERNAME = "preaching_mp3_bot"
PUBLICATION_RE = re.compile(r"^milovi-feed-\d{8}-\d{3}$")
RELEASE_ROOT = Path("content/telegram/milovi-cake/releases")
STATE_ROOT = Path("content/telegram/milovi-cake/feed")
INDEX_RELATIVE_PATH = STATE_ROOT / "index.json"


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid Milovi feed JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Milovi feed JSON must contain an object: {path}")
    return value


def exact_paths(publication_id: str) -> dict[str, Path]:
    if PUBLICATION_RE.fullmatch(publication_id) is None:
        raise ValueError("Milovi feed publication_id must match milovi-feed-YYYYMMDD-NNN")
    return {
        "release": RELEASE_ROOT / f"{publication_id}-runtime.json",
        "authority": RELEASE_ROOT / f"{publication_id}-execution-authority.json",
        "media": RELEASE_ROOT / f"{publication_id}-media.json",
        "ledger": STATE_ROOT / f"{publication_id}.json",
        "index": INDEX_RELATIVE_PATH,
    }


class MiloviExecutionAuthority(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.milovi-telegram-execution-authority"]
    schema_version: Literal[1]
    project_key: Literal["milovi-cake"]
    publication_id: str
    release_id: str
    release_candidate_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    release_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    provider_payload_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    execution_authorized: bool = False
    provider_mutation_allowed: bool = False
    authorized_by: str | None = Field(default=None, max_length=200)
    authorized_at: datetime | None = None
    authority_source: Literal["fresh_exact_human_authorization_only"]
    historical_authorization_inherits: Literal[False]
    automation_is_execution_authority: Literal[False]
    max_provider_attempts: Literal[1]
    blind_mutation_retries: Literal[0]

    @model_validator(mode="after")
    def validate_authority(self) -> "MiloviExecutionAuthority":
        if self.execution_authorized != self.provider_mutation_allowed:
            raise ValueError("execution_authorized and provider_mutation_allowed must change together")
        if self.execution_authorized:
            if self.release_digest is None or not self.authorized_by or self.authorized_at is None:
                raise ValueError("active execution authority requires exact release digest and human provenance")
            if self.authorized_at.tzinfo is None:
                raise ValueError("execution authorization timestamp must be timezone-aware")
        elif self.release_digest is not None or self.authorized_by is not None or self.authorized_at is not None:
            raise ValueError("inactive execution authority must not claim active authorization metadata")
        return self


class MiloviMediaSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    path: str = Field(min_length=1, max_length=500)
    git_blob_sha1: str = Field(pattern=r"^[0-9a-f]{40}$")
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    media_type: Literal["image/webp"]
    pixel_width: int = Field(gt=0)
    pixel_height: int = Field(gt=0)


class MiloviMediaTransport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    format: Literal["image/jpeg"]
    byte_size: int = Field(gt=0, le=10_000_000)
    sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    media_path: str = Field(min_length=1, max_length=500)
    filename: str = Field(min_length=5, max_length=128)
    encoder: Literal["Pillow/JPEG quality=95 subsampling=0 optimize=false progressive=false exif=empty"]


class MiloviFeedMediaBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.milovi-telegram-feed-media"]
    schema_version: Literal[1]
    project_key: Literal["milovi-cake"]
    publication_id: str
    media_id: str
    candidate_path: str
    caption_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source: MiloviMediaSource
    transport: MiloviMediaTransport
    provider_write_performed: Literal[False]


FeedStateName = Literal["pending", "dispatching", "published", "unknown", "failed", "skipped"]
FeedProviderEffect = Literal["impossible", "not_dispatched", "confirmed_absent", "may_exist", "verified"]


class MiloviFeedIndexEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publication_id: str
    release_id: str
    release_candidate_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    provider_payload_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    ledger_relative_path: str
    state: FeedStateName = "pending"
    provider_effect: FeedProviderEffect = "impossible"
    intent_id: str | None = None
    message_id: int | None = None
    message_url: str | None = None
    updated_at_utc: datetime | None = None


class MiloviFeedIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: Literal["video-channel-manager.milovi-telegram-feed-index"]
    schema_version: Literal[1]
    project_key: Literal["milovi-cake"]
    channel_username: Literal["@MiloviCake"]
    entries: dict[str, MiloviFeedIndexEntry]


def _load_authority(path: Path) -> MiloviExecutionAuthority:
    try:
        return MiloviExecutionAuthority.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid Milovi execution authority {path}: {exc}") from exc


def _load_media(path: Path) -> MiloviFeedMediaBinding:
    try:
        return MiloviFeedMediaBinding.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid Milovi feed media binding {path}: {exc}") from exc


def _load_index(path: Path) -> MiloviFeedIndex:
    try:
        return MiloviFeedIndex.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid Milovi feed index {path}: {exc}") from exc


def _save_index(path: Path, index: MiloviFeedIndex) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(index.model_dump_json(indent=2) + "\n", encoding="utf-8")


def validate_bundle(
    publication_id: str,
    *,
    require_release_authorized: bool = False,
    require_execution_authorized: bool = False,
) -> dict[str, Any]:
    paths = exact_paths(publication_id)
    profile = load_channel_profile(Path("content/telegram/channels/milovi-cake.json"))
    if (
        profile.project_key != PROJECT_KEY
        or profile.channel_username.casefold() != CHANNEL_USERNAME.casefold()
        or profile.state_branch != STATE_BRANCH
        or profile.concurrency_group != CONCURRENCY_GROUP
    ):
        raise ValueError("Milovi profile differs from permanent feed namespace")

    binding = load_target_binding(Path("content/telegram/channels/milovi-cake-target-binding.json"), profile)
    if (
        binding.chat_id != EXPECTED_CHAT_ID
        or binding.bot_id != EXPECTED_BOT_ID
        or binding.bot_username.casefold() != EXPECTED_BOT_USERNAME.casefold()
    ):
        raise ValueError("Milovi target binding differs from exact feed target")

    release = load_release(paths["release"])
    if (
        release.release_id != publication_id
        or release.project_key != PROJECT_KEY
        or release.channel_username.casefold() != CHANNEL_USERNAME.casefold()
        or release.profile_sha256 != profile.digest
        or release.target_binding_sha256 != binding.digest
        or release.chat_id != binding.chat_id
        or release.bot_id != binding.bot_id
        or (release.bot_username or "").casefold() != binding.bot_username.casefold()
        or len(release.items) != 1
        or release.items[0].publication_id != publication_id
    ):
        raise ValueError("Milovi runtime release differs from exact permanent feed binding")

    authority = _load_authority(paths["authority"])
    item = release.items[0]
    if (
        authority.publication_id != publication_id
        or authority.release_id != release.release_id
        or authority.release_candidate_sha256 != release.candidate_digest()
        or authority.provider_payload_sha256 != item.payload.provider_payload_sha256
    ):
        raise ValueError("Milovi execution authority differs from exact release/payload")

    media = _load_media(paths["media"])
    if media.publication_id != publication_id:
        raise ValueError("Milovi media binding publication_id differs from release")
    candidate = _read_json(Path(media.candidate_path))
    if (
        candidate.get("publication_id") != publication_id
        or candidate.get("project_key") != PROJECT_KEY
        or candidate.get("publication_authorized") is not False
        or candidate.get("execution_authorized") is not False
        or candidate.get("provider_mutation_allowed") is not False
    ):
        raise ValueError("frozen Milovi content candidate must remain provider-inert")
    caption = str(candidate.get("caption") or "")
    if _sha256_bytes(caption.encode("utf-8")) != media.caption_sha256:
        raise ValueError("Milovi candidate caption digest differs from media binding")
    if not isinstance(item.payload, GenericPhotoPayload):
        raise ValueError("current Milovi feed media binding requires a photo payload")
    if (
        item.payload.caption != caption
        or item.payload.media_path != media.transport.media_path
        or item.payload.media_sha256 != media.transport.sha256
        or item.payload.media_byte_size != media.transport.byte_size
        or item.payload.media_filename != media.transport.filename
        or item.source_sha256 != media.source.sha256
    ):
        raise ValueError("Milovi release payload differs from exact content/media binding")

    candidate_media = candidate.get("media")
    if not isinstance(candidate_media, dict) or (
        candidate_media.get("media_id") != media.media_id
        or candidate_media.get("source_path") != media.source.path
        or candidate_media.get("source_git_blob_sha1") != media.source.git_blob_sha1
        or candidate_media.get("source_sha256") != media.source.sha256
        or candidate_media.get("transport_sha256") != media.transport.sha256
        or candidate_media.get("transport_byte_size") != media.transport.byte_size
    ):
        raise ValueError("Milovi candidate media differs from exact feed media binding")

    if require_release_authorized and not release.release_authorized:
        raise ValueError("Milovi release is not freshly authorized")
    if require_execution_authorized:
        if not release.release_authorized:
            raise ValueError("Milovi release is not freshly authorized")
        if not authority.execution_authorized or not authority.provider_mutation_allowed:
            raise ValueError("fresh exact Milovi execution authority is missing")
        if authority.release_digest != release.digest:
            raise ValueError("Milovi execution authority does not bind exact authorized release digest")

    blockers: list[str] = []
    if not release.release_authorized:
        blockers.append("release_authorized=false")
    if not authority.execution_authorized:
        blockers.append("execution_authorized=false")
    if not authority.provider_mutation_allowed:
        blockers.append("provider_mutation_allowed=false")
    return {
        "valid": True,
        "publication_id": publication_id,
        "release_digest": release.digest,
        "release_candidate_sha256": release.candidate_digest(),
        "provider_payload_sha256": item.payload.provider_payload_sha256,
        "release_authorized": release.release_authorized,
        "execution_authorized": authority.execution_authorized,
        "provider_mutation_allowed": authority.provider_mutation_allowed,
        "provider_access_performed": False,
        "blockers": blockers,
    }


def materialize_photo(publication_id: str, *, source_path: Path, output_path: Path | None = None) -> dict[str, Any]:
    paths = exact_paths(publication_id)
    media = _load_media(paths["media"])
    source = source_path.read_bytes()
    if len(source) != media.source.byte_size or _sha256_bytes(source) != media.source.sha256:
        raise ValueError("Milovi source bytes differ from exact feed media binding")
    blob_sha1 = hashlib.sha1(
        f"blob {len(source)}\0".encode("ascii") + source,
        usedforsecurity=False,
    ).hexdigest()
    if blob_sha1 != media.source.git_blob_sha1:
        raise ValueError("Milovi source Git blob differs from exact feed media binding")
    try:
        from PIL import Image  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ValueError("Pillow is required to materialize exact Milovi feed photo bytes") from exc
    with Image.open(io.BytesIO(source)) as image:
        image.load()
        if image.format != "WEBP" or image.size != (media.source.pixel_width, media.source.pixel_height):
            raise ValueError("Milovi source media type/dimensions differ from exact binding")
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
    if len(jpeg) != media.transport.byte_size or _sha256_bytes(jpeg) != media.transport.sha256:
        raise ValueError("Milovi generated JPEG differs from exact reviewed transport bytes")
    effective_output = output_path or Path(media.transport.media_path)
    if effective_output.as_posix() != media.transport.media_path:
        raise ValueError("Milovi output path differs from exact release-bound media path")
    effective_output.parent.mkdir(parents=True, exist_ok=True)
    effective_output.write_bytes(jpeg)
    return {
        "verified": True,
        "publication_id": publication_id,
        "output": str(effective_output),
        "transport_sha256": media.transport.sha256,
        "transport_byte_size": len(jpeg),
        "provider_write_performed": False,
    }


def _index_entry(release: GenericReleaseQueue, ledger_relative_path: Path) -> MiloviFeedIndexEntry:
    item = release.items[0]
    return MiloviFeedIndexEntry(
        publication_id=item.publication_id,
        release_id=release.release_id,
        release_candidate_sha256=release.candidate_digest(),
        provider_payload_sha256=item.payload.provider_payload_sha256,
        ledger_relative_path=ledger_relative_path.as_posix(),
    )


def _require_index_identity(
    existing: MiloviFeedIndexEntry,
    release: GenericReleaseQueue,
    ledger_relative_path: Path,
) -> None:
    expected = _index_entry(release, ledger_relative_path)
    immutable = (
        "publication_id",
        "release_id",
        "release_candidate_sha256",
        "provider_payload_sha256",
        "ledger_relative_path",
    )
    for field in immutable:
        if getattr(existing, field) != getattr(expected, field):
            raise ValueError(f"channel-wide Milovi duplicate guard collision on {field}")


def state_init(publication_id: str, *, state_checkout: Path) -> dict[str, Any]:
    validate_bundle(publication_id, require_release_authorized=True)
    paths = exact_paths(publication_id)
    release = load_release(paths["release"])
    ledger_path = state_checkout / paths["ledger"]
    index_path = state_checkout / paths["index"]
    if ledger_path.exists():
        load_ledger(ledger_path, release)
    else:
        ledger = initialize_ledger(release)
        save_ledger(ledger_path, ledger)

    if index_path.exists():
        index = _load_index(index_path)
    else:
        index = MiloviFeedIndex(
            schema_name="video-channel-manager.milovi-telegram-feed-index",
            schema_version=1,
            project_key=PROJECT_KEY,
            channel_username=CHANNEL_USERNAME,
            entries={},
        )
    existing = index.entries.get(publication_id)
    if existing is None:
        index.entries[publication_id] = _index_entry(release, paths["ledger"])
    else:
        _require_index_identity(existing, release, paths["ledger"])
    _save_index(index_path, index)
    return {
        "initialized": True,
        "publication_id": publication_id,
        "ledger": paths["ledger"].as_posix(),
        "index": paths["index"].as_posix(),
        "provider_access_performed": False,
    }


def state_check(publication_id: str, *, state_checkout: Path, require_publishable: bool = False) -> dict[str, Any]:
    paths = exact_paths(publication_id)
    release = load_release(paths["release"])
    ledger = load_ledger(state_checkout / paths["ledger"], release)
    index = _load_index(state_checkout / paths["index"])
    existing = index.entries.get(publication_id)
    if existing is None:
        raise ValueError("channel-wide Milovi feed index has no exact publication registration")
    _require_index_identity(existing, release, paths["ledger"])
    ledger_entry = ledger.entries[publication_id]
    if (
        existing.state != ledger_entry.state
        or existing.provider_effect != ledger_entry.provider_effect
        or existing.intent_id != ledger_entry.intent_id
        or existing.message_id != ledger_entry.message_id
        or existing.message_url != ledger_entry.message_url
    ):
        raise ValueError("channel-wide Milovi feed index differs from exact durable release ledger")
    if require_publishable and (
        existing.state != "pending"
        or existing.provider_effect not in {"impossible", "not_dispatched", "confirmed_absent"}
    ):
        raise ValueError("channel-wide Milovi duplicate guard blocks another provider attempt")
    return {
        "valid": True,
        "publication_id": publication_id,
        "state": existing.state,
        "provider_effect": existing.provider_effect,
        "provider_access_performed": False,
    }


def sync_index(publication_id: str, *, state_checkout: Path) -> dict[str, Any]:
    paths = exact_paths(publication_id)
    release = load_release(paths["release"])
    ledger = load_ledger(state_checkout / paths["ledger"], release)
    index_path = state_checkout / paths["index"]
    index = _load_index(index_path)
    existing = index.entries.get(publication_id)
    if existing is None:
        raise ValueError("refusing to auto-register publication during dispatch; initialize state explicitly first")
    _require_index_identity(existing, release, paths["ledger"])
    ledger_entry = ledger.entries[publication_id]
    existing.state = ledger_entry.state
    existing.provider_effect = ledger_entry.provider_effect
    existing.intent_id = ledger_entry.intent_id
    existing.message_id = ledger_entry.message_id
    existing.message_url = ledger_entry.message_url
    existing.updated_at_utc = datetime.now(tz=UTC)
    _save_index(index_path, index)
    return {
        "synced": True,
        "publication_id": publication_id,
        "state": existing.state,
        "provider_effect": existing.provider_effect,
        "provider_access_performed": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Permanent single-writer Milovi Telegram feed contract")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("--publication-id", required=True)
    validate.add_argument("--require-release-authorized", action="store_true")
    validate.add_argument("--require-execution-authorized", action="store_true")

    materialize = sub.add_parser("materialize-photo")
    materialize.add_argument("--publication-id", required=True)
    materialize.add_argument("--source", type=Path, required=True)
    materialize.add_argument("--output", type=Path)

    init = sub.add_parser("state-init")
    init.add_argument("--publication-id", required=True)
    init.add_argument("--state-checkout", type=Path, required=True)

    check = sub.add_parser("state-check")
    check.add_argument("--publication-id", required=True)
    check.add_argument("--state-checkout", type=Path, required=True)
    check.add_argument("--require-publishable", action="store_true")

    sync = sub.add_parser("sync-index")
    sync.add_argument("--publication-id", required=True)
    sync.add_argument("--state-checkout", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "validate":
        result = validate_bundle(
            args.publication_id,
            require_release_authorized=args.require_release_authorized or args.require_execution_authorized,
            require_execution_authorized=args.require_execution_authorized,
        )
    elif args.command == "materialize-photo":
        result = materialize_photo(args.publication_id, source_path=args.source, output_path=args.output)
    elif args.command == "state-init":
        result = state_init(args.publication_id, state_checkout=args.state_checkout)
    elif args.command == "state-check":
        result = state_check(
            args.publication_id,
            state_checkout=args.state_checkout,
            require_publishable=args.require_publishable,
        )
    elif args.command == "sync-index":
        result = sync_index(args.publication_id, state_checkout=args.state_checkout)
    else:
        raise AssertionError(f"unhandled command: {args.command}")
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
