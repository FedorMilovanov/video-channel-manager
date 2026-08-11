from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Sequence, cast

import httpx

from video_channel_manager.platforms.http import HttpClientOwner, HttpOperationClass, RetryPolicy, execute_http_request
from video_channel_manager.svodka_rich_loader import load_svodka_rich_article
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_custom_emoji_catalog import load_custom_emoji_catalog
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof
from video_channel_manager.telegram_rich_models import (
    RichArticleDocument,
    RichBlockCaption,
    RichBlockHeading,
    RichBlockMedia,
    RichMediaItem,
    RichTextContent,
    RichTextCustomEmoji,
    RichTextNode,
)
from video_channel_manager.telegram_rich_provider import (
    HttpxTelegramRichMutationProvider,
    TelegramRichOutcomeArchiveReceipt,
    TelegramRichProviderOutcome,
    TelegramRichTargetBinding,
    publish_rich_once,
)
from video_channel_manager.telegram_rich_renderer import render_rich_document
from video_channel_manager.telegram_target_binding import load_target_binding

PROJECT = "svodka"
CHANNEL = "@deep_info_life"
CHAT_ID = -1003527567039
CHAT_USERNAME = "deep_info_life"
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"
REPOSITORY = "FedorMilovanov/video-channel-manager"
RELEASE_ID = "svodka-rich-v1-production-2026-08"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_json(value).encode()).hexdigest()


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
        release.get("schema_name") != "video-channel-manager.svodka-rich-production-release"
        or release.get("schema_version") != 1
        or release.get("release_id") != RELEASE_ID
        or release.get("project_key") != PROJECT
        or release.get("channel_username") != CHANNEL
        or release.get("chat_id") != CHAT_ID
        or release.get("bot_id") != BOT_ID
        or release.get("bot_username") != BOT_USERNAME
        or release.get("approved") is not True
        or release.get("publication_window_minutes") != 120
        or release.get("max_verified_per_day_moscow") != 2
    ):
        raise ValueError("invalid Svodka rich production release header")
    items = release.get("items")
    if not isinstance(items, list) or len(items) != 14:
        raise ValueError("rich production release must contain exactly 14 items")
    if [item.get("sequence") for item in items] != list(range(1, 15)):
        raise ValueError("rich production sequence must be exactly 1..14")
    ids = [str(item.get("publication_id")) for item in items]
    if len(set(ids)) != 14 or release.get("first_canary_publication_id") != ids[0]:
        raise ValueError("rich production ids/canary binding are invalid")
    schedules = [datetime.fromisoformat(str(item["scheduled_at"])) for item in items]
    if schedules != sorted(schedules) or any(dt.utcoffset() != timedelta(hours=3) for dt in schedules):
        raise ValueError("rich production schedule is invalid")
    per_day: dict[str, int] = {}
    for dt in schedules:
        key = dt.date().isoformat()
        per_day[key] = per_day.get(key, 0) + 1
    if any(count > 2 for count in per_day.values()):
        raise ValueError("rich production exceeds two verified posts/day")
    for key in ("profile", "target_binding", "media_registry", "custom_emoji_catalog"):
        _verify(root, cast(dict[str, Any], release[key]))
    for item in items:
        if item.get("publication_id") != item.get("article_id"):
            raise ValueError("publication/article id mismatch")
        _verify(root, cast(dict[str, Any], item["article"]))
    return release


def release_digest(release: dict[str, Any]) -> str:
    return _sha(release)


def _target(root: Path, release: dict[str, Any]) -> TelegramRichTargetBinding:
    profile = load_channel_profile(_verify(root, cast(dict[str, Any], release["profile"])))
    binding = load_target_binding(_verify(root, cast(dict[str, Any], release["target_binding"])), profile)
    if not profile.provider_writes_authorized:
        raise ValueError("Svodka provider write gate is disabled")
    if (binding.chat_id, binding.bot_id, binding.bot_username.casefold()) != (CHAT_ID, BOT_ID, BOT_USERNAME.casefold()):
        raise ValueError("Svodka target binding mismatch")
    return TelegramRichTargetBinding(
        schema_name="video-channel-manager.telegram-rich-target-binding",
        schema_version=1,
        project_key=PROJECT,
        channel_username=CHANNEL,
        profile_sha256=profile.digest,
        target_binding_sha256=binding.digest,
        source_binding=binding,
        chat_id=CHAT_ID,
        chat_username=CHAT_USERNAME,
        bot_id=BOT_ID,
        bot_username=BOT_USERNAME,
    )


