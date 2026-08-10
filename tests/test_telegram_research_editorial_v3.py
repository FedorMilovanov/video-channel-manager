from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_research import validate_public_copy
from video_channel_manager.telegram_research_editorial_v3 import (
    build_editorial_successor_candidate,
    load_editorial_successor,
    normalize_presentation_html,
    validate_rich_presentation,
)

ROOT = Path(__file__).parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/lordchrist.json"
PACKAGE_PATH = ROOT / "content/telegram/lordchrist/research-queues/editorial-successor-v3.json"


def test_editorial_successor_covers_only_unpublished_research_posts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    package = load_editorial_successor(PACKAGE_PATH)

    assert package.state == "provider_inert"
    assert package.predecessor_approved_release_digest == (
        "sha256:b836f9dc6733cdc922e5aaed97c250d1d46484fe75a216c1f12e586214a2626f"
    )
    assert [post.predecessor_sequence for post in package.posts] == [2, 3, 4, 5]
    assert all(post.predecessor_publication_id != post.publication_id for post in package.posts)
    assert "lordchrist-research-three-preachers-numbers" not in {
        post.predecessor_publication_id for post in package.posts
    }


def test_rich_presentations_preserve_exact_reader_copy_and_have_real_hierarchy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(ROOT)
    package = load_editorial_successor(PACKAGE_PATH)

    for post in package.posts:
        body = validate_public_copy(Path(post.body_path).read_text(encoding="utf-8"))
        presentation = normalize_presentation_html(Path(post.presentation_path).read_text(encoding="utf-8"))
        entities = validate_rich_presentation(body, presentation)

        assert presentation.startswith("<b>")
        assert sum(entity.type == "bold" for entity in entities) >= 2
        assert any(entity.type == "italic" for entity in entities)
        assert not any(entity.type == "text_link" for entity in entities)
        assert body.split("\n\n")[-1].startswith("✦ ")
        assert "бог" in body.split("\n\n")[-1].casefold()


def test_editorial_successor_builds_four_item_rich_provider_inert_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(ROOT)
    profile = load_channel_profile(PROFILE_PATH)
    package = load_editorial_successor(PACKAGE_PATH)
    release = build_editorial_successor_candidate(
        profile,
        package,
        release_id="lordchrist-research-editorial-v3-2026-08",
        start_at=datetime(2026, 8, 12, 15, 0, tzinfo=ZoneInfo("Europe/Moscow")),
    )

    assert release.release_authorized is False
    assert release.target_binding_sha256 is None
    assert [item.scheduled_at for item in release.items] == [
        datetime(2026, 8, day, 15, 0, tzinfo=ZoneInfo("Europe/Moscow")) for day in (12, 14, 16, 18)
    ]
    assert [item.publication_id for item in release.items] == [post.publication_id for post in package.posts]
    for item, post in zip(release.items, package.posts, strict=True):
        body = validate_public_copy(Path(post.body_path).read_text(encoding="utf-8"))
        assert item.payload.expected_plain_text == body
        assert len(item.payload.expected_entities) >= 3
        assert {entity.type for entity in item.payload.expected_entities} >= {"bold", "italic"}
        assert item.source_sha256 == post.digest


def test_rich_presentation_rejects_visible_text_drift() -> None:
    body = ("🕯️ Заголовок\n\n" + "Точный проверенный текст. " * 30 + "\n\n✦ Благодарим Бога за верный труд.")
    presentation = "<b>🕯️ Заголовок</b>\n\n" + "Подменённый текст. " * 30 + "\n\n<i>✦ Благодарим Бога за верный труд.</i>"

    with pytest.raises(ValueError, match="changes canonical reader text"):
        validate_rich_presentation(body, presentation)


def test_rich_presentation_rejects_heading_only_formatting() -> None:
    body = ("🕯️ Заголовок\n\n" + "Точный проверенный текст. " * 30 + "\n\n✦ Благодарим Бога за верный труд.")
    presentation = "<b>🕯️ Заголовок</b>\n\n" + "Точный проверенный текст. " * 30 + "\n\n✦ Благодарим Бога за верный труд."

    with pytest.raises(ValueError, match="italic reflection"):
        validate_rich_presentation(body, presentation)
