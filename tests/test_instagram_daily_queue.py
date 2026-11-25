import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from video_channel_manager.instagram.daily_queue import (
    PUBLISHED_SOURCE_IDS,
    RIGHTS_REVIEW,
    build_legendary_poet_daily_queue,
    detect_author,
    queue_sha256,
    select_daily_queue_item,
)

SNAPSHOT = (
    Path(__file__).resolve().parents[1]
    / "content"
    / "instagram"
    / "legendary-poet-youtube-shorts-snapshot-20260912.json"
)


def _queue():
    return build_legendary_poet_daily_queue(
        SNAPSHOT,
        account_id="17841435926122104",
        start_at=datetime(2026, 9, 14, 19, 0, tzinfo=timezone(timedelta(hours=3))),
    )


def test_full_short_inventory_partitions_without_duplicates() -> None:
    queue = _queue()
    assert queue.item_count == 62
    assert queue.published_count == 2
    assert queue.rights_review_count == 6
    assert queue.ready_count == 54
    assert {item.source_id for item in queue.items if item.status == "published"} == PUBLISHED_SOURCE_IDS
    assert {item.source_id for item in queue.items if item.status == "rights_review"} == set(RIGHTS_REVIEW)
    assert len({item.source_id for item in queue.items}) == 62
    assert len({item.publication_key for item in queue.items}) == 62


def test_ready_schedule_is_daily_and_seo_bounded() -> None:
    queue = _queue()
    ready = sorted(
        (item for item in queue.items if item.status == "ready"),
        key=lambda item: item.scheduled_at,
    )
    assert ready[0].scheduled_at.isoformat() == "2026-09-14T19:00:00+03:00"
    assert ready[-1].scheduled_at - ready[0].scheduled_at == timedelta(days=53)
    assert all(len(item.hashtags) <= 5 for item in ready)
    assert all(len(item.caption) <= 2200 for item in ready)
    assert all("#TheLegendaryPoet" in item.hashtags for item in ready)
    assert all(item.width < item.height for item in ready)
    assert all(item.duration_seconds <= 180 for item in ready)


def test_priority_queue_starts_with_proven_short_and_diversifies_authors() -> None:
    queue = _queue()
    ready = sorted(
        (item for item in queue.items if item.status == "ready"),
        key=lambda item: item.scheduled_at,
    )
    assert ready[0].source_id == "7IP9_wxDTAc"
    for left, right in zip(ready, ready[1:], strict=False):
        if left.author is not None and right.author is not None:
            assert left.author != right.author


def test_queue_digest_is_stable_sha256() -> None:
    digest = queue_sha256(_queue())
    assert digest.startswith("sha256:")
    assert len(digest) == 71


def test_detect_author_title_outweighs_noisy_tags_and_ambiguity_fails_closed() -> None:
    assert detect_author("Скифы — Александр Блок", ["Александр Пушкин"]) == "Александр Блок"
    assert detect_author("Парус — Михаил Лермонтов", ["Александр Пушкин"]) == "Михаил Лермонтов"
    assert detect_author("Лирика классиков", ["Александр Пушкин"]) == "Александр Пушкин"
    assert detect_author("Есенин и Маяковский", ["Александр Пушкин"]) is None
    assert detect_author("Пейзаж", ["Блок", "Пушкин"]) is None
    assert detect_author("Блокнот поэта", []) is None
    assert detect_author("РЭП от Пушкина — Зимний вечер", []) == "Александр Пушкин"
    assert detect_author("Зимняя мистика Сергея Есенина", []) == "Сергей Есенин"
    assert detect_author("Пушкина и Есенина", ["Александр Пушкин"]) is None
    assert detect_author("Пушкиназвание", []) is None


def test_frozen_snapshot_rebuild_identifies_real_title_authors() -> None:
    by_id = {item.source_id: item for item in _queue().items}
    assert by_id["F5kgP197YUE"].author == "Александр Блок"
    assert by_id["156l_su1P48"].author == "Александр Блок"
    assert by_id["x-TPtQ9E2mc"].author == "Михаил Лермонтов"
    assert by_id["d50lIlqZed4"].author == "Анна Ахматова"
    assert by_id["FKtflEKl-NY"].author == "Александр Пушкин"
    assert by_id["Sdv8puPeJYw"].author == "Сергей Есенин"


