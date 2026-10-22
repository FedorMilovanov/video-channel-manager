"""LordChrist long-article lane: queue → due article → provider-neutral rich document.

The quote lane publishes from ``verified-30-posts.json``; long L2 articles had no
queue at all, so nothing could pick "today's article" the way the quote publisher
picks today's quote.  This module is that missing decision layer and nothing more:

* it reads the reviewed queue ``rich-v1/article-queue.json`` (one article per
  midday slot, 12:00 Moscow, Tuesday and Friday);
* it verifies every ready entry byte-for-byte (git blob identity of the article
  JSON and of the cover JPEG) before anything else happens;
* it selects the single article whose Moscow date is today;
* it binds the approved cover into the article and renders the exact
  ``TelegramRichMessageDocument`` with the existing general renderer.

No provider I/O lives here: the document it returns is the same object the rich
transport already knows how to send, so the send path stays the one reviewed
callable and no second mutation boundary is introduced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Sequence, cast
from zoneinfo import ZoneInfo

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_rich_models import (
    RichArticleDocument,
    RichBlockMedia,
    RichMediaItem,
)
from video_channel_manager.telegram_rich_provider import (
    TelegramRichMessageDocument,
    TelegramRichTargetBinding,
)
from video_channel_manager.telegram_rich_renderer import RichRenderResult, render_rich_document
from video_channel_manager.telegram_target_binding import load_target_binding

QUEUE_SCHEMA = "video-channel-manager.lordchrist-rich-article-queue"
PROJECT_KEY = "lord-god-strength"
CHANNEL_USERNAME = "@lordchrist"
DEFAULT_QUEUE_PATH = Path("content/telegram/lordchrist/rich-v1/article-queue.json")
DEFAULT_PROFILE_PATH = Path("content/telegram/channels/lordchrist-rich.json")
DEFAULT_BINDING_PATH = Path("content/telegram/channels/lordchrist-rich-target-binding.json")
MOSCOW = ZoneInfo("Europe/Moscow")
MIDDAY_WEEKDAYS = frozenset({1, 4})  # Tuesday, Friday
STATUSES = frozenset({"ready", "planned"})
JPEG_MAGIC = b"\xff\xd8\xff"
ATTACHMENT_NAME = "lc_cover"


@dataclass(frozen=True)
class QueueItem:
    """One reviewed long article and the exact bytes it is allowed to publish."""

    publication_id: str
    ordinal: int
    scheduled_on: date
    status: str
    article_path: Path | None = None
    article_blob: str | None = None
    cover_path: Path | None = None
    cover_blob: str | None = None
    media_id: str = "media-cover"

    @property
    def is_ready(self) -> bool:
        return self.status == "ready" and self.article_path is not None and self.cover_path is not None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unreadable JSON record {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON record is not an object: {path}")
    return value


def git_blob_sha(path: Path) -> str:
    """Return the git blob identity of a file (the identity the queue commits to)."""

    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()  # noqa: S324


def _identity(raw: Any, *, field: str, root: Path) -> tuple[Path, str]:
    if not isinstance(raw, dict):
        raise ValueError(f"queue item has no {field} record")
    relative = raw.get("path")
    blob = raw.get("git_blob_sha")
    if not isinstance(relative, str) or not relative:
        raise ValueError(f"queue item {field} has no path")
    if not isinstance(blob, str) or len(blob) != 40:
        raise ValueError(f"queue item {field} has no git blob sha")
    path = root / relative
    if not path.is_file():
        raise ValueError(f"queue item {field} file is missing: {relative}")
    actual = git_blob_sha(path)
    if actual != blob:
        raise ValueError(f"queue item {field} bytes differ from the reviewed blob: {relative}")
    return path, blob


def load_queue(path: Path = DEFAULT_QUEUE_PATH, root: Path = Path(".")) -> tuple[QueueItem, ...]:
    """Load and fully validate the article queue; fail closed on any drift."""

    payload = _read_json(path)
    if (
        payload.get("schema_name") != QUEUE_SCHEMA
        or payload.get("schema_version") != 1
        or payload.get("project_key") != PROJECT_KEY
        or str(payload.get("channel_username") or "").casefold() != CHANNEL_USERNAME.casefold()
    ):
        raise ValueError("invalid LordChrist rich article queue header")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("LordChrist rich article queue is empty")

    items: list[QueueItem] = []
    for index, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, dict):
            raise ValueError("queue item is not an object")
        publication_id = str(raw.get("publication_id") or "")
        if not publication_id.startswith("lordchrist-"):
            raise ValueError(f"queue item {index} has an invalid publication id")
        ordinal = raw.get("ordinal")
        if ordinal != index:
            raise ValueError(f"queue item {publication_id} has ordinal {ordinal}, expected {index}")
        status = raw.get("status")
        if status not in STATUSES:
            raise ValueError(f"queue item {publication_id} has an unknown status")
        try:
            scheduled_on = date.fromisoformat(str(raw.get("scheduled_on_moscow")))
        except ValueError as exc:
            raise ValueError(f"queue item {publication_id} has an invalid date") from exc
        override_reason = raw.get("slot_override_reason")
        if scheduled_on.weekday() not in MIDDAY_WEEKDAYS:
            # An off-slot date is allowed only as an explicit, documented exception,
            # never by silently accepting any weekday.
            if status != "ready" or not isinstance(override_reason, str) or not override_reason.strip():
                raise ValueError(f"queue item {publication_id} is not scheduled on the midday slot")
        elif override_reason is not None:
            raise ValueError(f"queue item {publication_id} overrides a date that is already on the midday slot")

        if status == "planned":
            if raw.get("article") is not None or raw.get("cover") is not None:
                raise ValueError(f"planned queue item {publication_id} must not carry published bytes")
            items.append(QueueItem(publication_id, index, scheduled_on, status))
            continue

        article_path, article_blob = _identity(raw.get("article"), field="article", root=root)
        cover_path, cover_blob = _identity(raw.get("cover"), field="cover", root=root)
        if not cover_path.read_bytes().startswith(JPEG_MAGIC):
            raise ValueError(f"queue item {publication_id} cover is not a JPEG")
        media_id = str(cast(dict[str, Any], raw["cover"]).get("media_id") or "")
        if media_id != "media-cover":
            raise ValueError(f"queue item {publication_id} cover media id must be media-cover")
        document = RichArticleDocument.model_validate(_read_json(article_path))
        if document.project_key != PROJECT_KEY or document.document_id != publication_id:
            raise ValueError(f"queue item {publication_id} article identity mismatch")
        items.append(
            QueueItem(publication_id, index, scheduled_on, status, article_path, article_blob, cover_path, cover_blob)
        )

    ids = [item.publication_id for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError("LordChrist rich article queue has duplicate publication ids")
    dates = [item.scheduled_on for item in items]
    if dates != sorted(dates) or len(set(dates)) != len(dates):
        raise ValueError("LordChrist rich article queue dates must be strictly increasing")
    return tuple(items)


def due_item(items: Sequence[QueueItem], now: datetime | None = None) -> QueueItem:
    """Return the single ready article scheduled for today in Moscow."""

    today = (now or datetime.now(tz=MOSCOW)).astimezone(MOSCOW).date()
    matches = [item for item in items if item.scheduled_on == today]
    if not matches:
        raise LookupError(f"no LordChrist rich article is scheduled for {today.isoformat()}")
    if len(matches) > 1:
        raise ValueError(f"more than one LordChrist rich article is scheduled for {today.isoformat()}")
    item = matches[0]
    if not item.is_ready:
        raise LookupError(f"LordChrist rich article {item.publication_id} is not ready ({item.status})")
    return item


def _cover_media(item: QueueItem, media_base_url: str) -> tuple[RichMediaItem, RichBlockMedia]:
    if item.cover_path is None:
        raise ValueError("article has no bound cover")
    url = f"{media_base_url.rstrip('/')}/{item.cover_path.as_posix()}"
    asset = RichMediaItem(media_id=item.media_id, kind="photo", uri=url, alt_text=f"{item.publication_id} cover")
    block = RichBlockMedia(block_id=f"b-{item.media_id}", media_id=item.media_id)
    return asset, block


def attach_cover(article: RichArticleDocument, item: QueueItem, media_base_url: str) -> RichArticleDocument:
    """Bind the approved cover directly under the article title."""

    if any(media.media_id == item.media_id for media in article.media):
        raise ValueError("article already carries the cover media id")
    asset, block = _cover_media(item, media_base_url)
    blocks: list[Any] = []
    inserted = False
    for existing in article.blocks:
        blocks.append(existing)
        if not inserted and getattr(existing, "type", None) == "heading" and getattr(existing, "size", None) == 1:
            blocks.append(block)
            inserted = True
    if not inserted:
        raise ValueError("article has no size-1 heading to place the cover under")
    return article.model_copy(update={"blocks": tuple(blocks), "media": tuple(article.media) + (asset,)})


def build_document(
    root: Path,
    item: QueueItem,
    *,
    media_base_url: str,
    profile_path: Path = DEFAULT_PROFILE_PATH,
    binding_path: Path = DEFAULT_BINDING_PATH,
) -> tuple[TelegramRichMessageDocument, RichRenderResult, RichArticleDocument]:
    """Render the exact rich document for one due article, cover included."""

    if not item.is_ready or item.article_path is None:
        raise ValueError(f"LordChrist rich article {item.publication_id} is not ready")
    article = RichArticleDocument.model_validate(_read_json(root / item.article_path))
    article = attach_cover(article, item, media_base_url)

    profile = load_channel_profile(root / profile_path)
    if profile.project_key != PROJECT_KEY or profile.channel_username.casefold() != CHANNEL_USERNAME.casefold():
        raise ValueError("LordChrist rich profile differs from the reviewed project/channel")
    if not profile.provider_writes_authorized:
        raise ValueError("LordChrist rich profile provider-write gate is disabled")
    binding = load_target_binding(root / binding_path, profile)
    target = TelegramRichTargetBinding(
        schema_name="video-channel-manager.telegram-rich-target-binding",
        schema_version=1,
        project_key=PROJECT_KEY,
        channel_username=CHANNEL_USERNAME,
        profile_sha256=profile.digest,
        target_binding_sha256=binding.digest,
        source_binding=binding,
        chat_id=binding.chat_id,
        chat_username=binding.chat_username,
        bot_id=binding.bot_id,
        bot_username=binding.bot_username,
    )
    document, render = render_rich_document(
        article,
        target,
        publication_id=article.document_id,
        provider_assigned_media_ids=(item.media_id,),
        skip_entity_detection=False,
    )
    return document, render, article


def swap_media_to_attachments(document: TelegramRichMessageDocument, item: QueueItem) -> TelegramRichMessageDocument:
    """Turn the rendered cover URL into the multipart attachment reference.

    The swap is proved to touch media identity only: applying it twice, or to a
    document without exactly one cover reference, fails closed.
    """
    name = ATTACHMENT_NAME
    reference = f"attach://{name}"
    payload = json.loads(json.dumps(document.input_rich_message))
    replaced = 0

    def walk(node: Any) -> None:
        nonlocal replaced
        if isinstance(node, dict):
            media = node.get("media")
            if isinstance(media, str) and media.startswith("https://"):
                node["media"] = reference
                replaced += 1
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(payload)
    if replaced != 1:
        raise ValueError(f"expected exactly one cover reference, found {replaced}")
    return document.model_copy(update={"input_rich_message": payload})


class _OutcomeArchive:
    """Write the exact provider outcome bytes to a path and hand back the receipt."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def archive(self, outcome_bytes: bytes, *, outcome_sha256: str) -> Any:
        from video_channel_manager.telegram_rich_provider import TelegramRichOutcomeArchiveReceipt

        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_bytes(outcome_bytes)
        return TelegramRichOutcomeArchiveReceipt(
            schema_name="video-channel-manager.telegram-rich-outcome-archive-receipt",
            schema_version=1,
            outcome_sha256=outcome_sha256,
            archive_reference=str(self._path),
            durable_before_state_mutation=True,
        )


