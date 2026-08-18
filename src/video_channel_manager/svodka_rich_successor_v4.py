from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Sequence, cast

from video_channel_manager import svodka_rich_production as legacy
from video_channel_manager import svodka_rich_successor as v2
from video_channel_manager import svodka_rich_successor_v3 as v3
from video_channel_manager.svodka_rich_loader import load_svodka_rich_article
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_rich_models import (
    RichArticleDocument,
    RichBlockCaption,
    RichBlockMedia,
    RichMediaItem,
)
from video_channel_manager.telegram_rich_provider import (
    HttpxTelegramRichMutationProvider,
    TelegramRichProviderOutcome,
    publish_rich_once,
)
from video_channel_manager.telegram_rich_renderer import render_rich_document

RELEASE_ID = "svodka-rich-v4-cdn-finalizer-2026-08"
EXPECTED_ITEM_COUNT = 1
PREDECESSOR_RELEASE_ID = "svodka-rich-v2-successor-2026-08"
PREDECESSOR_PUBLICATION_ID = "svodka-rich-goldfish-three-second-memory-myth"
PREDECESSOR_MESSAGE_ID = 28
FAILED_PREDECESSOR_RELEASE_ID = "svodka-rich-v3-finalizer-2026-08"
FAILED_PREDECESSOR_ERROR = "Telegram rejected sendRichMessage: Bad Request: failed to get HTTP URL content"


def _media_override(release: dict[str, Any]) -> dict[str, Any]:
    raw = release.get("media_override")
    if not isinstance(raw, dict):
        raise ValueError("Svodka v4 release has no exact media override")
    if (
        raw.get("asset_id") != "asset-wombat-cubic-poop-media-01-v4"
        or raw.get("article_id") != "svodka-rich-wombat-cubic-poop"
        or raw.get("media_slot_id") != "media-01"
        or raw.get("kind") != "photo"
        or raw.get("expected_mime") != "image/jpeg"
        or raw.get("remote_ready") is not True
        or raw.get("provider_upload_status") != "not_uploaded"
        or raw.get("licence") != "Unsplash License"
    ):
        raise ValueError("invalid Svodka v4 media override identity")
    source_page = raw.get("canonical_source_page_url")
    media_url = raw.get("direct_media_url")
    if (
        not isinstance(source_page, str)
        or source_page != "https://unsplash.com/photos/a-wombat-stares-directly-at-the-camera-QvgZkCAfJdc"
        or not isinstance(media_url, str)
        or not media_url.startswith("https://images.unsplash.com/photo-1743938153060-7f6c4b1b9ba0?")
    ):
        raise ValueError("Svodka v4 media override is not the reviewed Unsplash asset")
    if not str(raw.get("caption") or "").strip() or not str(raw.get("depicts") or "").strip():
        raise ValueError("Svodka v4 media override lacks caption or alt text")
    return cast(dict[str, Any], raw)


def load_release(path: Path, root: Path) -> dict[str, Any]:
    release = legacy._read(path)
    predecessor = release.get("verified_predecessor_canary")
    failed = release.get("confirmed_absent_predecessor")
    if (
        release.get("schema_name") != "video-channel-manager.svodka-rich-successor-v4-release"
        or release.get("schema_version") != 1
        or release.get("release_id") != RELEASE_ID
        or release.get("project_key") != legacy.PROJECT
        or release.get("channel_username") != legacy.CHANNEL
        or release.get("chat_id") != legacy.CHAT_ID
        or release.get("bot_id") != legacy.BOT_ID
        or release.get("bot_username") != legacy.BOT_USERNAME
        or release.get("approved") is not True
        or release.get("publication_window_minutes") != 120
        or release.get("max_verified_per_day_moscow") != 2
        or not isinstance(predecessor, dict)
        or predecessor.get("release_id") != PREDECESSOR_RELEASE_ID
        or predecessor.get("publication_id") != PREDECESSOR_PUBLICATION_ID
        or predecessor.get("message_id") != PREDECESSOR_MESSAGE_ID
        or predecessor.get("required_state") != "published"
        or predecessor.get("required_provider_effect") != "verified"
        or not isinstance(failed, dict)
        or failed.get("release_id") != FAILED_PREDECESSOR_RELEASE_ID
        or failed.get("publication_id") != "svodka-rich-wombat-cubic-poop"
        or failed.get("required_state") != "failed_no_effect"
        or failed.get("required_provider_effect") != "confirmed_absent"
        or failed.get("required_error") != FAILED_PREDECESSOR_ERROR
    ):
        raise ValueError("invalid Svodka v4 finalizer release header")

    items = release.get("items")
    if not isinstance(items, list) or len(items) != EXPECTED_ITEM_COUNT:
        raise ValueError("Svodka v4 finalizer release must contain exactly one item")
    item = items[0]
    if (
        item.get("sequence") != 1
        or item.get("publication_id") != "svodka-rich-wombat-cubic-poop"
        or item.get("article_id") != item.get("publication_id")
        or item.get("dispatch_mode") != "scheduled"
    ):
        raise ValueError("Svodka v4 finalizer item identity is invalid")

    scheduled = datetime.fromisoformat(str(item["scheduled_at"]))
    if scheduled.utcoffset() != timedelta(hours=3):
        raise ValueError("Svodka v4 finalizer schedule must use UTC+03:00")

    for key in ("profile", "target_binding", "custom_emoji_catalog"):
        legacy._verify(root, cast(dict[str, Any], release[key]))
    legacy._verify(root, cast(dict[str, Any], item["article"]))
    _media_override(release)
    return release


