from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/lordchrist-telegram-poster.yml"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_lordchrist_scheduler_queues_pending_runs_without_cancelling_active_run() -> None:
    text = workflow_text()
    assert "group: lordchrist-telegram-publisher" in text
    assert "cancel-in-progress: false" in text
    assert "queue: max" in text
    assert "queue: single" not in text


def test_lordchrist_scheduler_preserves_two_moscow_windows_and_pins_runner() -> None:
    text = workflow_text()
    assert 'cron: "17 9 * * *"' in text
    assert 'cron: "17 21 * * *"' in text
    assert text.count("timezone: Europe/Moscow") >= 2
    assert "runs-on: ubuntu-24.04" in text
    assert "runs-on: ubuntu-latest" not in text
