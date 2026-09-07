from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from video_channel_manager.telegram_historical_bundle import load_source_catalog
from video_channel_manager.telegram_historical_editorial import (
    HistoricalEditorialQueueV1,
    HistoricalPost,
    HistoricalSchedule,
    HistoricalVerification,
    _validate_post_evidence,
    build_historical_rich_document,
    load_theology_profile,
)
from video_channel_manager.telegram_rich_models import RichBlockDetails
from video_channel_manager.telegram_rich_validation import plain_text

ROOT = Path(__file__).resolve().parents[1]
CYCLE_DIR = ROOT / "content/telegram/lordchrist/historical-editorial/v1/cycles/2026-09-cycle-02"
SOURCE_CATALOG = ROOT / "content/telegram/lordchrist/historical-editorial/v1/source-catalog.json"
THEOLOGY_PROFILE = ROOT / "content/telegram/lordchrist/historical-editorial/v1/theology-profile.json"
POST_FILES = (
    "01-spurgeon-down-grade-1887.json",
    "02-bunyan-bedford-prison.json",
    "03-judson-burmese-bible.json",
    "04-spurgeon-cholera.json",
    "05-carey-enquiry-missions.json",
    "06-fuller-gospel-worthy.json",
    "07-tyndale-new-testament-1526.json",
    "08-stam-china-december-1934.json",
    "09-sattler-schleitheim-1527.json",
)
BANNED_READER_PHRASES = (
    "Что установлено источниками",
    "Богословская оценка",
    "От истории к оценке",
    "Источники и границы уверенности",
    "где заканчивается документ",
    "в этой версии цикла",
    "современное исследование",
    "исследования показывают",
    "исследователи обычно",
    "по принятой исторической реконструкции",
    "академическая реконструкция",
)


def _load_posts() -> tuple[HistoricalPost, ...]:
    return tuple(
        HistoricalPost.model_validate(json.loads((CYCLE_DIR / "posts" / filename).read_text(encoding="utf-8")))
        for filename in POST_FILES
    )


def _queue() -> tuple[HistoricalEditorialQueueV1, object]:
    catalog, registry = load_source_catalog(SOURCE_CATALOG, repo_root=ROOT)
    theology = load_theology_profile(THEOLOGY_PROFILE)
    posts = _load_posts()
    for post in posts:
        _validate_post_evidence(post, registry, theology, date(2026, 9, 7))

    queue = HistoricalEditorialQueueV1(
        schema_name="video-channel-manager.telegram-historical-editorial-queue",
        schema_version=1,
        project_key="lord-god-strength",
        channel_username="@lordchrist",
        series_id="series-history-2026-09-cycle-02",
        purpose="evidence_backed_historical_edification",
        state="provider_inert",
        verification=HistoricalVerification(
            reviewed_urls=69,
            checked_on=date(2026, 9, 7),
            method="a_bplus_primary_archive_scholarly_crosscheck",
            production_threshold="A_or_B_plus_only",
            editorial_language="ru",
            anti_ranking=True,
        ),
        schedule=HistoricalSchedule(
            state="staged",
            provider_writes_authorized=False,
            activation_policy="manual_after_verified_historical_rich_canary",
            timezone="Europe/Moscow",
            local_time="19:17",
            iso_weekdays=(1, 3, 6),
            posts_per_week=3,
            max_verified_per_day=2,
            backfill_policy="none",
        ),
        source_binding_kind="catalog",
        source_binding_path="content/telegram/lordchrist/historical-editorial/v1/source-catalog.json",
        source_binding_sha256=catalog.digest,
        source_registry_sha256=registry.digest,
        theology_profile_path="content/telegram/lordchrist/historical-editorial/v1/theology-profile.json",
        theology_profile_sha256=theology.digest,
        posts=posts,
    )
    return queue, registry


def test_human_cycle_v2_all_nine_posts_pass_sealed_evidence_contract() -> None:
    queue, _registry = _queue()

    assert tuple(post.sequence for post in queue.posts) == tuple(range(1, 10))
    assert tuple(post.release_offset_days for post in queue.posts) == (0, 2, 5, 7, 9, 12, 14, 16, 19)
    assert len({post.publication_id for post in queue.posts}) == 9
    assert all(post.publication_id.endswith("-v2") for post in queue.posts)
    assert all(post.editorial_status == "ready" for post in queue.posts)
    assert all(post.fact_check_status == "accepted" for post in queue.posts)


def test_human_cycle_v2_reader_copy_hides_internal_audit_memo_language() -> None:
    queue, registry = _queue()

    for post in queue.posts:
        article = build_historical_rich_document(queue, post, registry)
        visible = plain_text(article)
        block_ids = {getattr(block, "block_id", "") for block in article.blocks}

        assert article.revision == "historical-human-v2"
        assert {"h-evidence", "p-evidence", "h-theology", "p-theology"}.isdisjoint(block_ids)
        assert all(phrase.casefold() not in visible.casefold() for phrase in BANNED_READER_PHRASES)
        source_drawers = [
            block for block in article.blocks if isinstance(block, RichBlockDetails) and block.block_id == "d-sources"
        ]
        assert len(source_drawers) == 1
        assert source_drawers[0].summary == "Источники"


def test_human_cycle_v2_has_concrete_history_not_search_summary_prose() -> None:
    queue, _registry = _queue()

    concrete_markers = (
        "1887",
        "1660",
        "1824",
        "1854",
        "1792",
        "1785",
        "1526",
        "1934",
        "1527",
    )
    for post, marker in zip(queue.posts, concrete_markers, strict=True):
        reader_text = " ".join(
            [post.title, post.lead, *(paragraph for section in post.sections for paragraph in section.paragraphs)]
        )
        assert marker in reader_text
        assert len(post.sections) >= 4
        assert len(reader_text) >= 1800