def _ledger(tmp_path, rows=()):
    database = tmp_path / "configured-ledger.db"
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute(
            "create table instagram_publications (publication_key text primary key, account_id text, status text)"
        )
        connection.executemany("insert into instagram_publications values (?, ?, ?)", rows)
    return f"sqlite:///{database.as_posix()}"


@pytest.mark.parametrize(
    "status",
    [
        "container_requested",
        "container_unknown",
        "container_created",
        "processing",
        "ready",
        "publish_requested",
        "publish_unknown",
        "published_unresolved",
        "retryable_failure",
        "terminal_failure",
        "unexpected_status",
    ],
)
def test_daily_selection_refuses_nonfinal_state_for_both_modes(tmp_path, status):
    queue = _queue()
    first = min((item for item in queue.items if item.status == "ready"), key=lambda item: item.scheduled_at)
    url = _ledger(tmp_path, [(first.publication_key, queue.account_id, status)])
    for source_id in (None, first.source_id):
        with pytest.raises(ValueError, match="durable ledger status is"):
            select_daily_queue_item(queue, url, source_id)


def test_daily_selection_skips_published_but_allows_planned(tmp_path):
    queue = _queue()
    first, second = sorted(
        (item for item in queue.items if item.status == "ready"), key=lambda item: item.scheduled_at
    )[:2]
    url = _ledger(
        tmp_path,
        [(first.publication_key, queue.account_id, "published"), (second.publication_key, queue.account_id, "planned")],
    )
    assert select_daily_queue_item(queue, url) == second
    assert select_daily_queue_item(queue, url, second.source_id) == second
    with pytest.raises(ValueError, match="already published"):
        select_daily_queue_item(queue, url, first.source_id)


def test_daily_selection_requires_existing_ledger_and_exact_account(tmp_path):
    queue = _queue()
    first = min((item for item in queue.items if item.status == "ready"), key=lambda item: item.scheduled_at)
    absent = tmp_path / "absent.db"
    with pytest.raises(ValueError, match="ledger is missing"):
        select_daily_queue_item(queue, f"sqlite:///{absent.as_posix()}")
    assert not absent.exists()
    with pytest.raises(ValueError, match="file-backed SQLite"):
        select_daily_queue_item(queue, "sqlite:///:memory:")
    url = _ledger(tmp_path, [(first.publication_key, "other-account", "planned")])
    with pytest.raises(ValueError, match="account differs"):
        select_daily_queue_item(queue, url, first.source_id)


def test_daily_selection_empty_and_complete_queue(tmp_path):
    queue = _queue()
    ready = sorted(
        (item for item in queue.items if item.status == "ready"), key=lambda item: item.scheduled_at
    )
    url = _ledger(tmp_path, [(item.publication_key, queue.account_id, "published") for item in ready])
    assert select_daily_queue_item(queue, url) is None
    with pytest.raises(ValueError, match="not a ready queue item"):
        select_daily_queue_item(queue, url, "missing-source")
    non_ready = tuple(item for item in queue.items if item.status != "ready")
    no_ready = queue.model_copy(update={"items": non_ready, "item_count": len(non_ready), "ready_count": 0})
    with pytest.raises(ValueError, match="no ready Instagram Reels"):
        select_daily_queue_item(no_ready, url)


def test_daily_selection_missing_key_uses_existing_ledger_read_only(tmp_path):
    queue = _queue()
    first = min((item for item in queue.items if item.status == "ready"), key=lambda item: item.scheduled_at)
    url = _ledger(tmp_path)
    database = tmp_path / "configured-ledger.db"
    before = database.read_bytes()
    assert select_daily_queue_item(queue, url) == first
    assert select_daily_queue_item(queue, url, first.source_id) == first
    assert database.read_bytes() == before
