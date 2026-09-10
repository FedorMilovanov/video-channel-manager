from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_historical_archival_revision import (
    HistoricalRevisionPackageV2,
    load_historical_archival_revision_package,
    preflight_historical_archival_revision,
)
from video_channel_manager.telegram_historical_bundle import HistoricalSourceShardV1
from video_channel_manager.telegram_historical_editorial import HistoricalPost, HistoricalSource
from video_channel_manager.telegram_rich_models import (
    RICH_ARTICLE_SCHEMA_NAME,
    RICH_ARTICLE_SCHEMA_VERSION,
    RichArticleDocument,
    RichArticleMetadata,
    RichArticleSource,
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

ARCHIVAL_RELEASE_SCHEMA = "video-channel-manager.telegram-historical-archival-live-release"
ARCHIVAL_MEDIA_POLICY = "exact_git_bound_archival_photos_reproved_before_sendRichMessage"
ARCHIVAL_SCHEDULE_RELEASE_RELATIVE_PATH = (
    "content/telegram/lordchrist/historical-editorial/v1/production-release-2026-09-cycle-02-v3-archival.json"
)
LEGACY_RELEASE_SCHEMA = "video-channel-manager.telegram-historical-production-release"
LEGACY_SCHEDULE_RELEASE_ID = "lordchrist-history-cycle-2026-09-14-human-v2-live-v1"
PROJECT = "lord-god-strength"
CHANNEL = "@lordchrist"
CHAT_ID = -1001295216957
CHAT_USERNAME = "lordchrist"
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"
STATE_BRANCH = "state/lordchrist-telegram"
EXPECTED_PUBLICATION_IDS = (
    "lordchrist-history-bunyan-bedford-prison-v3",
    "lordchrist-history-judson-burmese-bible-v3",
    "lordchrist-history-spurgeon-cholera-1854-v3",
    "lordchrist-history-carey-enquiry-missions-v3",
    "lordchrist-history-fuller-gospel-worthy-v3",
    "lordchrist-history-tyndale-new-testament-1526-v3",
    "lordchrist-history-stam-china-december-1934-v3",
    "lordchrist-history-sattler-schleitheim-1527-v3",
)
EXPECTED_DATES = (
    "2026-09-14",
    "2026-09-16",
    "2026-09-19",
    "2026-09-21",
    "2026-09-23",
    "2026-09-26",
    "2026-09-28",
    "2026-09-30",
)
EXTERNAL_CANARY_ID = "lordchrist-history-spurgeon-down-grade-1887-v3"
EXTERNAL_CANARY_RELEASE_ID = "lordchrist-history-spurgeon-down-grade-1887-v3-media-live-v1"
EXTERNAL_CANARY_MESSAGE_ID = 1516


def _git_blob(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()  # noqa: S324


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _digest(values: list[str]) -> str:
    encoded = json.dumps(values, ensure_ascii=False, separators=(",", ":"), sort_keys=False).encode("utf-8")
    return _sha256(encoded)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid archival historical release JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("archival historical release must be a JSON object")
    return value


def _resolve(root: Path, relative: str) -> Path:
    if Path(relative).is_absolute():
        raise ValueError("archival historical release paths must be repository-relative")
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ValueError("archival historical release path escapes repository root")
    return candidate


def _bound_path(root: Path, binding: dict[str, Any], *, label: str) -> Path:
    if set(binding) != {"path", "git_blob_sha"}:
        raise ValueError(f"archival historical {label} binding has unexpected fields")
    relative = binding.get("path")
    expected = binding.get("git_blob_sha")
    if not isinstance(relative, str) or not relative or not isinstance(expected, str) or len(expected) != 40:
        raise ValueError(f"archival historical {label} binding is invalid")
    path = _resolve(root, relative)
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"archival historical {label} is missing: {relative}") from exc
    if _git_blob(payload) != expected:
        raise ValueError(f"archival historical {label} Git blob differs: {relative}")
    return path


def _is_scheduled_legacy_bridge(value: dict[str, Any]) -> bool:
    return (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_EVENT_NAME") == "schedule"
        and value.get("schema_name") == LEGACY_RELEASE_SCHEMA
        and value.get("release_id") == LEGACY_SCHEDULE_RELEASE_ID
        and value.get("owning_issue") == 561
        and value.get("project_key") == PROJECT
        and str(value.get("channel_username") or "").casefold() == CHANNEL.casefold()
    )


def is_archival_release_payload(value: dict[str, Any]) -> bool:
    return value.get("schema_name") == ARCHIVAL_RELEASE_SCHEMA or _is_scheduled_legacy_bridge(value)


@dataclass(frozen=True)
class HistoricalArchivalQueue:
    posts: tuple[HistoricalPost, ...]
    digest: str
    checked_on: date


@dataclass(frozen=True)
class HistoricalArchivalRegistry:
    packages: dict[str, HistoricalRevisionPackageV2]
    sources: dict[str, tuple[HistoricalSource, ...]]
    media: dict[str, tuple[dict[str, Any], ...]]


def _load_sources(root: Path, package: HistoricalRevisionPackageV2) -> tuple[HistoricalSource, ...]:
    sources: list[HistoricalSource] = []
    for ref in package.source_shards:
        path = _resolve(root, ref.path)
        data = path.read_bytes()
        if _git_blob(data) != ref.git_blob_sha:
            raise ValueError(f"archival historical source shard Git blob differs: {ref.path}")
        shard = HistoricalSourceShardV1.model_validate_json(data)
        sources.extend(shard.sources)
    ids = [source.source_id for source in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("archival historical source ids are not unique within a publication")
    return tuple(sources)


def _media_record(package: HistoricalRevisionPackageV2, media: Any, *, source_commit: str) -> dict[str, Any]:
    path = media.accepted_file.path
    return {
        "asset_id": media.asset_id,
        "path": path,
        "git_blob_sha": media.accepted_file.git_blob_sha,
        "raw_url": f"https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/{source_commit}/{path}",
        "mime": media.accepted_mime,
        "byte_length": media.accepted_byte_length,
        "sha256": media.accepted_sha256,
        "placement_after": media.placement_after,
        "caption": media.depicts,
        "disclosure": f"{media.attribution_text} {media.claim_boundary}",
        "publication_id": package.publication_id,
    }


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
        "publication_id",
    }
    if set(record) != required:
        raise ValueError("archival historical media record has unexpected fields")
    if record.get("mime") not in {"image/jpeg", "image/png"}:
        raise ValueError("archival historical transport accepts JPEG/PNG only")
    path = _resolve(root, str(record["path"]))
    data = path.read_bytes()
    if _git_blob(data) != record.get("git_blob_sha"):
        raise ValueError(f"archival historical media Git blob differs: {record['asset_id']}")
    if len(data) != record.get("byte_length") or _sha256(data) != record.get("sha256"):
        raise ValueError(f"archival historical media byte identity differs: {record['asset_id']}")
    if record["mime"] == "image/jpeg" and not (data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9")):
        raise ValueError(f"archival historical JPEG signature differs: {record['asset_id']}")
    if record["mime"] == "image/png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"archival historical PNG signature differs: {record['asset_id']}")
    expected_url = (
        f"https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/{source_commit}/{record['path']}"
    )
    if record.get("raw_url") != expected_url:
        raise ValueError(f"archival historical raw URL differs: {record['asset_id']}")
    parsed = urlparse(str(record["raw_url"]))
    if parsed.scheme != "https" or parsed.hostname != "raw.githubusercontent.com":
        raise ValueError("archival historical transport URL must use raw.githubusercontent.com over HTTPS")


def load_archival_release(
    path: Path,
    root: Path,
) -> tuple[dict[str, Any], HistoricalArchivalQueue, HistoricalArchivalRegistry, Path, dict[str, Any]]:
    resolved_release = path if path.is_absolute() else root / path
    release = _read_json(resolved_release)
    if _is_scheduled_legacy_bridge(release):
        resolved_release = _resolve(root, ARCHIVAL_SCHEDULE_RELEASE_RELATIVE_PATH)
        release = _read_json(resolved_release)
    if release.get("schema_name") != ARCHIVAL_RELEASE_SCHEMA:
        raise ValueError("not an archival historical live release")
    if (
        release.get("schema_version") != 1
        or release.get("owning_issue") != 561
        or release.get("project_key") != PROJECT
        or str(release.get("channel_username") or "").casefold() != CHANNEL.casefold()
        or release.get("chat_id") != CHAT_ID
        or str(release.get("chat_username") or "").casefold() != CHAT_USERNAME
        or release.get("bot_id") != BOT_ID
        or str(release.get("bot_username") or "").casefold() != BOT_USERNAME
        or release.get("state_branch") != STATE_BRANCH
        or release.get("provider_writes_authorized") is not True
        or release.get("activation_policy") != "external_verified_approved_canary_then_exact_schedule"
        or release.get("editorial_approval_required") is not False
        or release.get("external_editorial_approval_required") is not True
        or release.get("canary_out_of_band") is not True
        or release.get("canary_publication_id") != EXTERNAL_CANARY_ID
        or release.get("max_provider_attempts_per_publication") != 1
        or release.get("blind_mutation_retries") != 0
        or release.get("backfill_policy") != "none"
        or release.get("media_policy") != ARCHIVAL_MEDIA_POLICY
        or release.get("replenishment_guard_remaining") != 1
    ):
        raise ValueError("archival historical release header/policy is invalid")
    publication_ids = tuple(release.get("publication_ids") or ())
    recurring_ids = tuple(release.get("recurring_publication_ids") or ())
    planned_dates = tuple(release.get("scheduled_dates_moscow") or ())
    recurring_dates = tuple(release.get("recurring_scheduled_dates_moscow") or ())
    if publication_ids != EXPECTED_PUBLICATION_IDS or recurring_ids != EXPECTED_PUBLICATION_IDS:
        raise ValueError("archival historical release must contain exactly the eight remaining v3 publications")
    if planned_dates != EXPECTED_DATES or recurring_dates != EXPECTED_DATES:
        raise ValueError("archival historical release dates differ from the reviewed Mon/Wed/Sat cadence")
    schedule = release.get("schedule")
    if not isinstance(schedule, dict) or (
        schedule.get("timezone") != "Europe/Moscow"
        or schedule.get("local_time") != "19:17"
        or tuple(schedule.get("iso_weekdays") or ()) != (1, 3, 6)
        or schedule.get("freshness_minutes") != 120
    ):
        raise ValueError("archival historical release schedule is invalid")
    source_commit = str(release.get("media_source_commit") or "")
    if len(source_commit) != 40 or any(ch not in "0123456789abcdef" for ch in source_commit):
        raise ValueError("archival historical media source commit must be exact")

    canary = release.get("external_canary_binding")
    if not isinstance(canary, dict) or set(canary) != {
        "ledger_path",
        "release_id",
        "publication_id",
        "message_id",
        "required_state",
        "required_provider_effect",
    }:
        raise ValueError("archival historical external canary binding is invalid")
    if (
        canary.get("ledger_path")
        != "content/telegram/lordchrist/historical-editorial/publication-ledger-spurgeon-v3-media.json"
        or canary.get("release_id") != EXTERNAL_CANARY_RELEASE_ID
        or canary.get("publication_id") != EXTERNAL_CANARY_ID
        or canary.get("message_id") != EXTERNAL_CANARY_MESSAGE_ID
        or canary.get("required_state") != "published"
        or canary.get("required_provider_effect") != "verified"
    ):
        raise ValueError("archival historical external canary identity differs from message 1516")

    package_bindings = release.get("revision_packages")
    if not isinstance(package_bindings, list) or len(package_bindings) != len(EXPECTED_PUBLICATION_IDS):
        raise ValueError("archival historical release requires exactly eight revision-package bindings")
    posts: list[HistoricalPost] = []
    packages: dict[str, HistoricalRevisionPackageV2] = {}
    sources_by_publication: dict[str, tuple[HistoricalSource, ...]] = {}
    media_by_publication: dict[str, tuple[dict[str, Any], ...]] = {}
    package_digests: list[str] = []
    checked_on: date | None = None
    for sequence, (expected_id, raw_binding) in enumerate(
        zip(EXPECTED_PUBLICATION_IDS, package_bindings, strict=True), start=1
    ):
        if not isinstance(raw_binding, dict) or set(raw_binding) != {"publication_id", "path", "git_blob_sha"}:
            raise ValueError("archival historical revision-package binding is invalid")
        if raw_binding.get("publication_id") != expected_id:
            raise ValueError("archival historical revision-package order differs from publication_ids")
        package_path = _bound_path(
            root,
            {"path": raw_binding["path"], "git_blob_sha": raw_binding["git_blob_sha"]},
            label=f"revision package {expected_id}",
        )
        preflight = preflight_historical_archival_revision(package_path, repo_root=root)
        package = load_historical_archival_revision_package(package_path, repo_root=root)
        if (
            preflight.status != "PASS"
            or preflight.publication_id != expected_id
            or package.publication_id != expected_id
        ):
            raise ValueError("archival historical revision package failed exact preflight binding")
        if len(package.archival_media) != 2:
            raise ValueError("each archival historical publication requires exactly two accepted exhibits")
        post_path = _resolve(root, package.post.path)
        post_payload = post_path.read_bytes()
        if _git_blob(post_payload) != package.post.git_blob_sha:
            raise ValueError("archival historical post Git blob differs from revision package")
        post = HistoricalPost.model_validate_json(post_payload).model_copy(update={"sequence": sequence})
        records = tuple(_media_record(package, media, source_commit=source_commit) for media in package.archival_media)
        for record in records:
            _validate_media_record(root, record, source_commit=source_commit)
        posts.append(post)
        packages[expected_id] = package
        sources_by_publication[expected_id] = _load_sources(root, package)
        media_by_publication[expected_id] = records
        package_digests.append(package.digest)
        checked_on = package.checked_on if checked_on is None else max(checked_on, package.checked_on)

    profile = release.get("profile")
    legacy_profile = release.get("legacy_profile")
    target_binding = release.get("target_binding")
    if not isinstance(profile, dict) or not isinstance(legacy_profile, dict) or not isinstance(target_binding, dict):
        raise ValueError("archival historical release lacks exact profile/target bindings")
    profile_path = _bound_path(root, profile, label="profile")
    legacy_profile_path = _bound_path(root, legacy_profile, label="legacy profile")
    target_binding_path = _bound_path(root, target_binding, label="target binding")
    if checked_on is None:
        raise ValueError("archival historical release has no checked_on evidence")
    queue = HistoricalArchivalQueue(posts=tuple(posts), digest=_digest(package_digests), checked_on=checked_on)
    registry = HistoricalArchivalRegistry(
        packages=packages,
        sources=sources_by_publication,
        media=media_by_publication,
    )
    return (
        release,
        queue,
        registry,
        profile_path,
        {
            "planned_dates": EXPECTED_DATES,
            "recurring_publication_ids": EXPECTED_PUBLICATION_IDS,
            "recurring_scheduled_dates_moscow": EXPECTED_DATES,
            "target_binding_path": target_binding_path,
            "legacy_profile_path": legacy_profile_path,
            "external_canary_ledger_relative_path": canary["ledger_path"],
        },
    )


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
        raise ValueError("archival historical profile/target differs from exact LordChrist target")
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


def build_archival_document(
    root: Path,
    release: dict[str, Any],
    queue: HistoricalArchivalQueue,
    registry: HistoricalArchivalRegistry,
    profile_path: Path,
    target_binding_path: Path,
    publication_id: str,
) -> tuple[TelegramRichMessageDocument, RichRenderResult]:
    if publication_id not in EXPECTED_PUBLICATION_IDS:
        raise ValueError("archival historical publication is outside the exact recurring release")
    post = next((item for item in queue.posts if item.publication_id == publication_id), None)
    if post is None:
        raise ValueError("archival historical queue does not contain requested publication")
    sources = registry.sources[publication_id]
    records = registry.media[publication_id]
    source_by_id = {source.source_id: source for source in sources}
    source_ids = tuple(dict.fromkeys(source_id for claim in post.claims for source_id in claim.source_ids))
    missing = tuple(source_id for source_id in source_ids if source_id not in source_by_id)
    if missing:
        raise ValueError(f"archival historical post references missing sources: {missing}")
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
    media_items = tuple(
        RichMediaItem(
            media_id=str(record["asset_id"]),
            kind="photo",
            uri=str(record["raw_url"]),
            alt_text=f"Архивная иллюстрация к публикации «{post.title}»",
        )
        for record in records
    )
    records_by_placement: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        records_by_placement.setdefault(str(record["placement_after"]), []).append(record)
    blocks: list[Any] = [RichBlockHeading(block_id="h-title", text=post.title, size=1)]
    placed: list[str] = []

    def append_placement(placement: str) -> None:
        for record in records_by_placement.get(placement, []):
            asset_id = str(record["asset_id"])
            blocks.append(
                RichBlockMedia(
                    block_id=f"m-{asset_id.removeprefix('img-')}",
                    media_id=asset_id,
                )
            )
            placed.append(asset_id)

    append_placement("title")
    blocks.append(RichBlockParagraph(block_id="p-lead", text=post.lead))
    append_placement("lead")
    for section in post.sections:
        blocks.append(RichBlockHeading(block_id=f"h-{section.section_id}", text=section.heading, size=2))
        for index, paragraph in enumerate(section.paragraphs, start=1):
            blocks.append(RichBlockParagraph(block_id=f"p-{section.section_id}-{index}", text=paragraph))
        append_placement(section.section_id)
    append_placement("evidence")
    blocks.append(RichBlockParagraph(block_id="p-pastoral-application", text=post.theology_review.editorial_evaluation))
    append_placement("theology")
    expected_media_ids = tuple(str(record["asset_id"]) for record in records)
    if tuple(placed) != expected_media_ids:
        raise ValueError("archival historical media placement did not consume exactly the bound exhibits in order")
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
        revision="historical-v3-archival",
    )
    document, render = render_rich_document(
        article,
        _target(profile_path, target_binding_path),
        publication_id=publication_id,
        provider_assigned_media_ids=expected_media_ids,
        skip_entity_detection=False,
    )
    if document.expected_media_sha256 is None or not document.provider_assigned_media_paths:
        raise ValueError("archival historical document did not bind provider-assigned media evidence")
    if render.media_placeholders or render.provider_assigned_media != expected_media_ids:
        raise ValueError("archival historical render lost exact media identities")
    return document, render


def _verify_remote_record(record: dict[str, Any], response: httpx.Response, local: bytes) -> None:
    if response.status_code != 200:
        raise ValueError(
            f"archival historical remote media HTTP status differs: {record['asset_id']}={response.status_code}"
        )
    actual_mime = response.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
    if actual_mime != str(record["mime"]):
        raise ValueError(f"archival historical remote media MIME differs: {record['asset_id']}")
    content = response.content
    if len(content) != record["byte_length"] or _sha256(content) != record["sha256"]:
        raise ValueError(f"archival historical remote media byte identity differs: {record['asset_id']}")
    announced = response.headers.get("content-length")
    if announced is not None and int(announced) != record["byte_length"]:
        raise ValueError(f"archival historical remote media Content-Length differs: {record['asset_id']}")
    if content != local:
        raise ValueError(f"archival historical remote media differs from exact committed bytes: {record['asset_id']}")


def verify_transport_media_bytes(
    root: Path,
    release: dict[str, Any],
    registry: HistoricalArchivalRegistry,
    publication_id: str,
    *,
    client: httpx.Client | None = None,
) -> tuple[dict[str, Any], ...]:
    if release.get("schema_name") != ARCHIVAL_RELEASE_SCHEMA or publication_id not in EXPECTED_PUBLICATION_IDS:
        raise ValueError("archival historical media verification requires an exact recurring publication")
    source_commit = str(release["media_source_commit"])
    proofs: list[dict[str, Any]] = []
    for record in registry.media[publication_id]:
        _validate_media_record(root, record, source_commit=source_commit)
        url = str(record["raw_url"])
        if client is None:
            response = httpx.get(url, headers={"Accept": str(record["mime"])}, timeout=20.0, follow_redirects=False)
        else:
            response = client.get(url, headers={"Accept": str(record["mime"])})
        local = _resolve(root, str(record["path"])).read_bytes()
        _verify_remote_record(record, response, local)
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


def _aware_timestamp(value: Any, *, label: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"archival historical {label} timestamp must be timezone-aware")
    return parsed


def sync_external_canary(
    ledger: dict[str, Any],
    release: dict[str, Any],
    witness: dict[str, Any] | None,
) -> tuple[dict[str, Any], bool]:
    if release.get("schema_name") != ARCHIVAL_RELEASE_SCHEMA:
        raise ValueError("external canary sync requires an archival historical release")
    if witness is None:
        if ledger.get("canary_verified_at_utc") is not None:
            raise ValueError("archival recurring ledger is armed but external canary ledger is missing")
        return ledger, False
    binding = release["external_canary_binding"]
    entries = witness.get("entries")
    raw = entries.get(binding["publication_id"]) if isinstance(entries, dict) else None
    if (
        witness.get("release_id") != binding["release_id"]
        or witness.get("channel_username") != CHANNEL
        or not isinstance(raw, dict)
        or raw.get("publication_id") != binding["publication_id"]
        or raw.get("state") != binding["required_state"]
        or raw.get("provider_effect") != binding["required_provider_effect"]
        or raw.get("message_id") != binding["message_id"]
    ):
        raise ValueError("archival historical external canary differs from durable message 1516 evidence")
    transport_at = witness.get("canary_transport_verified_at_utc")
    if not transport_at:
        raise ValueError("archival historical external canary lacks transport verification")
    transport_time = _aware_timestamp(transport_at, label="external canary transport")
    approved_at = witness.get("canary_editorial_approved_at_utc")
    approved_by = witness.get("canary_editorial_approved_by")
    witness_activation = witness.get("canary_verified_at_utc")
    local_activation = ledger.get("canary_verified_at_utc")
    if approved_at is None:
        if approved_by is not None or witness_activation is not None or local_activation is not None:
            raise ValueError(
                "archival historical recurring schedule cannot be armed before external editorial approval"
            )
        return ledger, False
    approved_time = _aware_timestamp(approved_at, label="external canary editorial approval")
    if approved_time < transport_time:
        raise ValueError("archival historical external editorial approval predates transport verification")
    if not isinstance(approved_by, str) or not approved_by.strip() or witness_activation != approved_at:
        raise ValueError("archival historical external editorial approval is not durably activation-bound")
    if local_activation not in {None, approved_at}:
        raise ValueError("archival historical recurring ledger is armed by a different canary approval")
    ledger["canary_verified_at_utc"] = approved_at
    return ledger, True


__all__ = [
    "ARCHIVAL_MEDIA_POLICY",
    "ARCHIVAL_RELEASE_SCHEMA",
    "ARCHIVAL_SCHEDULE_RELEASE_RELATIVE_PATH",
    "EXPECTED_DATES",
    "EXPECTED_PUBLICATION_IDS",
    "HistoricalArchivalQueue",
    "HistoricalArchivalRegistry",
    "build_archival_document",
    "is_archival_release_payload",
    "load_archival_release",
    "sync_external_canary",
    "verify_transport_media_bytes",
]
