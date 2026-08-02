from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run-lord-god-article-wave.ps1"


def test_article_wave_runner_declares_effective_source_contract() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "lord-god-article-wave-v3-source-contract.json" in source
    assert "Не найден контракт источников" in source
    assert "read-only аудит 40 ресурсов и 10 отложенных постов" in source
    assert "read-only аудит 30 URL" not in source
