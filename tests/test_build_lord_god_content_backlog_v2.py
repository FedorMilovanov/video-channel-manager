from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest


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


def _telegram_quote_evidence(tmp_path: Path) -> tuple[Path, Path]:
    queue_path = Path(__file__).resolve().parents[1] / "content" / "telegram" / "lordchrist" / "verified-30-posts.json"
    queue = module.TelegramQueue.model_validate(module.read_json(queue_path))
    entries = {
        post.publication_id: {
            "publication_id": post.publication_id,
            "payload_sha256": post.payload_sha256,
        }
        for post in queue.posts
    }
    first = queue.posts[0]
    entries[first.publication_id] = {
        "publication_id": first.publication_id,
        "payload_sha256": first.payload_sha256,
        "state": "published",
        "provider_effect": "verified",
        "intent_id": "1234567890abcdef",
        "dispatch_mode": "manual",
        "workflow_run_id": "123",
        "workflow_run_attempt": "1",
        "github_sha": "a" * 40,
        "github_workflow_sha": "b" * 40,
        "attempted_at_utc": "2026-08-07T12:14:29Z",
        "published_at_utc": "2026-08-07T12:14:31Z",
        "message_id": 1470,
        "message_url": "https://t.me/lordchrist/1470",
        "actual_chat_id": -1001295216957,
        "actual_chat_username": "lordchrist",
        "bot_id": 8716602202,
        "bot_username": "preaching_mp3_bot",
    }
    ledger_path = tmp_path / "publication-ledger.json"
    ledger_path.write_text(
        json.dumps(
            {
                "schema_name": "video-channel-manager.telegram-publication-ledger",
                "schema_version": 3,
                "project_key": "lord-god-strength",
                "channel_username": "@lordchrist",
                "queue_digest": queue.digest,
                "entries": entries,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return queue_path, ledger_path


def test_select_quotes_requires_published_verified_telegram_evidence(tmp_path: Path) -> None:
    queue_path, ledger_path = _telegram_quote_evidence(tmp_path)
    selected = module.select_quotes(queue_path, ledger_path, count=24)
    assert len(selected) == 1
    assert selected[0]["publication_id"] == "lordchrist-bunyan-cross-burden"
    assert selected[0]["telegram_message_id"] == 1470
    assert selected[0]["telegram_message_url"] == "https://t.me/lordchrist/1470"
    assert selected[0]["telegram_source_state"] == "published_verified"


def test_select_quotes_rejects_payload_drift(tmp_path: Path) -> None:
    queue_path, ledger_path = _telegram_quote_evidence(tmp_path)
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    first_id = next(iter(payload["entries"]))
    payload["entries"][first_id]["payload_sha256"] = "sha256:" + "0" * 64
    ledger_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="payload SHA mismatch"):
        module.select_quotes(queue_path, ledger_path, count=24)