def release_digest(release: dict[str, Any]) -> str:
    return legacy._sha(release)


def _bind_override_media(article: RichArticleDocument, release: dict[str, Any]) -> RichArticleDocument:
    raw = _media_override(release)
    slot_id = str(raw["media_slot_id"])
    slot = next((candidate for candidate in article.media_slots if candidate.slot_id == slot_id), None)
    if slot is None:
        raise ValueError("Svodka v4 override has no matching reviewed article slot")
    media_id = str(raw["asset_id"])
    caption = str(raw["caption"])
    attribution = str(raw.get("attribution_text") or "").strip()
    credit = None if not attribution or attribution in caption else attribution
    media = RichMediaItem(
        media_id=media_id,
        kind="photo",
        uri=str(raw["direct_media_url"]),
        alt_text=str(raw["depicts"])[:300],
    )
    block = RichBlockMedia(
        block_id=f"m-v4-{slot_id}",
        media_id=media_id,
        caption=RichBlockCaption(text=caption, credit=credit),
    )
    blocks = list(article.blocks)
    blocks.insert(legacy._insert_at(blocks, slot), block)
    updated = article.model_copy(update={"blocks": tuple(blocks), "media": (media,)})
    return RichArticleDocument.model_validate(updated.model_dump(mode="json"))


def build_document(root: Path, release: dict[str, Any], item: dict[str, Any]) -> tuple[Any, Any, RichArticleDocument]:
    article = load_svodka_rich_article(legacy._verify(root, cast(dict[str, Any], item["article"])))
    article = legacy._decorate(
        article,
        legacy._verify(root, cast(dict[str, Any], release["custom_emoji_catalog"])),
        str(item["emoji_role"]),
    )
    article = v3._canonicalize_plain_heading_runs(article)
    article = _bind_override_media(article, release)
    document, render = render_rich_document(
        article,
        legacy._target(root, release),
        publication_id=str(item["publication_id"]),
        provider_assigned_media_ids=tuple(media.media_id for media in article.media),
        skip_entity_detection=False,
    )
    return document, render, article


def new_ledger(release: dict[str, Any]) -> dict[str, Any]:
    item = cast(list[dict[str, Any]], release["items"])[0]
    return {
        "schema_name": "video-channel-manager.svodka-rich-production-ledger",
        "schema_version": 1,
        "release_id": RELEASE_ID,
        "release_sha256": release_digest(release),
        "project_key": legacy.PROJECT,
        "channel_username": legacy.CHANNEL,
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
        },
    }


def load_ledger(path: Path, release: dict[str, Any], *, create: bool = False) -> dict[str, Any]:
    ledger = new_ledger(release) if create and not path.exists() else legacy._read(path)
    if ledger.get("release_id") != RELEASE_ID or ledger.get("release_sha256") != release_digest(release):
        raise ValueError("Svodka v4 ledger is bound to another release")
    expected = [str(cast(list[dict[str, Any]], release["items"])[0]["publication_id"])]
    entries = ledger.get("entries")
    if not isinstance(entries, dict) or list(entries) != expected:
        raise ValueError("Svodka v4 ledger entries differ from release")
    return ledger


def select(
    release: dict[str, Any], ledger: dict[str, Any], now: datetime | None = None
) -> tuple[dict[str, Any], Literal["scheduled"]] | None:
    item = cast(list[dict[str, Any]], release["items"])[0]
    entry = cast(dict[str, dict[str, Any]], ledger["entries"])[str(item["publication_id"])]
    if entry["state"] in {"intent", "may_exist", "failed_no_effect"}:
        raise ValueError(f"durable blocker: {item['publication_id']}/{entry['state']}")
    if entry["state"] == "published":
        return None
    if entry["state"] != "pending":
        raise ValueError(f"unexpected Svodka v4 state: {entry['state']}")

    scheduled = datetime.fromisoformat(str(item["scheduled_at"]))
    current = (now or datetime.now(tz=UTC)).astimezone(scheduled.tzinfo)
    if current < scheduled:
        return None
    if current >= scheduled + timedelta(minutes=120):
        raise ValueError(f"strict-next window expired: {item['publication_id']}")
    return item, "scheduled"


def _item(release: dict[str, Any], publication_id: str) -> dict[str, Any]:
    item = cast(list[dict[str, Any]], release["items"])[0]
    if item.get("publication_id") != publication_id:
        raise ValueError(f"unknown Svodka v4 publication id: {publication_id}")
    return item


