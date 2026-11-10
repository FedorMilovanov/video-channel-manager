"""Regression proof for the optional source-locked poetry Shorts preflight.

Test data is synthetic: URLs, edition labels and verses are STRUCTURAL FIXTURES,
not verified literary sources or publication-ready quotations.
"""

from __future__ import annotations

from copy import deepcopy

from video_channel_manager.editorial._project_profiles import (
    LEGENDARY_POET_AUTHOR_PLAYLISTS,
    PROJECT_LINK_PROFILES,
)
from video_channel_manager.poetry_quote_shorts import validate_poetry_quote_packet


def packet() -> dict:
    edition = [
        "Тебе, горный край, я посвящаю строки,",
        "И осени вершиной белоснежной.",
        "На высоте живут мои дороги.",
    ]
    pin = (
        "*«Вымышленное учебное стихотворение»* — Тестовый Поэт.\n\n"
        "Весь сохранившийся текст чернового учебного образца:\n"
        + "\n".join(edition)
        + "\n\nhttps://thelegendarypoet.ru/"
    )
    return {
        "schema_version": 1,
        "project_key": "legendary-poet",
        "poet": "Тестовый Поэт",
        "work": "Вымышленное учебное стихотворение",
        "edition": {
            "author": "Тестовый Поэт",
            "work": "Вымышленное учебное стихотворение",
            "citation": "Synthetic test fixture — NOT a real academic edition",
            "version": "synthetic draft",
            "url": "https://example.org/test-edition",
            "state": "draft",
        },
        "sources": [
            {
                "url": "https://example.org/test-edition",
                "citation": "Synthetic fixture A",
                "class": "critical_edition",
            },
            {"url": "https://example.net/test-notes", "citation": "Synthetic fixture B", "class": "commentary"},
        ],
        "edition_lines": edition,
        "excerpt_lines": edition[:2],
        "excerpt_start_line": 1,
        "tts_lines": [
            "Тебе, горный край, я посвящаю строки,",
            "И осени́ вершиной белоснежной.",
        ],
        "full_comment_lines": edition,
        "pronunciation_notes": [{"token": "осени", "stressed": "осени́", "sense": "повелительное наклонение"}],
        "author_playlist": None,
        "other_playlists": ["https://www.youtube.com/playlist?list=PLy9lLJfoq3uaxXMvilfZIYVXsf4fY18T8"],
        "format_mode": "short_two_comments",
        "short_description": "Это пример короткого описания, а не готового текста для публикации." * 2,
        "pinned_comment": pin,
        "history_comment": (
            "Это структурный тест, намеренно использующий вымышленного автора и источники. "
            "Он доказывает, что валидатор различает выбранную редакцию, дословный фрагмент, "
            "ударение и отдельный исследовательский комментарий, но не проверяет историю литературы. "
            "Текст не предназначен для публичной публикации на канале."
        ),
        "audio_review": {"status": "unverified"},
    }


def codes(payload: dict, *, require_audio_review: bool = False) -> set[str]:
    return {issue.code for issue in validate_poetry_quote_packet(payload, require_audio_review=require_audio_review)}


def test_structural_fixture_passes_without_claiming_source_authenticity_or_audio() -> None:
    assert not codes(packet())


def test_rejects_other_poet_even_when_lines_are_unchanged() -> None:
    candidate = packet()
    candidate["poet"] = "Александр Пушкин"
    assert "edition_mismatch" in codes(candidate)


def test_rejects_variant_collage_and_noncontiguous_lines() -> None:
    candidate = packet()
    candidate["excerpt_lines"][1] = "Иное продолжение из чужой редакции."
    assert "excerpt_not_contiguous" in codes(candidate)


def test_requires_explicit_edition_start_line() -> None:
    candidate = packet()
    candidate["excerpt_start_line"] = 2
    assert "excerpt_not_contiguous" in codes(candidate)


