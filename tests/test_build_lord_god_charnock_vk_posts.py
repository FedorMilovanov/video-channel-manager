from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLITTER = ROOT / "scripts" / "build_lord_god_charnock_vk_posts.py"
PREPARE = ROOT / "scripts" / "prepare_lord_god_article_wave.py"
QUEUE = "content/telegram/lordchrist/telegraph-v1/article-queue.json"


def _build(tmp_path: Path) -> dict:
    output = tmp_path / "charnock-posts.json"
    subprocess.run(
        [
            sys.executable,
            str(SPLITTER),
            "--repository-root",
            str(ROOT),
            "--article-queue",
            QUEUE,
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(output.read_text(encoding="utf-8"))


def test_charnock_series_splits_all_fourteen_articles_into_vk_sized_parts(tmp_path: Path) -> None:
    payload = _build(tmp_path)

    assert payload["schema_name"] == "video-manager.lord-god-charnock-vk-posts"
    # 13 cycle articles + the Sunday historical special (history-01).
    assert len(payload["articles"]) == 14
    posts = payload["posts"]
    assert len(posts) == 32
    for article in payload["articles"]:
        parts = [post for post in posts if post["article_publication_id"] == article["publication_id"]]
        assert len(parts) == article["parts"]
        assert [post["part"] for post in parts] == list(range(1, len(parts) + 1))
        # Every part carries the article cover photo.
        assert all(post["cover_path"] == article["cover_path"] for post in parts)
    for post in posts:
        assert 0 < len(post["message"]) <= 15_000
        assert post["message"].startswith("📖 Стивен Чарнок. «О бытии Бога»")
        assert f"Часть {post['part']} из {post['parts_total']}" in post["message"]


def test_charnock_splitter_is_deterministic(tmp_path: Path) -> None:
    first = _build(tmp_path / "a")
    second = _build(tmp_path / "b")
    assert first == second


def test_prepare_article_wave_builds_verifiable_handoff(tmp_path: Path) -> None:
    posts_path = tmp_path / "charnock-posts.json"
    posts_path.write_text(json.dumps(_build(tmp_path), ensure_ascii=False), encoding="utf-8")
    # The handoff layout is repository-relative by contract, so the test
    # output must live under the repository root and is removed afterwards.
    output_dir = ROOT / ".pytest-charnock-handoff"
    subprocess.run(
        [
            sys.executable,
            str(PREPARE),
            "--repository-root",
            str(ROOT),
            "--posts",
            str(posts_path),
            "--article-queue",
            QUEUE,
            "--start-date",
            "2026-10-26",
            "--output-dir",
            str(output_dir),
            "--enable-provider-writes",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    try:
        _assert_handoff(output_dir)
    finally:
        import shutil

        shutil.rmtree(output_dir, ignore_errors=True)


def _assert_handoff(output_dir: Path) -> None:
    import json

    from video_channel_manager.wave_engine.models import WaveApplyIntent, WavePlan, WaveSourceEvidence

    source = WaveSourceEvidence.model_validate_json(
        (output_dir / "06-source.json").read_text(encoding="utf-8"), strict=True
    )
    plan = WavePlan.model_validate_json((output_dir / "07-plan.json").read_text(encoding="utf-8"), strict=True)
    intent = WaveApplyIntent.model_validate_json(
        (output_dir / "08-apply-intent.json").read_text(encoding="utf-8"), strict=True
    )
    source.verify_artifacts(ROOT)
    intent.assert_matches(plan, source)

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["operation_count"] == len(plan.operations)
    assert manifest["plan_self_digest"] == plan.self_digest
    publish_dates = [op.payload["publish_date"] for op in plan.operations]
    assert publish_dates == sorted(publish_dates)
    assert len(set(publish_dates)) == len(publish_dates)
    photo_ops = [op for op in plan.operations if "photo_path" in op.payload]
    assert len(photo_ops) == len(plan.operations)
