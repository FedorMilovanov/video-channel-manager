from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from video_channel_manager.editorial.content import parse_content_record, validate_content_record
from video_channel_manager.editorial.preview import preview_payload, renderer_for
from video_channel_manager.platforms.instagram.renderers import render_instagram_caption


def _instagram_payload() -> dict[str, object]:
    path = Path(__file__).resolve().parents[1] / "content" / "editorial" / "examples" / "tyutchev-night-sea.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    suitability = payload["platform_suitability"]
    assert isinstance(suitability, dict)
    suitability["instagram"] = ["reel", "carousel"]
    rendering = payload.get("rendering_metadata")
    assert isinstance(rendering, dict)
    rendering["instagram"] = {
        "cta": "Полный текст — по ссылке в профиле.",
        "hashtags": ["#Тютчев", "#РусскаяПоэзия", "#ПоэзияВМузыке"],
        "provenance_line": "Музыкальная интерпретация создана с использованием генеративных музыкальных технологий.",
        "ai_audio_disclosure_required": True,
    }
    return payload


def test_instagram_is_first_class_canonical_preview_target() -> None:
    payload = _instagram_payload()

    first = preview_payload(payload, platform="instagram", surface="reel")
    second = preview_payload(payload, platform="instagram", surface="reel")

    assert first.rendered == second.rendered
    assert first.rendered.platform == "instagram"
    assert first.rendered.surface == "reel"
    assert first.rendered.is_valid
    assert "#Тютчев #РусскаяПоэзия #ПоэзияВМузыке" in first.rendered.text
    assert "https://" not in first.rendered.text
    assert renderer_for("instagram").surface == "reel"


def test_instagram_surface_allowlist_is_fail_closed() -> None:
    payload = _instagram_payload()
    record = parse_content_record(payload)

    rendered = renderer_for("instagram", "feed").render(record)

    assert not rendered.is_valid
    assert any(issue.code == "platform_surface_not_suitable" for issue in rendered.issues)


def test_instagram_platform_target_requires_exact_numeric_provider_id() -> None:
    payload = _instagram_payload()
    targets = payload["platform_targets"]
    assert isinstance(targets, dict)
    targets["instagram.reel"] = "@TheLegendaryPoOet"

    errors = validate_content_record(payload)

    assert any("exact numeric Instagram provider account ID" in error for error in errors)

    targets["instagram.reel"] = "123456789012345"
    errors = validate_content_record(payload)
    assert not any("exact numeric Instagram provider account ID" in error for error in errors)


def test_instagram_caption_rejects_spammy_hashtags_and_raw_urls() -> None:
    text, issues = render_instagram_caption(
        project_key="legendary-poet",
        topic_line="Сергей Есенин — музыкальная интерпретация.",
        body="Источник и музыкальная интерпретация остаются разными объектами; фактическая подпись не меняет авторство.",
        cta="Подробнее: https://example.com/",
        hashtags=("#Есенин", "#есенин", "#Поэзия", "#Музыка", "#Литература", "#РусскаяПоэзия", "#Стихи"),
    )

    assert text
    codes = {issue.code for issue in issues if issue.severity == "error"}
    assert "instagram_hashtag_count" in codes
    assert "instagram_duplicate_hashtag" in codes
    assert "instagram_raw_url_in_caption" in codes


def test_lord_god_caption_rejects_engagement_as_faith_test() -> None:
    _, issues = render_instagram_caption(
        project_key="lord-god-strength",
        topic_line="Что говорит текст?",
        body="Краткий источник-ориентированный разбор сохраняет границу между текстом и выводом.",
        cta="Поставь лайк, если веришь.",
        hashtags=("#Библия", "#Писание", "#Христианство"),
    )

    assert any(issue.code == "instagram_faith_engagement_bait" and issue.severity == "error" for issue in issues)


def test_ai_audio_disclosure_is_required_when_flagged() -> None:
    _, issues = render_instagram_caption(
        project_key="legendary-poet",
        topic_line="Александр Блок — музыкальная интерпретация.",
        body="Музыкальный фрагмент остаётся современной интерпретацией исходного литературного произведения.",
        hashtags=("#Блок", "#РусскаяПоэзия", "#TheLegendaryPoet"),
        ai_audio_disclosure_required=True,
    )

    assert any(issue.code == "instagram_ai_audio_disclosure_missing" for issue in issues)


def test_instagram_metadata_type_errors_are_renderer_errors_not_silent_coercions() -> None:
    payload = deepcopy(_instagram_payload())
    rendering = payload["rendering_metadata"]
    assert isinstance(rendering, dict)
    instagram = rendering["instagram"]
    assert isinstance(instagram, dict)
    instagram["hashtags"] = "#Тютчев"

    rendered = preview_payload(payload, platform="instagram", surface="reel").rendered

    assert not rendered.is_valid
    assert any(issue.code == "instagram_hashtags_type" for issue in rendered.issues)
