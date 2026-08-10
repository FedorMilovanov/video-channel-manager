from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from video_channel_manager.telegram_publisher import initialize_ledger, load_queue, preview_next

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/lordchrist/verified-30-posts.json"
EXPECTED_QUEUE_DIGEST = "sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"


def _publish(entry: object, *, at: datetime, message_id: int) -> None:
    entry.state = "published"  # type: ignore[attr-defined]
    entry.provider_effect = "verified"  # type: ignore[attr-defined]
    entry.published_at_utc = at  # type: ignore[attr-defined]
    entry.message_id = message_id  # type: ignore[attr-defined]


def _historical_four_bunyan() -> tuple[object, object]:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    start = datetime(2026, 8, 7, 12, 14, tzinfo=UTC)
    for offset, post in enumerate(queue.posts[:4]):
        _publish(
            ledger.entries[post.publication_id],
            at=start + timedelta(days=offset),
            message_id=1470 + offset,
        )
    return queue, ledger


def test_editorial_rotation_keeps_immutable_queue_identity() -> None:
    queue = load_queue(QUEUE_PATH)
    assert queue.digest == EXPECTED_QUEUE_DIGEST
    assert queue.posts[0].source.author == "Джон Беньян"
    assert queue.posts[4].source.author == "Джон Беньян"
    assert queue.posts[5].source.author == "Чарльз Сперджен"


def test_four_historical_bunyan_posts_rotate_next_to_spurgeon() -> None:
    queue, ledger = _historical_four_bunyan()

    preview = preview_next(queue, ledger)

    assert preview.post is not None
    assert preview.post.publication_id == "lordchrist-spurgeon-putting-away-sin"
    assert preview.post.source.author == "Чарльз Сперджен"
    assert "editorial author rotation" in preview.reason


def test_rotation_continues_across_authors_without_rewriting_source_order() -> None:
    queue, ledger = _historical_four_bunyan()

    spurgeon = ledger.entries["lordchrist-spurgeon-putting-away-sin"]
    _publish(spurgeon, at=datetime(2026, 8, 11, 7, 17, tzinfo=UTC), message_id=1501)

    preview = preview_next(queue, ledger)
    assert preview.post is not None
    assert preview.post.publication_id == "lordchrist-calvin-prayer-treasures"
    assert preview.post.source.author == "Жан Кальвин"

    calvin = ledger.entries["lordchrist-calvin-prayer-treasures"]
    _publish(calvin, at=datetime(2026, 8, 12, 7, 17, tzinfo=UTC), message_id=1502)

    preview = preview_next(queue, ledger)
    assert preview.post is not None
    assert preview.post.publication_id == "lordchrist-owen-mortify-daily"
    assert preview.post.source.author == "Джон Оуэн"


def test_rotation_never_bypasses_unresolved_provider_effect() -> None:
    queue, ledger = _historical_four_bunyan()
    unresolved = ledger.entries["lordchrist-bunyan-burdened-man"]
    unresolved.state = "unknown"
    unresolved.provider_effect = "may_exist"

    preview = preview_next(queue, ledger)

    assert preview.post is None
    assert "strict queue blocked" in preview.reason
    assert "lordchrist-bunyan-burdened-man" in preview.reason