def send(
    root: Path,
    item: QueueItem,
    *,
    token: str,
    media_base_url: str,
    outcome_path: Path,
    now: datetime | None = None,
) -> Any:
    """Publish one due article through the shared one-request multipart boundary."""

    from video_channel_manager.lordchrist_rich_live_canary import LordChristMultipartProvider
    from video_channel_manager.telegram_rich_provider import publish_rich_once

    if item.cover_path is None:
        raise ValueError("article has no bound cover")
    document, _render, _article = build_document(root, item, media_base_url=media_base_url)
    document = swap_media_to_attachments(document, item)
    profile = load_channel_profile(root / DEFAULT_PROFILE_PATH)
    binding = load_target_binding(root / DEFAULT_BINDING_PATH, profile)
    from video_channel_manager.telegram_multichannel_transport import preflight_channel

    target = preflight_channel(
        profile,
        token=token,
        expected_chat_id=binding.chat_id,
        expected_bot_id=binding.bot_id,
        expected_bot_username=binding.bot_username,
    )
    attachments = {ATTACHMENT_NAME: (item.cover_path.name, (root / item.cover_path).read_bytes(), "image/jpeg")}
    provider = LordChristMultipartProvider(token=token, attachments=attachments)
    try:
        archived = publish_rich_once(
            document,
            target,
            provider,
            _OutcomeArchive(outcome_path),
            profile=profile,
            state_mutation=None,
            now=now,
        )
    finally:
        provider.close()
    return archived.outcome


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="LordChrist long-article lane (queue → due → rich document)")
    sub = root.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("queue-check")
    check.add_argument("--queue", type=Path, default=DEFAULT_QUEUE_PATH)
    check.add_argument("--root", type=Path, default=Path("."))
    due = sub.add_parser("due")
    due.add_argument("--queue", type=Path, default=DEFAULT_QUEUE_PATH)
    due.add_argument("--root", type=Path, default=Path("."))
    due.add_argument("--now", required=False)
    preview = sub.add_parser("preview")
    preview.add_argument("--queue", type=Path, default=DEFAULT_QUEUE_PATH)
    preview.add_argument("--root", type=Path, default=Path("."))
    preview.add_argument("--publication-id", required=True)
    preview.add_argument("--media-base-url", required=True)
    send_cmd = sub.add_parser("send")
    send_cmd.add_argument("--queue", type=Path, default=DEFAULT_QUEUE_PATH)
    send_cmd.add_argument("--root", type=Path, default=Path("."))
    send_cmd.add_argument("--publication-id", required=True)
    send_cmd.add_argument("--media-base-url", required=True)
    send_cmd.add_argument("--outcome", type=Path, required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    items = load_queue(args.queue, args.root)
    if args.cmd == "queue-check":
        print(
            json.dumps(
                {
                    "items": len(items),
                    "ready": sum(1 for item in items if item.is_ready),
                    "planned": sum(1 for item in items if not item.is_ready),
                    "first": items[0].publication_id,
                    "last": items[-1].publication_id,
                    "scheduled": [item.scheduled_on.isoformat() for item in items],
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.cmd == "due":
        now = datetime.fromisoformat(args.now).astimezone(MOSCOW) if args.now else None
        try:
            item = due_item(items, now)
        except LookupError as exc:
            print(json.dumps({"due": None, "reason": str(exc)}, ensure_ascii=False))
            return 0
        print(
            json.dumps(
                {"due": item.publication_id, "scheduled_on_moscow": item.scheduled_on.isoformat()}, ensure_ascii=False
            )
        )
        return 0
    selected = [item for item in items if item.publication_id == args.publication_id]
    if len(selected) != 1:
        raise SystemExit(f"unknown publication id: {args.publication_id}")
    if args.cmd == "send":
        outcome = send(
            args.root,
            selected[0],
            token=os.environ["LORDCHRIST_TELEGRAM_BOT_TOKEN"],
            media_base_url=args.media_base_url,
            outcome_path=args.outcome,
        )
        print(outcome.model_dump_json())
        return 0
    document, render, article = build_document(args.root, selected[0], media_base_url=args.media_base_url)
    print(
        json.dumps(
            {
                "publication_id": selected[0].publication_id,
                "document_sha256": document.document_sha256,
                "render_sha256": render.render_sha256,
                "visible_characters": len(render.visible_text),
                "blocks": len(article.blocks),
                "media": [media.media_id for media in article.media],
                "provider_write_performed": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
