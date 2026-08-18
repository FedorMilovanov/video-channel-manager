from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Sequence, cast
from zoneinfo import ZoneInfo

import httpx
from pydantic import model_validator

from video_channel_manager.lordchrist_cross_track_effect_guard import require_no_cross_track_unresolved_effects
from video_channel_manager.lordchrist_rich_successor import build_provider_free_document
from video_channel_manager.platforms.http import (
    HttpClientOwner,
    HttpOperationClass,
    HttpTransportFailure,
    RetryPolicy,
    execute_http_request,
)
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof, preflight_channel
from video_channel_manager.telegram_rich_models import RichArticleDocument
from video_channel_manager.telegram_rich_provider import (
    HttpxTelegramRichMutationProvider,
    TelegramRichMessageDocument,
    TelegramRichOutcomeArchiveReceipt,
    TelegramRichProviderOutcome,
    TelegramRichProviderResponse,
    TelegramRichProviderTimeout,
    TelegramRichProviderTransportError,
    TelegramRichRequestTimeout,
    publish_rich_once,
)

PROJECT = "lord-god-strength"
CHANNEL = "@lordchrist"
CHAT_ID = -1001295216957
CHAT_USERNAME = "lordchrist"
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"
REPOSITORY = "FedorMilovanov/video-channel-manager"
RELEASE_ID = "lordchrist-rich-live-canary-2026-08-18"
PUBLICATION_ID = "lordchrist-rich-sermons-survive-century"
OWNING_ISSUE = 473
MEDIA_USER_AGENT = "video-channel-manager-lordchrist-rich/1 (+https://github.com/FedorMilovanov/video-channel-manager)"
MEDIA_IDS = ("media-calvin", "media-spurgeon", "media-tape")
ATTACHMENT_NAMES = {
    "media-calvin": "lc_calvin",
    "media-spurgeon": "lc_spurgeon",
    "media-tape": "lc_tape",
}
ATTACHMENT_FILENAMES = {
    "media-calvin": "john-calvin.jpg",
    "media-spurgeon": "charles-spurgeon.jpg",
    "media-tape": "reel-to-reel.jpg",
}
MOSCOW = ZoneInfo("Europe/Moscow")

