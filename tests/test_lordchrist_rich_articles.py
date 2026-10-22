from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from video_channel_manager.lordchrist_rich_articles import (
    DEFAULT_QUEUE_PATH,
    QueueItem,
    attach_cover,
    build_document,
    due_item,
    load_queue,
    swap_media_to_attachments,
)

ROOT = Path(__file__).resolve().parents[1]
MOSCOW = ZoneInfo("Europe/Moscow")
MEDIA_BASE = "https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/" + "0" * 40


def _queue():
    return load_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)


def test_queue_lists_thirteen_dated_articles_with_three_ready() -> None:
    items = _queue()
    assert len(items) == 13
    assert [item.ordinal for item in items] == list(range(1, 14))
    assert sum(1 for item in items if item.is_ready) == 3
    assert items[0].publication_id == "lordchrist-rich-charnock-01"
    assert items[-1].publication_id == "lordchrist-rich-charnock-13"
    # The first article is the one documented off-slot exception (operator decision);
    # every other date must stay on the Tuesday/Friday midday slot.
    assert items[0].scheduled_on.weekday() not in {1, 4}
    assert all(item.scheduled_on.weekday() in {1, 4} for item in items[1:])


def test_off_slot_date_requires_an_explicit_documented_override() -> None:
    queue = load_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)
    raw = json.loads((ROOT / DEFAULT_QUEUE_PATH).read_text(encoding="utf-8"))
    assert raw["items"][0].get("slot_override_reason")
    assert all("slot_override_reason" not in item for item in raw["items"][1:])
    assert queue[0].scheduled_on.isoformat() == "2026-10-22"


def test_due_item_selects_the_single_article_of_that_midday() -> None:
    today = due_item(_queue(), datetime(2026, 10, 22, 12, 0, tzinfo=MOSCOW))
    assert today.publication_id == "lordchrist-rich-charnock-01"
    next_slot = due_item(_queue(), datetime(2026, 10, 27, 12, 0, tzinfo=MOSCOW))
    assert next_slot.publication_id == "lordchrist-rich-charnock-02"


def test_due_item_is_silent_on_a_day_without_an_article() -> None:
    with pytest.raises(LookupError, match="no LordChrist rich article"):
        due_item(_queue(), datetime(2026, 10, 23, 12, 0, tzinfo=MOSCOW))


def test_due_item_refuses_an_article_that_is_not_ready_yet() -> None:
    with pytest.raises(LookupError, match="is not ready"):
        due_item(_queue(), datetime(2026, 11, 6, 12, 0, tzinfo=MOSCOW))


def test_queue_rejects_article_bytes_that_differ_from_the_reviewed_blob(tmp_path: Path) -> None:
    ready = _queue()[0]
    article = json.loads((ROOT / ready.article_path).read_text(encoding="utf-8"))  # type: ignore[operator]
    article["metadata"]["title"] = "подменённый заголовок"
    changed = tmp_path / "article.json"
    changed.write_text(json.dumps(article, ensure_ascii=False), encoding="utf-8")

    queue = {
        "schema_name": "video-channel-manager.lordchrist-rich-article-queue",
        "schema_version": 1,
        "project_key": "lord-god-strength",
        "channel_username": "@lordchrist",
        "revision": "charnock-v1",
        "items": [
            {
                "publication_id": ready.publication_id,
                "ordinal": 1,
                "scheduled_on_moscow": ready.scheduled_on.isoformat(),
                "slot_override_reason": "тест: дата вне слота заявлена осознанно",
                "status": "ready",
                "article": {"path": "article.json", "git_blob_sha": ready.article_blob},
                "cover": {"path": "cover.jpg", "git_blob_sha": ready.cover_blob, "media_id": "media-cover"},
            }
        ],
    }
    (tmp_path / "cover.jpg").write_bytes((ROOT / ready.cover_path).read_bytes())  # type: ignore[operator]
    (tmp_path / "queue.json").write_text(json.dumps(queue, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="cover bytes differ|article bytes differ"):
        load_queue(tmp_path / "queue.json", tmp_path)


def test_preview_builds_a_rich_document_with_the_bound_cover() -> None:
    item = _queue()[1]
    document, render, article = build_document(ROOT, item, media_base_url=MEDIA_BASE)

    assert document.publication_id == item.publication_id
    assert [media.media_id for media in article.media] == ["media-cover"]
    assert render.visible_text
    assert len(render.visible_text) > 30_000
    assert any(getattr(block, "type", None) == "media" for block in article.blocks)


def test_cover_is_placed_directly_under_the_title() -> None:
    item = _queue()[0]
    _document, _render, article = build_document(ROOT, item, media_base_url=MEDIA_BASE)
    types = [getattr(block, "type", None) for block in article.blocks]
    assert types[0] == "heading"
    assert types[1] == "media"


def test_attaching_the_same_cover_twice_fails_closed() -> None:
    item = _queue()[0]
    document = json.loads((ROOT / item.article_path).read_text(encoding="utf-8"))  # type: ignore[operator]
    from video_channel_manager.telegram_rich_models import RichArticleDocument

    article = attach_cover(RichArticleDocument.model_validate(document), item, MEDIA_BASE)
    with pytest.raises(ValueError, match="already carries the cover media id"):
        attach_cover(article, item, MEDIA_BASE)


def test_swap_replaces_exactly_one_cover_reference() -> None:
    item = _queue()[0]
    document, _render, _article = build_document(ROOT, item, media_base_url=MEDIA_BASE)
    swapped = swap_media_to_attachments(document, item)

    assert swapped.input_rich_message != document.input_rich_message
    blob = json.dumps(swapped.input_rich_message, ensure_ascii=False)
    assert "attach://lc_cover" in blob
    assert MEDIA_BASE not in blob

    with pytest.raises(ValueError, match="expected exactly one cover reference"):
        swap_media_to_attachments(swapped, item)


def test_queue_item_rejects_a_publication_id_from_another_project() -> None:
    item = QueueItem(
        publication_id="svodka-article-01", ordinal=1, scheduled_on=datetime(2026, 10, 27).date(), status="planned"
    )
    assert not item.is_ready


def test_manual_article_dispatch_is_routed_away_from_the_quote_job() -> None:
    workflow = (ROOT / ".github" / "workflows" / "lordchrist-telegram-poster.yml").read_text(encoding="utf-8")
    jobs = workflow.split("\njobs:", 1)[1]
    publish_next = jobs.split("\n  publish-next:", 1)[1].split("\n    runs-on:", 1)[0]
    article = jobs.split("\n  charnock-rich:", 1)[1].split("\n    runs-on:", 1)[0]

    assert "inputs.action == 'publish-article'" in publish_next  # excluded from the quote lane
    assert "inputs.action == 'publish-article'" in article
    assert "github.event.schedule == '0 9 * * 2,5'" in article
