from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run-lord-god-article-wave.ps1"


def test_article_wave_runner_declares_source_and_photo_v5_contracts() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "lord-god-article-wave-v3-source-contract.json" in source
    assert "photo_wave_v5.py" in source
    assert "photo_wave_v4.py" in source
    assert "mutations.py" in source
    assert "sources.py" in source
    assert "wall.py" in source
    assert "read-only подготовка новой изолированной фото-волны v5" in source
    assert "без загрузки фото и без wall.post" in source
    assert "wall.parseAttachedLink" not in source
    assert "read-only аудит 30 URL" not in source
