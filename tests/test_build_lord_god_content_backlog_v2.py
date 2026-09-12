from __future__ import annotations

import importlib.util
import json
import subprocess
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_lord_god_content_backlog_v2.py"
SPEC = importlib.util.spec_from_file_location("lord_god_backlog_v2", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

PREPARE_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_lord_god_content_wave.py"
PREPARE_SPEC = importlib.util.spec_from_file_location("prepare_lord_god_content_wave", PREPARE_SCRIPT)
assert PREPARE_SPEC is not None and PREPARE_SPEC.loader is not None
prepare_module = importlib.util.module_from_spec(PREPARE_SPEC)
PREPARE_SPEC.loader.exec_module(prepare_module)


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
    assert [module.speaker_bucket(item) for item in selected] == ["macarthur", "sproul", "lawson", "washer"]


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


def _historical_evidence(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    repo = tmp_path / "historical-repo"
    post_path = repo / "historical" / "post.json"
    revision_path = repo / "historical" / "revision.json"
    release_path = repo / "historical-release.json"
    ledger_path = tmp_path / "historical-ledger.json"
    post_path.parent.mkdir(parents=True)
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "tests@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Tests"], check=True)

    publication_id = "lordchrist-history-spurgeon-down-grade-1887-v3"
    post = {
        "publication_id": publication_id,
        "topic_kind": "controversy",
        "title": "Сперджен и Down-Grade",
        "lead": "Проверенный исторический материал.",
        "sections": [{"paragraphs": ["Первый опубликованный абзац."]}],
    }
    post_path.write_text(json.dumps(post, ensure_ascii=False), encoding="utf-8")
    post_blob = subprocess.run(
        ["git", "-C", str(repo), "hash-object", "historical/post.json"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    revision = {
        "publication_id": publication_id,
        "post": {"path": "historical/post.json", "git_blob_sha": post_blob},
    }
    revision_path.write_text(json.dumps(revision, ensure_ascii=False), encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "historical/post.json", "historical/revision.json"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "fixture"], check=True, capture_output=True)
    revision_blob = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD:historical/revision.json"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    release = {
        "release_id": "historical-live-v1",
        "publication_ids": [publication_id],
        "revision": {"path": "historical/revision.json", "git_blob_sha": revision_blob},
    }
    release_path.write_text(json.dumps(release, ensure_ascii=False), encoding="utf-8")
    release_sha = module.release_digest(release)
    ledger = {
        "project_key": "lord-god-strength",
        "channel_username": "@lordchrist",
        "release_id": release["release_id"],
        "release_sha256": release_sha,
        "entries": {
            publication_id: {
                "publication_id": publication_id,
                "state": "published",
                "provider_effect": "verified",
                "published_at_utc": "2026-09-08T18:20:49.312774+00:00",
                "message_id": 1516,
                "message_url": "https://t.me/lordchrist/1516",
                "document_sha256": "sha256:" + "3" * 64,
            }
        },
    }
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
    return repo, release_path, ledger_path, publication_id


def test_select_historical_requires_exact_published_git_bound_evidence(tmp_path: Path) -> None:
    repo, release_path, ledger_path, publication_id = _historical_evidence(tmp_path)
    selected, _, _, release_sha = module.select_published_historical(
        repo,
        release_path,
        ledger_path,
        count=9,
    )
    assert len(selected) == 1
    assert selected[0]["publication_id"] == publication_id
    assert selected[0]["telegram_message_id"] == 1516
    assert selected[0]["telegram_message_url"] == "https://t.me/lordchrist/1516"
    assert selected[0]["telegram_source_state"] == "published_verified_historical"
    assert selected[0]["telegram_release_sha256"] == release_sha


def test_select_historical_excludes_nonpublished_entry(tmp_path: Path) -> None:
    repo, release_path, ledger_path, _ = _historical_evidence(tmp_path)
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entry = next(iter(ledger["entries"].values()))
    entry["state"] = "pending"
    entry["provider_effect"] = "impossible"
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    selected, _, _, _ = module.select_published_historical(repo, release_path, ledger_path, count=9)
    assert selected == []


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


