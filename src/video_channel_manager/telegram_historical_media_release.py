from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_historical_bundle import HistoricalSourceShardV1
from video_channel_manager.telegram_historical_editorial import HistoricalPost, HistoricalSource
from video_channel_manager.telegram_historical_revision import (
    HistoricalRevisionPackageV1,
    load_historical_revision_package,
    preflight_historical_revision,
)
from video_channel_manager.telegram_rich_models import (
    RICH_ARTICLE_SCHEMA_NAME,
    RICH_ARTICLE_SCHEMA_VERSION,
    RichArticleDocument,
    RichArticleMetadata,
    RichArticleSource,
    RichBlockCaption,
    RichBlockDetails,
    RichBlockHeading,
    RichBlockMedia,
    RichBlockParagraph,
    RichMediaItem,
    RichTextUrl,
)
from video_channel_manager.telegram_rich_provider import TelegramRichMessageDocument, TelegramRichTargetBinding
from video_channel_manager.telegram_rich_renderer import RichRenderResult, render_rich_document
from video_channel_manager.telegram_target_binding import load_target_binding

MEDIA_RELEASE_SCHEMA = "video-channel-manager.telegram-historical-live-media-release"
MEDIA_POLICY = "exact_https_photos_bound_before_sendRichMessage"
PROJECT = "lord-god-strength"
CHANNEL = "@lordchrist"
CHAT_ID = -1001295216957
CHAT_USERNAME = "lordchrist"
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _git_blob(value: bytes) -> str:
    return hashlib.sha1(f"blob {len(value)}\0".encode() + value).hexdigest()  # noqa: S324


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid historical media release JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("historical media release must be a JSON object")
    return value


def _resolve(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ValueError("historical media release path escapes repository root")
    return candidate


def _require_bound_file(root: Path, binding: dict[str, Any], *, label: str) -> Path:
    if set(binding) != {"path", "git_blob_sha"}:
        raise ValueError(f"historical media release {label} binding has unexpected fields")
    relative = binding.get("path")
    expected_blob = binding.get("git_blob_sha")
    if not isinstance(relative, str) or not relative or not isinstance(expected_blob, str) or len(expected_blob) != 40:
        raise ValueError(f"historical media release {label} binding is invalid")
    path = _resolve(root, relative)
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"historical media release {label} is missing: {relative}") from exc
    if _git_blob(payload) != expected_blob:
        raise ValueError(f"historical media release {label} Git blob differs: {relative}")
    return path


def is_media_release_payload(value: dict[str, Any]) -> bool:
    return value.get("schema_name") == MEDIA_RELEASE_SCHEMA


@dataclass(frozen=True)
class HistoricalMediaQueue:
    posts: tuple[HistoricalPost, ...]
    digest: str
    checked_on: date


