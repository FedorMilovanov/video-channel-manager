from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Sequence, cast

import httpx

from video_channel_manager import svodka_rich_production as legacy
from video_channel_manager.platforms.http import HttpClientOwner, HttpOperationClass, RetryPolicy, execute_http_request
from video_channel_manager.svodka_rich_loader import load_svodka_rich_article
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_rich_provider import (
    HttpxTelegramRichMutationProvider,
    TelegramRichProviderOutcome,
    publish_rich_once,
)
from video_channel_manager.telegram_rich_renderer import render_rich_document

RELEASE_ID = "svodka-rich-v2-successor-2026-08"
EXPECTED_ITEM_COUNT = 2
MEDIA_USER_AGENT = (
    "video-channel-manager-svodka-rich-bot/2 "
    "(+https://github.com/FedorMilovanov/video-channel-manager)"
)


def load_release(path: Path, root: Path) -> dict[str, Any]:
    release = legacy._read(path)
    if (
        release.get("schema_name") != "video-channel-manager.svodka-rich-production-release"
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
    ):
        raise ValueError("invalid Svodka successor release header")

    items = release.get("items")
    if not isinstance(items, list) or len(items) != EXPECTED_ITEM_COUNT:
        raise ValueError(f"Svodka successor release must contain exactly {EXPECTED_ITEM_COUNT} items")
    if [item.get("sequence") for item in items] != list(range(1, EXPECTED_ITEM_COUNT + 1)):
        raise ValueError("Svodka successor sequence is invalid")
    ids = [str(item.get("publication_id")) for item in items]
    if len(set(ids)) != EXPECTED_ITEM_COUNT or release.get("first_canary_publication_id") != ids[0]:
        raise ValueError("Svodka successor ids/canary binding are invalid")

    schedules = [datetime.fromisoformat(str(item["scheduled_at"])) for item in items]
    if schedules != sorted(schedules) or any(dt.utcoffset() != timedelta(hours=3) for dt in schedules):
        raise ValueError("Svodka successor schedule is invalid")
    per_day: dict[str, int] = {}
    for dt in schedules:
        key = dt.date().isoformat()
        per_day[key] = per_day.get(key, 0) + 1
    if any(count > 2 for count in per_day.values()):
        raise ValueError("Svodka successor exceeds two verified posts/day")

    for key in ("profile", "target_binding", "media_registry", "custom_emoji_catalog"):
        legacy._verify(root, cast(dict[str, Any], release[key]))
    for item in items:
        if item.get("publication_id") != item.get("article_id"):
            raise ValueError("Svodka successor publication/article id mismatch")
        legacy._verify(root, cast(dict[str, Any], item["article"]))
    return release


def release_digest(release: dict[str, Any]) -> str:
    return legacy._sha(release)


def build_document(root: Path, release: dict[str, Any], item: dict[str, Any]) -> tuple[Any, Any, Any]:
    article = load_svodka_rich_article(legacy._verify(root, cast(dict[str, Any], item["article"])))
    article = legacy._decorate(
        article,
        legacy._verify(root, cast(dict[str, Any], release["custom_emoji_catalog"])),
        str(item["emoji_role"]),
    )
    article = legacy._bind_media(article, root, release)
    document, render = render_rich_document(
        article,
        legacy._target(root, release),
        publication_id=str(item["publication_id"]),
        provider_assigned_media_ids=tuple(media.media_id for media in article.media),
        # Successor deliberately leaves entity detection enabled. Telegram may
        # normalize hashtag entities server-side; the historical v1 release is
        # left untouched and remains reproducible through the legacy module.
        skip_entity_detection=False,
    )
    return document, render, article


def new_ledger(release: dict[str, Any]) -> dict[str, Any]:
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
            for item in cast(list[dict[str, Any]], release["items"])
        },
    }


def load_ledger(path: Path, release: dict[str, Any], *, create: bool = False) -> dict[str, Any]:
    ledger = new_ledger(release) if create and not path.exists() else legacy._read(path)
    if ledger.get("release_id") != RELEASE_ID or ledger.get("release_sha256") != release_digest(release):
        raise ValueError("successor ledger is bound to another release")
    expected = [str(item["publication_id"]) for item in cast(list[dict[str, Any]], release["items"])]
    entries = ledger.get("entries")
    if not isinstance(entries, dict) or list(entries) != expected:
        raise ValueError("successor ledger entries/order differ from release")
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


def _item(release: dict[str, Any], publication_id: str) -> dict[str, Any]:
    for item in cast(list[dict[str, Any]], release["items"]):
        if item.get("publication_id") == publication_id:
            return item
    raise ValueError(f"unknown successor publication id: {publication_id}")


class _SuccessorMediaReader(HttpClientOwner):
    def __init__(self) -> None:
        self._initialize_http_client(
            None,
            timeout=httpx.Timeout(connect=15, read=30, write=15, pool=15),
            follow_redirects=False,
            trust_env=False,
        )

    def fetch(self, url: str) -> tuple[int, str, bytes]:
        result = execute_http_request(
            lambda: self._http_client.get(url, headers={"User-Agent": MEDIA_USER_AGENT}),
            provider="https-media",
            operation=HttpOperationClass.SAFE_READ,
            method="GET",
            resource="svodka-rich-successor-media",
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
    mime = {
        str(raw["asset_id"]): str(raw["expected_mime"])
        for raw in legacy._assets(root, release, str(item["article_id"]))
    }
    reader = _SuccessorMediaReader()
    evidence: list[dict[str, Any]] = []
    try:
        for media in article.media:
            status, content_type, content = reader.fetch(media.uri)
            expected_content_type = mime[media.media_id]
            if (
                status != 200
                or content_type != expected_content_type
                or not content
                or len(content) > 10_000_000
            ):
                raise ValueError(
                    f"media proof failed: {media.media_id} "
                    f"(status={status}, content_type={content_type!r}, "
                    f"expected_content_type={expected_content_type!r}, content_length={len(content)})"
                )
            signature_ok = (
                content.startswith(b"\xff\xd8\xff")
                if content_type == "image/jpeg"
                else content.startswith(b"\x89PNG\r\n\x1a\n")
            )
            if not signature_ok:
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
        raise ValueError("no eligible successor publication")
    item, mode = selected
    document, render, _article = build_document(root, release, item)
    target = legacy._proof(target_path)
    legacy._require_proof(target, document)
    if (
        repository != legacy.REPOSITORY
        or proof_media.get("release_sha256") != release_digest(release)
        or proof_media.get("publication_id") != item["publication_id"]
    ):
        raise ValueError("successor intent inputs differ from exact release")
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
) -> Any:
    if (
        intent.get("release_sha256") != release_digest(release)
        or intent.get("github_repository") != legacy.REPOSITORY
        or recheck.get("items") != cast(dict[str, Any], intent["media_proof"]).get("items")
    ):
        raise ValueError("successor durable intent/media recheck mismatch")
    item = _item(release, str(intent["publication_id"]))
    document, render, _article = build_document(root, release, item)
    if document.document_sha256 != intent.get("document_sha256") or render.render_sha256 != intent.get("render_sha256"):
        raise ValueError("successor document changed after durable intent")
    proof = legacy._proof(target_path)
    legacy._require_proof(proof, document)
    if legacy._sha(proof.model_dump(mode="json")) != intent.get("target_proof_sha256"):
        raise ValueError("successor target proof changed after durable intent")
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
        legacy._write(args.ledger, ledger)
        print(json.dumps({"entries": len(release["items"]), "provider_write_performed": False}))
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