def _prepare_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, Path, Path, Path, dict[str, object]]:
    queue_path, quote_ledger_path = _telegram_quote_evidence(tmp_path)
    queue = module.TelegramQueue.model_validate(module.read_json(queue_path))
    first = queue.posts[0]
    repo, historical_release_path, historical_ledger_path, _ = _historical_evidence(tmp_path)
    historical, historical_release_sha256, historical_ledger_sha256, historical_release_digest = (
        module.select_published_historical(
            repo,
            historical_release_path,
            historical_ledger_path,
            count=9,
        )
    )
    videos_path = repo / "videos.json"
    videos_path.write_text("[]\n", encoding="utf-8")
    backlog_path = repo / "backlog.json"
    backlog: dict[str, object] = {
        "schema_name": "video-manager.lord-god-content-backlog",
        "schema_version": 1,
        "project_key": "lord-god-strength",
        "community_id": 60805374,
        "owner_id": -60805374,
        "mode": "provider-inert",
        "live_revalidation_required": True,
        "telegram_quote_queue_digest": queue.digest,
        "telegram_quote_queue_sha256": prepare_module.file_sha256(queue_path),
        "telegram_quote_ledger_sha256": prepare_module.file_sha256(quote_ledger_path),
        "telegram_historical_release_sha256": historical_release_sha256,
        "telegram_historical_ledger_sha256": historical_ledger_sha256,
        "telegram_historical_release_digest": historical_release_digest,
        "slots": [
            {
                "kind": "telegram_quote",
                "publish_at": "2033-05-18T06:33:20+03:00",
                "publish_date": 2_000_000_000,
                "publication_id": first.publication_id,
                "title": first.title,
                "text": first.text,
                "source_url": str(first.source.url),
                "telegram_message_id": 1470,
                "telegram_message_url": "https://t.me/lordchrist/1470",
                "telegram_payload_sha256": first.payload_sha256,
                "telegram_source_state": "published_verified",
            },
            {
                "kind": "telegram_editorial",
                "publish_at": "2033-05-18T07:33:20+03:00",
                "publish_date": 2_000_003_600,
                **historical[0],
            },
        ],
    }
    backlog_path.write_text(json.dumps(backlog, ensure_ascii=False), encoding="utf-8")
    return (
        repo,
        backlog_path,
        videos_path,
        queue_path,
        quote_ledger_path,
        historical_release_path,
        historical_ledger_path,
        backlog,
    )


def test_prepare_binds_quote_and_historical_evidence_into_source(tmp_path: Path) -> None:
    (
        repo,
        backlog_path,
        videos_path,
        queue_path,
        quote_ledger_path,
        historical_release_path,
        historical_ledger_path,
        _,
    ) = _prepare_fixture(tmp_path)
    output = repo / "handoff"
    result = prepare_module.prepare(
        SimpleNamespace(
            repository_root=repo,
            backlog=backlog_path,
            videos=videos_path,
            quote_queue=queue_path,
            quote_ledger=quote_ledger_path,
            historical_release=historical_release_path,
            historical_ledger=historical_ledger_path,
            output_dir=output,
            enable_provider_writes=False,
        )
    )
    assert result["operation_count"] == 2
    assert "04-telegram-historical-release.json" in result["files"]
    assert "05-telegram-historical-ledger.json" in result["files"]
    source = prepare_module.WaveSourceEvidence.model_validate_json(
        (output / "06-source.json").read_text(encoding="utf-8"),
        strict=True,
    )
    assert len(source.artifacts) == 6


def test_prepare_rejects_quote_ledger_digest_drift(tmp_path: Path) -> None:
    (
        repo,
        backlog_path,
        videos_path,
        queue_path,
        quote_ledger_path,
        historical_release_path,
        historical_ledger_path,
        _,
    ) = _prepare_fixture(tmp_path)
    quote_ledger_path.write_text(quote_ledger_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="quote ledger SHA differs"):
        prepare_module.prepare(
            SimpleNamespace(
                repository_root=repo,
                backlog=backlog_path,
                videos=videos_path,
                quote_queue=queue_path,
                quote_ledger=quote_ledger_path,
                historical_release=historical_release_path,
                historical_ledger=historical_ledger_path,
                output_dir=repo / "handoff",
                enable_provider_writes=False,
            )
        )


def test_prepare_rejects_historical_ledger_digest_drift(tmp_path: Path) -> None:
    (
        repo,
        backlog_path,
        videos_path,
        queue_path,
        quote_ledger_path,
        historical_release_path,
        historical_ledger_path,
        _,
    ) = _prepare_fixture(tmp_path)
    historical_ledger_path.write_text(
        historical_ledger_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="historical ledger SHA differs"):
        prepare_module.prepare(
            SimpleNamespace(
                repository_root=repo,
                backlog=backlog_path,
                videos=videos_path,
                quote_queue=queue_path,
                quote_ledger=quote_ledger_path,
                historical_release=historical_release_path,
                historical_ledger=historical_ledger_path,
                output_dir=repo / "handoff",
                enable_provider_writes=False,
            )
        )