def _load_revision_sources(root: Path, package: HistoricalRevisionPackageV1) -> tuple[HistoricalSource, ...]:
    sources: list[HistoricalSource] = []
    for ref in package.source_shards:
        path = _resolve(root, ref.path)
        payload = path.read_bytes()
        if _git_blob(payload) != ref.git_blob_sha:
            raise ValueError(f"historical media source shard Git blob differs: {ref.path}")
        shard = HistoricalSourceShardV1.model_validate_json(payload)
        sources.extend(shard.sources)
    ids = [source.source_id for source in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("historical media source ids are not unique")
    return tuple(sources)


def _validate_media_record(root: Path, record: dict[str, Any], *, source_commit: str) -> None:
    required = {
        "asset_id",
        "path",
        "git_blob_sha",
        "raw_url",
        "mime",
        "byte_length",
        "sha256",
        "placement_after",
        "caption",
        "disclosure",
    }
    if set(record) != required:
        raise ValueError("historical media binding has unexpected fields")
    if record.get("mime") != "image/jpeg":
        raise ValueError("historical v3 transport accepts exact JPEG media only")
    path = _resolve(root, str(record["path"]))
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"historical media file is missing: {record['path']}") from exc
    if _git_blob(data) != record.get("git_blob_sha"):
        raise ValueError(f"historical media Git blob differs: {record['asset_id']}")
    if len(data) != record.get("byte_length") or _sha256_bytes(data) != record.get("sha256"):
        raise ValueError(f"historical media local byte identity differs: {record['asset_id']}")
    if not (data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9")):
        raise ValueError(f"historical media is not an exact JPEG payload: {record['asset_id']}")
    expected_url = (
        f"https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/{source_commit}/{record['path']}"
    )
    if record.get("raw_url") != expected_url:
        raise ValueError(f"historical media raw URL is not immutable/exact: {record['asset_id']}")
    parsed = urlparse(str(record["raw_url"]))
    if parsed.scheme != "https" or parsed.hostname != "raw.githubusercontent.com":
        raise ValueError("historical media transport URL must use raw.githubusercontent.com over HTTPS")


def load_media_release(
    path: Path,
    root: Path,
) -> tuple[dict[str, Any], HistoricalMediaQueue, tuple[HistoricalSource, ...], Path, dict[str, Any]]:
    release = _read_json(path if path.is_absolute() else root / path)
    if not is_media_release_payload(release):
        raise ValueError("not a historical live-media release")
    if (
        release.get("schema_version") != 1
        or release.get("owning_issue") != 561
        or release.get("project_key") != PROJECT
        or str(release.get("channel_username") or "").casefold() != CHANNEL.casefold()
        or release.get("chat_id") != CHAT_ID
        or str(release.get("chat_username") or "").casefold() != CHAT_USERNAME
        or release.get("bot_id") != BOT_ID
        or str(release.get("bot_username") or "").casefold() != BOT_USERNAME
        or release.get("state_branch") != "state/lordchrist-telegram"
        or release.get("provider_writes_authorized") is not True
        or release.get("activation_policy") != "verified_canary_then_exact_schedule"
        or release.get("editorial_approval_required") is not True
        or release.get("canary_out_of_band") is not True
        or release.get("max_provider_attempts_per_publication") != 1
        or release.get("blind_mutation_retries") != 0
        or release.get("backfill_policy") != "none"
        or release.get("media_policy") != MEDIA_POLICY
        or release.get("replenishment_guard_remaining") != 0
    ):
        raise ValueError("historical live-media release header/policy is invalid")

    publication_ids = release.get("publication_ids")
    if not isinstance(publication_ids, list) or len(publication_ids) != 1:
        raise ValueError("historical live-media canary release must contain exactly one publication")
    publication_id = publication_ids[0]
    if release.get("canary_publication_id") != publication_id:
        raise ValueError("historical live-media canary identity differs from publication_ids")
    if release.get("recurring_publication_ids") != [] or release.get("recurring_scheduled_dates_moscow") != []:
        raise ValueError("historical live-media v3 canary release must not arm recurring publication")

    source_commit = str(release.get("media_source_commit") or "")
    if len(source_commit) != 40 or any(ch not in "0123456789abcdef" for ch in source_commit):
        raise ValueError("historical media source commit must be an exact Git SHA")

    revision_binding = release.get("revision")
    if not isinstance(revision_binding, dict):
        raise ValueError("historical live-media release has no revision binding")
    revision_path = _require_bound_file(root, revision_binding, label="revision")
    report = preflight_historical_revision(revision_path, repo_root=root)
    package = load_historical_revision_package(revision_path, repo_root=root)
    if report.publication_id != publication_id or package.publication_id != publication_id:
        raise ValueError("historical live-media release publication differs from revision package")

    post_payload = _resolve(root, package.post.path).read_bytes()
    if _git_blob(post_payload) != package.post.git_blob_sha:
        raise ValueError("historical live-media post Git blob differs from revision binding")
    post = HistoricalPost.model_validate_json(post_payload)
    sources = _load_revision_sources(root, package)

    media = release.get("media")
    if not isinstance(media, list) or len(media) != 2:
        raise ValueError("historical Spurgeon v3 release requires exactly two media records")
    if [entry.get("asset_id") for entry in media] != [item.asset_id for item in package.editorial_media]:
        raise ValueError("historical live-media asset order differs from revision package")
    revision_by_id = {item.asset_id: item for item in package.editorial_media}
    for record in media:
        if not isinstance(record, dict):
            raise ValueError("historical media binding must be an object")
        _validate_media_record(root, record, source_commit=source_commit)
        accepted = revision_by_id[str(record["asset_id"])]
        if (
            record["mime"] != accepted.accepted_mime
            or record["byte_length"] != accepted.accepted_byte_length
            or record["sha256"] != accepted.accepted_sha256
            or record["placement_after"] != accepted.placement_after
            or record["disclosure"] != accepted.disclosure
        ):
            raise ValueError(f"historical live-media binding differs from accepted revision: {record['asset_id']}")

    profile_binding = release.get("profile")
    legacy_binding = release.get("legacy_profile")
    target_binding = release.get("target_binding")
    if not isinstance(profile_binding, dict):
        raise ValueError("historical live-media release lacks profile binding")
    if not isinstance(legacy_binding, dict):
        raise ValueError("historical live-media release lacks legacy profile binding")
    if not isinstance(target_binding, dict):
        raise ValueError("historical live-media release lacks target binding")
    profile_path = _require_bound_file(root, profile_binding, label="profile")
    legacy_profile_path = _require_bound_file(root, legacy_binding, label="legacy profile")
    target_binding_path = _require_bound_file(root, target_binding, label="target binding")

    queue = HistoricalMediaQueue(posts=(post,), digest=package.digest, checked_on=package.checked_on)
    canary_not_before = str(release.get("canary_not_before_moscow") or "")
    planned_date = canary_not_before.split("T", 1)[0]
    date.fromisoformat(planned_date)
    aux: dict[str, Any] = {
        "planned_dates": (planned_date,),
        "target_binding_path": target_binding_path,
        "legacy_profile_path": legacy_profile_path,
        "revision_package": package,
        "revision_preflight": report,
    }
    return release, queue, sources, profile_path, aux


def _target(profile_path: Path, target_binding_path: Path) -> TelegramRichTargetBinding:
    profile = load_channel_profile(profile_path)
    binding = load_target_binding(target_binding_path, profile)
    if (
        profile.project_key != PROJECT
        or profile.channel_username.casefold() != CHANNEL.casefold()
        or profile.provider_writes_authorized is not True
        or binding.chat_id != CHAT_ID
        or binding.chat_username.casefold() != CHAT_USERNAME
        or binding.bot_id != BOT_ID
        or binding.bot_username.casefold() != BOT_USERNAME
        or binding.can_post_messages is not True
    ):
        raise ValueError("historical live-media profile/target differs from exact LordChrist target")
    return TelegramRichTargetBinding(
        schema_name="video-channel-manager.telegram-rich-target-binding",
        schema_version=1,
        project_key=PROJECT,
        channel_username=CHANNEL,
        profile_sha256=profile.digest,
        target_binding_sha256=binding.digest,
        source_binding=binding,
        chat_id=binding.chat_id,
        chat_username=binding.chat_username,
        bot_id=binding.bot_id,
        bot_username=binding.bot_username,
    )


def build_media_document(
    root: Path,
    release: dict[str, Any],
    queue: HistoricalMediaQueue,
    sources: tuple[HistoricalSource, ...],
    profile_path: Path,
    target_binding_path: Path,
    publication_id: str,
) -> tuple[TelegramRichMessageDocument, RichRenderResult]:
    if publication_id != release.get("canary_publication_id") or len(queue.posts) != 1:
        raise ValueError("historical live-media document is restricted to the exact canary")
    post = queue.posts[0]
    if post.publication_id != publication_id:
        raise ValueError("historical live-media queue publication differs from requested canary")

    source_by_id = {source.source_id: source for source in sources}
    source_ids = tuple(dict.fromkeys(source_id for claim in post.claims for source_id in claim.source_ids))
    article_sources = tuple(
        RichArticleSource(
            source_id=source_id,
            label=source_by_id[source_id].title,
            url=source_by_id[source_id].url,
            verified_on=source_by_id[source_id].checked_on,
            evidence=f"{source_by_id[source_id].grade} · {source_by_id[source_id].evidence_role}",
        )
        for source_id in source_ids
    )
    media_records = {str(item["asset_id"]): item for item in release["media"]}
    media_items = tuple(
        RichMediaItem(
            media_id=str(item["asset_id"]),
            kind="photo",
            uri=str(item["raw_url"]),
            alt_text=str(item["caption"]),
        )
        for item in release["media"]
    )

    blocks: list[Any] = [
        RichBlockHeading(block_id="h-title", text=post.title, size=1),
        RichBlockParagraph(block_id="p-lead", text=post.lead),
    ]

    def append_media(asset_id: str) -> None:
        item = media_records[asset_id]
        blocks.append(
            RichBlockMedia(
                block_id=f"m-{asset_id.removeprefix('img-')}",
                media_id=asset_id,
                caption=RichBlockCaption(text=str(item["caption"]), credit=str(item["disclosure"])),
            )
        )

    for item in release["media"]:
        if item["placement_after"] == "lead":
            append_media(str(item["asset_id"]))

    for section in post.sections:
        blocks.append(RichBlockHeading(block_id=f"h-{section.section_id}", text=section.heading, size=2))
        for index, paragraph in enumerate(section.paragraphs, start=1):
            blocks.append(RichBlockParagraph(block_id=f"p-{section.section_id}-{index}", text=paragraph))
        for item in release["media"]:
            if item["placement_after"] == section.section_id:
                append_media(str(item["asset_id"]))

    detail_blocks = tuple(
        RichBlockParagraph(
            block_id=f"p-source-{index}",
            text=(
                RichTextUrl(text=source_by_id[source_id].publisher, url=source_by_id[source_id].url),
                f" — {source_by_id[source_id].title} [{source_by_id[source_id].grade}]",
            ),
        )
        for index, source_id in enumerate(source_ids, start=1)
    )
    blocks.append(RichBlockDetails(block_id="d-sources", summary="Источники", blocks=detail_blocks, is_open=False))

    article = RichArticleDocument(
        schema_name=RICH_ARTICLE_SCHEMA_NAME,
        schema_version=RICH_ARTICLE_SCHEMA_VERSION,
        document_id=post.publication_id,
        project_key=PROJECT,
        metadata=RichArticleMetadata(
            title=post.title,
            language="ru",
            summary=post.lead,
            author="Редакция «Господь Бог — Сила Моя»",
            tags=("история церкви", post.topic_kind),
            created_at=queue.checked_on,
        ),
        blocks=tuple(blocks),
        media=media_items,
        sources=article_sources,
        media_slots=(),
        revision="historical-v3-media",
    )
    media_ids = tuple(str(item["asset_id"]) for item in release["media"])
    document, render = render_rich_document(
        article,
        _target(profile_path, target_binding_path),
        publication_id=publication_id,
        provider_assigned_media_ids=media_ids,
        skip_entity_detection=False,
    )
    if document.expected_media_sha256 is None or document.provider_assigned_media_paths == ():
        raise ValueError("historical live-media document did not bind provider-assigned media evidence")
    if render.media_placeholders:
        raise ValueError("historical live-media document unexpectedly uses media placeholders")
    if render.provider_assigned_media != media_ids:
        raise ValueError("historical live-media render lost exact media identities")
    return document, render


def _verify_remote_payload(
    record: dict[str, Any], *, content: bytes, content_type: str, content_length: str | None
) -> None:
    actual_mime = content_type.split(";", 1)[0].strip().casefold()
    if actual_mime != str(record["mime"]):
        raise ValueError(f"historical remote media MIME differs: {record['asset_id']}")
    if content_length is not None:
        try:
            announced = int(content_length)
        except ValueError as exc:
            raise ValueError(f"historical remote media Content-Length is invalid: {record['asset_id']}") from exc
        if announced != record["byte_length"]:
            raise ValueError(f"historical remote media Content-Length differs: {record['asset_id']}")
    if len(content) != record["byte_length"]:
        raise ValueError(f"historical remote media byte length differs: {record['asset_id']}")
    if _sha256_bytes(content) != record["sha256"]:
        raise ValueError(f"historical remote media SHA-256 differs: {record['asset_id']}")
    if not (content.startswith(b"\xff\xd8\xff") and content.endswith(b"\xff\xd9")):
        raise ValueError(f"historical remote media JPEG signature differs: {record['asset_id']}")


def verify_transport_media_bytes(
    root: Path,
    release: dict[str, Any],
    *,
    client: httpx.Client | None = None,
) -> tuple[dict[str, Any], ...]:
    if not is_media_release_payload(release):
        raise ValueError("exact media verification requires a historical live-media release")
    source_commit = str(release["media_source_commit"])
    proofs: list[dict[str, Any]] = []
    for record in release["media"]:
        _validate_media_record(root, record, source_commit=source_commit)
        if client is None:
            response = httpx.get(
                str(record["raw_url"]),
                headers={"Accept": str(record["mime"])},
                timeout=20.0,
                follow_redirects=False,
            )
        else:
            response = client.get(str(record["raw_url"]), headers={"Accept": str(record["mime"])})
        if response.status_code != 200:
            raise ValueError(
                f"historical remote media HTTP status differs: {record['asset_id']}={response.status_code}"
            )
        _verify_remote_payload(
            record,
            content=response.content,
            content_type=response.headers.get("content-type", ""),
            content_length=response.headers.get("content-length"),
        )
        local = _resolve(root, str(record["path"])).read_bytes()
        if response.content != local:
            raise ValueError(f"historical remote media bytes differ from bound Git bytes: {record['asset_id']}")
        proofs.append(
            {
                "asset_id": record["asset_id"],
                "raw_url": record["raw_url"],
                "mime": record["mime"],
                "byte_length": record["byte_length"],
                "sha256": record["sha256"],
                "provider_write_performed": False,
            }
        )
    return tuple(proofs)


__all__ = [
    "HistoricalMediaQueue",
    "MEDIA_POLICY",
    "MEDIA_RELEASE_SCHEMA",
    "build_media_document",
    "is_media_release_payload",
    "load_media_release",
    "verify_transport_media_bytes",
]
