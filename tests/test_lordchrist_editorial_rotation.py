from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from video_channel_manager.telegram_publisher import (
    LedgerEntry,
    TelegramLedger,
    TelegramQueue,
    initialize_ledger,
    load_queue,
    preview_next,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/lordchrist/verified-30-posts.json"
EXPECTED_QUEUE_DIGEST = "sha256:43d1b07013bf6f9ffc578265f74ebc0c35d693066838fc9367fd5e839763cc11"


def _publish(entry: LedgerEntry, *, at: datetime, message_id: int) -> None:
    entry.state = "published"
    entry.provider_effect = "verified"
    entry.published_at_utc = at
    entry.message_id = message_id


def _historical_four_bunyan() -> tuple[TelegramQueue, TelegramLedger]:
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
    assert len(queue.posts) == 30
    # The v4 Puritan/Spurgeon queue deliberately spans multiple classic authors;
    # rotation simply walks the queue in order after the published prefix.
    assert len({post.source.author for post in queue.posts}) >= 5


def test_four_published_posts_rotate_to_fifth() -> None:
    queue, ledger = _historical_four_bunyan()

    preview = preview_next(queue, ledger)

    assert preview.post is not None
    assert preview.post.publication_id == queue.posts[4].publication_id
    assert preview.post.source.author == queue.posts[4].source.author


def test_rotation_continues_across_authors_without_rewriting_source_order() -> None:
    queue, ledger = _historical_four_bunyan()

    fifth = ledger.entries[queue.posts[4].publication_id]
    _publish(fifth, at=datetime(2026, 10, 29, 7, 0, tzinfo=UTC), message_id=1501)

    preview = preview_next(queue, ledger)
    assert preview.post is not None
    assert preview.post.publication_id == queue.posts[5].publication_id
    assert preview.post.source.author == queue.posts[5].source.author

    sixth = ledger.entries[queue.posts[5].publication_id]
    _publish(sixth, at=datetime(2026, 10, 30, 7, 0, tzinfo=UTC), message_id=1502)

    preview = preview_next(queue, ledger)
    assert preview.post is not None
    assert preview.post.publication_id == queue.posts[6].publication_id
    assert preview.post.source.author == queue.posts[6].source.author


def test_rotation_never_bypasses_unresolved_provider_effect() -> None:
    queue, ledger = _historical_four_bunyan()
    first_post = queue.posts[0]
    unresolved = ledger.entries[first_post.publication_id]
    unresolved.state = "unknown"
    unresolved.provider_effect = "may_exist"

    preview = preview_next(queue, ledger)

    assert preview.post is None
    assert "strict queue blocked" in preview.reason
    assert first_post.publication_id in preview.reason