def test_tts_may_add_accents_but_not_edit_words_or_punctuation() -> None:
    candidate = packet()
    candidate["tts_lines"][0] = "Тебе, горный край, я снова посвящаю строки,"
    assert "tts_text_drift" in codes(candidate)


def test_detects_wrong_stress_against_verified_pronunciation_note() -> None:
    candidate = packet()
    candidate["tts_lines"][1] = "И осе́ни вершиной белоснежной."
    results = codes(candidate)
    assert "stress_not_in_tts" in results
    assert "unreviewed_stress" in results


def test_detects_inconsistent_pronunciation_note() -> None:
    candidate = packet()
    candidate["pronunciation_notes"][0]["stressed"] = "осени"
    assert "stress_mark" in codes(candidate)


def test_fails_when_full_pin_poem_omits_a_line() -> None:
    candidate = packet()
    candidate["pinned_comment"] = candidate["pinned_comment"].replace(
        "На высоте живут мои дороги.", ""
    )
    assert "pin_text_missing" in codes(candidate)


def test_fails_when_full_text_is_from_another_edition() -> None:
    candidate = packet()
    candidate["full_comment_lines"][2] = "Другая строка из чужой редакции."
    assert "full_text_mismatch" in codes(candidate)


def test_draft_is_not_misrepresented_as_finished_poem() -> None:
    candidate = packet()
    candidate["pinned_comment"] = candidate["pinned_comment"].replace("сохранившийся", "окончательный")
    assert "draft_disclosure" in codes(candidate)


def test_second_comment_cannot_republish_entire_poem() -> None:
    candidate = packet()
    candidate["history_comment"] += "\n" + "\n".join(candidate["edition_lines"])
    assert "duplicated_poem" in codes(candidate)


def test_must_supply_two_distinct_sources_and_true_edition_record() -> None:
    candidate = packet()
    candidate["sources"][1]["url"] = candidate["sources"][0]["url"]
    assert "source_independence" in codes(candidate)
    candidate = packet()
    candidate["sources"][0]["url"] = "http://example.org/bad"
    assert "source_record" in codes(candidate)


def test_playlist_links_must_match_registered_author() -> None:
    candidate = packet()
    candidate["poet"] = "Михаил Лермонтов"
    candidate["edition"]["author"] = "Михаил Лермонтов"
    candidate["author_playlist"] = LEGENDARY_POET_AUTHOR_PLAYLISTS["Сергей Есенин"]
    assert "author_playlist_mismatch" in codes(candidate)


def test_unknown_quote_playlist_holds_until_exact_registration() -> None:
    candidate = packet()
    candidate["other_playlists"] = ["https://www.youtube.com/playlist?list=PLKcHOT3kiGT4"]
    assert "unknown_playlist" in codes(candidate)


def test_audio_requires_a_real_review_receipt_for_strict_preflight() -> None:
    candidate = packet()
    assert "audio_unverified" in codes(candidate, require_audio_review=True)
    candidate["audio_review"] = {"status": "reviewed", "reviewer": "Operator", "sha256": "c" * 64}
    assert not codes(candidate, require_audio_review=True)
    candidate["audio_review"]["sha256"] = "not-a-sha"
    assert "audio_receipt" in codes(candidate, require_audio_review=True)


def test_declared_author_playlists_are_all_present_in_shared_profile() -> None:
    public_links = PROJECT_LINK_PROFILES["legendary-poet"]
    assert len(LEGENDARY_POET_AUTHOR_PLAYLISTS) >= 12
    assert set(LEGENDARY_POET_AUTHOR_PLAYLISTS.values()).issubset(public_links)


def test_the_validator_never_invokes_a_provider_writer() -> None:
    import inspect
    import video_channel_manager.poetry_quote_shorts as module

    source = inspect.getsource(module)
    for forbidden in ("youtube_client", "requests.post", "create_comment(", "update_video("):
        assert forbidden not in source


def test_not_mutating_user_input() -> None:
    candidate = packet()
    before = deepcopy(candidate)
    validate_poetry_quote_packet(candidate)
    assert candidate == before
