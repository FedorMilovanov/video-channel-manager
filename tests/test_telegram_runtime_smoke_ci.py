from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CI_PATH = ROOT / ".github/workflows/ci.yml"


def test_ci_exercises_isolated_minimal_telegram_runtime_without_provider_access() -> None:
    workflow = CI_PATH.read_text(encoding="utf-8")
    assert "Build isolated minimal Telegram runtime" in workflow
    assert "Smoke test guarded Telegram CLI without provider access" in workflow
    assert "requirements/telegram-publisher.txt" in workflow
    assert "INITIALIZE_NEW_LORDCHRIST_LEDGER" in workflow
    assert "lordchrist-smoke-ledger.json" in workflow
    assert "ledger_entries\"] == 30" in workflow
    assert "preview[\"post\"][\"sequence\"] == 1" in workflow
    assert "LORDCHRIST_TELEGRAM_BOT_TOKEN" not in workflow
