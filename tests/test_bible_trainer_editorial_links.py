from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from video_channel_manager.editorial.content import (
    LORD_GOD_STRENGTH,
    parse_content_record,
    validate_content_record,
)


ROOT = Path(__file__).resolve().parents[1]


def _example_payload() -> dict[str, object]:
    path = ROOT / "content" / "editorial" / "examples" / "tyutchev-night-sea.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _lord_god_payload() -> dict[str, object]:
    payload = deepcopy(_example_payload())
    payload["project_key"] = LORD_GOD_STRENGTH
    payload["channel_id"] = "UCeSJsC6go2c9pdJCuUI1BYA"
    payload["content_id"] = "lord-god-bible-trainer-example"
    payload["variation_key"] = "lord-god-bible-trainer-example-v1"
    links = payload["links"]
    assert isinstance(links, list)
    site = links[0]
    vk = links[2]
    assert isinstance(site, dict)
    assert isinstance(vk, dict)
    site["label"] = "📌 *Господь Бог — Сила Моя:*"
    site["url"] = "https://gospod-bog.ru/"
    vk["url"] = "https://vk.ru/the_lord_god_is_my_strength"
    payload["links"] = [site, vk, links[3]]
    return payload


def _trainer_link(
    url: str = "https://t.me/milovanovaibot?startapp=v1_yt_ch2__chapter2",
    *,
    platform: str = "youtube",
) -> dict[str, object]:
    return {
        "kind": "bible_trainer",
        "label": "📖 *Тренажёр по 1 Петра*",
        "url": url,
        "platforms": [platform],
        "surfaces": ["description"] if platform == "youtube" else ["video_description"],
    }


def _append_trainer(payload: dict[str, object], link: dict[str, object]) -> None:
    links = payload["links"]
    assert isinstance(links, list)
    links.append(link)


def test_exact_youtube_chapter_link_is_accepted_only_when_explicit() -> None:
    payload = _lord_god_payload()
    _append_trainer(payload, _trainer_link())

    assert validate_content_record(payload) == []
    record = parse_content_record(payload)
    youtube_links = record.links_for("youtube", "description")
    vk_links = record.links_for("vk", "video_description")

    assert any(link.kind == "bible_trainer" for link in youtube_links)
    assert all(link.kind != "bible_trainer" for link in vk_links)


def test_existing_lord_god_content_does_not_gain_an_automatic_trainer_cta() -> None:
    payload = _lord_god_payload()

    assert validate_content_record(payload) == []
    record = parse_content_record(payload)

    assert all(link.kind != "bible_trainer" for link in record.links)


def test_wrong_telegram_bot_fails_closed() -> None:
    payload = _lord_god_payload()
    _append_trainer(
        payload,
        _trainer_link("https://t.me/not_the_bible_bot?startapp=v1_yt_ch2__chapter2"),
    )

    errors = validate_content_record(payload)

    assert any("not an approved Bible trainer deep link" in error for error in errors)


def test_tampered_source_destination_pair_fails_closed() -> None:
    payload = _lord_god_payload()
    _append_trainer(
        payload,
        _trainer_link("https://t.me/milovanovaibot?startapp=v1_yt_ch2__chapter3"),
    )

    errors = validate_content_record(payload)

    assert any("not an approved Bible trainer deep link" in error for error in errors)


def test_fake_generic_chapter_one_link_is_not_registered() -> None:
    payload = _lord_god_payload()
    _append_trainer(
        payload,
        _trainer_link("https://t.me/milovanovaibot?startapp=v1_yt_ch1__chapter1"),
    )

    errors = validate_content_record(payload)

    assert any("not an approved Bible trainer deep link" in error for error in errors)


def test_attribution_source_must_match_editorial_platform() -> None:
    payload = _lord_god_payload()
    _append_trainer(payload, _trainer_link(platform="vk"))

    errors = validate_content_record(payload)

    assert any("platforms must be exactly [youtube]" in error for error in errors)


def test_bible_trainer_link_cannot_cross_into_another_project() -> None:
    payload = _example_payload()
    _append_trainer(payload, _trainer_link())

    errors = validate_content_record(payload)

    assert any("Bible trainer is only approved for project lord-god-strength" in error for error in errors)


def test_exact_vk_chapter_link_uses_vk_attribution() -> None:
    payload = _lord_god_payload()
    _append_trainer(
        payload,
        _trainer_link(
            "https://t.me/milovanovaibot?startapp=v1_vk_ch4__chapter4",
            platform="vk",
        ),
    )

    assert validate_content_record(payload) == []