def media_proof(
    root: Path, release: dict[str, Any], item: dict[str, Any], expected: dict[str, Any] | None = None
) -> dict[str, Any]:
    _document, _render, article = build_document(root, release, item)
    raw = _media_override(release)
    expected_content_type = str(raw["expected_mime"])
    reader = v2._SuccessorMediaReader()
    evidence: list[dict[str, Any]] = []
    try:
        for media in article.media:
            status, content_type, content = reader.fetch(media.uri)
            if status != 200 or content_type != expected_content_type or not content or len(content) > 10_000_000:
                raise ValueError(
                    f"media proof failed: {media.media_id} "
                    f"(status={status}, content_type={content_type!r}, "
                    f"expected_content_type={expected_content_type!r}, content_length={len(content)})"
                )
            if not content.startswith(b"\xff\xd8\xff"):
                raise ValueError(
                    f"media signature failed: {media.media_id} "
                    f"(content_type={content_type!r}, content_length={len(content)})"
                )
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
        raise ValueError("no eligible Svodka v4 publication")
    item, mode = selected
    document, render, _article = build_document(root, release, item)
    target = legacy._proof(target_path)
    legacy._require_proof(target, document)
    if (
        repository != legacy.REPOSITORY
        or proof_media.get("release_sha256") != release_digest(release)
        or proof_media.get("publication_id") != item["publication_id"]
    ):
        raise ValueError("Svodka v4 intent inputs differ from exact release")

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
        "target_proof_sha256": legacy._sha(target.model_dump(mode="json")),
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
        or intent.get("github_repository") != legacy.REPOSITORY
        or recheck.get("items") != cast(dict[str, Any], intent["media_proof"]).get("items")
    ):
        raise ValueError("Svodka v4 durable intent/media recheck mismatch")
    item = _item(release, str(intent["publication_id"]))
    document, render, _article = build_document(root, release, item)
    if document.document_sha256 != intent.get("document_sha256") or render.render_sha256 != intent.get("render_sha256"):
        raise ValueError("Svodka v4 document changed after durable intent")
    proof = legacy._proof(target_path)
    legacy._require_proof(proof, document)
    if legacy._sha(proof.model_dump(mode="json")) != intent.get("target_proof_sha256"):
        raise ValueError("Svodka v4 target proof changed after durable intent")

    profile = load_channel_profile(legacy._verify(root, cast(dict[str, Any], release["profile"])))
    provider = HttpxTelegramRichMutationProvider(token=token)
    try:
        archived = publish_rich_once(
            document,
            proof,
            provider,
            legacy._Archiver(outcome_path),
            profile=profile,
            state_mutation=None,
        )
    finally:
        provider.close()
    return archived.outcome


def apply(ledger: dict[str, Any], intent: dict[str, Any], outcome: TelegramRichProviderOutcome) -> dict[str, Any]:
    return legacy.apply(ledger, intent, outcome)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="cmd", required=True)
    for name in ("preview", "ensure-ledger", "select", "media-proof", "prepare", "send", "apply", "status"):
        command = sub.add_parser(name)
        command.add_argument("--release", type=Path, required=True)
        command.add_argument("--root", type=Path, default=Path("."))
        if name in {"ensure-ledger", "select", "prepare", "apply", "status"}:
            command.add_argument("--ledger", type=Path, required=True)
        if name == "media-proof":
            command.add_argument("--publication-id", required=True)
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
        items = []
        for item in cast(list[dict[str, Any]], release["items"]):
            document, rendered, article = build_document(args.root, release, item)
            items.append(
                {
                    "publication_id": item["publication_id"],
                    "scheduled_at": item["scheduled_at"],
                    "dispatch_mode": item["dispatch_mode"],
                    "document_sha256": document.document_sha256,
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
        legacy._write(args.ledger, ledger)
        print(json.dumps({"entries": 1, "provider_write_performed": False}))
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
        expected = legacy._read(args.expected) if args.expected else None
        value = media_proof(args.root, release, _item(release, args.publication_id), expected)
        legacy._write(args.output, value)
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
            legacy._read(args.media_proof),
            args.github_repository,
            args.github_sha,
            args.run_id,
            args.run_attempt,
        )
        legacy._write(args.ledger, ledger)
        legacy._write(args.intent_output, intent)
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
        intent = legacy._read(args.intent)
        outcome = send(
            args.root,
            release,
            intent,
            args.target_proof,
            legacy._read(args.media_recheck),
            args.outcome,
            os.environ["SVODKA_TELEGRAM_BOT_TOKEN"],
        )
        print(
            json.dumps(
                {
                    "publication_id": intent["publication_id"],
                    "provider_effect": outcome.provider_effect,
                    "message_id": outcome.message_id,
                },
                ensure_ascii=False,
            )
        )
        return 0 if outcome.provider_effect == "verified" else 4
    if args.cmd == "apply":
        ledger = load_ledger(args.ledger, release)
        intent = legacy._read(args.intent)
        outcome = TelegramRichProviderOutcome.model_validate_json(args.outcome.read_text(encoding="utf-8"))
        ledger = apply(ledger, intent, outcome)
        legacy._write(args.ledger, ledger)
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
