from __future__ import annotations

from video_channel_manager.platforms.vk.editorial_review import (
    build_vk_deferred_editorial_findings,
    reviewable_description_text,
)


def _kinds(value: str, *, include_technical_surfaces: bool = False) -> set[str]:
    return {
        str(item["kind"])
        for item in build_vk_deferred_editorial_findings(
            "-235216998_456239132",
            value,
            include_technical_surfaces=include_technical_surfaces,
        )
    }


def test_hashtag_does_not_create_sensitive_claim() -> None:
    description = "Некрасов написал это в 1855 году.\n\n#Реквием #БессмертныйПолк"

    assert "#БессмертныйПолк" not in reviewable_description_text(description)
    assert _kinds(description) == {"factual_editorial_review"}
    assert _kinds(description, include_technical_surfaces=True) == {
        "factual_editorial_review",
        "sensitive_claim_review",
    }


def test_real_sensitive_claim_remains_localized() -> None:
    description = "В тексте прямо обсуждается смерть героя и её влияние на семью."

    findings = build_vk_deferred_editorial_findings("video-1", description)

    assert [item["kind"] for item in findings] == ["sensitive_claim_review"]
    assert findings[0]["matched_terms"] == ["смерть"]
    assert findings[0]["evidence"][0]["excerpt"] == description


def test_footer_and_urls_do_not_create_claims() -> None:
    description = (
        "Нейтральное описание.\n\n"
        "🎧 The Legendary Poet - поэзия, музыка и литературные материалы.\n"
        "🌐 Сайт: https://thelegendarypoet.ru/\n"
        "#Бог #Смерть"
    )

    assert build_vk_deferred_editorial_findings("video-2", description) == []
