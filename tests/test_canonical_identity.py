import pytest

from video_channel_manager.application.identity import (
    TextPurpose,
    UrlRouteKind,
    canonicalize_collection_title,
    canonicalize_description,
    canonicalize_display_title,
    canonicalize_http_url,
    canonicalize_identity_title,
    canonicalize_project_url,
    canonicalize_public_url,
    canonicalize_variation,
    compare_exact_fields,
)
from video_channel_manager.editorial._project_profiles import (
    LEGENDARY_POET,
    LORD_GOD_STRENGTH,
    PROJECT_LINK_PROFILES,
)


def test_identity_title_preserves_original_and_records_deterministic_evidence() -> None:
    first = canonicalize_identity_title("Берёза — Version 2 @TheLegendaryPoet #Shorts")
    second = canonicalize_identity_title("Берёза — Version 2 @TheLegendaryPoet #Shorts")

    assert first.original == "Берёза — Version 2 @TheLegendaryPoet #Shorts"
    assert first.canonical == "береза версия 2"
    assert first.ruleset_version == "wave-8b-v1"
    assert first.transformations == [
        "casefold",
        "fold_yo",
        "remove_known_brand_markers",
        "normalize_version_label",
        "punctuation_to_spaces",
        "collapse_whitespace",
        "trim_outer_whitespace",
    ]
    assert first.digest == second.digest


def test_display_title_preserves_case_and_punctuation() -> None:
    evidence = canonicalize_display_title("  БЕРЁЗА — Сергей  Есенин  ")

    assert evidence.canonical == "БЕРЁЗА — Сергей Есенин"
    assert "casefold" not in evidence.transformations
    assert "punctuation_to_spaces" not in evidence.transformations


def test_description_normalizes_layout_without_casefolding() -> None:
    evidence = canonicalize_description("Первая строка  \r\n\r\n\r\nВТОРАЯ строка  ")

    assert evidence.canonical == "Первая строка\n\nВТОРАЯ строка"
    assert "line_endings_lf" in evidence.transformations
    assert "trim_line_trailing_whitespace" in evidence.transformations
    assert "casefold" not in evidence.transformations


def test_variation_identity_keeps_version_number_significant() -> None:
    version_two = canonicalize_variation("Version 2")
    version_two_ru = canonicalize_variation("Версия 2")
    version_three = canonicalize_variation("Version 3")

    assert version_two.canonical == "версия-2"
    assert version_two.canonical == version_two_ru.canonical
    assert version_two.canonical != version_three.canonical


def test_collection_and_video_identity_use_separate_rules() -> None:
    video = canonicalize_identity_title("@TheLegendaryPoet")
    collection = canonicalize_collection_title("@TheLegendaryPoet")

    assert video.purpose == TextPurpose.IDENTITY_TITLE
    assert collection.purpose == TextPurpose.COLLECTION_TITLE
    assert video.canonical == ""
    assert collection.canonical == "thelegendarypoet"


def test_exact_field_readback_rejects_combined_row_false_positive() -> None:
    result = compare_exact_fields(
        {
            "artist": "Джон МакАртур",
            "title": "Диагноз Отвергающих Христа - Луки 20:19-26",
        },
        {
            "combined": "Диагноз Отвергающих Христа - Луки 20:19-26 - Джон МакАртур",
        },
        {
            "artist": TextPurpose.DISPLAY_TITLE,
            "title": TextPurpose.DISPLAY_TITLE,
        },
    )

    assert result.exact is False
    assert result.missing_fields == ["artist", "title"]
    assert result.unexpected_fields == ["combined"]


def test_exact_field_readback_rejects_prefix_match() -> None:
    result = compare_exact_fields(
        {"title": "Диагноз Отвергающих Христа - Луки 20:19-26"},
        {"title": "Диагноз Отвергающих Христа - Луки 20:19-26 - Джон МакАртур"},
        {"title": TextPurpose.DISPLAY_TITLE},
    )

    assert result.exact is False
    assert result.items[0].observed is not None
    assert result.items[0].expected.canonical != result.items[0].observed.canonical


def test_exact_field_readback_accepts_only_per_field_canonical_equality() -> None:
    result = compare_exact_fields(
        {
            "artist": "Джон МакАртур",
            "title": "Диагноз Отвергающих Христа - Луки 20:19-26",
        },
        {
            "artist": "  Джон  МакАртур ",
            "title": "Диагноз Отвергающих Христа - Луки 20:19-26",
            "duration": "57:40",
        },
        {
            "artist": TextPurpose.DISPLAY_TITLE,
            "title": TextPurpose.DISPLAY_TITLE,
        },
    )

    assert result.exact is True
    assert result.missing_fields == []
    assert result.unexpected_fields == ["duration"]
    assert all(item.exact for item in result.items)


def test_http_url_evidence_records_component_changes() -> None:
    evidence = canonicalize_http_url("HTTPS://THELEGENDARYPOET.RU:443/#fragment")

    assert evidence.canonical == "https://thelegendarypoet.ru/"
    assert evidence.transformations == [
        "lowercase_scheme",
        "lowercase_host",
        "remove_default_port",
        "drop_fragment",
    ]


def test_project_url_requires_exact_expected_profile() -> None:
    evidence = canonicalize_project_url(
        "https://www.youtube.com/@TheLegendaryPoet/playlists/",
        expected_project_key=LEGENDARY_POET,
        project_profiles=PROJECT_LINK_PROFILES,
    )

    assert evidence.project_key == LEGENDARY_POET
    assert evidence.route_kind == UrlRouteKind.PUBLIC_COLLECTION
    assert evidence.canonical == "https://www.youtube.com/@TheLegendaryPoet/playlists"


def test_project_url_rejects_foreign_profile() -> None:
    with pytest.raises(ValueError, match="another project profile"):
        canonicalize_project_url(
            "https://vk.ru/the_lord_god_is_my_strength",
            expected_project_key=LEGENDARY_POET,
            project_profiles=PROJECT_LINK_PROFILES,
        )


def test_project_url_rejects_unknown_profile() -> None:
    with pytest.raises(ValueError, match="not approved"):
        canonicalize_project_url(
            "https://vk.ru/some_unknown_public_page",
            expected_project_key=LORD_GOD_STRENGTH,
            project_profiles=PROJECT_LINK_PROFILES,
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://studio.youtube.com/channel/example",
        "https://vk.ru/thelegendarypoet/admin",
        "https://vk.ru/thelegendarypoet?act=edit",
    ],
)
def test_public_url_rejects_author_admin_routes(url: str) -> None:
    with pytest.raises(ValueError, match="Author/admin URL"):
        canonicalize_public_url(url)