def _prepend(text: RichTextContent, *prefix: RichTextNode) -> RichTextContent:
    rest = text if isinstance(text, tuple) else (text,)
    return cast(RichTextContent, tuple(prefix) + rest)


def _decorate(article: RichArticleDocument, catalog_path: Path, role: str) -> RichArticleDocument:
    catalog = load_custom_emoji_catalog(catalog_path)
    themed = catalog.item_for_role(role)
    icon = RichTextCustomEmoji(custom_emoji_id=themed.custom_emoji_id, alternative_text=themed.fallback_emoji)
    section = 0
    blocks: list[Any] = []
    for block in article.blocks:
        if isinstance(block, RichBlockHeading) and block.size == 1:
            blocks.append(block.model_copy(update={"text": _prepend(block.text, icon, " ")}))
        elif isinstance(block, RichBlockHeading) and block.size == 2:
            section += 1
            if section > 9:
                raise ValueError("more than nine numbered sections")
            item = catalog.item_for_digit(section, style="primary")
            digit = RichTextCustomEmoji(custom_emoji_id=item.custom_emoji_id, alternative_text=item.fallback_emoji)
            blocks.append(block.model_copy(update={"text": _prepend(block.text, digit, " ")}))
        else:
            blocks.append(block)
    return article.model_copy(update={"blocks": tuple(blocks)})


def _assets(root: Path, release: dict[str, Any], article_id: str) -> list[dict[str, Any]]:
    registry = _read(_verify(root, cast(dict[str, Any], release["media_registry"])))
    raw_assets = registry.get("assets")
    if not isinstance(raw_assets, list):
        raise ValueError("media registry lacks assets")
    return [
        raw
        for raw in raw_assets
        if isinstance(raw, dict)
        and raw.get("article_id") == article_id
        and raw.get("remote_ready") is True
        and isinstance(raw.get("direct_media_url"), str)
        and str(raw["direct_media_url"]).startswith("https://")
        and raw.get("expected_mime") in {"image/jpeg", "image/png"}
    ]


def _insert_at(blocks: list[Any], slot: Any) -> int:
    ids = [getattr(block, "block_id", "") for block in blocks]
    placement = getattr(slot, "placement", {})
    before = placement.get("before") if isinstance(placement, dict) else None
    after = placement.get("after") if isinstance(placement, dict) else None
    if before:
        target = "p-lead" if before == "lead" else "h-title" if before == "title" else f"h-{before}"
        if target in ids:
            return ids.index(target)
    if after:
        if after == "lead" and "p-lead" in ids:
            return ids.index("p-lead") + 1
        if after == "title" and "h-title" in ids:
            return ids.index("h-title") + 1
        hits = [i for i, block_id in enumerate(ids) if block_id == f"h-{after}" or block_id.startswith(f"b-{after}-")]
        if hits:
            return max(hits) + 1
    footers = [i for i, block_id in enumerate(ids) if block_id in {"p-footer", "p-hashtags"}]
    return min(footers) if footers else len(blocks)


def _bind_media(article: RichArticleDocument, root: Path, release: dict[str, Any]) -> RichArticleDocument:
    slots = {slot.slot_id: slot for slot in article.media_slots}
    blocks = list(article.blocks)
    media: list[RichMediaItem] = []
    planned: list[tuple[int, RichBlockMedia]] = []
    for n, raw in enumerate(_assets(root, release, article.document_id), start=1):
        slot_id = str(raw.get("media_slot_id"))
        slot = slots.get(slot_id)
        if slot is None:
            raise ValueError(f"remote media has no matching slot: {raw.get('asset_id')}")
        media_id, url = str(raw["asset_id"]), str(raw["direct_media_url"])
        caption = str(raw.get("caption") or slot.caption or raw.get("depicts") or "Иллюстрация")
        attribution = str(raw.get("attribution_text") or "").strip()
        credit = None if not attribution or attribution in caption else attribution
        media.append(
            RichMediaItem(media_id=media_id, kind="photo", uri=url, alt_text=str(raw.get("depicts") or caption)[:300])
        )
        planned.append(
            (
                _insert_at(blocks, slot),
                RichBlockMedia(
                    block_id=f"m-{n}-{slot_id}",
                    media_id=media_id,
                    caption=RichBlockCaption(text=caption, credit=credit),
                ),
            )
        )
    for index, block in sorted(planned, key=lambda value: value[0], reverse=True):
        blocks.insert(index, block)
    updated = article.model_copy(update={"blocks": tuple(blocks), "media": tuple(media)})
    return RichArticleDocument.model_validate(updated.model_dump(mode="json"))