AttachmentBundle = dict[str, tuple[str, bytes, str]]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _blob(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()  # noqa: S324


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return value


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _verify(root: Path, identity: dict[str, Any]) -> Path:
    path = root / str(identity["path"])
    actual = _blob(path.read_bytes())
    if actual != identity.get("git_blob_sha"):
        raise ValueError(f"release-bound Git blob differs: {path} ({actual})")
    return path


def load_release(path: Path, root: Path) -> dict[str, Any]:
    release = _read(path)
    if (
        release.get("schema_name") != "video-channel-manager.lordchrist-rich-live-canary-release"
        or release.get("schema_version") != 1
        or release.get("release_id") != RELEASE_ID
        or release.get("owning_issue") != OWNING_ISSUE
        or release.get("project_key") != PROJECT
        or release.get("channel_username") != CHANNEL
        or release.get("chat_id") != CHAT_ID
        or release.get("bot_id") != BOT_ID
        or str(release.get("bot_username") or "").casefold() != BOT_USERNAME.casefold()
        or release.get("state_branch") != "state/lordchrist-telegram"
        or release.get("approved") is not True
        or release.get("max_combined_verified_per_day_moscow") != 2
        or release.get("max_rich_verified_per_day_moscow") != 1
        or release.get("publication_id") != PUBLICATION_ID
    ):
        raise ValueError("invalid LordChrist rich live canary release header")

    not_before = datetime.fromisoformat(str(release["execute_not_before_moscow"]))
    not_after = datetime.fromisoformat(str(release["execute_not_after_moscow"]))
    if not_before.utcoffset() != timedelta(hours=3) or not_after.utcoffset() != timedelta(hours=3):
        raise ValueError("LordChrist live canary window must use UTC+03:00")
    if not_after <= not_before:
        raise ValueError("LordChrist live canary window is empty")

    for key in ("profile", "legacy_profile", "target_binding", "media_registry", "article"):
        _verify(root, cast(dict[str, Any], release[key]))
    return release


def release_digest(release: dict[str, Any]) -> str:
    return _sha(release)


def require_live_window(release: dict[str, Any], now: datetime | None = None) -> None:
    current = (now or datetime.now(tz=UTC)).astimezone(MOSCOW)
    not_before = datetime.fromisoformat(str(release["execute_not_before_moscow"]))
    not_after = datetime.fromisoformat(str(release["execute_not_after_moscow"]))
    if current < not_before or current > not_after:
        raise ValueError("LordChrist rich live canary authorization window is not active")


def _attachment_reference(media_id: str) -> str:
    try:
        return f"attach://{ATTACHMENT_NAMES[media_id]}"
    except KeyError as exc:
        raise ValueError(f"unknown LordChrist live attachment media id: {media_id}") from exc


def _media_records(value: Any) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []

    def walk(candidate: Any, path: str) -> None:
        if isinstance(candidate, dict):
            block_type = candidate.get("type")
            if block_type in {"photo", "video", "animation", "audio", "voice_note"}:
                media_object = candidate.get(str(block_type))
                if isinstance(media_object, dict):
                    identity = media_object.get("media")
                    if isinstance(identity, str):
                        records.append({"path": path, "type": str(block_type), "media": identity})
            for key, child in candidate.items():
                walk(child, f"{path}/{key}")
        elif isinstance(candidate, list):
            for index, child in enumerate(candidate):
                walk(child, f"{path}/{index}")

    walk(value, "$")
    return records


def _attachment_names(value: Any) -> frozenset[str]:
    names: set[str] = set()

    def walk(candidate: Any) -> None:
        if isinstance(candidate, dict):
            identity = candidate.get("media")
            if isinstance(identity, str) and identity.startswith("attach://"):
                name = identity.removeprefix("attach://")
                if not name:
                    raise ValueError("empty LordChrist multipart attachment name")
                names.add(name)
            for child in candidate.values():
                walk(child)
        elif isinstance(candidate, list):
            for child in candidate:
                walk(child)

    walk(value)
    return frozenset(names)


def _replace_source_urls_with_attachments(
    value: dict[str, Any],
    source_article: RichArticleDocument,
) -> dict[str, Any]:
    replacement = {media.uri: _attachment_reference(media.media_id) for media in source_article.media}
    if set(replacement.values()) != {f"attach://{name}" for name in ATTACHMENT_NAMES.values()}:
        raise ValueError("LordChrist source article does not map one-to-one onto the reviewed attachment set")
    updated = copy.deepcopy(value)

    def walk(candidate: Any) -> None:
        if isinstance(candidate, dict):
            identity = candidate.get("media")
            if isinstance(identity, str) and identity in replacement:
                candidate["media"] = replacement[identity]
            for child in candidate.values():
                walk(child)
        elif isinstance(candidate, list):
            for child in candidate:
                walk(child)

    walk(updated)
    return updated


class _AttachmentTelegramRichMessageDocument(TelegramRichMessageDocument):
    """Issue-473 document variant for official multipart `attach://` InputMediaPhoto values.

    The generic HTTPS-backed document is constructed and fully validated first.
    `build_document()` then proves this object differs only by replacing the
    three exact source media identities with their one-to-one attachment names.
    """

    @model_validator(mode="after")
    def validate_document(self) -> "_AttachmentTelegramRichMessageDocument":
        if self.legacy_fallback is not None:
            raise ValueError("LordChrist rich live canary forbids legacy fallback")
        selected_paths = self.provider_assigned_media_paths
        if len(selected_paths) != 3 or len(selected_paths) != len(set(selected_paths)):
            raise ValueError("LordChrist rich live canary requires exactly three unique provider media paths")
        input_records = {record["path"]: record for record in _media_records(self.input_rich_message)}
        if set(selected_paths) != set(input_records):
            raise ValueError("LordChrist rich attachment paths must cover every outgoing media block exactly once")
        if {record["type"] for record in input_records.values()} != {"photo"}:
            raise ValueError("LordChrist rich live canary supports photo attachments only")
        names = _attachment_names(self.input_rich_message)
        if names != frozenset(ATTACHMENT_NAMES.values()):
            raise ValueError("LordChrist rich document attachment names differ from the reviewed exact set")
        if any(not record["media"].startswith("attach://") for record in input_records.values()):
            raise ValueError("LordChrist rich provider media must be multipart attachments")
        _canonical_json(self.input_rich_message)
        _canonical_json(self.expected_returned_rich_message)
        return self


@dataclass(frozen=True)
class _AttachmentRenderEvidence:
    article_digest: str
    visible_text: str
    provider_assigned_media: tuple[str, ...]
    render_sha256: str


def _attached_article(source_article: RichArticleDocument) -> RichArticleDocument:
    if tuple(media.media_id for media in source_article.media) != MEDIA_IDS:
        raise ValueError("LordChrist source article media order differs from reviewed live canary order")
    media = tuple(
        media.model_copy(update={"uri": _attachment_reference(media.media_id)}) for media in source_article.media
    )
    return source_article.model_copy(update={"media": media})


def _prove_only_media_identity_changed(
    source_document: TelegramRichMessageDocument,
    attached_document: _AttachmentTelegramRichMessageDocument,
    source_article: RichArticleDocument,
) -> None:
    restored = copy.deepcopy(attached_document.input_rich_message)
    reverse = {_attachment_reference(media.media_id): media.uri for media in source_article.media}

    def walk(candidate: Any) -> None:
        if isinstance(candidate, dict):
            identity = candidate.get("media")
            if isinstance(identity, str) and identity in reverse:
                candidate["media"] = reverse[identity]
            for child in candidate.values():
                walk(child)
        elif isinstance(candidate, list):
            for child in candidate:
                walk(child)

    walk(restored)
    if restored != source_document.input_rich_message:
        raise ValueError("LordChrist attachment document differs from reviewed source by more than media identity")
    if attached_document.expected_returned_rich_message != source_document.expected_returned_rich_message:
        raise ValueError("LordChrist attachment document changed the reviewed expected RichMessage")
    if attached_document.target != source_document.target:
        raise ValueError("LordChrist attachment document changed the exact target binding")
    if attached_document.provider_assigned_media_paths != source_document.provider_assigned_media_paths:
        raise ValueError("LordChrist attachment document changed provider-assigned media paths")


def build_document(root: Path, release: dict[str, Any]) -> tuple[Any, Any, Any]:
    source_document, source_render, source_article = build_provider_free_document(
        _verify(root, cast(dict[str, Any], release["article"])),
        _verify(root, cast(dict[str, Any], release["media_registry"])),
        _verify(root, cast(dict[str, Any], release["profile"])),
        _verify(root, cast(dict[str, Any], release["target_binding"])),
    )
    if source_article.document_id != PUBLICATION_ID or source_document.publication_id != PUBLICATION_ID:
        raise ValueError("LordChrist live canary source document identity mismatch")
    if tuple(media.media_id for media in source_article.media) != MEDIA_IDS:
        raise ValueError("LordChrist live canary must bind exactly the three reviewed media slots")
    if len(source_document.provider_assigned_media_paths) != 3:
        raise ValueError("LordChrist source document must render exactly three provider media paths")

    article = _attached_article(source_article)
    input_rich_message = _replace_source_urls_with_attachments(source_document.input_rich_message, source_article)
    document = _AttachmentTelegramRichMessageDocument(
        schema_name="video-channel-manager.telegram-rich-message-document",
        schema_version=1,
        publication_id=source_document.publication_id,
        target=source_document.target,
        input_rich_message=input_rich_message,
        expected_returned_rich_message=copy.deepcopy(source_document.expected_returned_rich_message),
        provider_assigned_media_paths=source_document.provider_assigned_media_paths,
        legacy_fallback=None,
    )
    _prove_only_media_identity_changed(source_document, document, source_article)
    render_payload = {
        "article_digest": article.digest,
        "input_rich_message": document.input_rich_message,
        "expected_returned_rich_message": document.expected_returned_rich_message,
        "visible_text": source_render.visible_text,
        "provider_assigned_media": list(MEDIA_IDS),
        "delivery_mode": "multipart-attach",
    }
    render = _AttachmentRenderEvidence(
        article_digest=article.digest,
        visible_text=source_render.visible_text,
        provider_assigned_media=MEDIA_IDS,
        render_sha256=_sha(render_payload),
    )
    return document, render, article


def new_ledger(release: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "video-channel-manager.lordchrist-rich-live-canary-ledger",
        "schema_version": 1,
        "release_id": RELEASE_ID,
        "release_sha256": release_digest(release),
        "owning_issue": OWNING_ISSUE,
        "project_key": PROJECT,
        "channel_username": CHANNEL,
        "entries": {
            PUBLICATION_ID: {
                "publication_id": PUBLICATION_ID,
                "state": "pending",
                "provider_effect": "impossible",
                "workflow_run_id": None,
                "workflow_run_attempt": None,
                "github_sha": None,
                "document_sha256": None,
                "intent_created_at_utc": None,
                "published_at_utc": None,
                "message_id": None,
                "message_url": None,
                "error": None,
            }
        },
    }


def load_ledger(path: Path, release: dict[str, Any], *, create: bool = False) -> dict[str, Any]:
    ledger = new_ledger(release) if create and not path.exists() else _read(path)
    if (
        ledger.get("schema_name") != "video-channel-manager.lordchrist-rich-live-canary-ledger"
        or ledger.get("schema_version") != 1
        or ledger.get("release_id") != RELEASE_ID
        or ledger.get("release_sha256") != release_digest(release)
        or ledger.get("owning_issue") != OWNING_ISSUE
        or ledger.get("project_key") != PROJECT
        or ledger.get("channel_username") != CHANNEL
    ):
        raise ValueError("LordChrist rich live canary ledger is bound to another release")
    entries = ledger.get("entries")
    if not isinstance(entries, dict) or list(entries) != [PUBLICATION_ID]:
        raise ValueError("LordChrist rich live canary ledger entries differ from release")
    return ledger


def _rich_entry(ledger: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, dict[str, Any]], ledger["entries"])[PUBLICATION_ID]


