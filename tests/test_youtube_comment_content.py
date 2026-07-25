from __future__ import annotations

from copy import deepcopy

from video_channel_manager.platforms.youtube.comment_content import (
    canonicalize_url,
    extract_urls,
    render_comment_content,
    validate_comment_content,
)


def _legacy_record() -> dict[str, object]:
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


def _v2_record() -> dict[str, object]:
    return {
        "schema_name": "video-manager.youtube-comment-content",
        "schema_version": 2,
        "status": "approved",
        "profile": "long_form_poetry",
        "variation_key": "blok-publication-history-1908-v1",
        "channel_id": "channel-1",
        "video_id": "video-2",
        "video_title": "Title",
        "reviewed_at": "2026-07-25T12:00:00+00:00",
        "source_ids": ["primary", "playlist"],
        "fact": {
            "heading": "📖 *История публикации*",
            "fact_type": "first_publication",
            "source_ids": ["primary"],
            "text": (
                "Стихотворение датировано 1908 годом и было напечатано в составе авторского цикла; "
                "издательская история помогает увидеть, что текст задумывался не как случайная отдельная миниатюра."
            ),
        },
        "question": {
            "lead": "_Вопрос к слушателю:_",
            "text": "Какой структурный переход в этой музыкальной версии слышится вам наиболее отчётливо?",
        },
        "links": [
            {"kind": "site", "label": "📌 *The Legendary Poet:*", "url": "https://thelegendarypoet.ru/"},
            {
                "kind": "playlist",
                "label": "🎧 *Александр Блок — плейлист:*",
                "url": "https://www.youtube.com/playlist?list=PLy9lLJfoq3ua3Q9BQe1Dhuzn7Knbz2djU",
            },
            {"kind": "vk", "label": "*Сообщество проекта VK:*", "url": "https://vk.com/thelegendarypoet"},
            {"kind": "primary_text", "label": "📚 _Полный текст:_", "url": "https://example.org/source"},
        ],
        "sources": [
            {"source_id": "primary", "title": "Primary", "url": "https://example.org/source"},
            {
                "source_id": "playlist",
                "title": "Playlist",
                "url": "https://www.youtube.com/playlist?list=PLy9lLJfoq3ua3Q9BQe1Dhuzn7Knbz2djU",
            },
        ],
    }


def test_legacy_approved_sourced_content_is_valid() -> None:
    assert validate_comment_content(_legacy_record(), expected_channel_id="channel-1") == []


def test_v2_deep_fact_content_is_valid_and_compact() -> None:
    record = _v2_record()
    assert validate_comment_content(record, expected_channel_id="channel-1") == []
    rendered = render_comment_content(record)
    assert "📌 *The Legendary Poet:* https://thelegendarypoet.ru/" in rendered
    assert "*Сообщество проекта VK:* https://vk.com/thelegendarypoet" in rendered
    assert "VK:\n" not in rendered
    assert "🔵" not in rendered


def test_v2_rejects_coloured_circle_and_orphan_vk_label() -> None:
    record = deepcopy(_v2_record())
    fact = record["fact"]
    links = record["links"]
    assert isinstance(fact, dict)
    assert isinstance(links, list)
    fact["heading"] = "🔵 *История публикации*"
    vk = links[2]
    assert isinstance(vk, dict)
    vk["label"] = "VK:"
    errors = validate_comment_content(record)
    assert "colored circle markers are not allowed" in errors
    assert "VK link label must be exactly *Сообщество проекта VK:*" in errors


def test_v2_requires_substantial_fact_and_exact_evidence_mapping() -> None:
    record = deepcopy(_v2_record())
    fact = record["fact"]
    assert isinstance(fact, dict)
    fact["text"] = "Короткий общий факт."
    fact["source_ids"] = ["missing"]
    errors = validate_comment_content(record)
    assert "fact.text must contain a substantial 100-900 character sourced fact" in errors
    assert "fact.source_ids missing from source_ids: missing" in errors


def test_unknown_source_id_is_rejected() -> None:
    record = deepcopy(_legacy_record())
    source_ids = record["source_ids"]
    assert isinstance(source_ids, list)
    source_ids.append("invented-source")
    errors = validate_comment_content(record)
    assert "source_ids missing from sources: invented-source" in errors


def test_unregistered_comment_url_is_rejected() -> None:
    record = deepcopy(_legacy_record())
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
    record = deepcopy(_legacy_record())
    sources = record["sources"]
    assert isinstance(sources, list)
    second = sources[1]
    assert isinstance(second, dict)
    second["path"] = "../outside.md"
    errors = validate_comment_content(record)
    assert "source editorial-links has an unsafe repository path" in errors