def _item(release: dict[str, Any], publication_id: str) -> dict[str, Any]:
    for item in cast(list[dict[str, Any]], release["items"]):
        if item.get("publication_id") == publication_id:
            return item
    raise ValueError(f"unknown publication id: {publication_id}")


def build_document(root: Path, release: dict[str, Any], item: dict[str, Any]) -> tuple[Any, Any, RichArticleDocument]:
    article = load_svodka_rich_article(_verify(root, cast(dict[str, Any], item["article"])))
    article = _decorate(
        article, _verify(root, cast(dict[str, Any], release["custom_emoji_catalog"])), str(item["emoji_role"])
    )
    article = _bind_media(article, root, release)
    document, render = render_rich_document(
        article,
        _target(root, release),
        publication_id=str(item["publication_id"]),
        provider_assigned_media_ids=tuple(media.media_id for media in article.media),
        skip_entity_detection=True,
    )
    return document, render, article


class _Reader(HttpClientOwner):
    def __init__(self) -> None:
        self._initialize_http_client(
            None, timeout=httpx.Timeout(connect=15, read=30, write=15, pool=15), follow_redirects=False, trust_env=False
        )

    def fetch(self, url: str) -> tuple[int, str, bytes]:
        result = execute_http_request(
            lambda: self._http_client.get(url, headers={"User-Agent": "video-channel-manager-svodka-rich/1"}),
            provider="https-media",
            operation=HttpOperationClass.SAFE_READ,
            method="GET",
            resource="svodka-rich-production-media",
            retry_policy=RetryPolicy(max_attempts=2),
        )
        response = result.response
        return (
            response.status_code,
            response.headers.get("content-type", "").split(";", 1)[0].strip().lower(),
            response.content,
        )


def media_proof(
    root: Path, release: dict[str, Any], item: dict[str, Any], expected: dict[str, Any] | None = None
) -> dict[str, Any]:
    _document, _render, article = build_document(root, release, item)
    mime = {str(raw["asset_id"]): str(raw["expected_mime"]) for raw in _assets(root, release, str(item["article_id"]))}
    reader = _Reader()
    evidence: list[dict[str, Any]] = []
    try:
        for media in article.media:
            status, content_type, content = reader.fetch(media.uri)
            if status != 200 or content_type != mime[media.media_id] or not content or len(content) > 10_000_000:
                raise ValueError(f"media proof failed: {media.media_id}")
            signature_ok = (
                content.startswith(b"\xff\xd8\xff")
                if content_type == "image/jpeg"
                else content.startswith(b"\x89PNG\r\n\x1a\n")
            )
            if not signature_ok:
                raise ValueError(f"media signature failed: {media.media_id}")
            evidence.append(
                {
                    "media_id": media.media_id,
                    "url": media.uri,
                    "content_type": content_type,
                    "content_length": len(content),
                    "content_sha256": "sha256:" + hashlib.sha256(content).hexdigest(),
                }
            )
    finally:
        reader.close()
    proof = {
        "schema_name": "video-channel-manager.svodka-rich-production-media-proof",
        "schema_version": 1,
        "release_sha256": release_digest(release),
        "publication_id": item["publication_id"],
        "checked_at_utc": datetime.now(tz=UTC).isoformat(),
        "items": evidence,
        "provider_write_performed": False,
    }
    if expected is not None and expected.get("items") != proof["items"]:
        raise ValueError("media bytes changed after durable intent")
    return proof


