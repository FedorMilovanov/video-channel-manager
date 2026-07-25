from __future__ import annotations

from copy import deepcopy

from video_channel_manager.platforms.youtube.comment_content import (
    canonicalize_url,
    extract_urls,
    validate_comment_content,
)


def _record() -> dict[str, object]:
    return {
        "schema_name": "video-manager.youtube-comment-content",
        "schema_version": 1,
        "status": "approved",
        "channel_id": "channel-1",
        "video_id": "video-1",
        "video_title": "Title",
        "reviewed_at": "2026-07-25T12:00:00+00:00",
        "source_ids": ["primary", "editorial-links"],
        "comment_text": (
            "Проверенный факт.\n\n"
            "https://thelegendarypoet.ru/\n"
            "https://www.youtube.com/playlist?list=PLy9lLJfoq3ua3Q9BQe1Dhuzn7Knbz2djU\n"
            "https://example.org/source"
        ),
        "sources": [
            {"source_id": "primary", "title": "Primary", "url": "https://example.org/source"},
            {
                "source_id": "editorial-links",
                "title": "Editorial links",
                "path": "docs/youtube-comment-editorial-standard.md",
            },
        ],
    }


def test_approved_sourced_content_is_valid() -> None:
    assert validate_comment_content(_record(), expected_channel_id="channel-1") == []


def test_unknown_source_id_is_rejected() -> None:
    record = deepcopy(_record())
    source_ids = record["source_ids"]
    assert isinstance(source_ids, list)
    source_ids.append("invented-source")
    errors = validate_comment_content(record)
    assert "source_ids missing from sources: invented-source" in errors


def test_unregistered_comment_url_is_rejected() -> None:
    record = deepcopy(_record())
    record["comment_text"] = str(record["comment_text"]) + "\nhttps://invented.example/path"
    errors = validate_comment_content(record)
    assert any(error.startswith("comment contains URLs absent from sources/project link map") for error in errors)


def test_url_canonicalization_removes_fragments_and_default_ports() -> None:
    assert canonicalize_url("HTTPS://Example.ORG:443/path/#section") == "https://example.org/path"
    assert extract_urls("Источник: https://example.org/path).") == ["https://example.org/path"]


def test_url_canonicalization_preserves_balanced_parentheses() -> None:
    url = "https://ru.wikisource.org/wiki/О,_я_хочу_безумно_жить_(Блок)"
    assert canonicalize_url(url) == url
    assert extract_urls(f"Полный текст: {url}.") == [url]


def test_unsafe_repository_source_path_is_rejected() -> None:
    record = deepcopy(_record())
    sources = record["sources"]
    assert isinstance(sources, list)
    second = sources[1]
    assert isinstance(second, dict)
    second["path"] = "../outside.md"
    errors = validate_comment_content(record)
    assert "source editorial-links has an unsafe repository path" in errors
