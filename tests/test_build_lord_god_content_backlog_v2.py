from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_lord_god_content_backlog_v2.py"
SPEC = importlib.util.spec_from_file_location("lord_god_backlog_v2", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def video(title: str, *, views: int = 10, duration: int = 600) -> dict[str, object]:
    return {
        "state": "unposted",
        "title": title,
        "views": views,
        "duration_seconds": duration,
        "published_at": "2026-01-01T00:00:00Z",
        "video_id": f"-60805374_{abs(hash(title)) % 1000000 + 1}",
    }


def test_eligible_video_rejects_broken_and_personal_items() -> None:
    assert module.eligible_video(video("Джон МакАртур. Благодать"), max_views=100)
    assert not module.eligible_video(video("Ошибка импорта: видео недоступно"), max_views=100)
    assert not module.eligible_video(video("Соня 8 лет. День рождения"), max_views=100)
    assert not module.eligible_video(video("Короткий ролик", duration=30), max_views=100)
    assert not module.eligible_video(video("Хорошая проповедь", views=101), max_views=100)


def test_select_videos_round_robins_major_speakers() -> None:
    audit = {
        "videos": [
            video("Джон МакАртур. Писание", views=3),
            video("Джон МакАртур. Церковь", views=4),
            video("Роберт Спраул. Святость Бога", views=1),
            video("Стивен Лоусон. Проповедь", views=2),
            video("Пол Вошер. Евангелие", views=5),
        ]
    }
    selected = module.select_videos(audit, count=4, max_views=100)
    assert [module.speaker_bucket(item) for item in selected] == [
        "macarthur", "sproul", "lawson", "washer"
    ]


def test_build_slots_uses_distinct_moscow_times() -> None:
    videos = [
        {**video("Джон МакАртур. Писание"), "video_id": "-60805374_1"},
        {**video("Пол Вошер. Евангелие"), "video_id": "-60805374_2"},
    ]
    texts = [
        {
            "publication_id": "tg-1",
            "title": "История",
            "text": "Текст",
            "source_path": "post.json",
            "topic_kind": "history",
        }
    ]
    slots = module.build_slots(date(2026, 9, 15), 2, videos, texts, [])
    assert len(slots) == 3
    assert len({slot["publish_date"] for slot in slots}) == 3
    assert slots[0]["publish_at"].endswith("13:00:00+03:00")
    assert slots[1]["publish_at"].endswith("19:00:00+03:00")