def new_ledger(release: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "video-channel-manager.svodka-rich-production-ledger",
        "schema_version": 1,
        "release_id": RELEASE_ID,
        "release_sha256": release_digest(release),
        "project_key": PROJECT,
        "channel_username": CHANNEL,
        "entries": {
            str(item["publication_id"]): {
                "publication_id": item["publication_id"],
                "scheduled_at": item["scheduled_at"],
                "state": "pending",
                "provider_effect": "impossible",
                "dispatch_mode": None,
                "workflow_run_id": None,
                "workflow_run_attempt": None,
                "document_sha256": None,
                "message_id": None,
                "message_url": None,
                "error": None,
            }
            for item in cast(list[dict[str, Any]], release["items"])
        },
    }


def load_ledger(path: Path, release: dict[str, Any], create: bool = False) -> dict[str, Any]:
    ledger = new_ledger(release) if create and not path.exists() else _read(path)
    if ledger.get("release_id") != RELEASE_ID or ledger.get("release_sha256") != release_digest(release):
        raise ValueError("ledger is bound to another release")
    expected = [str(item["publication_id"]) for item in cast(list[dict[str, Any]], release["items"])]
    entries = ledger.get("entries")
    if not isinstance(entries, dict) or list(entries) != expected:
        raise ValueError("ledger entries/order differ from release")
    return ledger


def select(
    release: dict[str, Any], ledger: dict[str, Any], now: datetime | None = None
) -> tuple[dict[str, Any], Literal["canary", "scheduled"]] | None:
    entries = cast(dict[str, dict[str, Any]], ledger["entries"])
    blockers = [e for e in entries.values() if e["state"] in {"intent", "may_exist", "failed_no_effect"}]
    if blockers:
        raise ValueError(f"durable blocker: {blockers[0]['publication_id']}/{blockers[0]['state']}")
    next_item = next(
        (
            item
            for item in cast(list[dict[str, Any]], release["items"])
            if entries[str(item["publication_id"])]["state"] == "pending"
        ),
        None,
    )
    if next_item is None:
        return None
    scheduled = datetime.fromisoformat(str(next_item["scheduled_at"]))
    current = (now or datetime.now(tz=UTC)).astimezone(scheduled.tzinfo)
    if current < scheduled:
        return None
    if current >= scheduled + timedelta(minutes=120):
        raise ValueError(f"strict-next window expired: {next_item['publication_id']}")
    canary_done = any(
        e["state"] == "published" and e.get("dispatch_mode") == "canary" and e["provider_effect"] == "verified"
        for e in entries.values()
    )
    return next_item, "scheduled" if canary_done else "canary"


def _proof(path: Path) -> GenericTargetProof:
    return GenericTargetProof.model_validate_json(path.read_text(encoding="utf-8"))


def _require_proof(proof: GenericTargetProof, document: Any) -> None:
    if (proof.chat_id, proof.bot_id, proof.bot_username.casefold(), proof.can_post_messages, proof.profile_sha256) != (
        document.target.chat_id,
        document.target.bot_id,
        document.target.bot_username.casefold(),
        True,
        document.target.profile_sha256,
    ):
        raise ValueError("fresh target proof differs from exact rich target")