def _legacy_verified_today(legacy_ledger_path: Path, today_moscow: str) -> int:
    legacy = _read(legacy_ledger_path)
    entries = legacy.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("legacy LordChrist ledger has no entries")
    count = 0
    for raw in entries.values():
        if not isinstance(raw, dict) or raw.get("state") != "published" or raw.get("provider_effect") != "verified":
            continue
        published = raw.get("published_at_utc")
        if not published:
            raise ValueError("verified legacy LordChrist entry lacks published_at_utc")
        if (
            datetime.fromisoformat(str(published).replace("Z", "+00:00")).astimezone(MOSCOW).date().isoformat()
            == today_moscow
        ):
            count += 1
    return count


def guard_state(
    root: Path,
    state_root: Path,
    release: dict[str, Any],
    ledger: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    require_live_window(release, now)
    cross_track = require_no_cross_track_unresolved_effects(
        profile_path=_verify(root, cast(dict[str, Any], release["legacy_profile"])),
        legacy_queue_path=root / "content/telegram/lordchrist/verified-30-posts.json",
        legacy_ledger_path=state_root / "content/telegram/lordchrist/publication-ledger.json",
        research_ledger_path=state_root / "content/telegram/lordchrist/research-v2/publication-ledger.json",
    )
    entry = _rich_entry(ledger)
    if entry["state"] in {"intent", "may_exist", "failed_no_effect"}:
        raise ValueError(f"unresolved LordChrist rich canary state blocks writer: {entry['state']}")
    current = (now or datetime.now(tz=UTC)).astimezone(MOSCOW)
    today = current.date().isoformat()
    legacy_count = _legacy_verified_today(
        state_root / "content/telegram/lordchrist/publication-ledger.json",
        today,
    )
    rich_count = 1 if entry["state"] == "published" and entry.get("provider_effect") == "verified" else 0
    if rich_count >= int(release["max_rich_verified_per_day_moscow"]):
        raise ValueError("LordChrist rich daily verified limit is already used")
    if legacy_count + rich_count >= int(release["max_combined_verified_per_day_moscow"]):
        raise ValueError("combined LordChrist verified daily limit is already used")
    return {
        "clear": True,
        "moscow_date": today,
        "legacy_verified_today": legacy_count,
        "rich_verified_today": rich_count,
        "combined_verified_today": legacy_count + rich_count,
        "cross_track": cross_track,
        "provider_write_performed": False,
    }


def _target_proof(path: Path) -> GenericTargetProof:
    return GenericTargetProof.model_validate_json(path.read_text(encoding="utf-8"))


def _require_target(proof: GenericTargetProof, document: Any, *, now: datetime | None = None) -> None:
    if (proof.chat_id, proof.bot_id, proof.bot_username.casefold(), proof.can_post_messages, proof.profile_sha256) != (
        document.target.chat_id,
        document.target.bot_id,
        document.target.bot_username.casefold(),
        True,
        document.target.profile_sha256,
    ):
        raise ValueError("fresh LordChrist target proof differs from exact rich target")
    age = (now or datetime.now(tz=UTC)) - proof.checked_at_utc.astimezone(UTC)
    if age < -timedelta(minutes=1) or age > timedelta(minutes=15):
        raise ValueError("LordChrist rich target proof is stale")


def run_preflight(root: Path, release: dict[str, Any], *, token: str) -> GenericTargetProof:
    require_live_window(release)
    document, _render, _article = build_document(root, release)
    profile = load_channel_profile(_verify(root, cast(dict[str, Any], release["profile"])))
    proof = preflight_channel(
        profile,
        token=token,
        expected_chat_id=CHAT_ID,
        expected_bot_id=BOT_ID,
        expected_bot_username=BOT_USERNAME,
    )
    _require_target(proof, document)
    return proof


def _source_assets(root: Path, release: dict[str, Any]) -> tuple[dict[str, str], ...]:
    registry = _read(_verify(root, cast(dict[str, Any], release["media_registry"])))
    raw_assets = registry.get("assets")
    if not isinstance(raw_assets, list):
        raise ValueError("LordChrist rich media registry has no assets")
    by_id: dict[str, dict[str, Any]] = {}
    for raw in raw_assets:
        if not isinstance(raw, dict) or raw.get("article_id") != PUBLICATION_ID:
            continue
        media_id = str(raw.get("media_slot_id") or "")
        if media_id in MEDIA_IDS:
            if media_id in by_id:
                raise ValueError(f"duplicate LordChrist live source media slot: {media_id}")
            by_id[media_id] = raw
    if tuple(media_id for media_id in MEDIA_IDS if media_id in by_id) != MEDIA_IDS:
        raise ValueError("LordChrist live source registry does not contain the exact three reviewed media slots")

    result: list[dict[str, str]] = []
    for media_id in MEDIA_IDS:
        raw = by_id[media_id]
        url = raw.get("direct_media_url")
        mime = raw.get("expected_mime")
        if (
            not isinstance(url, str)
            or not url.startswith("https://upload.wikimedia.org/")
            or mime != "image/jpeg"
            or raw.get("remote_ready") is not True
            or raw.get("acquisition_status") != "source_and_license_reviewed"
        ):
            raise ValueError(f"LordChrist live source media is not exact reviewed Wikimedia JPEG: {media_id}")
        result.append(
            {
                "media_id": media_id,
                "url": url,
                "content_type": "image/jpeg",
                "attachment_name": ATTACHMENT_NAMES[media_id],
                "filename": ATTACHMENT_FILENAMES[media_id],
            }
        )
    return tuple(result)


class _LordChristMediaReader(HttpClientOwner):
    def __init__(self) -> None:
        self._initialize_http_client(
            None,
            timeout=httpx.Timeout(connect=15, read=30, write=15, pool=15),
            follow_redirects=True,
            trust_env=False,
        )

    def fetch(self, url: str) -> tuple[int, str, bytes]:
        result = execute_http_request(
            lambda: self._http_client.get(url, headers={"User-Agent": MEDIA_USER_AGENT}),
            provider="https-media",
            operation=HttpOperationClass.SAFE_READ,
            method="GET",
            resource="lordchrist-rich-live-canary-media",
            retry_policy=RetryPolicy(max_attempts=2),
        )
        response = result.response
        return (
            response.status_code,
            response.headers.get("content-type", "").split(";", 1)[0].strip().lower(),
            response.content,
        )


def _fetch_media_bundle(root: Path, release: dict[str, Any]) -> tuple[list[dict[str, Any]], AttachmentBundle]:
    evidence: list[dict[str, Any]] = []
    attachments: AttachmentBundle = {}
    reader = _LordChristMediaReader()
    try:
        for source in _source_assets(root, release):
            status, content_type, content = reader.fetch(source["url"])
            if (
                status != 200
                or content_type != source["content_type"]
                or not content
                or len(content) > 10_000_000
                or not content.startswith(b"\xff\xd8\xff")
            ):
                raise ValueError(
                    f"LordChrist rich media proof failed: {source['media_id']} "
                    f"status={status} content_type={content_type!r} bytes={len(content)}"
                )
            digest = "sha256:" + hashlib.sha256(content).hexdigest()
            evidence.append(
                {
                    "media_id": source["media_id"],
                    "source_url": source["url"],
                    "attachment_name": source["attachment_name"],
                    "filename": source["filename"],
                    "content_type": content_type,
                    "content_length": len(content),
                    "content_sha256": digest,
                }
            )
            attachments[source["attachment_name"]] = (source["filename"], content, content_type)
    finally:
        reader.close()
    if set(attachments) != set(ATTACHMENT_NAMES.values()):
        raise ValueError("LordChrist live attachment bundle differs from the exact reviewed set")
    return evidence, attachments


def media_proof(
    root: Path,
    release: dict[str, Any],
    *,
    expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    require_live_window(release)
    evidence, _attachments = _fetch_media_bundle(root, release)
    proof = {
        "schema_name": "video-channel-manager.lordchrist-rich-live-media-proof",
        "schema_version": 1,
        "release_sha256": release_digest(release),
        "publication_id": PUBLICATION_ID,
        "delivery_mode": "multipart-attach",
        "checked_at_utc": datetime.now(tz=UTC).isoformat(),
        "items": evidence,
        "provider_write_performed": False,
    }
    if expected is not None and expected.get("items") != proof["items"]:
        raise ValueError("LordChrist rich media bytes changed after durable intent")
    return proof


def prepare(
    root: Path,
    state_root: Path,
    release: dict[str, Any],
    ledger: dict[str, Any],
    target_path: Path,
    proof_media: dict[str, Any],
    *,
    repository: str,
    sha: str,
    run_id: str,
    attempt: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    guard_state(root, state_root, release, ledger)
    entry = _rich_entry(ledger)
    if entry["state"] != "pending":
        raise ValueError("LordChrist rich canary is not pending")
    document, render, _article = build_document(root, release)
    target = _target_proof(target_path)
    _require_target(target, document)
    proof_items = proof_media.get("items")
    if (
        repository != REPOSITORY
        or proof_media.get("release_sha256") != release_digest(release)
        or proof_media.get("publication_id") != PUBLICATION_ID
        or proof_media.get("delivery_mode") != "multipart-attach"
        or not isinstance(proof_items, list)
        or len(proof_items) != 3
        or [item.get("media_id") for item in proof_items if isinstance(item, dict)] != list(MEDIA_IDS)
    ):
        raise ValueError("LordChrist rich durable intent inputs differ from exact release")
    created_at = datetime.now(tz=UTC).isoformat()
    intent = {
        "schema_name": "video-channel-manager.lordchrist-rich-live-canary-intent",
        "schema_version": 1,
        "release_sha256": release_digest(release),
        "owning_issue": OWNING_ISSUE,
        "publication_id": PUBLICATION_ID,
        "delivery_mode": "multipart-attach",
        "github_repository": repository,
        "github_sha": sha,
        "workflow_run_id": run_id,
        "workflow_run_attempt": attempt,
        "document_sha256": document.document_sha256,
        "render_sha256": render.render_sha256,
        "target_proof_sha256": _sha(target.model_dump(mode="json")),
        "media_proof": proof_media,
        "created_at_utc": created_at,
        "mutation_request_limit": 1,
        "automatic_retry_allowed": False,
        "blind_retry_allowed": False,
        "fallback_allowed": False,
    }
    entry.update(
        {
            "state": "intent",
            "provider_effect": "impossible",
            "workflow_run_id": run_id,
            "workflow_run_attempt": attempt,
            "github_sha": sha,
            "document_sha256": document.document_sha256,
            "intent_created_at_utc": created_at,
            "error": None,
        }
    )
    return intent, ledger


class _Archiver:
    def __init__(self, path: Path) -> None:
        self.path = path

    def archive(self, outcome_bytes: bytes, *, outcome_sha256: str) -> TelegramRichOutcomeArchiveReceipt:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(outcome_bytes)
        if "sha256:" + hashlib.sha256(outcome_bytes).hexdigest() != outcome_sha256:
            raise ValueError("LordChrist rich provider outcome archive digest mismatch")
        return TelegramRichOutcomeArchiveReceipt(
            schema_name="video-channel-manager.telegram-rich-outcome-archive-receipt",
            schema_version=1,
            outcome_sha256=outcome_sha256,
            archive_reference=f"workflow-local:{self.path}",
            durable_before_state_mutation=True,
        )


class _LordChristMultipartProvider(HttpxTelegramRichMutationProvider):
    """One-request sendRichMessage adapter carrying exact reviewed JPEG bytes as attachments."""

    def __init__(self, *, token: str, attachments: AttachmentBundle, http_client: httpx.Client | None = None) -> None:
        super().__init__(token=token, http_client=http_client)
        if set(attachments) != set(ATTACHMENT_NAMES.values()):
            raise ValueError("LordChrist multipart provider attachment names differ from the reviewed exact set")
        self._attachments = attachments

    def send_rich_message(
        self,
        *,
        chat_id: int,
        rich_message: dict[str, Any],
        timeout: TelegramRichRequestTimeout,
    ) -> TelegramRichProviderResponse:
        if _attachment_names(rich_message) != frozenset(self._attachments):
            raise ValueError("LordChrist multipart request attachment references differ from the exact byte bundle")
        files = {
            name: (filename, content, content_type)
            for name, (filename, content, content_type) in self._attachments.items()
        }
        try:
            result = execute_http_request(
                lambda: self._http_client.post(
                    self._send_url,
                    data={"chat_id": str(chat_id), "rich_message": _canonical_json(rich_message)},
                    files=files,
                    timeout=timeout.as_httpx(),
                ),
                provider="telegram",
                operation=HttpOperationClass.AMBIGUOUS_MUTATION,
                method="POST",
                resource="sendRichMessage",
                retry_policy=RetryPolicy(max_attempts=1),
            )
        except HttpTransportFailure as exc:
            before_request = exc.cause_type in {"ConnectTimeout", "PoolTimeout", "ConnectError"}
            if "Timeout" in exc.cause_type:
                raise TelegramRichProviderTimeout(request_may_have_been_dispatched=not before_request) from exc
            raise TelegramRichProviderTransportError(request_may_have_been_dispatched=not before_request) from exc
        response = result.response
        try:
            body: Any = response.json()
        except ValueError:
            body = None
        return TelegramRichProviderResponse(status_code=response.status_code, body=body)


def send(
    root: Path,
    release: dict[str, Any],
    intent: dict[str, Any],
    target_path: Path,
    recheck: dict[str, Any],
    outcome_path: Path,
    *,
    token: str,
) -> TelegramRichProviderOutcome:
    require_live_window(release)
    if (
        intent.get("release_sha256") != release_digest(release)
        or intent.get("owning_issue") != OWNING_ISSUE
        or intent.get("github_repository") != REPOSITORY
        or intent.get("publication_id") != PUBLICATION_ID
        or intent.get("delivery_mode") != "multipart-attach"
        or cast(dict[str, Any], intent.get("media_proof", {})).get("items") != recheck.get("items")
    ):
        raise ValueError("LordChrist rich durable intent/media recheck mismatch")
    document, render, _article = build_document(root, release)
    if document.document_sha256 != intent.get("document_sha256") or render.render_sha256 != intent.get("render_sha256"):
        raise ValueError("LordChrist rich document changed after durable intent")
    target = _target_proof(target_path)
    _require_target(target, document)
    if _sha(target.model_dump(mode="json")) != intent.get("target_proof_sha256"):
        raise ValueError("LordChrist rich target proof changed after durable intent")

    final_evidence, attachments = _fetch_media_bundle(root, release)
    if final_evidence != recheck.get("items"):
        raise ValueError("LordChrist exact attachment bytes changed after immediate media recheck")
    if _attachment_names(document.input_rich_message) != frozenset(attachments):
        raise ValueError("LordChrist exact document attachment identities differ from final byte bundle")

    profile = load_channel_profile(_verify(root, cast(dict[str, Any], release["profile"])))
    provider = _LordChristMultipartProvider(token=token, attachments=attachments)
    try:
        archived = publish_rich_once(
            document,
            target,
            provider,
            _Archiver(outcome_path),
            profile=profile,
            state_mutation=None,
        )
    finally:
        provider.close()
    return archived.outcome


def apply(ledger: dict[str, Any], intent: dict[str, Any], outcome: TelegramRichProviderOutcome) -> dict[str, Any]:
    entry = _rich_entry(ledger)
    if (
        entry["state"] != "intent"
        or entry.get("document_sha256") != intent.get("document_sha256")
        or outcome.document_sha256 != intent.get("document_sha256")
    ):
        raise ValueError("LordChrist rich outcome has no exact durable intent")
    if outcome.provider_effect == "verified":
        entry.update(
            {
                "state": "published",
                "provider_effect": "verified",
                "published_at_utc": datetime.now(tz=UTC).isoformat(),
                "message_id": outcome.message_id,
                "message_url": outcome.message_url,
                "error": None,
            }
        )
    elif outcome.provider_effect == "may_exist":
        entry.update(
            {
                "state": "may_exist",
                "provider_effect": "may_exist",
                "error": outcome.error or "ambiguous provider effect",
            }
        )
    else:
        entry.update(
            {
                "state": "failed_no_effect",
                "provider_effect": outcome.provider_effect,
                "error": outcome.error or f"provider effect: {outcome.provider_effect}",
            }
        )
    return ledger


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="cmd", required=True)
    for name in ("preview", "ensure-ledger", "guard", "preflight", "media-proof", "prepare", "send", "apply", "status"):
        command = sub.add_parser(name)
        command.add_argument("--release", type=Path, required=True)
        command.add_argument("--root", type=Path, default=Path("."))
        if name in {"ensure-ledger", "guard", "prepare", "apply", "status"}:
            command.add_argument("--ledger", type=Path, required=True)
        if name in {"guard", "prepare"}:
            command.add_argument("--state-root", type=Path, required=True)
        if name == "preflight":
            command.add_argument("--output", type=Path, required=True)
        if name == "media-proof":
            command.add_argument("--expected", type=Path)
            command.add_argument("--output", type=Path, required=True)
        if name == "prepare":
            command.add_argument("--target-proof", type=Path, required=True)
            command.add_argument("--media-proof", type=Path, required=True)
            command.add_argument("--github-repository", required=True)
            command.add_argument("--github-sha", required=True)
            command.add_argument("--run-id", required=True)
            command.add_argument("--run-attempt", required=True)
            command.add_argument("--intent-output", type=Path, required=True)
        if name == "send":
            command.add_argument("--intent", type=Path, required=True)
            command.add_argument("--target-proof", type=Path, required=True)
            command.add_argument("--media-recheck", type=Path, required=True)
            command.add_argument("--outcome", type=Path, required=True)
        if name == "apply":
            command.add_argument("--intent", type=Path, required=True)
            command.add_argument("--outcome", type=Path, required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    release = load_release(args.release, args.root)
    if args.cmd == "preview":
        document, render, article = build_document(args.root, release)
        print(
            json.dumps(
                {
                    "release_id": RELEASE_ID,
                    "release_sha256": release_digest(release),
                    "owning_issue": OWNING_ISSUE,
                    "publication_id": PUBLICATION_ID,
                    "document_sha256": document.document_sha256,
                    "render_sha256": render.render_sha256,
                    "media_ids": [media.media_id for media in article.media],
                    "media_count": len(article.media),
                    "delivery_mode": "multipart-attach",
                    "attachment_names": sorted(_attachment_names(document.input_rich_message)),
                    "provider_write_performed": False,
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.cmd == "ensure-ledger":
        ledger = load_ledger(args.ledger, release, create=True)
        _write(args.ledger, ledger)
        print(json.dumps({"state": _rich_entry(ledger)["state"], "provider_write_performed": False}))
        return 0
    if args.cmd == "guard":
        ledger = load_ledger(args.ledger, release)
        print(json.dumps(guard_state(args.root, args.state_root, release, ledger), ensure_ascii=False))
        return 0
    if args.cmd == "preflight":
        target_proof = run_preflight(args.root, release, token=os.environ["LORDCHRIST_TELEGRAM_BOT_TOKEN"])
        _write(args.output, target_proof.model_dump(mode="json"))
        print(target_proof.model_dump_json())
        return 0
    if args.cmd == "media-proof":
        expected = _read(args.expected) if args.expected else None
        media_evidence = media_proof(args.root, release, expected=expected)
        _write(args.output, media_evidence)
        print(json.dumps(media_evidence, ensure_ascii=False))
        return 0
    if args.cmd == "prepare":
        ledger = load_ledger(args.ledger, release)
        intent, ledger = prepare(
            args.root,
            args.state_root,
            release,
            ledger,
            args.target_proof,
            _read(args.media_proof),
            repository=args.github_repository,
            sha=args.github_sha,
            run_id=args.run_id,
            attempt=args.run_attempt,
        )
        _write(args.intent_output, intent)
        _write(args.ledger, ledger)
        print(json.dumps(intent, ensure_ascii=False))
        return 0
    if args.cmd == "send":
        outcome = send(
            args.root,
            release,
            _read(args.intent),
            args.target_proof,
            _read(args.media_recheck),
            args.outcome,
            token=os.environ["LORDCHRIST_TELEGRAM_BOT_TOKEN"],
        )
        print(outcome.model_dump_json())
        return 0
    if args.cmd == "apply":
        ledger = load_ledger(args.ledger, release)
        outcome = TelegramRichProviderOutcome.model_validate_json(args.outcome.read_text(encoding="utf-8"))
        ledger = apply(ledger, _read(args.intent), outcome)
        _write(args.ledger, ledger)
        print(json.dumps(_rich_entry(ledger), ensure_ascii=False))
        return 0
    if args.cmd == "status":
        ledger = load_ledger(args.ledger, release)
        print(json.dumps(_rich_entry(ledger), ensure_ascii=False))
        return 0
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
