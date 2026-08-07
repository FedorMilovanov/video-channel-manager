from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CI_PATH = ROOT / ".github/workflows/ci.yml"
PUBLISHER_WORKFLOW_PATH = ROOT / ".github/workflows/lordchrist-telegram-poster.yml"


def test_ci_exercises_isolated_minimal_telegram_runtime_without_provider_access() -> None:
    workflow = CI_PATH.read_text(encoding="utf-8")
    assert "Build isolated minimal Telegram runtime" in workflow
    assert "Smoke test guarded Telegram CLI without provider access" in workflow
    assert "requirements/telegram-publisher.txt" in workflow
    assert "INITIALIZE_NEW_LORDCHRIST_LEDGER" in workflow
    assert "lordchrist-smoke-ledger.json" in workflow
    assert 'ledger_entries"] == 30' in workflow
    assert 'preview["post"]["sequence"] == 1' in workflow
    assert "LORDCHRIST_TELEGRAM_BOT_TOKEN" not in workflow


def test_publisher_runs_only_from_main_and_minimizes_git_write_credentials() -> None:
    workflow = PUBLISHER_WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "Scheduled workflow re-runs are forbidden" in workflow

    code_checkout, after_code = workflow.split("- name: Determine guarded execution mode", maxsplit=1)
    read_only_checkout, writer_checkout = after_code.split("- name: Enable publication ledger writer", maxsplit=1)
    assert "persist-credentials: false" in code_checkout
    assert "- name: Check out publication ledger read-only" in read_only_checkout
    assert "persist-credentials: false" in read_only_checkout
    assert "if: steps.intent.outputs.do_publish == 'true'" in writer_checkout
    assert "persist-credentials: true" in writer_checkout