def prepare(
    root: Path,
    release: dict[str, Any],
    ledger: dict[str, Any],
    target_path: Path,
    proof_media: dict[str, Any],
    repository: str,
    sha: str,
    run_id: str,
    attempt: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    selected = select(release, ledger)
    if selected is None:
        raise ValueError("no eligible rich publication")
    item, mode = selected
    document, render, _article = build_document(root, release, item)
    target = _proof(target_path)
    _require_proof(target, document)
    if (
        repository != REPOSITORY
        or proof_media.get("release_sha256") != release_digest(release)
        or proof_media.get("publication_id") != item["publication_id"]
    ):
        raise ValueError("intent inputs differ from exact release")
    intent = {
        "schema_name": "video-channel-manager.svodka-rich-production-intent",
        "schema_version": 1,
        "release_sha256": release_digest(release),
        "publication_id": item["publication_id"],
        "dispatch_mode": mode,
        "github_repository": repository,
        "github_sha": sha,
        "workflow_run_id": run_id,
        "workflow_run_attempt": attempt,
        "document_sha256": document.document_sha256,
        "render_sha256": render.render_sha256,
        "target_proof_sha256": _sha(target.model_dump(mode="json")),
        "media_proof": proof_media,
        "created_at_utc": datetime.now(tz=UTC).isoformat(),
        "mutation_request_limit": 1,
        "automatic_retry_allowed": False,
        "blind_retry_allowed": False,
    }
    entry = cast(dict[str, dict[str, Any]], ledger["entries"])[str(item["publication_id"])]
    entry.update(
        {
            "state": "intent",
            "provider_effect": "impossible",
            "dispatch_mode": mode,
            "workflow_run_id": run_id,
            "workflow_run_attempt": attempt,
            "document_sha256": document.document_sha256,
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
            raise ValueError("provider outcome archive digest mismatch")
        return TelegramRichOutcomeArchiveReceipt(
            schema_name="video-channel-manager.telegram-rich-outcome-archive-receipt",
            schema_version=1,
            outcome_sha256=outcome_sha256,
            archive_reference=f"workflow-local:{self.path}",
            durable_before_state_mutation=True,
        )


def send(
    root: Path,
    release: dict[str, Any],
    intent: dict[str, Any],
    target_path: Path,
    recheck: dict[str, Any],
    outcome_path: Path,
    token: str,
) -> TelegramRichProviderOutcome:
    if (
        intent.get("release_sha256") != release_digest(release)
        or intent.get("github_repository") != REPOSITORY
        or recheck.get("items") != cast(dict[str, Any], intent["media_proof"]).get("items")
    ):
        raise ValueError("durable intent/media recheck mismatch")
    item = _item(release, str(intent["publication_id"]))
    document, render, _article = build_document(root, release, item)
    if document.document_sha256 != intent.get("document_sha256") or render.render_sha256 != intent.get("render_sha256"):
        raise ValueError("document changed after durable intent")
    proof = _proof(target_path)
    _require_proof(proof, document)
    if _sha(proof.model_dump(mode="json")) != intent.get("target_proof_sha256"):
        raise ValueError("target proof changed after durable intent")
    profile = load_channel_profile(_verify(root, cast(dict[str, Any], release["profile"])))
    provider = HttpxTelegramRichMutationProvider(token=token)
    try:
        archived = publish_rich_once(
            document, proof, provider, _Archiver(outcome_path), profile=profile, state_mutation=None
        )
    finally:
        provider.close()
    return archived.outcome


def apply(ledger: dict[str, Any], intent: dict[str, Any], outcome: TelegramRichProviderOutcome) -> dict[str, Any]:
    entry = cast(dict[str, dict[str, Any]], ledger["entries"])[str(intent["publication_id"])]
    if (
        entry["state"] != "intent"
        or entry["document_sha256"] != intent.get("document_sha256")
        or outcome.document_sha256 != intent.get("document_sha256")
    ):
        raise ValueError("outcome has no exact durable intent")
    if outcome.provider_effect == "verified":
        entry.update(
            {
                "state": "published",
                "provider_effect": "verified",
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
    for name in ("preview", "ensure-ledger", "select", "media-proof", "prepare", "send", "apply", "status"):
        p = sub.add_parser(name)
        p.add_argument("--release", type=Path, required=True)
        p.add_argument("--root", type=Path, default=Path("."))
        if name in {"ensure-ledger", "select", "prepare", "apply", "status"}:
            p.add_argument("--ledger", type=Path, required=True)
        if name == "media-proof":
            p.add_argument("--publication-id", required=True)
            p.add_argument("--expected", type=Path)
            p.add_argument("--output", type=Path, required=True)
        if name == "prepare":
            p.add_argument("--target-proof", type=Path, required=True)
            p.add_argument("--media-proof", type=Path, required=True)
            p.add_argument("--github-repository", required=True)
            p.add_argument("--github-sha", required=True)
            p.add_argument("--run-id", required=True)
            p.add_argument("--run-attempt", required=True)
            p.add_argument("--intent-output", type=Path, required=True)
        if name == "send":
            p.add_argument("--intent", type=Path, required=True)
            p.add_argument("--target-proof", type=Path, required=True)
            p.add_argument("--media-recheck", type=Path, required=True)
            p.add_argument("--outcome", type=Path, required=True)
        if name == "apply":
            p.add_argument("--intent", type=Path, required=True)
            p.add_argument("--outcome", type=Path, required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    release = load_release(args.release, args.root)
    if args.cmd == "preview":
        items = []
        for item in cast(list[dict[str, Any]], release["items"]):
            doc, rendered, article = build_document(args.root, release, item)
            items.append(
                {
                    "publication_id": item["publication_id"],
                    "scheduled_at": item["scheduled_at"],
                    "document_sha256": doc.document_sha256,
                    "render_sha256": rendered.render_sha256,
                    "media_count": len(article.media),
                }
            )
        print(
            json.dumps(
                {"release_sha256": release_digest(release), "items": items, "provider_write_performed": False},
                ensure_ascii=False,
            )
        )
        return 0
    if args.cmd == "ensure-ledger":
        ledger = load_ledger(args.ledger, release, create=True)
        _write(args.ledger, ledger)
        print(json.dumps({"entries": 14, "provider_write_performed": False}))
        return 0
    if args.cmd == "select":
        chosen = select(release, load_ledger(args.ledger, release))
        if chosen is None:
            print(json.dumps({"eligible": False, "provider_write_performed": False}))
            return 3
        item, mode = chosen
        print(
            json.dumps(
                {
                    "eligible": True,
                    "publication_id": item["publication_id"],
                    "dispatch_mode": mode,
                    "provider_write_performed": False,
                }
            )
        )
        return 0
    if args.cmd == "media-proof":
        expected = _read(args.expected) if args.expected else None
        value = media_proof(args.root, release, _item(release, args.publication_id), expected)
        _write(args.output, value)
        print(
            json.dumps(
                {
                    "publication_id": args.publication_id,
                    "media_count": len(value["items"]),
                    "provider_write_performed": False,
                }
            )
        )
        return 0
    if args.cmd == "prepare":
        ledger = load_ledger(args.ledger, release)
        intent, ledger = prepare(
            args.root,
            release,
            ledger,
            args.target_proof,
            _read(args.media_proof),
            args.github_repository,
            args.github_sha,
            args.run_id,
            args.run_attempt,
        )
        _write(args.ledger, ledger)
        _write(args.intent_output, intent)
        print(
            json.dumps(
                {
                    "publication_id": intent["publication_id"],
                    "dispatch_mode": intent["dispatch_mode"],
                    "provider_write_performed": False,
                }
            )
        )
        return 0
    if args.cmd == "send":
        token = os.environ.get("SVODKA_TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise SystemExit("SVODKA_TELEGRAM_BOT_TOKEN is required")
        outcome = send(
            args.root, release, _read(args.intent), args.target_proof, _read(args.media_recheck), args.outcome, token
        )
        print(
            json.dumps(
                {
                    "provider_effect": outcome.provider_effect,
                    "message_id": outcome.message_id,
                    "message_url": outcome.message_url,
                },
                ensure_ascii=False,
            )
        )
        return 0 if outcome.provider_effect == "verified" else 4
    if args.cmd == "apply":
        ledger = load_ledger(args.ledger, release)
        intent = _read(args.intent)
        outcome = TelegramRichProviderOutcome.model_validate_json(args.outcome.read_text(encoding="utf-8"))
        ledger = apply(ledger, intent, outcome)
        _write(args.ledger, ledger)
        state = cast(dict[str, dict[str, Any]], ledger["entries"])[str(intent["publication_id"])]["state"]
        print(
            json.dumps(
                {"publication_id": intent["publication_id"], "state": state, "provider_effect": outcome.provider_effect}
            )
        )
        return 0 if state == "published" else 4
    ledger = load_ledger(args.ledger, release)
    counts: dict[str, int] = {}
    for entry in cast(dict[str, dict[str, Any]], ledger["entries"]).values():
        counts[entry["state"]] = counts.get(entry["state"], 0) + 1
    print(json.dumps({"release_sha256": release_digest(release), "counts": counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
